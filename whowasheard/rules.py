"""규칙 초안 — 1차 결과를 보고 사람이 「공론이 아니다」라고 고른 묶음에서 규칙을 뽑는다.

흐름: 1차(규칙 없이 전부) → 사람이 묶음을 고름 → 이 모듈이 초안 작성 → 사람이 고침 → 2차.
고른 묶음에 유독 자주 나오고 나머지에는 드문 문구를 후보로 낸다. 후보는 초안일 뿐이다.

Draft rules from clusters a person marked as "not public discourse" after
the first pass. Candidate phrases are frequent in the marked clusters and rare
elsewhere. It is a draft: a person reads and edits it before the second pass.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Dict, Iterable, List

_W = re.compile(r"[가-힣]+|[A-Za-z']+|\d+")


def _grams(text: str, n_min=2, n_max=4):
    w = _W.findall(text)
    out = set()
    for n in range(n_min, n_max + 1):
        for i in range(len(w) - n + 1):
            out.add(" ".join(w[i:i + n]))
    return out


def draft(members: Dict[int, List[str]], exclude: Iterable[int], per_cluster: int = 3,
          min_cover: float = 0.3, max_other: float = 0.02) -> List[dict]:
    """고른 묶음마다, 그 묶음 글에 자주 나오고(min_cover 이상) 남긴 묶음에는 드문(max_other 이하) 문구를 뽑는다.
    For each excluded cluster: phrases common inside it and rare in the clusters that were kept."""
    ex = [int(c) for c in exclude]
    ot_texts = [t for c, ts in members.items() if int(c) not in ex for t in ts]
    co = Counter()
    for t in ot_texts:
        co.update(_grams(t.lower()))
    picked = []
    for c in ex:
        ts = members.get(c, [])
        if not ts:
            continue
        ce = Counter()
        for t in ts:
            ce.update(_grams(t.lower()))
        cand = []
        for g, n in ce.items():
            cov = n / len(ts)
            oth = co[g] / max(1, len(ot_texts))
            if cov >= min_cover and oth <= max_other:
                cand.append((cov - oth, len(g), g, cov, oth))
        cand.sort(reverse=True)
        k = 0
        for _, _, g, cov, oth in cand:
            if any(g in p["phrase"] or p["phrase"] in g for p in picked):
                continue
            pat = "(?i)" + r"\W+".join(re.escape(x) for x in g.split(" "))
            picked.append({"phrase": g, "pattern": pat, "cluster": c, "cover_excluded": round(cov, 3), "cover_other": round(oth, 4)})
            k += 1
            if k >= per_cluster:
                break
    return picked


def write_draft(public: dict, members: Dict[int, List[str]], exclude: Iterable[int], name: str, out: str,
                agreement: dict | None = None, base: dict | None = None):
    """base를 주면 앞 차수 규칙을 그대로 이어받고 새 후보를 더한다 (패턴마다 길이 상한을 따로 가진다)."""
    ex = [int(c) for c in exclude]
    cands = draft(members, ex)
    fp = hashlib.sha256(json.dumps(public.get("runs"), sort_keys=True).encode()).hexdigest()[:12]
    words = {c["id"]: c["words"] for c in public["clusters"]}
    d = {
        "name": name, "version": "1",
        "description_ko": "1차 결과를 보고 사람이 정한 규칙 — 초안. 후보 문구를 읽고 지우거나 고친 뒤 쓰세요.",
        "description_en": "Rules decided by a person after the first pass — DRAFT. Review and edit the candidates before use.",
        "text_policy": public.get("text_policy", "private"),
        "min_chars": (base or {}).get("min_chars", public.get("rules", {}).get("min_chars", 30)),
        "embed_max_chars": (base or {}).get("embed_max_chars"),
        "exclude_values": (base or {}).get("exclude_values", {}),
        "dedup_prefix": public.get("rules", {}).get("dedup_prefix", 200),
        "exclude_patterns": ([p if isinstance(p, dict) else {"pattern": p, "max_chars": (base or {}).get("pattern_max_chars", 0)}
                              for p in (base or {}).get("exclude_patterns", [])]
                             + [{"pattern": c["pattern"], "max_chars": 0} for c in cands]),
        "extra_stopwords": list((base or {}).get("extra_stopwords", [])),
        "_derived_from": {
            "round": public.get("round", 1),
            "base_preset": (base or {}).get("name"),
            "previous_fingerprint": fp,
            "reviewers": (agreement or {}).get("reviewers", []),
            "kappa": (agreement or {}).get("kappa"),
            "percent_agreement": (agreement or {}).get("percent_agreement"),
            "policy": (agreement or {}).get("policy"),
            "split": (agreement or {}).get("split", []),
            "excluded_clusters": [{"id": c, "words": words.get(c, []), "n": len(members.get(c, []))} for c in ex],
            "candidates": cands,
            "note": "cover_excluded = 고른 묶음 글 가운데 이 문구가 든 몫 · cover_other = 나머지 묶음에서의 몫",
        },
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    return d
