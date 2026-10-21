"""수치 대장·금지 문장 검사 — 초고를 넣으면 걸리는 데를 짚는다.

규약
  1. 값을 옮길 때 「무엇 위에서 잰 값인지(분모)」를 함께 옮긴다. 분모 없는 비율은 경고한다.
  2. 대장에 없는 비율은 「모르는 수치」로 표시한다 — 틀렸다는 뜻이 아니라 확인하라는 뜻이다.
  3. 쓰면 안 되는 말은 「대신 쓸 말」과 함께 돌려준다.

대장은 사람이 고치는 TSV 파일 둘이다 (머리글은 영어·한국어 둘 다 받는다).
  facts.tsv — item/항목 · value/값 · denominator/분모 · source/출처 · status/상태
  bans.tsv  — phrase/낱말 · level/등급(ban·금지 / caution·주의) · reason/까닭 · instead/대신 쓸 말
위치: 환경변수 WWH_LEDGER_DIR, 없으면 이 폴더의 ledger/ (예시가 들어 있다).

Ledger of confirmed figures and banned phrases. Paste a draft; it flags banned
phrases, percentages without a denominator, and figures not in the ledger.
"""
import csv
import os
import re

DIR = os.environ.get("WWH_LEDGER_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger")
ALIAS = {"항목": "item", "값": "value", "분모": "denominator", "출처": "source", "상태": "status",
         "낱말": "phrase", "등급": "level", "까닭": "reason", "대신 쓸 말": "instead"}


def _read(fn):
    p = os.path.join(DIR, fn)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    return [{ALIAS.get(k.strip(), k.strip()): (v or "").strip() for k, v in r.items() if k}
            for r in rows if any((v or "").strip() for v in r.values())]


def facts():
    return _read("facts.tsv")


def bans():
    return _read("bans.tsv")


def find(keyword, limit=30):
    k = re.sub(r"\s+", "", keyword).lower()
    return [r for r in facts() if k in re.sub(r"\s+", "", "".join(r.values())).lower()][:limit]


_NUM = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(%|퍼센트|percent|명|건)?")
_DEN = re.compile(r"(명|분모|가운데|중|응답자|전체|기준|of |among|out of|respondents|base)", re.I)


def check(text):
    flat = re.sub(r"\s+", " ", text)
    tight = re.sub(r"\s+", "", text).lower()
    hits = {"ban": [], "caution": [], "unknown": [], "no_denominator": [], "ok": []}
    for b in bans():
        w = b.get("phrase", "")
        if w and (w.lower() in flat.lower() or re.sub(r"\s+", "", w).lower() in tight):
            lvl = "ban" if b.get("level", "").lower() in ("ban", "금지") else "caution"
            hits[lvl].append(b)
    known = {}
    for f in facts():
        known.setdefault(f.get("value", "").replace(",", ""), []).append(f)
    for m in _NUM.finditer(text):
        raw, unit = m.group(1), (m.group(2) or "")
        v = raw.replace(",", "")
        if len(v.replace(".", "")) < 2 and not unit:
            continue
        around = text[max(0, m.start() - 45):m.end() + 45].strip()
        pct = unit.lower() in ("%", "퍼센트", "percent")
        if v in known:
            f = known[v][0]
            hits["ok"].append({"value": raw + unit, "item": f.get("item", ""), "denominator": f.get("denominator", "")})
            if pct and not _DEN.search(around):
                hits["no_denominator"].append({"value": raw + unit, "denominator": f.get("denominator", ""), "at": around})
        elif pct:
            hits["unknown"].append({"value": raw + unit, "at": around})
    L = []
    if hits["ban"]:
        L.append("■ 쓰면 안 되는 말 · banned")
        L += [f"   ⛔ 「{h['phrase']}」 — {h.get('reason','')}\n      → {h.get('instead','')}" for h in hits["ban"]]
    if hits["caution"]:
        L.append("■ 한 번 더 볼 말 · caution")
        L += [f"   ⚠ 「{h['phrase']}」 — {h.get('reason','')}\n      → {h.get('instead','')}" for h in hits["caution"]]
    if hits["no_denominator"]:
        L.append("■ 분모가 안 적힌 비율 · no denominator")
        L += [f"   ⚠ {h['value']} — 대장 분모 「{h['denominator']}」\n      … {h['at']} …" for h in hits["no_denominator"]]
    if hits["unknown"]:
        L.append("■ 대장에 없는 비율 — 원자료에서 다시 세어 확인 · not in ledger")
        L += [f"   ? {h['value']}  … {h['at']} …" for h in hits["unknown"]]
    if hits["ok"]:
        L.append("■ 대장과 맞는 수치 · matches")
        L += [f"   ✓ {h['value']} = {h['item']} ({h['denominator']})" for h in hits["ok"]]
    return ("\n".join(L) if L else "걸리는 게 없습니다. Nothing flagged."), hits
