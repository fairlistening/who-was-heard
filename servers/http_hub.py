# -*- coding: utf-8 -*-
"""세 MCP 서버를 이 PC 안의 HTTP 주소 하나로 띄운다. 표준 라이브러리만.
Serve the three MCP servers over local HTTP (MCP "Streamable HTTP", JSON responses). Stdlib only.

  http://127.0.0.1:8730/                     상태 페이지 · status page (주소·앱별 설정 예시)
  http://127.0.0.1:8730/listen-check/mcp     MCP
  http://127.0.0.1:8730/ledger/mcp
  http://127.0.0.1:8730/survey-template/mcp

★ 127.0.0.1에만 묶는다. 같은 와이파이의 다른 기기도, 인터넷도 이 주소에 닿지 못한다.
  다른 사이트가 브라우저를 통해 몰래 부르는 것(DNS 리바인딩)도 Host·Origin 검사로 막는다.
  Bound to 127.0.0.1 only; Host and Origin headers are checked.
"""
import html
import importlib.util
import json
import os
import secrets
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mcpkit  # noqa: E402
import app_register  # noqa: E402
import studio  # noqa: E402
from urllib.parse import parse_qs, urlsplit  # noqa: E402

DEFAULT_PORT = 8730
SERVERS = ("listen-check", "ledger", "survey-template")
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
# Docker로 돌리는 채팅 앱(LibreChat 등)이 이 PC의 서버를 부를 때 쓰는 이름 · name Docker containers use for the host
DOCKER_HOSTS = ("host.docker.internal",)


