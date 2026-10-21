"""서베이 원자료 조회 — 분모 규약을 도구에 박아 둔 틀.

규약
  1. 비율은 항상 가중값. 미가중 사례수를 함께 보여 준다.
  2. 집단(분모)은 설정 파일에 미리 정한 이름으로만 고른다 — 분모가 뒤섞이지 않게.
  3. 보기는 이름으로 고른다. 애매하면 멈추고 보기 목록을 보여 준다.
  4. 사례수가 작은 칸(기본 30 미만)은 경고를 붙인다.
  5. 두 집단 차이는 Kish 유효표본으로 잰 z 값을 함께 낸다.

설정: 환경변수 WWH_SURVEY_CONFIG(없으면 example/survey.json — 가상 자료).
Survey lookups with denominator rules built in. Configure via WWH_SURVEY_CONFIG.
"""
import csv
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
_C = {}


def cfg():
    if "cfg" not in _C:
        p = os.environ.get("WWH_SURVEY_CONFIG") or os.path.join(HERE, "example", "survey.json")
        c = json.load(open(p, encoding="utf-8"))
        base = os.path.dirname(p)
        rows = list(csv.DictReader(open(os.path.join(base, c["data"]), encoding="utf-8-sig")))
        for r in rows:
            r["_wt"] = float(r.get(c.get("weight", "wt"), 1) or 1)
        book = list(csv.DictReader(open(os.path.join(base, c["codebook"]), encoding="utf-8-sig")))
        _C.update(cfg=c, rows=rows, book=book)
    return _C["cfg"]


def rows():
    cfg()
    return _C["rows"]


def _v(r, col):
    try:
        return int(float(r.get(col, "")))
    except (TypeError, ValueError):
        return None


def options(q):
    cfg()
    return sorted({(int(b["code"]), b["label"]) for b in _C["book"] if b["column"] == q})


def question_text(q):
    cfg()
    return next((b["question"] for b in _C["book"] if b["column"] == q), "")


def search(kw, limit=25):
    cfg()
    k = re.sub(r"\s+", "", kw).lower()
    seen, out = set(), []
    for b in _C["book"]:
        if b["column"] in seen:
            continue
        if k in re.sub(r"\s+", "", b["question"] + b["column"]).lower():
            seen.add(b["column"])
            out.append((b["column"], b["question"]))
    return out[:limit]


def pick_option(q, want):
    opts = options(q)
    w = str(want).strip()
    if re.fullmatch(r"\d+", w):
        hit = [o for o in opts if o[0] == int(w)]
        if hit:
            return hit[0]
    cand = [o for o in opts if re.sub(r"\s+", "", w).lower() in re.sub(r"\s+", "", o[1]).lower()]
    if len(cand) == 1:
        return cand[0]
    raise RuntimeError(("걸리는 보기가 없습니다" if not cand else "여러 보기에 걸립니다") + " — " + " / ".join(f"{a}={b}" for a, b in (cand or opts)))


def _match(r, conds):
    return all(_v(r, c["col"]) in set(c["in"]) for c in conds)


def subset(names):
    g = cfg()["groups"]
    conds = []
    for n in names:
        if n not in g:
            raise RuntimeError(f"그런 집단이 없습니다: {n} — 쓸 수 있는 것: " + " / ".join(g))
        conds += g[n]
    return [r for r in rows() if _match(r, conds)]


def wpct(rs, q, codes):
    tot = sum(r["_wt"] for r in rs)
    return (sum(r["_wt"] for r in rs if _v(r, q) in codes) / tot * 100) if tot > 0 else None


def neff(rs):
    s, s2 = sum(r["_wt"] for r in rs), sum(r["_wt"] ** 2 for r in rs)
    return s * s / s2 if s2 > 0 else 0.0


def ztest(p1, n1, p2, n2):
    if min(n1, n2) < 5:
        return None
    a, b = p1 / 100, p2 / 100
    pp = (a * n1 + b * n2) / (n1 + n2)
    se = math.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
    return abs(a - b) / se if se > 0 else None


def cross(q, option_names, groups):
    codes = {pick_option(q, o)[0] for o in option_names}
    labels = [lab for c, lab in options(q) if c in codes]
    small = cfg().get("small_n", 30)
    out = [f"{q} — {question_text(q)}", f"고른 보기: {' + '.join(labels)} (가중 %, 사례수는 미가중)"]
    first = None
    for g in groups:
        rs = subset([g] if g else [])
        p, n, ne = wpct(rs, q, codes), len(rs), neff(rs)
        z = ztest(first[0], first[1], p, ne) if first and p is not None else None
        star = "" if z is None else ("***" if z >= 2.58 else "**" if z >= 1.96 else " ·")
        warn = f"  ⚠ 사례수 {n} — 방향만 읽는다" if n < small else ""
        out.append(f"  {g or '전체'}: {p:.1f}%  (n={n:,}){'  z=' + format(z, '.2f') + star if z is not None else ''}{warn}" if p is not None else f"  {g}: 값 없음")
        if first is None and p is not None:
            first = (p, ne)
    out.append("z는 첫 집단과의 차이(Kish 유효표본). ** p<.05 · *** p<.01")
    return "\n".join(out)
