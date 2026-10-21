# -*- coding: utf-8 -*-
"""자료 직접 받기 — 분석 화면 ①에서 부른다. 받은 자료는 이 PC의 프로젝트 폴더에만 남는다.
Fetch data directly from a source. Everything stays in the project folder on this computer.

  us-congress      미국 의회 회의록 (govinfo, 키 없음)
  korean-nanet     국회 회의록 — 국회도서관 국가학술정보 클라우드 「입법정보」 회의록 데이터셋(XLSX) → 발언 단위 (+ 이름 추정)
  open-assembly    열린국회정보 Open API — API 코드와 인증키로 표를 받는다 (회의록 목록 등)
  polis            Polis 공개 토론 자료 (CC BY 4.0)
  youtube-comments 유튜브 댓글 (공식 API, 본인 키)
  youtube-live     유튜브 실시간 채팅 — 방송 중인 영상만 (공식 API, 본인 키)
  url              주소 — CSV·TSV·XLSX·JSON 파일은 그대로, 웹 페이지는 문단 단위로

★ 인증키는 저장하지 않는다(받는 동안만 메모리에). 작성자 ID는 받자마자 이 PC의 비밀값으로 해시한다.
  API keys are never written to disk. Author IDs are hashed on arrival with a local secret.
"""
import csv
import datetime as dt
import hashlib
import html
import importlib.util
import io
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UA = "who-was-heard (local research tool)"


