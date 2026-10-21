"""MCP 서버 — listen-check. 공론 지도와 진단 보고서를 만든다.

★ 이 서버는 집계만 돌려준다. 입력 글을 대화로 돌려보내지 않는다.
  표본 원문은 사용자의 PC에 쓰인 내부 검토판(HTML)에서 사람이 직접 읽는다.
  → 남이 넣은 글에 숨은 지시문이 대화에 섞여 들어오는 일도 막는다.

MCP server. Returns aggregates only — never input text — to the conversation.
Samples are read by a person in the locally written internal report.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))                 # servers/
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # repo root
import mcpkit  # noqa: E402
from whowasheard import presets as P  # noqa: E402
from whowasheard.data import columns, load_table  # noqa: E402

INS = """공론을 한데 모으되, 묻히는 목소리를 놓치지 않기 위한 도구입니다 (Fair Listening · 고루듣기).

이 도구는 AI 의견 지도를 얼마나 믿을 수 있는지까지만 말합니다. 주제가 무엇을 뜻하는지는 사람이 정합니다.
It tells you how far to trust an AI opinion map — not what it means.

쓰는 순서
 1. inspect_table — 열 이름만 봅니다(값은 돌려주지 않습니다).
 2. diagnose — 규칙 없이 1차 보고서. 결과로 공개판·내부 검토판 HTML 경로와 집계 요약이 옵니다.
 3. 사람이 내부 검토판을 열어 묶음을 읽고, 채점자마다 판단 파일(exclude·labels)을 씁니다.
 4. draft_rules — 채점자 일치도(κ)를 재고 합의된 것만 규칙 초안에 넣습니다. 사람이 읽고 고칩니다.
 5. diagnose(preset=초안, previous=앞 차수 _public.json) — 2차, 3차 … 몇 번이든.
 6. apply_labels — 합의된 주제 이름을 넣습니다.

지킬 것
 · 이 서버는 입력 글을 대화로 돌려주지 않습니다. 원문은 내부 검토판에서 사람이 읽습니다.
 · 일반인 글(채팅·댓글)은 text_policy="private"(기본). 공인의 공개 발언(의회 회의록 등)만 "public".
 · 「안 묶임」·「흔들림」·「누가 빠졌나」를 빼고 결과를 전하지 마세요."""


def t_presets(a):
    out = []
    for n in P.available():
        p = P.load(n)
        out.append(f"{n} — {P.describe(p)}\n   {p.get('description_ko', '')}")
    return "\n".join(out)


def t_inspect(a):
    c = columns(a["path"])
    lines = [f"행 {c['rows']:,}개 · 열 {len(c['columns'])}개 (값은 보여주지 않습니다)"]
    for col in c["columns"]:
        lines.append(f"  {col}  — 채워진 칸 {c['filled'][col]:,} · 평균 {c['avg_chars'][col]}자 · 서로 다른 값 {c['distinct'][col]:,}")
    lines.append("\n글이 든 열(긴 평균 글자 수)과 집단 열(서로 다른 값이 적은 열)을 골라 diagnose에 넘기세요.")
    return "\n".join(lines)


def _shared_cache():
    """분석 화면과 같은 임베딩 저장소(해시와 숫자만) — 2차·3차에서 다시 계산하지 않는다."""
    try:
        import studio  # servers/ 가 경로에 있을 때(허브)
        return studio.shared_cache()
    except Exception:
        home = os.environ.get("WWH_WORK") or os.path.join(os.path.expanduser("~"), "Documents", "who-was-heard")
        return os.path.join(home, "_cache", "embeddings")


def t_diagnose(a):
    import json
    from whowasheard.cluster import ClusterParams
    from whowasheard.report import diagnose, summary_text, write_reports
    preset = P.load(a.get("preset") or "none")
    policy = a.get("text_policy") or preset.get("text_policy", "private")
    prev = None
    if a.get("previous"):
        with open(a["previous"], encoding="utf-8") as f:
            prev = json.load(f)
    if a.get("min_chars") not in (None, ""):  # 0도 그대로 · 0 is valid
        preset = dict(preset, min_chars=int(a["min_chars"]))
    drop = {}
    for item in str(a.get("drop") or "").split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            drop.setdefault(k.strip(), []).append(v.strip())
    rows = load_table(a["path"])
    params = ClusterParams(selection=a.get("selection") or "eom",
                           min_cluster_size=int(a["min_cluster_size"]) if a.get("min_cluster_size") else None)
    rep = diagnose(rows, a["text"], a["group"], a.get("speaker"), per_group=int(a.get("per_group", 1000)),
                   params=params, text_policy=policy, preset=preset, previous=prev, drop=drop or None,
                   context=tuple(x for x in (a.get("context") or "").split(",") if x),
                   title=a.get("title", "공론 지도"), subject=a.get("subject", ""),
                   source=a.get("source") or os.path.basename(a["path"]),
                   cache_dir=_shared_cache())
    out = a.get("out_dir") or os.path.join(os.path.dirname(os.path.abspath(a["path"])), "who-was-heard-report")
    name = a.get("name") or f"r{rep.public['round']}"
    paths = write_reports(rep, out, name)
    return (summary_text(rep) + f"\n\n{rep.public['round']}차 보고서"
            f"\n공개판: {paths['public_html']}\n내부 검토판(반출 금지 — 사람이 직접 여세요): {paths['internal_html']}"
            f"\n다음 차수에 previous로 넘길 파일: {paths['public_json']}")


def t_draft(a):
    from whowasheard.report import load_report
    from whowasheard.reviews import agreement, load as load_reviews
    from whowasheard.rules import write_draft
    run = a["run"]
    rep = load_report(run + "_public.json", run + "_INTERNAL_do-not-share.json")
    agr = None
    if a.get("reviews"):
        agr = agreement(load_reviews(a["reviews"].split(",")), [c["id"] for c in rep.public["clusters"]], a.get("policy", "majority"))
        ex = agr["excluded"]
    else:
        ex = [int(x) for x in str(a.get("exclude", "")).split(",") if x.strip()]
    d = write_draft(rep.public, rep.internal.get("members", {}), ex, a.get("name", "my-rules"), a["out"], agr)
    head = (f"채점자 {len(agr['reviewers'])}명 · κ={agr['kappa']} · 일치율 {agr['percent_agreement']}%\n"
            f"엇갈린 묶음: {', '.join(str(s['id']) for s in agr['split']) or '없음'}\n") if agr else ""
    # 후보 문구는 원문에서 나온 짧은 구절이다 — 대화에는 개수만, 내용은 파일에서 사람이 본다
    return head + f"합의로 뺄 묶음: {ex}\n규칙 초안: {a['out']} · 후보 문구 {len(d['exclude_patterns'])}개\n파일을 열어 읽고 고친 뒤 diagnose의 preset으로 넘기세요."


def t_labels(a):
    import json
    from whowasheard.report import apply_labels, load_report, write_reports
    from whowasheard.reviews import agreement, load as load_reviews
    run = a["run"]
    rep = load_report(run + "_public.json", run + "_INTERNAL_do-not-share.json")
    if a.get("reviews"):
        agr = agreement(load_reviews(a["reviews"].split(",")), [c["id"] for c in rep.public["clusters"]])
        labels, by = agr["labels"], "채점자 " + ", ".join(agr["reviewers"])
    else:
        labels, by = json.load(open(a["labels"], encoding="utf-8")), a.get("by", "")
    apply_labels(rep.public, labels, by)
    d, n = os.path.split(run)
    p = write_reports(rep, d or ".", n)
    return f"주제 이름 {len(labels)}개를 넣었습니다: {p['public_html']}"


def t_principles(a):
    return """⓪ 지도를 얼마나 믿을 수 있는지까지만 말한다. 무엇을 쓸지는 사람이 정한다.
