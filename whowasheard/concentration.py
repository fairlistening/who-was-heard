"""소수가 판을 채우나 — 작성자 집중도(원칙 ⑤).

Do a few people fill the room? Speaker concentration per group.
Empty speaker IDs are counted separately, never guessed.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List


def gini(values: List[int]) -> float:
    v = sorted(values)
    n = len(v)
    if n == 0 or sum(v) == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(v))
    return round((2 * cum) / (n * sum(v)) - (n + 1) / n, 4)


def concentration(records: List[dict], group: str, speaker: str) -> Dict[str, dict]:
    """집단별 {작성자 수, 상위 10명 몫, 상위 1% 몫, 지니, 빈칸 수}."""
    by = defaultdict(Counter)
    blank = Counter()
    for r in records:
        g = str(r.get(group, "")).strip()
        if not g:
            continue
        s = str(r.get(speaker, "")).strip()
        if s:
            by[g][s] += 1
        else:
            blank[g] += 1
    out = {}
    for g in sorted(set(by) | set(blank)):
        vals = sorted(by[g].values(), reverse=True)
        tot = sum(vals)
        n1 = max(1, round(len(vals) * 0.01)) if vals else 0
        out[g] = {
            "speakers": len(vals),
            "texts": tot,
            "blank": blank[g],
            "top10_pct": round(sum(vals[:10]) / tot * 100, 1) if tot else 0.0,
            "top1pct_pct": round(sum(vals[:n1]) / tot * 100, 1) if tot else 0.0,
            "top1pct_n": n1,
            "gini": gini(vals),
        }
    return out
