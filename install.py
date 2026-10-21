"""설치 — 라이브러리를 깔고, 원하면 MCP 서버를 Claude 데스크톱 설정에 등록한다.
Install the library and, optionally, register the MCP servers in Claude Desktop.

  python install.py              라이브러리 설치 + 점검
  python install.py --mcp        위 + Claude 데스크톱에 MCP 서버 셋 등록

등록할 때 지금 설정 파일을 먼저 백업하고, 이미 있는 다른 서버 항목은 건드리지 않는다.
Before registering, the current config is backed up; other servers are left untouched.
"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SERVERS = {
    "listen-check": os.path.join(HERE, "servers", "listen-check", "server.py"),
    "ledger": os.path.join(HERE, "servers", "ledger", "server.py"),
    "survey-template": os.path.join(HERE, "servers", "survey-template", "server.py"),
}


def config_path():
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude_desktop_config.json")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
    return os.path.expanduser("~/.config/Claude/claude_desktop_config.json")


def register():
    cp = config_path()
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    cfg = {}
    if os.path.exists(cp):
        bak = cp.replace(".json", ".backup_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(cp, bak)
        print("백업 · backup:", bak)
        try:
            with open(cp, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            print("지금 설정 파일을 읽지 못했습니다 · could not read config:", e)
            print("백업은 남겼습니다. 새로 씁니다 · backup kept; writing a new one.")
            cfg = {}
    srv = cfg.setdefault("mcpServers", {})
    before = sorted(srv)
    for name, path in SERVERS.items():
        srv[name] = {"command": sys.executable, "args": [path]}
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("등록 · registered:", ", ".join(SERVERS))
    kept = [s for s in before if s not in SERVERS]
    print("그대로 둔 서버 · untouched:", ", ".join(kept) or "-")
    print("Claude 데스크톱을 완전히 종료한 뒤 다시 켜세요 · Fully quit and restart Claude Desktop.")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("설치 · installing (pip install -e .[full]) …")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", HERE + "[full]"])
    print("점검 · running tests …")
    subprocess.check_call([sys.executable, "-m", "unittest", "discover", os.path.join(HERE, "tests")])
    if "--mcp" in sys.argv:
        register()
    print("\n끝 · done.")
    print("  명령줄 · CLI:  who-was-heard columns <자료.csv>")
    print("  MCP(HTTP):     start.pyw 더블클릭 (창 없이) · double-click start.pyw (no console) — 맥 · macOS: start.command")


if __name__ == "__main__":
    main()