def _example(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "examples", rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _salt(work):
    p = os.path.join(work, "_salt.txt")
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
    with open(p, encoding="utf-8") as f:
        return f.read().strip()


def _h(x, s):
    return hashlib.sha256((s + "|" + x).encode()).hexdigest()[:16] if x else ""


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def _get_json(url):
    try:
        raw, _ = _get(url)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(body).get("error", {}).get("message") or body[:200]
        except Exception:
            msg = body[:200]
        raise RuntimeError(f"HTTP {e.code}: {msg}")
    return json.loads(raw.decode("utf-8"))


def _write(out, rows, fields=None):
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ── 미국 의회 ─────────────────────────────────────────────────────────

def us_congress(p, out, job, work):
    m = _example("us-congress/fetch_congressional_record.py", "wwh_crec")
    m.CACHE = os.path.join(work, "_cache", "govinfo")
    os.makedirs(m.CACHE, exist_ok=True)
    d0, d1 = dt.date.fromisoformat(p["start"]), dt.date.fromisoformat(p["end"])
    if d1 < d0 or (d1 - d0).days > 92:
        raise ValueError("기간은 92일 이내로 · up to 92 days at a time")
    rows, d, days = [], d0, 0
    total = (d1 - d0).days + 1
    while d <= d1:
        if job.get("stop"):
            break
        job["detail"] = d.isoformat()
        b = m.fetch(d.isoformat())
        if b:
            days += 1
            rows.extend(m.parse_day(d.isoformat(), b))
        job["count"] = len(rows)
        job["pct"] = round(((d - d0).days + 1) / total * 100)
        d += dt.timedelta(days=1)
    if not rows:
        raise RuntimeError("그 기간에 회의가 없습니다 · no sessions in that range")
    _write(out, rows, ["date", "chamber", "speaker", "bioguide", "party", "state", "title", "text"])
    return {"rows": len(rows), "note": f"{days} session days",
            "suggest": {"text": "text", "group": "party", "speaker": "speaker", "context": ["date", "chamber", "title"],
                        "text_policy": "public", "embed_chars": 1000, "min_group_size": 20,
                        "group_order": ["Democrat", "Republican"],
                        "subject": f"U.S. Congressional Record, {p['start']} – {p['end']}",
                        "source": "govinfo.gov Congressional Record (public domain)"}}


# ── 국회 회의록 (국회도서관 엑셀) ─────────────────────────────────────────

NANET_LIST = "https://losi-open.nanet.go.kr/user/dataset/datasetList.do?category_cd=2&category_name=%EC%9E%85%EB%B2%95%EC%A0%95%EB%B3%B4"


_DATE_KO = re.compile(r"(\d{4})\s*[년.\-/]\s*(\d{1,2})\s*[월.\-/]\s*(\d{1,2})")
MEMBER_ROLES = ("위원", "의원", "위원장", "소위원장", "의장", "부의장", "위원장대리", "간사")


def iso_date(v):
    """「2025년01월06일」「2025년7월28일」「2025-03-04」「2025.3.4」 → 2025-03-04."""
    m = _DATE_KO.search(str(v or ""))
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else str(v or "")[:10]


def split_speaker(v):
    """「서영교 위원」「소위원장 박수영」「기획재정부제1차관 이형일」 → (이름, 직함, 구분).
    구분: 의원(직함이 위원·위원장·소위원장·의장 등과 정확히 같을 때) / 국회 사무처(전문위원 등) /
    정부·기관·증인 등 / 알 수 없음(숫자 ID 등). 「금융위원회부위원장」처럼 이름에 위원이 들어간 직함은 의원이 아니다."""
    t = str(v or "").strip()
    if not t or t.isdigit():
        return "", "", "알 수 없음"
    parts = t.split()
    if len(parts) == 1:
        return t, "", "알 수 없음"
    if parts[-1] in MEMBER_ROLES:
        name, role = " ".join(parts[:-1]), parts[-1]
    else:
        name, role = parts[-1], " ".join(parts[:-1])
    if role in MEMBER_ROLES:
        side = "의원"
    elif role.endswith("전문위원") or role in ("입법조사관", "사무총장", "입법차장", "사무차장"):
        side = "국회 사무처"
    else:
        side = "정부·기관·증인 등"
    return name, role, side


def korean_nanet(p, out, job, work):
    """국회도서관 국가학술정보 클라우드 「입법정보」 데이터셋(본회의·상임위·특위·예결위·국감·국조·소위 회의록 XLSX).
    여러 파일을 한꺼번에 넣을 수 있고, 기간·위원회·회의 구분으로 거를 수 있다."""
    files = p["files"]
    prep = _example("korean-assembly/prepare_nanet.py", "wwh_nanet")
    infer = _example("korean-assembly/infer_speaker_names.py", "wwh_infer")
    tmp_all = out + ".raw.csv"
    rows_all, fields = [], None
    for k, src in enumerate(files):
        job["detail"] = f"{os.path.basename(src)} ({k + 1}/{len(files)})"
        tmp = out + f".part{k}.csv"
        prep.main(src, tmp)
        with open(tmp, encoding="utf-8") as f:
            rd = csv.DictReader(f)
            fields = fields or rd.fieldnames
            rows_all.extend(rd)
        os.remove(tmp)
        job["count"] = len(rows_all)
        job["pct"] = round((k + 1) / len(files) * 80)
    if not rows_all:
        raise RuntimeError("엑셀에서 발언을 찾지 못했습니다(국회도서관 회의록 데이터셋인지 확인) · no utterances found")
    for r in rows_all:
        r["date"] = iso_date(r.get("date"))
    d0, d1 = iso_date(p.get("date_from")) if p.get("date_from") else "", iso_date(p.get("date_to")) if p.get("date_to") else ""
    com = [c.strip() for c in (p.get("committee") or "").split(",") if c.strip()]
    kind = [c.strip() for c in (p.get("kind") or "").split(",") if c.strip()]
    keep = []
    for r in rows_all:
        dt_ = (r.get("date") or "")[:10]
        if d0 and dt_ < d0:
            continue
        if d1 and dt_ > d1:
            continue
        if com and not any(c in (r.get("committee") or "") for c in com):
            continue
        if kind and not any(c in (r.get("kind") or "") for c in kind):
            continue
        keep.append(r)
    if not keep:
        raise RuntimeError("조건에 맞는 발언이 없습니다 · nothing matches the filters")
    numeric = sum(1 for r in keep if str(r.get("speaker_id", "")).isdigit())
    nm = {}
    if numeric > len(keep) * 0.5:  # 발언자 칸이 숫자 ID일 때만 이름을 추정한다
        _write(tmp_all, keep, fields)
        job["detail"] = "발언자 이름 추정 · inferring speaker names"
        names = out + ".names.csv"
        infer.main(tmp_all, names)
        with open(names, encoding="utf-8") as f:
            nm = {r["id"]: r["name"] for r in csv.DictReader(f)}
        os.remove(tmp_all)
    rows = []
    for r in keep:
        sid = str(r.get("speaker_id", "")).strip()
        if sid.isdigit():
            r["speaker"] = nm.get(sid) or f"ID {sid}"
            r["speaker_name"], r["speaker_role"], r["side"] = (nm.get(sid, ""), "", "알 수 없음")
            r["speaker_named"] = "inferred" if sid in nm else ""
        else:
            r["speaker"] = sid
            r["speaker_name"], r["speaker_role"], r["side"] = split_speaker(sid)
            r["speaker_named"] = "given"
        rows.append(r)
    job["count"] = len(rows)
    job["pct"] = 100
    _write(out, rows)
    span = f"{min(r['date'] for r in rows)} ~ {max(r['date'] for r in rows)}"
    sides = {}
    for r in rows:
        sides[r["side"]] = sides.get(r["side"], 0) + 1
    who = (f"발언자 {len(nm)}명 이름 추정(확인 필요)" if numeric > len(keep) * 0.5 else
           "발언자 이름·직함 있음 · " + " · ".join(f"{k} {v:,}" for k, v in sorted(sides.items(), key=lambda x: -x[1])))
    return {"rows": len(rows), "note": f"파일 {len(files)}개 · {span} · {who}",
            "suggest": {"text": "text", "group": "committee", "speaker": "speaker", "context": ["date", "committee"],
                        "text_policy": "public", "min_chars": 5, "per_group": 2000 if len(rows) > 20000 else 0,
                        "subject": f"국회 회의록 {span}",
                        "source": "국회도서관 국가학술정보 클라우드 「입법정보」 회의록 데이터셋 · NANET minutes datasets"}}


# ── 열린국회정보 Open API ─────────────────────────────────────────────

def open_assembly(p, out, job, work):
    code = (p.get("code") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9]{4,40}", code):
        raise ValueError("API 코드를 적으세요 (열린국회정보 「Open API 상세」의 요청주소 끝부분) · enter the API code")
    key = (p.get("key") or "").strip()
    if not key:
        raise ValueError("인증키가 필요합니다 · an API key is required")
    extra = dict(urllib.parse.parse_qsl((p.get("params") or "").strip().lstrip("?&")))
    rows, page, total = [], 1, None
    maxp = int(p.get("max_pages") or 50)
    while page <= maxp and not job.get("stop"):
        q = dict(extra, KEY=key, Type="json", pIndex=page, pSize=100)
        d = _get_json(f"{OA_BASE}{code}?" + urllib.parse.urlencode(q))
        if code not in d:
            res = d.get("RESULT") or {}
            if res.get("CODE") == "INFO-200" and rows:
                break
            raise RuntimeError(f"{res.get('CODE', '')} {res.get('MESSAGE', json.dumps(d)[:200])}")
        blocks = d[code]
        head = blocks[0].get("head", []) if blocks else []
        for h in head:
            if "list_total_count" in h:
                total = h["list_total_count"]
        got = blocks[1].get("row", []) if len(blocks) > 1 else []
        rows.extend(got)
        job["count"] = len(rows)
        if total:
            job["pct"] = min(100, round(len(rows) / total * 100))
        if not got or (total and len(rows) >= total):
            break
        page += 1
        time.sleep(0.2)
    if not rows:
        raise RuntimeError("받은 행이 없습니다 · no rows returned")
    _write(out, rows)
    links = [k for k in rows[0] if re.search(r"(PDF|HWP|LINK|URL)", k, re.I)]
    note = f"{len(rows):,}행 · API {code}"
    if links:
        note += f" · 링크 열: {', '.join(links)} (본문이 파일로만 제공되는 API일 수 있음)"
    return {"rows": len(rows), "note": note, "suggest": {"text_policy": "public", "source": f"열린국회정보 Open API {code}"}}


# ── Polis ───────────────────────────────────────────────────────────

def polis(p, out, job, work):
    conv = (p.get("conversation") or "").strip()
    if not re.fullmatch(r"[\w.\-]+", conv):
        raise ValueError("대화 이름 (예: american-assembly.bowling-green) · conversation name")
    m = _example("polis/fetch_polis.py", "wwh_polis")
    job["detail"] = conv
    m.main(conv, out)
    with open(out, encoding="utf-8") as f:
        n = sum(1 for _ in f) - 1
    job["count"] = n
    return {"rows": n, "suggest": {"text": "text", "group": "opinion_group", "speaker": "author_id", "text_policy": "private",
                                    "min_chars": 5, "selection": "leaf", "min_cluster_size": 10,
                                    "drop": [["moderation", "rejected"]], "group_order": ["Group A", "Group B", "no group"],
                                    "source": f"Polis open data · {conv} (CC BY 4.0)"}}


# ── 유튜브 ──────────────────────────────────────────────────────────

YT = "https://www.googleapis.com/youtube/v3/"
OA_BASE = "https://open.assembly.go.kr/portal/openapi/"


def video_id(s):
    s = s.strip()
    if re.fullmatch(r"[\w-]{11}", s):
        return s
    u = urllib.parse.urlparse(s if "://" in s else "https://" + s)
    if u.hostname and u.hostname.endswith("youtu.be"):
        return u.path.strip("/")[:11]
    q = urllib.parse.parse_qs(u.query).get("v")
    if q:
        return q[0][:11]
    m = re.search(r"/(?:live|shorts|embed)/([\w-]{11})", u.path)
    return m.group(1) if m else None


def _videos(ids, key):
    out = {}
    for i in range(0, len(ids), 50):
        d = _get_json(YT + "videos?" + urllib.parse.urlencode(
            {"part": "snippet,liveStreamingDetails", "id": ",".join(ids[i:i + 50]), "key": key}))
        for it in d.get("items", []):
            out[it["id"]] = it
    return out


def youtube_comments(p, out, job, work):
    key = (p.get("key") or "").strip()
    if not key:
        raise ValueError("유튜브 API 키가 필요합니다 · a YouTube API key is required")
    lines = [ln.strip() for ln in (p.get("videos") or "").splitlines() if ln.strip()]
    pairs = []
    for ln in lines:
        url, _, grp = ln.partition(",")
        vid = video_id(url)
        if not vid:
            raise ValueError(f"영상 주소를 알아보지 못했습니다 · not a video URL: {url}")
        pairs.append((vid, grp.strip()))
    if not pairs:
        raise ValueError("영상 주소를 한 줄에 하나씩 · one video URL per line")
    meta = _videos([v for v, _ in pairs], key)
    s = _salt(work)
    m = _example("youtube/fetch_youtube_comments.py", "wwh_ytc")
    m.API = YT + "commentThreads"
    rows = []
    for k, (vid, grp) in enumerate(pairs):
        if job.get("stop"):
            break
        sn = (meta.get(vid) or {}).get("snippet", {})
        job["detail"] = sn.get("title", vid)[:60]
        try:
            for c in m.fetch(vid, key, max_pages=int(p.get("max_pages") or 50)):
                author = (c.get("authorChannelId") or {}).get("value", "")
                rows.append({"video_id": vid, "video_title": sn.get("title", ""), "channel": sn.get("channelTitle", ""),
                             "group": grp or sn.get("channelTitle", ""), "author": _h(author, s),
                             "published": c.get("publishedAt", ""), "likes": c.get("likeCount", 0),
                             "text": c.get("textDisplay", "")})
                job["count"] = len(rows)
                if job.get("stop"):
                    break
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{vid}: HTTP {e.code} — 댓글이 꺼져 있거나 키·할당량 문제 · comments disabled, or key/quota")
        job["pct"] = round((k + 1) / len(pairs) * 100)
    if not rows:
        raise RuntimeError("받은 댓글이 없습니다 · no comments")
    _write(out, rows)
    return {"rows": len(rows), "note": f"영상 {len(pairs)}개 · 작성자 ID는 해시",
            "suggest": {"text": "text", "group": "group", "speaker": "author", "text_policy": "private",
                        "source": "YouTube comments (Data API) — 재배포 금지 · do not redistribute"}}


def youtube_live(p, out, job, work):
    key = (p.get("key") or "").strip()
    if not key:
        raise ValueError("유튜브 API 키가 필요합니다 · a YouTube API key is required")
    vid = video_id(p.get("url") or "")
    if not vid:
        raise ValueError("방송 주소를 알아보지 못했습니다 · not a video URL")
    meta = _videos([vid], key).get(vid)
    if not meta:
        raise RuntimeError("영상을 찾지 못했습니다 · video not found")
    chat = (meta.get("liveStreamingDetails") or {}).get("activeLiveChatId")
    if not chat:
        raise RuntimeError("지금 방송 중이 아니거나 채팅이 꺼져 있습니다. 공식 API로는 끝난 방송의 채팅을 받을 수 없습니다. · "
                           "Not live now (or chat disabled). The official API cannot fetch chat from ended streams.")
    sn = meta["snippet"]
    s = _salt(work)
    limit = time.time() + 60 * float(p.get("max_minutes") or 180)
    rows, page = [], None
    fields = ["video_id", "video_title", "channel", "group", "author", "published", "kind", "text"]
    f = open(out, "w", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    try:
        while not job.get("stop") and time.time() < limit:
            q = {"liveChatId": chat, "part": "snippet,authorDetails", "maxResults": 2000, "key": key}
            if page:
                q["pageToken"] = page
            try:
                d = _get_json(YT + "liveChat/messages?" + urllib.parse.urlencode(q))
            except RuntimeError as e:
                if "liveChatEnded" in str(e) or "ended" in str(e).lower() or "403" in str(e):
                    job["detail"] = "방송이 끝났습니다 · stream ended"
                    break
                raise
            for it in d.get("items", []):
                sp = it.get("snippet", {})
                kind = sp.get("type", "")
                text = (sp.get("textMessageDetails") or {}).get("messageText") or sp.get("displayMessage", "")
                if not text:
                    continue
                r = {"video_id": vid, "video_title": sn.get("title", ""), "channel": sn.get("channelTitle", ""),
                     "group": sn.get("channelTitle", ""), "author": _h((it.get("authorDetails") or {}).get("channelId", ""), s),
                     "published": sp.get("publishedAt", ""), "kind": kind, "text": text}
                w.writerow(r)
                rows.append(1)
            f.flush()
            job["count"] = len(rows)
            job["detail"] = "수집 중 — 「수집 멈추기」로 끝냅니다 · collecting — press Stop to finish"
            page = d.get("nextPageToken")
            if d.get("offlineAt"):
                break
            wait = max(2.0, (d.get("pollingIntervalMillis") or 5000) / 1000)
            for _ in range(int(wait * 4)):
                if job.get("stop"):
                    break
                time.sleep(0.25)
    finally:
        f.close()
    if not rows:
        raise RuntimeError("받은 채팅이 없습니다 · no chat messages")
    return {"rows": len(rows), "note": "작성자 ID는 해시 · author IDs hashed",
            "suggest": {"text": "text", "group": "group", "speaker": "author", "text_policy": "private", "min_chars": 2,
                        "source": f"YouTube live chat — {sn.get('title', vid)} (재배포 금지 · do not redistribute)"}}


# ── 주소 · URL ───────────────────────────────────────────────────────

class _Para(HTMLParser):
    KEEP = {"p", "li", "blockquote", "dd", "td", "h1", "h2", "h3"}
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "form", "aside"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.buf, self.depth, self.skip, self.title, self.in_title = [], [], 0, 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag in self.KEEP:
            self.depth += 1
        if tag == "br":
            self.buf.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False
        if tag in self.KEEP and self.depth:
            self.depth -= 1
            if self.depth == 0:
                t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
                if t:
                    self.out.append((tag, t))
                self.buf = []

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self.depth and not self.skip:
            self.buf.append(data)


def url_source(p, out, job, work):
    urls = [u.strip() for u in (p.get("urls") or "").splitlines() if u.strip()]
    if not urls:
        raise ValueError("주소를 한 줄에 하나씩 · one URL per line")
    for u in urls:
        if not re.match(r"https?://", u):
            raise ValueError(f"http(s) 주소만 · http(s) only: {u}")
    min_chars = int(p.get("min_chars") or 5)
    first = None
    if len(urls) == 1:
        raw, ctype = _get(urls[0], timeout=120)
        first = (raw, ctype)
        ext = os.path.splitext(urllib.parse.urlparse(urls[0]).path)[1].lower()
        if ext in (".xlsx", ".xlsm") or "spreadsheetml" in ctype:
            x = out[:-4] + ".xlsx"
            with open(x, "wb") as f:
                f.write(raw)
            return {"rows": None, "file": os.path.basename(x), "suggest": {"source": urls[0]}}
        if ext in (".csv", ".tsv") or "text/csv" in ctype or "tab-separated" in ctype:
            with open(out[:-4] + ext if ext == ".tsv" else out, "wb") as f:
                f.write(raw)
            return {"rows": None, "file": os.path.basename(out[:-4] + ext if ext == ".tsv" else out), "suggest": {"source": urls[0]}}
        if ext == ".json" or "json" in ctype:
            d = json.loads(raw.decode("utf-8"))
            if isinstance(d, dict):
                d = next((v for v in d.values() if isinstance(v, list)), [d])
            rows = [r if isinstance(r, dict) else {"value": r} for r in d]
            rows = [{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in r.items()} for r in rows]
            _write(out, rows)
            job["count"] = len(rows)
            return {"rows": len(rows), "suggest": {"source": urls[0]}}
    rows = []
    for k, u in enumerate(urls):
        if job.get("stop"):
            break
        job["detail"] = u[:80]
        raw, ctype = first if (first and k == 0) else _get(u, timeout=60)
        cs = re.search(r"charset=([\w-]+)", ctype)
        txt = None
        for enc in ([cs.group(1)] if cs else []) + ["utf-8", "cp949"]:
            try:
                txt = raw.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        prs = _Para()
        prs.feed(txt or raw.decode("utf-8", "replace"))
        title = html.unescape(prs.title.strip())[:200]
        host = urllib.parse.urlparse(u).hostname or ""
        n = 0
        for tag, t in prs.out:
            if len(t) < min_chars:
                continue
            n += 1
            rows.append({"page": title or u, "site": host, "url": u, "n": n, "tag": tag, "text": t})
        job["count"] = len(rows)
        job["pct"] = round((k + 1) / len(urls) * 100)
        time.sleep(0.3)
    if not rows:
        raise RuntimeError("문단을 찾지 못했습니다 · no paragraphs found")
    _write(out, rows)
    return {"rows": len(rows), "note": f"페이지 {len(urls)}개 · 문단 단위",
            "suggest": {"text": "text", "group": "site" if len({r['site'] for r in rows}) > 1 else "page",
                        "text_policy": "private", "source": "; ".join(urls[:5]) + (" …" if len(urls) > 5 else "")}}


SOURCES = {
    "us-congress": us_congress,
    "korean-nanet": korean_nanet,
    "open-assembly": open_assembly,
    "polis": polis,
    "youtube-comments": youtube_comments,
    "youtube-live": youtube_live,
    "url": url_source,
}
SECRET_KEYS = ("key",)