def load_servers():
    hs = {}
    for name in SERVERS:
        path = os.path.join(HERE, name, "server.py")
        spec = importlib.util.spec_from_file_location("wwh_srv_" + name.replace("-", "_"), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        hs[name] = mcpkit.make_handler(name, mod.INS, mod.TOOLS)
    return hs


def _host_ok(h, port):
    if not h:
        return False
    h = h.strip().lower()
    return any(h in (f"{x}:{port}", x) for x in LOCAL_HOSTS + DOCKER_HOSTS)


def _origin_ok(o):
    if not o or o == "null":
        return o is None  # 'null' origin (sandboxed pages, files) is refused
    o = o.lower()
    for x in LOCAL_HOSTS:
        for scheme in ("http://", "https://"):
            if o == scheme + x or o.startswith(scheme + x + ":"):
                return True
    return False


def make_server(port=DEFAULT_PORT, handlers=None, on_stop=None, status=None):
    """status: 상태를 dict로 돌려주는 함수(설치 진행 등) — /health에 실린다."""
    handlers = handlers or load_servers()
    stop_token = secrets.token_urlsafe(16)

    class H(BaseHTTPRequestHandler):
        server_version = "who-was-heard"

        def log_message(self, fmt, *a):  # 원문이 로그에 찍히지 않게 요청 줄만 · request line only
            if sys.stderr:  # 창 없이 돌 때(pythonw)는 stderr가 없다
                sys.stderr.write("  %s %s\n" % (self.command, self.path.split("?")[0]))

        def _guard(self):
            if not _host_ok(self.headers.get("Host"), self.server.server_address[1]):
                self._send(403, {"error": "host not allowed"}); return False
            if not _origin_ok(self.headers.get("Origin")):
                self._send(403, {"error": "origin not allowed — this server only answers apps on this PC"}); return False
            return True

        def _send(self, code, body=None, ctype="application/json; charset=utf-8", headers=()):
            data = b"" if body is None else (body if isinstance(body, bytes) else
                                             (body.encode("utf-8") if isinstance(body, str) else
                                              json.dumps(body, ensure_ascii=False).encode("utf-8")))
            self.send_response(code)
            if data:
                self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for k, v in headers:
                self.send_header(k, v)
            self.end_headers()
            if data:
                self.wfile.write(data)

        def _studio(self, method, raw):
            u = urlsplit(self.path)
            try:
                code, body, ctype = studio.route(method, u.path, parse_qs(u.query), raw, self.headers, stop_token)
            except Exception as e:
                code, body, ctype = 500, {"error": f"{type(e).__name__}: {e}"}, None
            return self._send(code, body, ctype or "application/json; charset=utf-8")

        def _server_name(self):
            parts = self.path.split("?")[0].strip("/").split("/")
            if len(parts) == 2 and parts[1] == "mcp" and parts[0] in handlers:
                return parts[0]
            return None

        def do_GET(self):
            if not self._guard():
                return
            p = self.path.split("?")[0]
            if p.startswith(("/api/", "/files/")):
                return self._studio("GET", b"")
            if p == "/studio":
                return self._send(200, studio_page(stop_token), "text/html; charset=utf-8")
            if p in ("/", "/index.html"):
                return self._send(200, status_page(self.server.server_address[1], stop_token), "text/html; charset=utf-8")
            if p == "/favicon.ico":
                return self._send(204)
            if p == "/apps":
                if self.headers.get("X-WWH-Token") != stop_token:
                    return self._send(403, {"error": "bad token"})
                return self._send(200, [app_register.status(a) for a in APP_IDS if a in app_register.APPS])
            if p == "/health":
                return self._send(200, dict({"ok": True, "app": "who-was-heard", "servers": list(handlers)},
                                            **(status() if status else {})))
            if self._server_name():
                # 이 서버는 SSE 스트림을 열지 않는다 (규약상 허용) · no SSE stream offered
                return self._send(405, {"error": "use POST"}, headers=[("Allow", "POST")])
            self._send(404, {"error": "not found"})

        def do_DELETE(self):
            if not self._guard():
                return
            self._send(405, {"error": "sessions are not stored"}, headers=[("Allow", "POST")])

        def do_POST(self):
            if not self._guard():
                return
            p = self.path.split("?")[0]
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            if p.startswith("/api/"):
                return self._studio("POST", raw)
            if p in ("/apps/register", "/apps/unregister"):
                try:
                    q = json.loads(raw.decode("utf-8"))
                except Exception:
                    q = {}
                if q.get("token") != stop_token:
                    return self._send(403, {"error": "bad token"})
                app = q.get("app")
                if app not in app_register.APPS:
                    return self._send(400, {"error": "unknown app"})
                port_ = self.server.server_address[1]
                r = (app_register.register(app, f"http://127.0.0.1:{port_}") if p.endswith("/register")
                     else app_register.unregister(app))
                return self._send(200, r)
            if p == "/stop":
                if raw.decode("utf-8", "ignore").strip() != stop_token:
                    return self._send(403, {"error": "bad token"})
                self._send(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                if on_stop:
                    on_stop()
                return
            name = self._server_name()
            if not name:
                return self._send(404, {"error": "not found"})
            try:
                msg = json.loads(raw.decode("utf-8"))
            except Exception:
                return self._send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            handle = handlers[name]
            batch = isinstance(msg, list)
            out = [r for r in (handle(m) for m in (msg if batch else [msg])) if r is not None]
            extra = []
            if not batch and isinstance(msg, dict) and msg.get("method") == "initialize":
                extra.append(("Mcp-Session-Id", uuid.uuid4().hex))
            if not out:
                return self._send(202, None, headers=extra)  # 알림만 · notifications only
            self._send(200, out if batch else out[0], headers=extra)

    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    httpd.daemon_threads = True
    return httpd




# ── 안내 페이지 · setup page ──────────────────────────────────────────────

APP_IDS = ("claude-code", "cursor", "vscode", "windsurf", "gemini", "codex", "lmstudio", "librechat", "claude-desktop")  # 탭 순서 · tab order

DESC = {
    "listen-check": ("공론 지도와 진단 보고서", "Discourse map and diagnostic report"),
    "ledger": ("초고의 수치·금지 문장 검사", "Check a draft's figures and banned phrases"),
    "survey-template": ("분모 규약을 지킨 서베이 조회", "Survey lookups with denominator rules"),
}


def snippets(base, lang="ko"):
    """앱별 설정 예시 (2026-10 기준). App configuration examples, in Korean or English comments."""
    ko = lang == "ko"
    u = {s: f"{base}/{s}/mcp" for s in SERVERS}

    def js(key, extra=None, top="mcpServers"):
        return json.dumps({top: {s: dict({key: u[s]}, **(extra or {})) for s in SERVERS}}, indent=2)

    long_note = ("# listen-check의 진단(diagnose)은 자료가 크면 몇 분 걸립니다. 아래는 30분까지 기다리는 설정입니다.\n" if ko else
                 "# Diagnose can take minutes on large tables; the setting below waits up to 30 minutes.\n")
    return [
        ("Claude Code", "터미널에서" if ko else "In a terminal",
         "\n".join(f"claude mcp add --transport http {s} {u[s]}" for s in SERVERS)
         + "\n\n" + long_note + ("# 환경변수 " if ko else "# environment variable ") + "MCP_TOOL_TIMEOUT=1800000"),
        ("Cursor", "~/.cursor/mcp.json", js("url")),
        ("VS Code", ".vscode/mcp.json", js("url", {"type": "http"}, top="servers")),
        ("Windsurf", "~/.codeium/windsurf/mcp_config.json", js("serverUrl")),
        ("Gemini CLI", "~/.gemini/settings.json", js("httpUrl", {"timeout": 1800000})),
        ("Codex CLI", "~/.codex/config.toml",
         long_note + "\n" + "\n\n".join(f'[mcp_servers.{s}]\nurl = "{u[s]}"'
                                        + ("\ntool_timeout_sec = 1800" if s == "listen-check" else "")
                                        for s in SERVERS)),
        ("LM Studio", "mcp.json (Program → Edit mcp.json)", js("url")),
        ("LibreChat", "librechat.yaml — mcpServers" if not ko else "librechat.yaml — mcpServers 아래",
         ("# LibreChat을 Docker로 돌릴 때(가장 흔한 설치) 기준입니다.\n"
          "# 직접 설치(npm)했다면 host.docker.internal 을 127.0.0.1 로 바꾸세요. 저장한 뒤 LibreChat을 다시 시작합니다.\n" if ko else
          "# For LibreChat running in Docker (the usual install).\n"
          "# For a direct (npm) install, replace host.docker.internal with 127.0.0.1. Restart LibreChat after saving.\n")
         + "mcpServers:\n" + "".join(
             f"  {s}:\n    type: streamable-http\n    url: {u[s].replace('127.0.0.1', 'host.docker.internal')}\n"
             + ("    timeout: 1800000\n" if s == "listen-check" else "") for s in SERVERS).rstrip("\n")),
        ("Claude Desktop", "HTTP 대신 stdio로 등록" if ko else "Registered over stdio instead of HTTP",
         "python install.py --mcp\n\n" + (
             "# Claude 데스크톱은 이 PC 안의 HTTP 주소를 직접 붙이지 않습니다.\n"
             "# 같은 서버를 stdio로 등록합니다. 도구는 똑같습니다." if ko else
             "# Claude Desktop does not attach local HTTP URLs.\n"
             "# This registers the same servers over stdio; the tools are identical.")),
    ]


def _os_lang():
    """이 PC의 언어·지역 설정 → 'ko' / 'en' / ''. The OS display language or locale, as a hint."""
    try:
        if sys.platform.startswith("win"):
            import ctypes
            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "ko" if (lid & 0x3FF) == 0x12 else "en"
        import locale
        loc = (locale.getlocale()[0] or os.environ.get("LANG") or "").lower()
        return "ko" if loc.startswith("ko") else ("en" if loc else "")
    except Exception:
        return ""


def status_page(port, stop_token):
    base = f"http://127.0.0.1:{port}"
    rows = "".join(
        f'<li><div class="nm">{s}<span class="d"><span class="l-ko">{DESC[s][0]}</span>'
        f'<span class="l-en">{DESC[s][1]}</span></span></div>'
        f'<code id="u{i}">{base}/{s}/mcp</code><button class="cp" data-t="u{i}" data-k="copy"></button></li>'
        for i, s in enumerate(SERVERS))
    ko, en = snippets(base, "ko"), snippets(base, "en")
    tabs, panes = [], []
    for i, ((app, wk, ck), (_, we, ce)) in enumerate(zip(ko, en)):
        tabs.append(f'<button class="tab{" on" if i == 0 else ""}" data-i="{i}">{html.escape(app)}</button>')
        blocks = ""
        for lg, w, c in (("ko", wk, ck), ("en", we, ce)):
            blocks += (f'<div class="l-{lg}"><div class="where"><span>{html.escape(w)}</span>'
                       f'<button class="cp" data-t="c{i}{lg}" data-k="copy"></button></div>'
                       f'<pre id="c{i}{lg}">{html.escape(c)}</pre></div>')
        reg = (f'<div class="reg" data-app="{APP_IDS[i]}"><div class="rtop"><span class="rs"></span>'
               f'<span class="rbtns"><button class="rb" data-act="register" data-k="reg"></button>'
               f'<button class="rb ghost" data-act="unregister" data-k="unreg" hidden></button></span></div>'
               f'<p class="rmsg" hidden></p></div><p class="or" data-k="or"></p>')
        if APP_IDS[i] not in app_register.APPS:  # 설정 파일 위치가 설치마다 다른 앱 · settings path varies
            reg = '<div class="reg"><p class="rmsg" data-k="manual_only"></p></div>'
        panes.append(f'<div class="pane" data-i="{i}"{"" if i == 0 else " hidden"}>{reg}{blocks}</div>')
    return (PAGE.replace("{{ROWS}}", rows).replace("{{TABS}}", "".join(tabs)).replace("{{PANES}}", "".join(panes))
            .replace("{{BASE}}", base).replace("{{TOKEN}}", stop_token).replace("{{OSLANG}}", _os_lang()))


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Who Was Heard MCP</title>
<style>
:root{--bg:#f6f5f1;--card:#fffefb;--fg:#1d1c1a;--mut:#6b675f;--line:#e2ded4;--acc:#2a6f5b;--accbg:#e3efe9;--code:#f1efe8;--warn:#9a3b1c;--warnbg:#f8e9e2;--note:#7a5a10;--notebg:#f7efd9;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--card:#1f1e1b;--fg:#ecebe6;--mut:#a29e94;--line:#34322d;--acc:#6cc3a3;--accbg:#1e3029;--code:#262521;--warn:#f08a62;--warnbg:#3a2219;--note:#e7c46f;--notebg:#352c16;color-scheme:dark}}
*{box-sizing:border-box}
[hidden]{display:none!important}
main>*,section,.pane{min-width:0}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif}
main{max-width:780px;margin:0 auto;padding-block:32px 64px;padding-inline:16px;display:grid;gap:24px}
html[lang=ko] .l-en,html[lang=en] .l-ko{display:none}
.top{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between}
h1{font-size:24px;margin:0;text-wrap:balance}
h2{font-size:15px;margin:0 0 12px;letter-spacing:.02em}
p{margin:0}
.mut{color:var(--mut)}
.small{font-size:13px}
.live{display:inline-flex;align-items:center;gap:8px;background:var(--accbg);color:var(--acc);padding:4px 12px;border-radius:999px;font-size:13px;font-weight:600}
.live:before{content:"";width:8px;height:8px;border-radius:50%;background:currentColor}
.live.off{background:var(--warnbg);color:var(--warn)}
.lang{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.lang button{border:0;border-radius:0;padding:5px 12px}
.lang button.on{background:var(--fg);color:var(--bg)}
.banner{border-radius:10px;padding:12px 14px;font-size:14px}
.studio{display:grid;gap:4px;text-decoration:none;color:var(--fg);background:var(--accbg);border:1px solid var(--acc);border-radius:10px;padding:14px 16px}
.studio b{color:var(--acc);font-size:16px}
.studio span{font-size:13.5px;color:var(--mut)}
.studio:hover{box-shadow:0 0 0 1px var(--acc)}
.banner.note{background:var(--notebg);color:var(--note)}
.banner.err{background:var(--warnbg);color:var(--warn)}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px}
ul{list-style:none;margin:0;padding:0;display:grid;gap:12px}
li{display:grid;grid-template-columns:210px minmax(0,1fr) auto;gap:10px;align-items:center}
.nm{font-weight:600;display:grid}
.nm .d{font-weight:400;font-size:12.5px;color:var(--mut)}
code,pre{font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}
li code{background:var(--code);padding:4px 8px;border-radius:6px;overflow-x:auto;white-space:nowrap}
button{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:4px 10px;font-size:13px}
button:hover{border-color:var(--acc)}
button:disabled{opacity:.5;cursor:default}
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.tab.on{background:var(--acc);border-color:var(--acc);color:var(--card)}
.where{display:flex;gap:10px;align-items:center;justify-content:space-between;font-size:13px;color:var(--mut);margin-bottom:6px}
.where span{min-width:0;overflow-wrap:anywhere}
pre{background:var(--code);margin:0;padding:12px;border-radius:8px;overflow-x:auto}
.reg{border:1px solid var(--line);border-radius:8px;padding:12px;display:grid;gap:8px;margin-bottom:12px;min-width:0}
.rtop{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between}
.rs{font-size:13.5px;min-width:0}
.rs.yes{color:var(--acc);font-weight:600}
.rbtns{display:flex;flex-wrap:wrap;gap:8px}
.rb{background:var(--acc);border-color:var(--acc);color:var(--card);padding:6px 14px;font-weight:600}
.rb.ghost{background:var(--card);color:var(--fg);border-color:var(--line);font-weight:400}
.rmsg{font-size:13px;margin:0;overflow-wrap:anywhere;min-width:0}
.rmsg.bad{color:var(--warn)}
.rmsg.good{color:var(--acc)}
.or{font-size:12.5px;color:var(--mut);margin:0 0 6px}
.stopbox{display:grid;gap:12px}
.stoprow{display:flex;flex-wrap:wrap;gap:12px;align-items:center}
#stop{border-color:var(--warn);color:var(--warn);padding:8px 16px;font-size:14px;font-weight:600}
#stop.arm{background:var(--warn);color:var(--card)}
@media (max-width:600px){li{grid-template-columns:minmax(0,1fr) auto}li .nm{grid-column:1/-1}}
</style></head><body><main>
<div class="top"><span class="live" id="state" data-k="on"></span>
<div class="lang" role="group" aria-label="Language"><button data-l="ko">한국어</button><button data-l="en">English</button></div></div>
<div style="display:grid;gap:10px"><h1>Who Was Heard MCP</h1><p class="mut" data-k="lede"></p></div>
<a href="/studio" class="studio"><b data-k="studio_h"></b><span data-k="studio_d"></span></a>
<div class="banner note" id="installing" hidden data-k="installing"></div>
<div class="banner err" id="insterr" hidden><span data-k="insterr"></span> <code id="logpath"></code></div>
<section><h2 data-k="urls"></h2><ul>{{ROWS}}</ul></section>
<section><h2 data-k="connect"></h2><p class="mut small" data-k="connect_d" style="margin:-6px 0 12px"></p><div class="tabs">{{TABS}}</div>{{PANES}}
<p class="mut small" style="margin-top:12px" data-k="cnote"></p></section>
<section class="stopbox"><h2 data-k="stoph" style="margin:0"></h2><p class="mut small" data-k="bg"></p>
<div class="stoprow"><button id="stop" data-k="stop"></button><span class="mut small" id="stopmsg"></span></div></section>
<p class="mut small" id="auto"></p>
</main>
<script>
var T={ko:{on:"켜져 있음",off:"꺼짐",copy:"복사",copied:"복사됨",
lede:"이 PC 안에서만 열리는 주소입니다(127.0.0.1). 같은 와이파이의 다른 기기도, 인터넷도 닿지 않습니다. 서버는 대화에 집계만 돌려주고, 원문은 PC의 내부 검토판에만 남습니다.",
installing:"처음 실행이라 필요한 패키지를 설치하고 있습니다(몇 분). ledger·survey-template은 지금 쓸 수 있고, listen-check의 진단은 설치가 끝나면 됩니다.",
insterr:"패키지 설치가 끝나지 않았습니다. 인터넷 연결을 확인한 뒤 start.py를 실행해 창에 뜨는 내용을 보세요. 기록 파일:",
urls:"서버 주소",connect:"앱에 붙이기 (선택)",connect_d:"Claude·Cursor 같은 AI 앱에서 대화로 쓰고 싶을 때만 합니다. 위 「분석하기」만 쓸 거라면 건너뛰어도 됩니다.",
cnote:"2026년 10월 기준입니다. 앱이 바뀌면 그 앱의 MCP 안내를 따르세요. ChatGPT처럼 인터넷 주소(https)만 받는 앱은 이 PC 안의 주소에 닿지 못합니다. 원문을 밖으로 내보내지 않는다는 원칙에 따른 것입니다.",
stoph:"MCP 서버 끄기",bg:"서버는 창 없이 뒤에서 돕니다. 이 페이지를 닫아도 계속 켜져 있으니, 끌 때는 아래 버튼을 누르세요.",
stop:"MCP 서버 끄기",arm:"한 번 더 누르면 꺼집니다",
stopped:"서버가 꺼졌습니다. 다시 켜려면 start.pyw를 더블클릭하세요(맥은 start.command).",
gone:"서버에 닿지 않습니다. 꺼졌거나 다시 켜는 중입니다.",
studio_h:"분석하기 →",studio_d:"CSV 하나로 1차 실행 → 판단 → 규칙 → 2차·3차 … 를 이 PC의 브라우저에서 돌립니다. AI 앱 없이도 됩니다.",
manual_only:"LibreChat은 설치 방식(Docker·직접 설치)마다 설정 파일 위치가 달라 자동 등록 대신 아래 설정을 librechat.yaml에 복사해 붙여 넣습니다.",
reg:"등록",reg2:"다시 등록",unreg:"등록 취소",or:"또는 아래 설정을 복사해 붙여 넣으세요.",
r_yes:"등록돼 있습니다",r_no:"아직 등록 안 됨",r_none:"이 PC에서 앱을 찾지 못했습니다",r_bad:"설정 파일을 자동으로 읽지 못합니다 — 복사해 붙여 주세요",r_busy:"처리 중…",bak:"원래 파일 백업:",
auto_tz:"이 PC의 지역 설정(%s)에 맞춰 한국어로 표시했습니다.",auto_os:"이 PC의 언어 설정에 맞춰 한국어로 표시했습니다.",auto_br:"브라우저 언어에 맞춰 한국어로 표시했습니다.",picked:"직접 고른 언어입니다."},
en:{on:"Running",off:"Stopped",copy:"Copy",copied:"Copied",
lede:"This address opens only on this computer (127.0.0.1) — not from other devices on your network, not from the internet. The servers return aggregates only; raw texts stay in the internal report on this computer.",
installing:"First run: installing dependencies (a few minutes). ledger and survey-template work now; listen-check's diagnose works once installation finishes.",
insterr:"Installation did not finish. Check your internet connection, then run start.py to see the details in a window. Log file:",
urls:"Server URLs",connect:"Connect an app (optional)",connect_d:"Only if you want to use the tools by chatting in an AI app such as Claude or Cursor. Skip this if you only use Analyze above.",
cnote:"As of October 2026. If an app changes, follow its own MCP guide. Apps that only accept a public https URL, such as ChatGPT, cannot reach an address on this computer — by design, so raw texts never leave it.",
stoph:"Stop the MCP servers",bg:"The servers run in the background with no window. They keep running after you close this page; use the button below to stop them.",
stop:"Stop MCP servers",arm:"Click again to stop",
stopped:"The servers are stopped. To start them again, double-click start.pyw (start.command on macOS).",
gone:"Can't reach the servers. They are stopped or restarting.",
studio_h:"Analyze →",studio_d:"Run round 1 → review → rules → round 2, 3 … from a single CSV, in this computer's browser. No AI app needed.",
manual_only:"LibreChat keeps its settings in a different place depending on how it was installed (Docker or direct), so copy the settings below into librechat.yaml instead of using a button.",
reg:"Register",reg2:"Register again",unreg:"Unregister",or:"Or copy and paste the settings below.",
r_yes:"Registered",r_no:"Not registered yet",r_none:"This app was not found on this computer",r_bad:"Can't read the settings file automatically — please copy and paste",r_busy:"Working…",bak:"Backup of the original file:",
auto_tz:"Shown in English based on this computer's region (%s).",auto_os:"Shown in English based on this computer's language setting.",auto_br:"Shown in English based on your browser language.",picked:"Language chosen by you."}};
var OSLANG="{{OSLANG}}",lang,why,arg="",stopped=false;
function store(k,v){try{if(v===undefined)return localStorage.getItem(k);localStorage.setItem(k,v)}catch(e){return null}}
function detect(){var s=store("wwh-lang");if(s==="ko"||s==="en"){why="picked";return s}
 var tz="";try{tz=Intl.DateTimeFormat().resolvedOptions().timeZone||""}catch(e){}
 if(tz){arg=tz;why="auto_tz";return /^Asia\\/(Seoul|Pyongyang)$/.test(tz)?"ko":(OSLANG==="ko"?(why="auto_os","ko"):"en")}
 if(OSLANG){why="auto_os";return OSLANG}
 var L=(navigator.languages||[navigator.language||""]);why="auto_br";return L.some(function(x){return /^ko/i.test(x)})?"ko":"en"}
function apply(l){lang=l;document.documentElement.lang=l;
 document.querySelectorAll("[data-k]").forEach(function(e){var k=e.dataset.k;if(k==="on"&&stopped)k="off";if(e.id==="stop"&&e.classList.contains("arm"))k="arm";e.textContent=T[l][k]});
 document.querySelectorAll(".lang button").forEach(function(b){b.classList.toggle("on",b.dataset.l===l)});
 document.getElementById("auto").textContent=T[l][why].replace("%s",arg);
 if(stopped)document.getElementById("stopmsg").textContent=T[l].stopped}
document.querySelectorAll(".lang button").forEach(function(b){b.onclick=function(){store("wwh-lang",b.dataset.l);why="picked";apply(b.dataset.l)}});
function sel(el){var r=document.createRange();r.selectNodeContents(el);var s=getSelection();s.removeAllRanges();s.addRange(r)}
document.querySelectorAll(".cp").forEach(function(b){b.onclick=function(){var el=document.getElementById(b.dataset.t);
 var done=function(){b.textContent=T[lang].copied;setTimeout(function(){b.textContent=T[lang].copy},1200)};
 if(navigator.clipboard){navigator.clipboard.writeText(el.textContent).then(done,function(){sel(el)})}else sel(el)}});
document.querySelectorAll(".tab").forEach(function(b){b.onclick=function(){
 document.querySelectorAll(".tab").forEach(function(x){x.classList.toggle("on",x===b)});
 document.querySelectorAll(".pane").forEach(function(p){p.hidden=p.dataset.i!==b.dataset.i})}});
function setOff(msg){stopped=true;setTimeout(renderApps,0);var s=document.getElementById("state");s.classList.add("off");s.textContent=T[lang].off;
 var b=document.getElementById("stop");b.disabled=true;b.classList.remove("arm");b.textContent=T[lang].stop;
 document.getElementById("stopmsg").textContent=T[lang][msg]}
var stopBtn=document.getElementById("stop"),armT;
stopBtn.onclick=function(){if(!stopBtn.classList.contains("arm")){stopBtn.classList.add("arm");stopBtn.textContent=T[lang].arm;
  armT=setTimeout(function(){stopBtn.classList.remove("arm");stopBtn.textContent=T[lang].stop},4000);return}
 clearTimeout(armT);fetch("/stop",{method:"POST",body:"{{TOKEN}}"}).then(function(){setOff("stopped")},function(){setOff("stopped")})};
function poll(){if(stopped)return;fetch("/health",{cache:"no-store"}).then(function(r){return r.json()}).then(function(h){
 var s=document.getElementById("state");s.classList.remove("off");s.textContent=T[lang].on;document.getElementById("stopmsg").textContent="";
 document.getElementById("installing").hidden=!h.installing;
 var e=document.getElementById("insterr");e.hidden=!h.install_error;if(h.install_log)document.getElementById("logpath").textContent=h.install_log;
 setTimeout(poll,h.installing?3000:15000)},function(){if(!stopped){var s=document.getElementById("state");s.classList.add("off");s.textContent=T[lang].off;
 document.getElementById("stopmsg").textContent=T[lang].gone;setTimeout(poll,5000)}})}
var APPS={},lastMsg={};
function renderApps(){document.querySelectorAll(".reg").forEach(function(r){var a=APPS[r.dataset.app];if(!a)return;
 var st=r.querySelector(".rs"),rb=r.querySelector('[data-act=register]'),ub=r.querySelector('[data-act=unregister]');
 var k=a.unreadable?"r_bad":(!a.found?"r_none":(a.registered?"r_yes":"r_no"));
 st.textContent=T[lang][k];st.classList.toggle("yes",!!a.registered);
 rb.disabled=stopped||!a.found||!!a.unreadable;rb.textContent=T[lang][a.registered?"reg2":"reg"];ub.hidden=!a.registered;ub.disabled=stopped;
 var m=r.querySelector(".rmsg"),L=lastMsg[r.dataset.app];
 if(L){m.hidden=false;m.className="rmsg "+(L.ok?"good":"bad");m.textContent=(lang==="ko"?L.message_ko:L.message_en)+(L.backup?"  "+T[lang].bak+" "+L.backup:"")}})}
function loadApps(){fetch("/apps",{headers:{"X-WWH-Token":"{{TOKEN}}"},cache:"no-store"}).then(function(r){return r.json()}).then(function(list){
 list.forEach(function(a){APPS[a.app]=a});renderApps()},function(){})}
document.querySelectorAll(".reg .rb").forEach(function(b){b.onclick=function(){var r=b.closest(".reg"),app=r.dataset.app;
 r.querySelector(".rs").textContent=T[lang].r_busy;r.querySelectorAll(".rb").forEach(function(x){x.disabled=true});
 fetch("/apps/"+b.dataset.act,{method:"POST",body:JSON.stringify({app:app,token:"{{TOKEN}}"})}).then(function(x){return x.json()}).then(function(res){
  lastMsg[app]=res;loadApps()},function(){lastMsg[app]={ok:false,message_ko:"서버에 닿지 않습니다.",message_en:"Can't reach the server."};renderApps()})}});
var _apply=apply;apply=function(l){_apply(l);renderApps()};
apply(detect());poll();loadApps();
</script></body></html>"""


def studio_page(token):
    with open(os.path.join(HERE, "studio.html"), encoding="utf-8") as f:
        return f.read().replace("{{TOKEN}}", token)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="who-was-heard MCP over local HTTP")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    a = ap.parse_args(argv)
    httpd = make_server(a.port)
    print(f"http://127.0.0.1:{a.port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
