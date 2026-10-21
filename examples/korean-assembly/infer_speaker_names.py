"""발언자 숫자 ID에 이름을 「추정」해 붙인다 — 위원장이 「○○○ 위원님 질의해 주십시오」라고 부른 직후의 발언자 ID를 센다.
Infer names for numeric speaker IDs from chair call-outs ("Member X, please go ahead") followed by that member's turn.

  python infer_speaker_names.py minutes.csv speaker_names.csv

* 추정이다. 같은 ID에 같은 이름이 3번 이상, 70% 이상 짝지어질 때만 쓴다. 결과의 votes/total을 함께 남긴다.
* 공개 보고서에 쓰기 전에 공식 의원 목록과 대조할 것. 보고서 「선택」 칸에 추정임을 적는다(--speaker-names 와 함께).
* This is an inference. Verify against an official member list before publishing.
"""
import collections
import csv
import re
import sys

PAT = re.compile(r"([가-힣]{2,4})\s?위원님?\s*(?:질의|발언|말씀)")
STOP = {"다음", "이번", "여러", "존경", "저희", "모든", "각각", "우리", "먼저", "마지막", "다른", "해당", "관련", "계신"}


def main(src, out, min_votes=3, min_share=0.7):
    with open(src, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    votes = collections.defaultdict(collections.Counter)
    for a, b in zip(rows, rows[1:]):
        if a["meeting"] != b["meeting"] or not b["speaker_id"].isdigit():
            continue
        m = PAT.findall(a["text"][-120:])
        if m and m[-1] not in STOP:
            votes[b["speaker_id"]][m[-1]] += 1
    n = 0
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "votes", "total", "note"])
        for sid, c in votes.items():
            name, k = c.most_common(1)[0]
            tot = sum(c.values())
            if k >= min_votes and k / tot >= min_share:
                w.writerow([sid, name, k, tot, "inferred from chair call-outs — verify"])
                n += 1
    print(f"{n} IDs named → {out}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
