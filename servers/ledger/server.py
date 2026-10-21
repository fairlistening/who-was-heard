"""MCP 서버 — 수치 대장·금지 문장 검사. Ledger of figures and banned phrases."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import mcpkit  # noqa: E402
import ledger as L  # noqa: E402

INS = """확정 수치와 「쓰면 안 되는 말」을 모아 둔 대장입니다.
 · 초고를 fact_check에 통째로 넣으면 금지 표현·분모 없는 비율·대장에 없는 수치를 짚습니다.
 · 「대장에 없는 수치」는 틀렸다는 말이 아니라 원자료에서 다시 세어 확인하라는 말입니다.
 · 대장은 사람이 고치는 TSV입니다 (facts.tsv · bans.tsv). 위치: WWH_LEDGER_DIR 또는 servers/ledger/ledger/.
규약: 값을 옮길 때 「무엇 위에서 잰 값인지」를 함께 옮깁니다."""


def t_check(a):
    t = a.get("text", "")
    return L.check(t)[0] if t.strip() else "text에 초고를 넣으세요."


def t_find(a):
    rows = L.find(a.get("keyword", ""), int(a.get("limit", 30)))
    if not rows:
        return "대장에 그런 항목이 없습니다."
    return "\n".join(["item\tvalue\tdenominator\tsource\tstatus"] +
                     ["\t".join(r.get(k, "") for k in ("item", "value", "denominator", "source", "status")) for r in rows])


def t_all(a):
    rows = L.facts()
    return "\n".join([f"{len(rows)} rows", "item\tvalue\tdenominator\tsource\tstatus"] +
                     ["\t".join(r.get(k, "") for k in ("item", "value", "denominator", "source", "status")) for r in rows])


def t_bans(a):
    return "\n".join(f"{'⛔' if b.get('level','').lower() in ('ban','금지') else '⚠'} {b.get('phrase','')} — {b.get('reason','')} → {b.get('instead','')}"
                     for b in L.bans()) or "금지 목록이 비어 있습니다."


def t_add(a):
    p = os.path.join(L.DIR, "facts.tsv")
    new = not os.path.exists(p)
    with open(p, "a", encoding="utf-8") as f:
        if new:
            f.write("item\tvalue\tdenominator\tsource\tstatus\n")
        f.write("\t".join([a.get("item", ""), str(a.get("value", "")), a.get("denominator", ""), a.get("source", ""), a.get("status", "confirmed")]) + "\n")
    return "대장에 넣었습니다."


S = {"type": "string"}
TOOLS = [
    {"name": "fact_check", "description": "★ 초고를 넣으면 금지 표현·분모 없는 비율·대장에 없는 수치를 짚는다.",
     "inputSchema": {"type": "object", "properties": {"text": S}, "required": ["text"]}, "fn": t_check},
    {"name": "fact_find", "description": "대장에서 수치 찾기.", "inputSchema": {"type": "object", "properties": {"keyword": S, "limit": {"type": "integer"}}, "required": ["keyword"]}, "fn": t_find},
    {"name": "fact_all", "description": "대장 전체.", "inputSchema": {"type": "object", "properties": {}}, "fn": t_all},
    {"name": "ban_list", "description": "쓰면 안 되는 말과 대신 쓸 말.", "inputSchema": {"type": "object", "properties": {}}, "fn": t_bans},
    {"name": "fact_add", "description": "확정 수치를 대장에 더한다. 분모를 꼭 적는다.",
     "inputSchema": {"type": "object", "properties": {"item": S, "value": S, "denominator": S, "source": S, "status": S},
                     "required": ["item", "value", "denominator"]}, "fn": t_add},
]

if __name__ == "__main__":
    mcpkit.run("ledger", INS, TOOLS)
