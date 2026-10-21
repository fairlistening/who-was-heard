# -*- coding: utf-8 -*-
"""원클릭 실행 — MCP 서버 셋을 이 PC 안의 주소로 켜고, 브라우저에 안내 페이지를 연다.
One-click start: run the three MCP servers on a local address and open the setup page.

  윈도  start.pyw 더블클릭       창 없이 뒤에서 돈다 (끄기는 안내 페이지의 버튼)
  맥    start.command 더블클릭   뒤에서 돈다
  어디서나  python start.py      창에 기록을 보며 돈다 (문제를 찾을 때)

처음 한 번은 필요한 패키지를 뒤에서 설치한다(몇 분). 그동안에도 ledger·survey-template은 쓸 수 있다.

  --background     뒤로 띄우고 바로 끝난다 (창 없이)
  --port 8740      다른 포트
  --no-browser     브라우저 안 열기
  --no-install     설치 확인 건너뛰기
"""
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "servers"))
sys.path.insert(0, HERE)
NEEDED = ("numpy", "umap", "hdbscan", "sklearn", "sentence_transformers", "openpyxl")
LOG_DIR = os.path.join(HERE, "_logs")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
STATE = {"installing": False, "install_error": False, "install_log": ""}


def _log(*a):
    line = " ".join(str(x) for x in a)
    if sys.stdout:  # 창 없이 돌 때(pythonw)는 stdout이 없다
        try:
            print(line, flush=True)
        except Exception:
            pass
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "start.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")
    except Exception:
        pass


def missing():
    return [m for m in NEEDED if importlib.util.find_spec(m) is None]


def install_in_background():
    """빠진 패키지를 창 없이 설치한다. 서버는 그동안에도 돈다."""
    miss = missing()
    if not miss:
        return
    STATE["installing"] = True
    log = os.path.join(LOG_DIR, "install.log")
    STATE["install_log"] = log
    _log("처음 실행: 패키지 설치 시작 · installing:", ", ".join(miss), "→", log)

    def run():
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(log, "w", encoding="utf-8") as f:
            r = subprocess.call([sys.executable.replace("pythonw", "python"), "-m", "pip", "install", "-e", HERE + "[full]"],
                                stdout=f, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        importlib.invalidate_caches()
        STATE["installing"] = False
        STATE["install_error"] = r != 0
        _log("설치 끝 · install finished" if r == 0 else "설치 실패 · install failed — see " + log)

    threading.Thread(target=run, daemon=True).start()


def ours(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as r:
            return json.load(r).get("app") == "who-was-heard"
    except Exception:
        return False


def detach(argv):
    """자기 자신을 창 없이 다시 띄우고 끝난다. Relaunch detached, without a console."""
    args = [a for a in argv if a != "--background"]
    exe = sys.executable
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "cwd": HERE}
    if sys.platform.startswith("win"):
        w = os.path.join(os.path.dirname(exe), "pythonw.exe")
        exe = w if os.path.exists(w) else exe
        kw["creationflags"] = NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kw["start_new_session"] = True
    subprocess.Popen([exe, os.path.abspath(__file__)] + args, **kw)


def main(argv=None):
    import argparse
    argv = sys.argv[1:] if argv is None else argv
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="who-was-heard — one-click local MCP servers")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--background", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--no-install", action="store_true")
    a = ap.parse_args(argv)

    if sys.version_info < (3, 9):
        _log("파이썬 3.9 이상이 필요합니다 · Python 3.9+ required.")
        return 1

    import http_hub
    want = a.port or http_hub.DEFAULT_PORT
    if ours(want):  # 이미 켜져 있으면 안내 페이지만 연다
        _log("이미 켜져 있습니다 · already running:", f"http://127.0.0.1:{want}/")
        if not a.no_browser:
            webbrowser.open(f"http://127.0.0.1:{want}/")
        return 0
    if a.background:
        detach(argv)
        _log("뒤에서 켰습니다 · started in the background")
        return 0

    httpd, port = None, want
    for port in ([want] if a.port else range(want, want + 10)):
        try:
            httpd = http_hub.make_server(port, status=lambda: dict(STATE))
            break
        except OSError:
            continue
    if httpd is None:
        _log(f"포트 {want}을(를) 쓸 수 없습니다 · port unavailable. --port 로 다른 번호를 주세요.")
        return 1

    if not a.no_install:
        install_in_background()

    url = f"http://127.0.0.1:{port}/"
    _log(f"켜짐 · running  {url}")
    for s in http_hub.SERVERS:
        _log(f"    {s:<16} {url}{s}/mcp")
    if port != http_hub.DEFAULT_PORT:
        _log(f"  ※ 기본 포트 {http_hub.DEFAULT_PORT}이 사용 중이라 {port}로 켰습니다 · default port busy, using {port}")
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        _log("꺼짐 · stopped")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:
        _log("오류 · error:", repr(e))
        code = 1
    if code and sys.stdin and sys.stdin.isatty():  # 창이 오류와 함께 바로 사라지지 않게
        try:
            input("\n엔터를 누르면 창이 닫힙니다 · Press Enter to close ")
        except Exception:
            pass
    sys.exit(code or 0)