① 어느 주제에도 안 묶인 몫을 숨기지 않는다.
② 흔들림을 같이 낸다 — 무작위 출발점만 바꿔 여러 번 돌린다.
③ 누가 빠졌는지 낸다 — 집단별 탈락률.
④ 규모 맞춤판과 원래 비율판을 둘 다 낸다.
⑤ 소수가 판을 채우는지 잰다.
⑥ 주제 수를 코드가 몰래 정하지 않는다 — 상한이 없다.
⑦ 원문은 밖으로 나가지 않게 — 공개판과 내부 검토판을 나눈다. 공인의 공개 발언만 예외.
⑧ 규칙은 결과를 보고 사람이 정하고, 여러 사람이 따로 판단해 일치도를 잰다."""


S = {"type": "string"}
TOOLS = [
    {"name": "list_presets", "description": "규칙 파일 목록. List rule presets.", "inputSchema": {"type": "object", "properties": {}}, "fn": t_presets},
    {"name": "inspect_table", "description": "표의 열 이름·행 수만 본다. 값(원문)은 돌려주지 않는다.",
     "inputSchema": {"type": "object", "properties": {"path": S}, "required": ["path"]}, "fn": t_inspect},
    {"name": "diagnose", "description": "★ 공론 지도 + 진단 보고서(공개판·내부 검토판)를 PC에 쓰고 집계 요약을 돌려준다.",
     "inputSchema": {"type": "object", "properties": {
         "path": S, "text": S, "group": S, "speaker": S, "context": {"type": "string", "description": "대표 발언 옆에 붙일 열, 쉼표로"},
         "preset": S, "text_policy": {"type": "string", "enum": ["private", "quotes", "public"]}, "previous": S,
         "per_group": {"type": "integer"}, "out_dir": S, "name": S, "title": S, "subject": S, "source": S,
         "min_chars": {"type": "integer", "description": "이보다 짧은 글은 뺀다"},
         "drop": {"type": "string", "description": "열=값 인 글을 뺀다, 쉼표로 (예: moderation=rejected)"},
         "selection": {"type": "string", "enum": ["eom", "leaf"], "description": "자료가 작으면 leaf가 더 잘게 나눈다"},
         "min_cluster_size": {"type": "integer"}},
         "required": ["path", "text", "group"]}, "fn": t_diagnose},
    {"name": "draft_rules", "description": "채점자 판단 파일들로 일치도(κ)를 재고, 합의된 「공론 아님」 묶음에서 규칙 초안을 쓴다.",
     "inputSchema": {"type": "object", "properties": {"run": S, "reviews": S, "exclude": S, "policy": {"type": "string", "enum": ["majority", "all"]},
                                                      "out": S, "name": S}, "required": ["run", "out"]}, "fn": t_draft},
    {"name": "apply_labels", "description": "합의된 주제 이름을 보고서에 넣는다.",
     "inputSchema": {"type": "object", "properties": {"run": S, "reviews": S, "labels": S, "by": S}, "required": ["run"]}, "fn": t_labels},
    {"name": "principles", "description": "이 도구의 원칙 ⓪~⑧.", "inputSchema": {"type": "object", "properties": {}}, "fn": t_principles},
]

if __name__ == "__main__":
    mcpkit.run("listen-check", INS, TOOLS)
