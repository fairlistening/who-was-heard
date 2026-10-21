"""명령줄.

  who-was-heard columns   자료.csv                      열 이름·행 수 (값은 보여주지 않음)
  who-was-heard presets                                 규칙 파일 목록
  who-was-heard report    자료.csv --text 내용 --group 집단 [--speaker 작성자] [--preset 규칙]
  who-was-heard rules-draft --run 결과/r1 --reviews A.json,B.json --out 규칙2.json
  who-was-heard label     --run 결과/r2 --reviews A.json,B.json

권장 흐름 · Recommended flow (차수 제한 없음 · any number of rounds)
  1) report (규칙 없이, 1차)
  2) 채점자마다 따로 판단 파일 작성 — 공론이 아닌 묶음(exclude)·주제 이름(labels)
  3) rules-draft --reviews ...   → 일치도(κ)를 재고, 합의된 것만 규칙 초안에
  4) 초안을 읽고 고치기
  5) report --preset 규칙2.json --previous 결과/r1_public.json   (2차)
  6) 필요하면 2)~5) 반복 — 3차, 4차 …
  7) label --reviews ...  (합의된 주제 이름 넣기)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

from .cluster import ClusterParams
from .data import columns, load_table
from .embed import DEFAULT_MODEL
from . import presets as P



def _jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _names(path):
    if not path:
        return None
    if path.endswith(".json"):
        return _jload(path)
    with open(path, encoding="utf-8-sig") as f:
        return {r["id"]: r["name"] for r in csv.DictReader(f)}


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="who-was-heard",
                                 description="공론을 한데 모으되, 묻히는 목소리를 놓치지 않기 위한 도구 (Fair Listening)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("columns", help="열 이름·행 수만 보기 (값은 보여주지 않음)")
    c.add_argument("path")
    sub.add_parser("presets", help="규칙 파일 목록")

    r = sub.add_parser("report", help="공론 지도 + 진단 보고서 (공개판·내부 검토판)")
    r.add_argument("path")
    r.add_argument("--text", required=True, help="글이 든 열")
    r.add_argument("--group", required=True, help="집단을 가르는 열 (정당·채널·지역·회의 구분 등)")
    r.add_argument("--speaker", help="작성자·발언자 ID 열")
    r.add_argument("--speaker-names", help="ID→이름 짝 (CSV: id,name 또는 JSON)")
    r.add_argument("--context", default="", help="대표 발언 옆에 붙일 열들, 쉼표로 (예: date,title)")
    r.add_argument("--preset", default="none", help="규칙 파일 이름 또는 경로 (기본 none = 길이·중복만)")
    r.add_argument("--text-policy", choices=["private", "quotes", "public"], help="원문 공개 여부 (기본은 규칙 파일을 따름)")
    r.add_argument("--previous", help="바로 앞 차수 보고서의 _public.json — 차수 사슬로 기록됨")
    r.add_argument("--out", default="who-was-heard-report")
    r.add_argument("--name", default="report")
    r.add_argument("--per-group", type=int, default=1000, help="집단마다 최대 건수 (0이면 전부)")
    r.add_argument("--model", default=DEFAULT_MODEL)
    r.add_argument("--min-chars", type=int, help="이보다 짧은 글은 뺀다 (기본: 규칙 파일)")
    r.add_argument("--drop", action="append", default=[], help="열=값 인 글을 뺀다 (여러 번 가능). 예: --drop moderated=rejected")
    r.add_argument("--min-group-size", type=int, default=0, help="글이 이보다 적은 집단은 「기타」로 합친다")
    r.add_argument("--group-order", default="", help="집단 순서(색 순서), 쉼표로")
    r.add_argument("--cache", help="임베딩 저장 폴더 — 다음 차수에 다시 계산하지 않는다 (원문은 저장하지 않음)")
    r.add_argument("--embed-chars", type=int, help="임베딩에 쓸 앞부분 글자 수 (기본: 규칙 파일 또는 400)")
    r.add_argument("--seeds", default="42,1,7,11,23")
    r.add_argument("--min-cluster-size", type=int)
    r.add_argument("--selection", choices=["eom", "leaf"], default="eom", help="HDBSCAN 묶음 고르기 — 자료가 작으면 leaf가 더 잘게 나눈다")
    r.add_argument("--title", default="공론 지도")
    r.add_argument("--subject", default="", help="무엇의 공론인가 (예: 미국 의회 2026년 3월)")
    r.add_argument("--source", default="")

    d = sub.add_parser("rules-draft", help="1차 결과에서 고른 묶음으로 규칙 초안 만들기")
    d.add_argument("--run", required=True, help="결과 폴더/이름 (예: out/report)")
    d.add_argument("--exclude", help="(혼자 판단할 때) 공론이 아니라고 고른 묶음 번호, 쉼표로")
    d.add_argument("--reviews", help="채점자 판단 파일들, 쉼표로 — 일치도를 재고 합의된 것만 넣는다")
    d.add_argument("--policy", choices=["majority", "all"], default="majority", help="합의 기준 (과반 / 전원 일치)")
    d.add_argument("--out", required=True)
    d.add_argument("--name", default="my-rules")
    d.add_argument("--base", help="앞 차수 규칙 파일 — 그 규칙을 이어받고 새 후보를 더한다")

    lb = sub.add_parser("label", help="사람이 붙인 주제 이름을 넣어 보고서 다시 쓰기")
    lb.add_argument("--run", required=True)
    lb.add_argument("--labels", help='JSON {"묶음번호": "주제 이름"}')
    lb.add_argument("--reviews", help="채점자 판단 파일들, 쉼표로 — 이름이 엇갈리면 「A / B」로 둘 다 적는다")
    lb.add_argument("--by", default="", help="누가 이름을 붙였나 (보고서에 찍힘)")

    a = ap.parse_args(argv)

    if a.cmd == "columns":
        print(json.dumps(columns(a.path), ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "presets":
        for n in P.available():
            p = P.load(n)
            print(f"{n:18s} {P.describe(p)}\n{'':18s} {p.get('description_ko','')}")
        return 0

    from .report import apply_labels, diagnose, load_report, summary_text, write_reports
    if a.cmd == "rules-draft":
        from .rules import write_draft
        rep = load_report(a.run + "_public.json", a.run + "_INTERNAL_do-not-share.json")
        agr = None
        if a.reviews:
            from .reviews import agreement, load as load_reviews
            agr = agreement(load_reviews(a.reviews.split(",")), [c["id"] for c in rep.public["clusters"]], a.policy)
            ex = agr["excluded"]
            print(f"채점자 {len(agr['reviewers'])}명 · κ={agr['kappa']} · 일치율 {agr['percent_agreement']}% · 합의로 뺄 묶음 {ex}")
            for sp in agr["split"]:
                print(f"  엇갈림: 묶음 {sp['id']} — {sp['exclude_votes']}/{sp['of']}명이 「공론 아님」")
        elif a.exclude:
            ex = [int(x) for x in a.exclude.split(",")]
        else:
            print("--exclude 또는 --reviews 가 필요합니다.")
            return 2
        base = P.load(a.base) if a.base else None
        dd = write_draft(rep.public, rep.internal.get("members", {}), ex, a.name, a.out, agr, base)
        print(f"규칙 초안: {a.out} · 후보 문구 {len(dd['exclude_patterns'])}개 — 읽고 고친 뒤 --preset 으로 쓰세요.")
        for cnd in dd["_derived_from"]["candidates"]:  # 새 후보만
            print(f"  {cnd['cover_excluded']:.0%} / {cnd['cover_other']:.1%}  {cnd['phrase']}")
        return 0
    if a.cmd == "label":
        rep = load_report(a.run + "_public.json", a.run + "_INTERNAL_do-not-share.json")
        if a.reviews:
            from .reviews import agreement, load as load_reviews
            agr = agreement(load_reviews(a.reviews.split(",")), [c["id"] for c in rep.public["clusters"]])
            labels = agr["labels"]
            by = a.by or ("채점자 " + ", ".join(agr["reviewers"]) + " — 엇갈린 이름은 「A / B」로 함께 적음")
        else:
            labels = _jload(a.labels)
            by = a.by
        apply_labels(rep.public, labels, by)
        out, name = os.path.split(a.run)
        paths = write_reports(rep, out or ".", name)
        print("이름을 넣었습니다:", paths["public_html"])
        return 0

    preset = P.load(a.preset)
    if a.min_chars is not None:
        preset = dict(preset, min_chars=a.min_chars)
    policy = a.text_policy or preset.get("text_policy", "private")
    rows = load_table(a.path)
    params = ClusterParams(seeds=tuple(int(s) for s in a.seeds.split(",")), min_cluster_size=a.min_cluster_size, selection=a.selection)
    prev = _jload(a.previous) if a.previous else None
    rep = diagnose(rows, a.text, a.group, a.speaker, per_group=a.per_group, params=params, model=a.model,
                   text_policy=policy, speaker_names=_names(a.speaker_names),
                   context=tuple(x.strip() for x in a.context.split(",") if x.strip()),
                   title=a.title, subject=a.subject, source=a.source or os.path.basename(a.path),
                   preset=preset, previous=prev, embed_max_chars=a.embed_chars, cache_dir=a.cache,
                   drop=({k: [v] for k, v in (x.split("=", 1) for x in a.drop)} if a.drop else None),
                   min_group_size=a.min_group_size, group_order=tuple(x.strip() for x in a.group_order.split(",") if x.strip()))
    paths = write_reports(rep, a.out, a.name)
    print(summary_text(rep))
    print("\n공개판:", paths["public_html"])
    print("내부 검토판(반출 금지):", paths["internal_html"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
