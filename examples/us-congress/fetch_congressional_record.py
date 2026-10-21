"""미국 의회 회의록(Congressional Record)을 내려받아 발언 단위 CSV로 만든다.
Download the U.S. Congressional Record from govinfo.gov and split it into
speaker turns with name, party, state and chamber.

  python fetch_congressional_record.py 2026-03-01 2026-03-31 crec_2026-03.csv

* 미국 연방정부 저작물이라 저작권이 없다 (17 U.S.C. §105). Public domain.
* 날짜별 묶음(zip)은 인증키 없이 받는다: https://www.govinfo.gov/content/pkg/CREC-YYYY-MM-DD.zip
* 상원(S)·하원(H) 본회의 발언만 쓴다. 의장석(PRESIDING OFFICER 등) 발언은 뺀다.
* 표준 라이브러리만 쓴다.
"""
import csv
import datetime as dt
import html
import io
import os
import re
import sys
import time
import urllib.request
import zipfile

URL = "https://www.govinfo.gov/content/pkg/CREC-{d}.zip"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
PARTY = {"D": "Democrat", "R": "Republican", "I": "Independent", "ID": "Independent"}
TURN = re.compile(r"^  ((?:Mr|Ms|Mrs|Miss|Dr)\. [A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+)*(?: of [A-Z][A-Za-z ]+)?)\. ", re.M)
CHAIR = re.compile(r"^  (?:The (?:PRESIDING OFFICER|SPEAKER|ACTING PRESIDENT|CHAIR|CLERK|VICE PRESIDENT)[^.]*|The SPEAKER pro tempore[^.]*)\.", re.M)


def fetch(day: str) -> bytes | None:
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"CREC-{day}.zip")
    if os.path.exists(p):
        with open(p, "rb") as f:
            b = f.read()
        if b[:2] == b"PK":
            return b
        os.remove(p)
    req = urllib.request.Request(URL.format(d=day), headers={"User-Agent": "who-was-heard example (research)"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            b = r.read()
    except Exception:
        return None  # 회의가 없던 날 / no session that day
    if b[:2] != b"PK":
        return None  # 묶음이 아니라 안내 페이지가 온 날 / not a package (no session)
    with open(p, "wb") as f:
        f.write(b)
    time.sleep(1)
    return b


def members(mods: str):
    """MODS에서 'Mr. GRASSLEY' → (Chuck Grassley, R, IA, S)."""
    out = {}
    for m in re.finditer(r"<congMember([^>]*)>(.*?)</congMember>", mods, re.S):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        parsed = re.search(r'<name type="parsed">([^<]+)</name>', m.group(2))
        full = re.search(r'<name type="authority-fnf">([^<]+)</name>', m.group(2))
        if parsed:
            out[html.unescape(parsed.group(1).strip())] = (html.unescape(full.group(1).strip() if full else parsed.group(1).strip()),
                                            a.get("party", ""), a.get("state", ""), a.get("chamber", ""), a.get("bioGuideId", ""))
    return out


def text_of(htm: str) -> str:
    t = re.sub(r"<[^>]+>", "", htm)
    return html.unescape(t)


def split_turns(body: str):
    """본문을 발언자 차례로 나눈다. 의장석 발언은 경계로만 쓰고 버린다."""
    marks = [(m.start(), m.group(1)) for m in TURN.finditer(body)] + [(m.start(), None) for m in CHAIR.finditer(body)]
    marks.sort()
    for i, (pos, who) in enumerate(marks):
        if who is None:
            continue
        end = marks[i + 1][0] if i + 1 < len(marks) else len(body)
        seg = body[pos:end]
        seg = re.sub(r"^\s*" + re.escape(who) + r"\.\s*", "", seg)
        seg = re.sub(r"\s+", " ", seg).strip()
        seg = re.sub(r"_{5,}.*$", "", seg).strip()
        yield who, seg


def parse_day(day: str, b: bytes):
    z = zipfile.ZipFile(io.BytesIO(b))
    names = z.namelist()
    mods = next((n for n in names if n.endswith("mods.xml")), None)
    mem = members(z.read(mods).decode("utf-8", "replace")) if mods else {}
    for n in names:
        m = re.search(r"-Pg([SH])\d", n)
        if not (n.endswith(".htm") and m):
            continue
        body = text_of(z.read(n).decode("utf-8", "replace"))
        title = next((ln.strip() for ln in body.splitlines() if ln.strip().isupper() and len(ln.strip()) > 8), "")
        for who, seg in split_turns(body):
            info = mem.get(who)
            if not info:
                continue
            full, party, state, chamber, bio = info
            yield {"date": day, "chamber": "Senate" if (chamber or m.group(1)) == "S" else "House",
                   "speaker": full, "bioguide": bio, "party": PARTY.get(party, party or "Unknown"),
                   "state": state, "title": title.title(), "text": seg}


def main(start: str, end: str, out: str):
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    rows, days = [], 0
    d = d0
    while d <= d1:
        b = fetch(d.isoformat())
        if b:
            days += 1
            got = list(parse_day(d.isoformat(), b))
            rows.extend(got)
            print(d.isoformat(), len(got), "turns", flush=True)
        d += dt.timedelta(days=1)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "chamber", "speaker", "bioguide", "party", "state", "title", "text"])
        w.writeheader()
        w.writerows(rows)
    print(f"{days} session days · {len(rows):,} speaker turns → {out}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    main(*sys.argv[1:])
