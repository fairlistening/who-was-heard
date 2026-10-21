"""진단 — 정리부터 공론 지도·보고서까지 한 번에.

보고서의 머리는 **공론**이다 — 무엇이 논의됐고 누가 말했나.
그 아래에 **이 지도를 얼마나 믿을 수 있나**를 둔다 — 흔들림, 빠진 목소리, 도구의 선택.

원문을 밖에 낼지는 자료의 성격이 정한다(text_policy).
  · "private"(기본)  일반인 글(채팅·댓글 등). 공개판에 문장·작성자를 싣지 않는다.
                     표본 문장은 내부 검토판에만 둔다 — 분석자가 읽고 묶음 이름을 붙이기 위해.
  · "quotes"         원문은 공개, 작성자는 비공개. 공개판에 대표 발언을 싣되 작성자·상위 작성자는 싣지 않는다.
                     (공개 토론·청원·공개 댓글처럼 문장을 인용해도 되는 자료. 약관·저작권·개인정보는 분석자가 확인한다)
  · "public"         공인의 공개 발언(국회 회의록 등). 대표 발언과 발언자 이름을 공개판에 싣는다.

The head of the report is the public discourse itself — what was discussed
and by whom. Below it: how far to trust the map. Whether text is published
depends on the data: "private" (default, ordinary people's posts — never in the
public report) or "public" (public officials' on-record statements).
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import json
import os
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np

from . import __version__
from .clean import CleanRules, clean
from .cluster import ClusterParams, hull, pairwise_ari, run_many, run_summary, stability
from .concentration import concentration
from .embed import DEFAULT_MODEL
from .keywords import ctfidf

TEMPLATE = os.path.join(os.path.dirname(__file__), "templates", "report.html")
POLICIES = ("private", "quotes", "public")


@dataclass
class Report:
    public: dict
    internal: dict = field(default_factory=dict)   # {"samples": {cid: [..]}, "reps": {cid: [..]}}



def _jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _reps(E, ids, k):
    """묶음 중심에 가장 가까운 글 k개 — 그 묶음을 가장 잘 대표하는 발언."""
    if len(ids) == 0:
        return []
    V = E[ids]
    c = V.mean(0)
    c = c / (np.linalg.norm(c) or 1)
    sims = V @ c
    return [int(ids[i]) for i in np.argsort(-sims)[:k]]


def diagnose(records: List[dict], text: str, group: str, speaker: Optional[str] = None,
             rules: Optional[CleanRules] = None, per_group: int = 1000,
             params: Optional[ClusterParams] = None, model: str = DEFAULT_MODEL,
             embed_fn: Optional[Callable] = None, layout_fn=None, cluster_fn=None,
             sample_seed: int = 42, samples_per_cluster: int = 5, reps_per_cluster: int = 3,
             text_policy: str = "private", speaker_names: Optional[Dict[str, str]] = None,
             speaker_names_note: str = "", context: tuple = (),
             title: str = "공론 지도", subject: str = "", source: str = "", extra_stop=(),
             preset: Optional[dict] = None, embed_max_chars: Optional[int] = None,
             previous: Optional[dict] = None, cache_dir: Optional[str] = None,
             min_group_size: int = 0, group_order: tuple = (), drop: Optional[Dict[str, list]] = None,
             progress: Optional[Callable[[str], None]] = None,
             embed_progress=None, should_stop=None, also_read=()) -> Report:
    """progress(stage): 'clean' → 'embed' → 'cluster' → 'summarize' 단계마다 불린다 (화면 진행 표시용)."""
    step = progress or (lambda s: None)
    step("clean")
    if preset:
        rules = rules or CleanRules(min_chars=preset.get("min_chars", 30), dedup_prefix=preset.get("dedup_prefix", 200),
                                    exclude_patterns=tuple(preset.get("exclude_patterns", [])),
                                    exclude_values=preset.get("exclude_values", {}),
                                    pattern_max_chars=preset.get("pattern_max_chars", 0))
        extra_stop = tuple(extra_stop) + tuple(preset.get("extra_stopwords", []))
        embed_max_chars = embed_max_chars or preset.get("embed_max_chars")
    embed_max_chars = embed_max_chars or 400
    if text_policy not in POLICIES:
        raise ValueError(f"text_policy는 {POLICIES} 중 하나여야 합니다")
    rules = rules or CleanRules()
    params = params or ClusterParams()
    names = speaker_names or {}
    if drop:
        from dataclasses import replace as _rep
        ev = dict(rules.exclude_values)
        ev.update(drop)
        rules = _rep(rules, exclude_values=ev)
    if min_group_size:
        cnt = {}
        for r in records:
            g = str(r.get(group, "")).strip()
            cnt[g] = cnt.get(g, 0) + 1
        small = {g for g, n in cnt.items() if n < min_group_size}
        if small:
            records = [dict(r, **{group: "기타 · Other"}) if str(r.get(group, "")).strip() in small else r for r in records]
    kept, stats = clean(records, text, group, speaker, rules, context)
    order = [g for g in group_order if g in stats]
    rest = sorted((g for g in stats if g not in order and g != "기타 · Other"), key=lambda g: -stats[g]["kept"])
    groups = order + rest + (["기타 · Other"] if "기타 · Other" in stats and "기타 · Other" not in order else [])
    if not kept:
        tot = {k: sum(st[k] for st in stats.values()) for k in ("total", "short", "dup", "excluded", "rule")}
        avg = (sum(len(str(r.get(text, "") or "")) for r in records) / max(1, len(records)))
        raise ValueError(
            f"정리 후 남은 글이 없습니다 · nothing left after cleaning — 전체 {tot['total']:,}건 중 "
            f"짧음 {tot['short']:,} (기준 {rules.min_chars}자) · 중복 {tot['dup']:,} · 열 값으로 뺌 {tot['excluded']:,} · 규칙 {tot['rule']:,}. "
            f"고른 글 열 「{text}」의 평균 길이는 {avg:.0f}자입니다. 글이 든 열을 맞게 골랐는지, 짧은 글 기준이 너무 높지 않은지 확인하세요.")
    conc = concentration(records, group, speaker) if speaker else {}

    rnd = random.Random(sample_seed)
    by_g: Dict[str, list] = {}
    for k in kept:
        by_g.setdefault(k["group"], []).append(k)
    samp = []
    for g in groups:
        pool = by_g.get(g, [])
        samp.extend(rnd.sample(pool, min(per_group, len(pool))) if per_group else pool)
    texts = [s["text"] for s in samp]
    gi = np.array([groups.index(s["group"]) for s in samp])

    step("embed")
    if embed_fn is None:
        from .embed import embed as _embed
        E = _embed(texts, model=model, max_chars=embed_max_chars, cache_dir=cache_dir,
                   also_read=also_read, progress=embed_progress, should_stop=should_stop)
    else:
        E = np.asarray(embed_fn(texts), dtype="float32")
    En = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)

    step("cluster")
    runs = run_many(E, params, layout_fn, cluster_fn)
    step("summarize")
    xy, lab = runs[0][1], runs[0][2]
    app = stability(runs, params.same_cluster_jaccard)
    words = ctfidf(texts, lab, extra_stop=extra_stop)

    def who(sid):
        if not sid:
            return ""
        if sid in names:
            return names[sid]
        return f"ID {sid}" if sid.isdigit() else sid

    clusters, samples, reps_all, members = [], {}, {}, {}
    for c in sorted(app, key=lambda c: -int((lab == c).sum())):
        ids = np.where(lab == c)[0]
        cen = xy[ids].mean(0)
        sp = Counter(samp[i]["speaker"] for i in ids if samp[i]["speaker"])
        top_sp = [{"name": who(s), "named": s in names, "n": n} for s, n in sp.most_common(5)]
        rep_ids = _reps(En, ids, reps_per_cluster)
        reps = [{"text": texts[i], "speaker": who(samp[i]["speaker"]), "ctx": samp[i]["ctx"],
                 "group": samp[i]["group"]} for i in rep_ids]
        item = {
            "id": int(c), "n": int(len(ids)), "app": int(app[c]), "words": words.get(int(c), []),
            "comp": [int((gi[ids] == k).sum()) for k in range(len(groups))],
            "cx": round(float(cen[0]), 3), "cy": round(float(cen[1]), 3), "hull": hull(xy[ids]),
            "speakers_n": len(sp), "label": "",
        }
        if text_policy == "public":
            item["reps"] = reps
            item["top_speakers"] = top_sp
        elif text_policy == "quotes":  # 원문만, 작성자 없이 · text only, no authors
            item["reps"] = [{"text": r["text"], "group": r["group"]} for r in reps]
        clusters.append(item)
        reps_all[int(c)] = reps
        members[int(c)] = [texts[i] for i in ids]
        pick = rnd.sample(list(ids), min(samples_per_cluster, len(ids)))
        samples[int(c)] = [{"text": texts[i], "speaker": who(samp[i]["speaker"]), "ctx": samp[i]["ctx"]} for i in pick]
        if text_policy in ("private", "quotes"):
            # 공개판엔 작성자를 싣지 않지만, 내부판에서는 상위 작성자를 볼 수 있게
            samples[int(c)].insert(0, {"top_speakers": top_sp})

    kept_n = [stats[g]["kept"] for g in groups]
    share = [k / sum(kept_n) for k in kept_n]
    eq = [sum(1 for x in gi if x == k) / len(gi) for k in range(len(groups))]
    popw = [round(s / e, 4) if e else 0.0 for s, e in zip(share, eq)]

    choices = [
        ["자료 / data", source or "(지정 안 됨)"],
        ["원문 공개 / text policy", {"public": "공인의 공개 발언 — 대표 발언·발언자 이름 공개",
                                     "quotes": "원문 공개·작성자 비공개 — 대표 발언만 싣고 작성자는 싣지 않음",
                                     "private": "일반인 글 — 공개판에 문장·작성자를 싣지 않음"}[text_policy]],
        ["정리 규칙 / cleaning", rules.describe()],
        ["표본 / sample", (f"집단마다 최대 {per_group:,}건 무작위 추출(출발점 번호 {sample_seed})" if per_group else "표본 없이 전부") + f" · 임베딩은 앞 {embed_max_chars}자"],
        ["의견 추출 / extraction", "쓰지 않음 (LLM 없음)"],
        ["임베딩 / embedding", "사용자 지정 함수" if embed_fn else model],
        ["배치 / layout", f"UMAP · 묶기는 {params.cluster_dims}차원, 그림은 2차원 · 이웃 {params.n_neighbors} · {params.metric}"],
        ["묶기 / clustering", f"HDBSCAN({params.selection}) · 최소 묶음 {params.resolved_mcs(len(texts))} · 묶음 수 상한 없음"],
        ["흔들림 / stability", f"무작위 출발점 {len(params.seeds)}가지({'·'.join(map(str, params.seeds))}) · 같은 묶음 = 겹침(Jaccard) {params.same_cluster_jaccard} 이상"],
        ["대표 발언 / representatives", f"묶음 중심(임베딩)에 가장 가까운 {reps_per_cluster}건"],
        ["특징어 / keywords", "c-TF-IDF · 조사 단순 제거 · 잠정"],
        ["주제 이름 / labels", "사람이 표본을 읽고 붙임 (붙이기 전엔 비어 있음)"],
        ["도구 / tool", f"who-was-heard {__version__} · {_dt.date.today().isoformat()}"],
    ]
    if min_group_size:
        choices.insert(2, ["작은 집단 / small groups", f"글 {min_group_size}건 미만 집단은 「기타」로 합침"])
    if preset:
        from .presets import describe as _pd
        choices.insert(2, ["규칙 파일 / preset", _pd(preset)])
    if speaker_names:
        choices.insert(2, ["발언자 이름 / speaker names", speaker_names_note or f"ID→이름 {len(names)}명 연결"])

    public = {
        "title": title, "subject": subject, "text_policy": text_policy, "groups": groups,
        "points": [[round(float(xy[i, 0]), 3), round(float(xy[i, 1]), 3), int(gi[i]), int(lab[i])] for i in range(len(texts))],
        "clusters": clusters,
        "unclustered_by_group": [round(float((lab[gi == k] == -1).mean() * 100), 1) if (gi == k).any() else 0.0 for k in range(len(groups))],
        "runs": run_summary(runs), "ari": pairwise_ari(runs),
        "clean": {g: stats[g] for g in groups}, "concentration": conc,
        "popw": popw, "n_sample": len(texts), "per_group": per_group, "choices": choices,
        "rules": rules.as_dict(),
        "preset": ({k: preset[k] for k in ("name", "version", "_sha256", "exclude_patterns") if k in preset} if preset else None),
    }
    hist = _history(previous, preset)
    public["history"] = hist
    public["round"] = len(hist) + 1
    return Report(public=public, internal={"samples": samples, "reps": reps_all, "members": members})


def _history(prev: Optional[dict], preset: Optional[dict]):
    """앞 차수들의 사슬. 각 차수: 묶음 수, 표본, 쓴 규칙, 그 결과를 보고 사람이 뺀 것·일치도."""
    if not prev:
        return []
    chain = list(prev.get("history", []))
    der = (preset or {}).get("_derived_from") or {}
    chain.append({
        "round": prev.get("round", len(chain) + 1),
        "clusters": len(prev.get("clusters", [])),
        "n_sample": prev.get("n_sample"),
        "preset": (prev.get("preset") or {}).get("name"),
        "preset_sha": (prev.get("preset") or {}).get("_sha256"),
        "unclustered_pct": [r.get("unclustered_pct") for r in prev.get("runs", [])],
        "excluded_after": der.get("excluded_clusters", []),
        "reviewers": der.get("reviewers", []),
        "kappa": der.get("kappa"),
        "percent_agreement": der.get("percent_agreement"),
        "split": der.get("split", []),
    })
    return chain


def apply_labels(report_public: dict, labels: Dict[str, str], who: str = "") -> dict:
    """사람이 붙인 주제 이름을 넣는다. labels = {묶음번호: 이름}."""
    for c in report_public["clusters"]:
        if str(c["id"]) in labels:
            c["label"] = labels[str(c["id"])]
    if who:
        for ch in report_public["choices"]:
            if ch[0].startswith("주제 이름"):
                ch[1] = who
    return report_public


def _render(public: dict, internal: Optional[dict]) -> str:
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    payload = dict(public)
    payload["mode"] = "internal" if internal is not None else "public"
    if internal is not None:
        payload["samples"] = {str(k): v for k, v in internal.get("samples", {}).items()}
        payload["ireps"] = {str(k): v for k, v in internal.get("reps", {}).items()}
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return tpl.replace("__TITLE__", _html.escape(public["title"])).replace("__DATA__", data)


def write_reports(report: Report, outdir: str, name: str = "report") -> Dict[str, str]:
    """공개판 HTML·JSON, 내부 검토판 HTML·JSON을 쓴다."""
    os.makedirs(outdir, exist_ok=True)
    paths = {
        "public_html": os.path.join(outdir, f"{name}_public.html"),
        "public_json": os.path.join(outdir, f"{name}_public.json"),
        "internal_html": os.path.join(outdir, f"{name}_INTERNAL_do-not-share.html"),
        "internal_json": os.path.join(outdir, f"{name}_INTERNAL_do-not-share.json"),
    }
    # 다 쓴 뒤 한 번에 바꿔 끼운다 — 쓰는 도중에 다른 요청이 반쯤 쓴 파일을 읽지 않게
    # Write to a temp file and swap in, so a reader never sees a half-written file.
    def _put(path, text):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)

    _put(paths["public_html"], _render(report.public, None))
    _put(paths["public_json"], json.dumps(report.public, ensure_ascii=False, indent=1))
    _put(paths["internal_html"], _render(report.public, report.internal))
    _put(paths["internal_json"], json.dumps({str(k): v for k, v in report.internal.items()}, ensure_ascii=False, indent=1))
    return paths


def load_report(public_json: str, internal_json: Optional[str] = None) -> Report:
    pub = _jload(public_json)
    internal = {}
    if internal_json and os.path.exists(internal_json):
        raw = _jload(internal_json)
        internal = {k: {int(c): v for c, v in d.items()} for k, d in raw.items()}
    return Report(public=pub, internal=internal)


def summary_text(report: Report) -> str:
    """사람이 읽는 요약 — 집계만. Aggregates only, no input text."""
    p = report.public
    ks = [r["clusters"] for r in p["runs"]]
    us = [r["unclustered_pct"] for r in p["runs"]]
    nr = len(p["runs"])
    stable = sum(1 for c in p["clusters"] if c["app"] > int(nr * 0.6))
    top = sorted(p["clusters"], key=lambda c: -c["n"])[:8]
    lines = [
        f"표본 {p['n_sample']:,}건 · 집단 {len(p['groups'])}개 · 원문 정책 {p['text_policy']}",
        "큰 주제: " + " / ".join((c.get("label") or "·".join(c["words"][:2]) or f"묶음 {c['id']}") + f"({c['n']})" for c in top),
        f"묶음 수 {min(ks)}–{max(ks)}개 (무작위 출발점 {nr}가지) · 안 묶임 {min(us)}–{max(us)}%",
        f"자주 다시 나온 묶음 {stable}/{len(p['clusters'])} · 판끼리 일치도 ARI 평균 {p['ari']['mean']}",
        "집단별 정리 탈락률: " + " · ".join(f"{g} {p['clean'][g]['dropped_pct']}%" for g in p["groups"]),
    ]
    lines.append("※ 이 요약은 지도를 얼마나 믿을 수 있는지까지만 말합니다. 주제의 뜻은 사람이 정합니다.")
    return "\n".join(lines)
