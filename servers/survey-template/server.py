"""MCP 서버 — 서베이 원자료 조회 틀 (분모 규약 내장). Survey lookups with denominator rules."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import mcpkit  # noqa: E402
import survey as S  # noqa: E402

INS = """서베이 원자료를 직접 세는 도구의 틀입니다. 기본 설정은 가상 예시 자료입니다(WWH_SURVEY_CONFIG로 바꿈).
 · 비율은 모두 가중값, 사례수는 미가중. 둘을 함께 적습니다.
 · 집단(분모)은 설정 파일에 정한 이름으로만 고릅니다.
 · 보기는 이름으로 고릅니다. 애매하면 도구가 멈추고 보기를 보여 줍니다.
 · 작은 칸에는 경고가 붙습니다 — 방향만 읽습니다.
쓰는 순서: survey_find → survey_question → survey_cross"""


def t_groups(a):
    return "\n".join(f"{g}  (n={len(S.subset([g])):,})" for g in S.cfg()["groups"])


def t_find(a):
    h = S.search(a.get("keyword", ""))
    return "\n".join(f"{c}\t{t}" for c, t in h) or "걸리는 문항이 없습니다."


def t_question(a):
    q = a["question"]
    rs = S.rows()
    return "\n".join([f"{q} — {S.question_text(q)} (전체 n={len(rs):,}, 가중 %)"] +
                     [f"  {c}. {lab}  {S.wpct(rs, q, {c}):.1f}%" for c, lab in S.options(q)])


def t_cross(a):
    return S.cross(a["question"], [x.strip() for x in a["options"].split(",")], [x.strip() for x in a["groups"].split(",")])


T = {"type": "string"}
TOOLS = [
    {"name": "survey_groups", "description": "쓸 수 있는 집단(분모)과 사례수.", "inputSchema": {"type": "object", "properties": {}}, "fn": t_groups},
    {"name": "survey_find", "description": "문항 찾기.", "inputSchema": {"type": "object", "properties": {"keyword": T}, "required": ["keyword"]}, "fn": t_find},
    {"name": "survey_question", "description": "문항의 보기와 전체 가중 분포.", "inputSchema": {"type": "object", "properties": {"question": T}, "required": ["question"]}, "fn": t_question},
    {"name": "survey_cross", "description": "★ 보기(이름, 쉼표로 합산) × 집단(쉼표로) 가중 % · 사례수 · z.",
     "inputSchema": {"type": "object", "properties": {"question": T, "options": T, "groups": T}, "required": ["question", "options", "groups"]}, "fn": t_cross},
]

if __name__ == "__main__":
    mcpkit.run("survey-template", INS, TOOLS)
