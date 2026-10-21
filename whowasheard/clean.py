"""정리 규칙과 집단별 탈락률.

규칙 하나하나가 결과를 바꾼다. 그래서 규칙은 보고서에 그대로 찍히고,
집단마다 얼마나 빠졌는지가 함께 나온다(원칙 ③ 누가 빠졌나).

Cleaning rules and per-group drop rates. Every rule changes the result,
so the rules are printed in the report and drops are reported per group.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Sequence

_WS = re.compile(r"\s+")


@dataclass
class CleanRules:
    min_chars: int = 30          # 이보다 짧은 글은 뺀다 / drop shorter texts
    dedup_prefix: int = 200      # 앞 N자가 같으면 중복으로 본다 / duplicate if first N chars match
    exclude_speakers: Sequence[str] = field(default_factory=tuple)  # 운영 계정 등 / e.g. bot accounts
    exclude_patterns: Sequence[str] = field(default_factory=tuple)  # 의사진행·인사 등 공론이 아닌 말 / procedural talk
    exclude_values: Dict[str, Sequence[str]] = field(default_factory=dict)  # 열 값으로 빼기 (예: 운영자가 거른 글) / drop by column value
    pattern_max_chars: int = 0       # >0이면 이보다 짧은 글에만 패턴을 적용 — 긴 연설 속 한 구절로 연설 전체가 빠지지 않게
    keep_empty_group: bool = False

    def describe(self) -> str:
        s = f"{self.min_chars}자 미만 제외 · 앞 {self.dedup_prefix}자 같은 글 중복 제외"
        if self.exclude_speakers:
            s += f" · 지정 작성자 {len(self.exclude_speakers)}명 제외"
        if self.exclude_patterns:
            s += f" · 공론이 아닌 말(의사진행 등) 패턴 {len(self.exclude_patterns)}개 제외"
            caps = sorted({int(p.get("max_chars") or 0) if isinstance(p, dict) else int(self.pattern_max_chars or 0)
                           for p in self.exclude_patterns})
            if caps != [0]:
                parts = [("길이 제한 없음" if c == 0 else f"{c}자 미만 글에만") for c in caps]
                s += f"(패턴마다 다름: {' / '.join(parts)})" if len(caps) > 1 else f"({parts[0]} 적용)"
        for c, v in self.exclude_values.items():
            s += f" · {c} = {'/'.join(map(str, v))} 제외"
        return s

    def as_dict(self):
        d = asdict(self)
        d["exclude_speakers"] = len(self.exclude_speakers)
        d["exclude_patterns"] = list(self.exclude_patterns)
        d["exclude_values"] = {k: list(v) for k, v in self.exclude_values.items()}
        return d


def normalize(t: str) -> str:
    return _WS.sub(" ", str(t or "")).strip()


def clean(records: List[dict], text: str, group: str, speaker: str | None = None,
          rules: CleanRules | None = None, context: Sequence[str] = ()):
    """records → (남은 글 목록, 집단별 통계).

    Returns (kept, stats) where stats[group] = {total, short, dup, excluded, rule, kept, dropped_pct}.
    """
    rules = rules or CleanRules()
    excl = set(rules.exclude_speakers)
    pats = []
    for p in rules.exclude_patterns:   # 문자열 또는 {"pattern": ..., "max_chars": N}
        if isinstance(p, dict):
            pats.append((re.compile(p["pattern"]), int(p.get("max_chars") or 0)))
        else:
            pats.append((re.compile(p), int(rules.pattern_max_chars or 0)))
    seen = set()
    stats: Dict[str, Dict[str, float]] = {}
    kept = []
    for r in records:
        g = str(r.get(group, "")).strip()
        if not g and not rules.keep_empty_group:
            continue
        g = g or "(빈칸)"
        s = stats.setdefault(g, {"total": 0, "short": 0, "dup": 0, "excluded": 0, "rule": 0, "kept": 0})
        s["total"] += 1
        if speaker and excl and str(r.get(speaker, "")).strip() in excl:
            s["excluded"] += 1
            continue
        if rules.exclude_values and any(str(r.get(c, "")).strip() in set(map(str, v)) for c, v in rules.exclude_values.items()):
            s["excluded"] += 1
            continue
        t = normalize(r.get(text, ""))
        if len(t) < rules.min_chars:
            s["short"] += 1
            continue
        if pats and any((not cap or len(t) < cap) and rx.search(t) for rx, cap in pats):
            s["rule"] += 1
            continue
        key = t[: rules.dedup_prefix]
        if key in seen:
            s["dup"] += 1
            continue
        seen.add(key)
        s["kept"] += 1
        kept.append({"text": t, "group": g, "speaker": str(r.get(speaker, "")).strip() if speaker else "",
                     "ctx": " · ".join(str(r.get(c, "")).strip() for c in context if str(r.get(c, "")).strip())})
    for s in stats.values():
        s["dropped_pct"] = round((s["total"] - s["kept"]) / s["total"] * 100, 1) if s["total"] else 0.0
    return kept, stats
