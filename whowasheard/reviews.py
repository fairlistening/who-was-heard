"""여러 사람이 따로 판단하고, 일치도를 잰다.

채점자마다 판단 파일 하나:
  {"reviewer": "A", "exclude": [17, 19], "labels": {"3": "검찰 개혁"}, "notes": {"17": "의사진행"}}

  · exclude — 「공론이 아니다」라고 고른 묶음
  · labels  — 묶음에 붙인 주제 이름

일치도는 Fleiss' κ(채점자 둘 이상)와 단순 일치율. 규칙에는 합의된 것만 넣는다
(기본 과반 · 「전원 일치」로 바꿀 수 있다). 엇갈린 묶음은 목록으로 돌려준다 — 다시 사람이 본다.

Several reviewers judge independently; agreement is measured (Fleiss' kappa)
and only agreed exclusions go into the rule draft.
"""
from __future__ import annotations

import json
from typing import Dict, List



def _jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load(paths: List[str]) -> List[dict]:
    out = []
    for p in paths:
        d = _jload(p)
        d.setdefault("reviewer", p)
        d["exclude"] = [int(x) for x in d.get("exclude", [])]
        d["labels"] = {str(k): v for k, v in d.get("labels", {}).items()}
        out.append(d)
    return out


def fleiss_kappa(table: List[List[int]]) -> float | None:
    """table[i] = [범주별 표 수] (각 행의 합 = 채점자 수)."""
    if not table:
        return None
    n = sum(table[0])
    N = len(table)
    if n < 2:
        return None
    k = len(table[0])
    p_j = [sum(r[j] for r in table) / (N * n) for j in range(k)]
    P_i = [(sum(x * x for x in r) - n) / (n * (n - 1)) for r in table]
    P_bar = sum(P_i) / N
    P_e = sum(p * p for p in p_j)
    if P_e == 1:
        return 1.0
    return round((P_bar - P_e) / (1 - P_e), 3)


def agreement(reviews: List[dict], cluster_ids: List[int], policy: str = "majority") -> Dict:
    n = len(reviews)
    table, decided, split = [], [], []
    for c in cluster_ids:
        yes = sum(1 for r in reviews if c in r["exclude"])
        table.append([yes, n - yes])
        need = n if policy == "all" else n // 2 + 1
        if yes >= need:
            decided.append(c)
        elif 0 < yes:
            split.append({"id": c, "exclude_votes": yes, "of": n})
    same = sum(1 for r in table if max(r) == n)
    labels = {}
    for c in cluster_ids:
        vs = [r["labels"].get(str(c)) for r in reviews if r["labels"].get(str(c))]
        if vs:
            uniq = sorted(set(vs), key=vs.index)
            labels[str(c)] = uniq[0] if len(uniq) == 1 else " / ".join(uniq)
    return {
        "reviewers": [r["reviewer"] for r in reviews], "policy": policy,
        "kappa": fleiss_kappa(table) if n >= 2 else None,
        "percent_agreement": round(same / len(table) * 100, 1) if table else None,
        "excluded": decided, "split": split, "labels": labels,
    }
