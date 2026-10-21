"""우리 코드가 쓰는 바깥 모듈을 훑어 출력한다 — deps.py를 고칠 때 대조용."""
import ast, glob, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OURS = {"whowasheard", "mcpkit", "studio", "sources", "http_hub", "app_register", "survey", "ledger", "server"}
mods = set()
for f in glob.glob(os.path.join(HERE, "servers", "**", "*.py"), recursive=True) + \
        glob.glob(os.path.join(HERE, "whowasheard", "**", "*.py"), recursive=True) + [os.path.join(HERE, "start.py")]:
    for n in ast.walk(ast.parse(open(f, encoding="utf-8").read())):
        if isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            mods.add(n.module)
print("\n".join(sorted(m for m in mods if m.split(".")[0] not in OURS)))
