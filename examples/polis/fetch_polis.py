"""Polis 공개 데이터(CC BY 4.0)에서 대화 하나를 받아, 의견마다 작성자의 의견 집단을 붙인 CSV로 만든다.
Download one Polis open-data conversation (CC BY 4.0) and attach each comment author's opinion group.

  python fetch_polis.py american-assembly.bowling-green bowling-green.csv
  python fetch_polis.py vtaiwan.uberx uberx.csv

* 출처: https://github.com/compdemocracy/openData (The Computational Democracy Project, CC BY 4.0)
* 참여자는 숫자 ID로 익명화돼 있다. 일반 시민의 글이므로 보고서는 기본값(private, 원문 비공개)으로 돌린다.
* opinion_group — Polis가 찬반 투표로 나눈 의견 집단(작성자 기준). 투표가 적어 집단에 안 든 사람은 「no group」.
* moderation — 운영자가 받아들임(accepted)·거부(rejected)·보류(unmoderated). 거부된 의견도 지우지 않고 남겨,
  보고서의 「누가 빠졌나」에서 집단별로 얼마나 걸러졌는지 보이게 한다 (--drop moderation=rejected).
* 표준 라이브러리만 쓴다.
"""
import csv
import io
import sys
import urllib.request

BASE = "https://raw.githubusercontent.com/compdemocracy/openData/master/{conv}/{file}"
MOD = {"1": "accepted", "-1": "rejected", "0": "unmoderated"}


def get(conv, file):
    req = urllib.request.Request(BASE.format(conv=conv, file=file), headers={"User-Agent": "who-was-heard example"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))


def main(conv, out):
    comments = get(conv, "comments.csv")
    parts = get(conv, "participants-votes.csv")
    grp = {p["participant"]: p.get("group-id", "") for p in parts}
    rows = []
    for c in comments:
        g = grp.get(c["author-id"], "")
        rows.append({
            "comment_id": c["comment-id"], "author_id": c["author-id"],
            "opinion_group": f"Group {chr(65 + int(g))}" if g not in ("", None) else "no group",
            "moderation": MOD.get(str(c.get("moderated", "")), "unknown"),
            "agrees": c.get("agrees", ""), "disagrees": c.get("disagrees", ""),
            "text": c["comment-body"],
        })
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    by = {}
    for r in rows:
        by.setdefault(r["opinion_group"], [0, 0])
        by[r["opinion_group"]][0] += 1
        by[r["opinion_group"]][1] += r["moderation"] == "rejected"
    print(f"{len(rows)} comments → {out}")
    for g, (n, rej) in sorted(by.items()):
        print(f"  {g}: {n} comments, {rej} rejected by moderators")


if __name__ == "__main__":
    main(*sys.argv[1:3])
