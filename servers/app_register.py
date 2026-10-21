# -*- coding: utf-8 -*-
"""앱 자동 등록 — 안내 페이지의 「등록」 버튼이 부른다. 표준 라이브러리만.
Register / unregister the three servers in an AI app's MCP settings. Called by the setup page's buttons.

원칙 · Rules
 · 정해 둔 앱의 설정 파일에만 쓴다. 다른 파일은 건드리지 않는다.
 · 쓰기 전에 원래 파일을 같은 폴더에 백업한다 (*.backup_YYYYmmdd_HHMMSS).
 · 우리 서버 셋만 더하거나 뺀다. 이미 있던 다른 서버는 그대로 둔다.
   같은 이름이라도 우리 주소·우리 파일을 가리키지 않으면 지우지 않는다.
 · 앱이 이 PC에 없으면(설정 폴더가 없으면) 새로 만들지 않는다.
 · 주석이 든 설정 파일처럼 안전하게 읽지 못하면 고치지 않고 복사-붙여넣기를 안내한다.
"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SERVERS = ("listen-check", "ledger", "survey-template")
MARK_BEGIN = "# >>> who-was-heard (자동 등록 · added by who-was-heard)"
MARK_END = "# <<< who-was-heard"


def _home():
    return os.environ.get("WWH_TEST_HOME") or os.path.expanduser("~")


def _appdata():
    """윈도 %APPDATA%, 맥 ~/Library/Application Support, 리눅스 ~/.config"""
    if os.environ.get("WWH_TEST_HOME"):
        return os.path.join(_home(), "AppData")
    if sys.platform.startswith("win"):
        return os.environ.get("APPDATA") or os.path.join(_home(), "AppData", "Roaming")
    if sys.platform == "darwin":
        return os.path.join(_home(), "Library", "Application Support")
    return os.path.join(_home(), ".config")


def _python():
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):  # stdio에는 창 없는 pythonw가 아니라 python을
        cand = exe[:-len("pythonw.exe")] + "python.exe"
        exe = cand if os.path.exists(cand) else exe
    return exe


def stdio_entry(name):
    return {"command": _python(), "args": [os.path.join(HERE, name, "server.py")]}


# 앱 정의 · app definitions ─────────────────────────────────────────────
# kind: json (top 키 아래에 서버 이름별 항목) / toml (표식 블록) / cli (claude 명령)
APPS = {
    "claude-desktop": {"label": "Claude Desktop", "kind": "json", "top": "mcpServers",
                       "path": lambda: os.path.join(_appdata(), "Claude", "claude_desktop_config.json"),
                       "entry": lambda name, url: stdio_entry(name)},
    "claude-code": {"label": "Claude Code", "kind": "cli"},
    "cursor": {"label": "Cursor", "kind": "json", "top": "mcpServers",
               "path": lambda: os.path.join(_home(), ".cursor", "mcp.json"),
               "entry": lambda name, url: {"url": url}},
    "vscode": {"label": "VS Code", "kind": "json", "top": "servers",
               "path": lambda: os.path.join(_appdata(), "Code", "User", "mcp.json"),
               "entry": lambda name, url: {"type": "http", "url": url}},
    "windsurf": {"label": "Windsurf", "kind": "json", "top": "mcpServers",
                 "path": lambda: os.path.join(_home(), ".codeium", "windsurf", "mcp_config.json"),
                 "entry": lambda name, url: {"serverUrl": url}},
    "gemini": {"label": "Gemini CLI", "kind": "json", "top": "mcpServers",
               "path": lambda: os.path.join(_home(), ".gemini", "settings.json"),
               "entry": lambda name, url: {"httpUrl": url, "timeout": 1800000}},
    "codex": {"label": "Codex CLI", "kind": "toml",
              "path": lambda: os.path.join(_home(), ".codex", "config.toml")},
    "lmstudio": {"label": "LM Studio", "kind": "json", "top": "mcpServers",
                 "path": lambda: os.path.join(_home(), ".lmstudio", "mcp.json"),
                 "entry": lambda name, url: {"url": url}},
}


def _is_ours(name, val):
    """같은 이름의 항목이 우리 것인지 — 우리 주소나 우리 server.py를 가리킬 때만."""
    if not isinstance(val, dict):
        return False
    for k in ("url", "serverUrl", "httpUrl"):
        u = str(val.get(k) or "")
        if u.startswith(("http://127.0.0.1:", "http://localhost:")) and u.rstrip("/").endswith(f"/{name}/mcp"):
            return True
    args = val.get("args") or []
    return any(str(a).replace("\\", "/").endswith(f"servers/{name}/server.py") for a in args)


def _backup(path):
    if os.path.exists(path):
        bak = f"{path}.backup_{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(path, bak)
        return bak
    return ""


def _write(path, text):
    tmp = path + ".wwh-tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def _read_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig") as f:
        raw = f.read()
    if not raw.strip():
        return {}
    return json.loads(raw)  # 주석·끝 쉼표가 있으면 실패 → 손대지 않는다


def _toml_block(base):
    lines = [MARK_BEGIN]
    for s in SERVERS:
        lines += [f"[mcp_servers.{s}]", f'url = "{base}/{s}/mcp"']
        if s == "listen-check":
            lines.append("tool_timeout_sec = 1800")
        lines.append("")
    lines.append(MARK_END)
    return "\n".join(lines)


def _strip_toml_block(text):
    if MARK_BEGIN not in text:
        return text, False
    a = text.index(MARK_BEGIN)
    b = text.find(MARK_END, a)
    b = len(text) if b < 0 else b + len(MARK_END)
    return (text[:a].rstrip("\n") + "\n" + text[b:].lstrip("\n")).strip("\n") + "\n", True


def _rd(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _claude_cli():
    return shutil.which("claude")


def status(app):
    d = APPS[app]
    out = {"app": app, "label": d["label"], "kind": d["kind"], "found": False, "registered": False, "path": ""}
    if d["kind"] == "cli":
        exe = _claude_cli()
        out["found"] = bool(exe)
        out["path"] = exe or ""
        if exe:
            try:
                r = subprocess.run([exe, "mcp", "list"], capture_output=True, text=True, timeout=20,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                out["registered"] = all(f"/{s}/mcp" in r.stdout for s in SERVERS)
            except Exception:
                pass
        return out
    path = d["path"]()
    out["path"] = path
    out["found"] = os.path.isdir(os.path.dirname(path))
    if not os.path.exists(path):
        return out
    try:
        if d["kind"] == "toml":
            out["registered"] = MARK_BEGIN in _rd(path)
        else:
            cfg = _read_json(path).get(d["top"]) or {}
            out["registered"] = all(_is_ours(s, cfg.get(s)) for s in SERVERS)
    except Exception:
        out["unreadable"] = True
    return out


def register(app, base):
    """base: http://127.0.0.1:8730 · 돌려주는 값: {ok, message_ko, message_en, backup, path}"""
    d = APPS[app]
    if d["kind"] == "cli":
        exe = _claude_cli()
        if not exe:
            return _fail("claude 명령을 찾지 못했습니다. Claude Code가 설치돼 있는지 확인하세요.",
                         "Could not find the `claude` command. Is Claude Code installed?")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for s in SERVERS:
            subprocess.run([exe, "mcp", "remove", "--scope", "user", s], capture_output=True, timeout=30, creationflags=flags)
            r = subprocess.run([exe, "mcp", "add", "--scope", "user", "--transport", "http", s, f"{base}/{s}/mcp"],
                               capture_output=True, text=True, timeout=30, creationflags=flags)
            if r.returncode != 0:
                return _fail(f"등록하지 못했습니다: {r.stderr.strip()[:200]}", f"Registration failed: {r.stderr.strip()[:200]}")
        return _ok("Claude Code에 등록했습니다. 새 세션부터 쓸 수 있습니다.",
                   "Registered in Claude Code. Available from the next session.", "", exe)

    path = d["path"]()
    if not os.path.isdir(os.path.dirname(path)):
        return _fail(f"이 PC에서 {d['label']} 설정 폴더를 찾지 못했습니다. 앱을 한 번 실행한 뒤 다시 누르세요.",
                     f"Could not find {d['label']}'s settings folder. Open the app once, then try again.")
    if d["kind"] == "toml":
        text = _rd(path) if os.path.exists(path) else ""
        text, _ = _strip_toml_block(text)
        # 같은 이름의 표가 이미 손으로 적혀 있으면 겹치지 않게 멈춘다
        if any(f"[mcp_servers.{s}]" in text for s in SERVERS):
            return _fail("설정 파일에 같은 이름의 서버가 이미 있습니다. 직접 확인해 주세요.",
                         "The settings already define servers with these names; please check by hand.")
        bak = _backup(path)
        _write(path, (text.rstrip("\n") + "\n\n" if text.strip() else "") + _toml_block(base) + "\n")
    else:
        try:
            cfg = _read_json(path)
        except Exception:
            return _fail("설정 파일에 주석 등이 있어 자동으로 고치지 않았습니다. 아래 설정을 복사해 붙여 주세요.",
                         "The settings file has comments or other content we can't safely edit. Please copy and paste the settings below.")
        if not isinstance(cfg, dict):
            return _fail("설정 파일 형식이 예상과 달라 고치지 않았습니다.", "Unexpected settings format; not changed.")
        top = cfg.setdefault(d["top"], {})
        clash = [s for s in SERVERS if s in top and not _is_ours(s, top[s])]
        if clash:
            return _fail(f"같은 이름의 다른 서버가 있어 덮어쓰지 않았습니다: {', '.join(clash)}",
                         f"Another server already uses these names, so nothing was overwritten: {', '.join(clash)}")
        for s in SERVERS:
            top[s] = d["entry"](s, f"{base}/{s}/mcp")
        bak = _backup(path)
        _write(path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    return _ok(f"{d['label']}에 등록했습니다. 앱을 완전히 껐다 켜세요.",
               f"Registered in {d['label']}. Fully quit and restart the app.", bak, path)


def unregister(app):
    d = APPS[app]
    if d["kind"] == "cli":
        exe = _claude_cli()
        if not exe:
            return _fail("claude 명령을 찾지 못했습니다.", "Could not find the `claude` command.")
        for s in SERVERS:
            subprocess.run([exe, "mcp", "remove", "--scope", "user", s], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return _ok("Claude Code에서 뺐습니다.", "Removed from Claude Code.", "", exe)
    path = d["path"]()
    if not os.path.exists(path):
        return _ok("등록돼 있지 않습니다.", "Not registered.", "", path)
    if d["kind"] == "toml":
        text = _rd(path)
        new, found = _strip_toml_block(text)
        if not found:
            return _ok("등록돼 있지 않습니다.", "Not registered.", "", path)
        bak = _backup(path)
        _write(path, new)
    else:
        try:
            cfg = _read_json(path)
        except Exception:
            return _fail("설정 파일을 안전하게 읽지 못해 고치지 않았습니다.", "Could not safely read the settings file; not changed.")
        top = cfg.get(d["top"]) or {}
        mine = [s for s in SERVERS if _is_ours(s, top.get(s))]
        if not mine:
            return _ok("등록돼 있지 않습니다.", "Not registered.", "", path)
        for s in mine:
            del top[s]
        bak = _backup(path)
        _write(path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    return _ok(f"{d['label']}에서 뺐습니다. 앱을 껐다 켜세요.", f"Removed from {d['label']}. Restart the app.", bak, path)


def _ok(ko, en, backup, path):
    return {"ok": True, "message_ko": ko, "message_en": en, "backup": backup, "path": path}


def _fail(ko, en):
    return {"ok": False, "message_ko": ko, "message_en": en, "backup": "", "path": ""}


def main(argv=None):
    """명령줄에서도 쓴다 · CLI: python servers/app_register.py register cursor [--port 8730]"""
    import argparse
    ap = argparse.ArgumentParser(description="Register who-was-heard MCP servers in an app")
    ap.add_argument("action", choices=["status", "register", "unregister"])
    ap.add_argument("app", choices=sorted(APPS))
    ap.add_argument("--port", type=int, default=8730)
    a = ap.parse_args(argv)
    if a.action == "status":
        r = status(a.app)
    elif a.action == "register":
        r = register(a.app, f"http://127.0.0.1:{a.port}")
    else:
        r = unregister(a.app)
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
