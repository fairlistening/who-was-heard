# 앱에 붙이기 · Connecting an app

## 1. 켜기 · Start

| | 한국어 | English |
|---|---|---|
| 윈도 · Windows | **`start.pyw` 더블클릭** — 검은 창 없이 뒤에서 켜진다 | double-click **`start.pyw`** — runs in the background, no console |
| 맥 · macOS | **`start.command` 더블클릭** — 뒤에서 켜진다. 터미널 창은 닫아도 된다 | double-click **`start.command`**; you may close the Terminal window |
| 문제를 찾을 때 · troubleshooting | `python start.py` — 창에 기록을 보며 돈다 | `python start.py` shows the log in a window |

켜지면 브라우저에 안내 페이지가 열린다. 주소와 앱별 설정을 거기서 복사한다. **끄기는 안내 페이지의 「MCP 서버 끄기」 버튼**이다(두 번 눌러 확인). 페이지를 닫아도 서버는 계속 돈다. 다시 열려면 `start.pyw`를 한 번 더 누르면 된다 — 이미 켜져 있으면 페이지만 연다.

A setup page opens in the browser. **Stop with the "Stop MCP servers" button** on that page (click twice to confirm); closing the page leaves the servers running. Double-clicking `start.pyw` again just reopens the page.

- **언어 · Language** — 이 PC의 지역 설정(시간대)과 언어 설정을 보고 한국어·영어를 고른다. 위치 정보는 묻지 않는다. 오른쪽 위 「한국어 / English」로 바꿀 수 있고, 고른 언어는 이 브라우저에 기억된다. · Chosen from this computer's region (time zone) and language settings — no location permission is requested. Switch with the 한국어 / English buttons; the choice is remembered in this browser.
- **처음 실행 · First run** — 필요한 패키지를 창 없이 뒤에서 설치한다(몇 분). 그동안 안내 페이지에 표시가 뜨고, ledger·survey-template은 바로 쓸 수 있다. 기록은 `_logs/`에 남는다. · Dependencies install in the background; the page shows progress, and ledger/survey-template work immediately. Logs go to `_logs/`.

```
http://127.0.0.1:8730/                     안내 페이지 · setup page
http://127.0.0.1:8730/listen-check/mcp     공론 지도·진단 · discourse map & diagnostics
http://127.0.0.1:8730/ledger/mcp           초고 수치·금지 문장 검사 · fact & phrase checker
http://127.0.0.1:8730/survey-template/mcp  서베이 조회 틀 · survey lookups
```

- **이 PC 안에서만 열립니다** (127.0.0.1). 같은 와이파이의 다른 기기도, 인터넷도 닿지 않습니다. 다른 사이트가 브라우저를 거쳐 부르는 요청은 Host·Origin 검사로 거절합니다. · Bound to 127.0.0.1 only; requests from other sites via the browser are refused (Host/Origin checks).
- 서버는 대화에 **집계만** 돌려줍니다. 원문은 PC의 내부 검토판에만 남습니다. · Servers return aggregates only.
- 8730번이 이미 쓰이고 있으면 8731… 순으로 켜고 안내 페이지에 그 주소가 나옵니다. 그때는 앱 설정의 포트도 바꾸세요. · If 8730 is busy, the next free port is used.

## 2. 버튼으로 등록 · Register with one click

안내 페이지 「앱에 붙이기」의 탭마다 **「등록」 버튼**이 있다. 누르면 그 앱의 설정 파일에 세 서버를 넣는다. 그다음 앱을 완전히 껐다 켜면 된다. 「등록 취소」로 되돌린다.
Each app tab on the setup page has a **Register** button that adds the three servers to that app's settings; restart the app afterwards. **Unregister** reverses it.

- 쓰기 전에 원래 설정 파일을 같은 폴더에 백업한다(`*.backup_날짜_시각`). · The original file is backed up first.
- 우리 서버 셋만 넣고 뺀다. 다른 서버는 그대로 둔다. 같은 이름의 다른 서버가 있으면 덮어쓰지 않고 멈춘다. · Only our three entries are touched; a different server with the same name is never overwritten.
- 앱의 설정 폴더가 없으면(앱이 없으면) 아무것도 만들지 않는다. 주석이 든 설정 파일처럼 안전하게 읽지 못하면 고치지 않고 복사-붙여넣기를 안내한다. · Nothing is created if the app isn't installed; files we can't parse safely (e.g. with comments) are left alone.
- 버튼은 이 PC의 안내 페이지에서만 작동한다(페이지마다 다른 확인값). · Buttons work only from the local setup page (per-page token).
- Claude 데스크톱은 stdio로, Claude Code는 `claude mcp add --scope user`로, Codex는 `config.toml`에 표식 블록으로 넣는다. · Claude Desktop is registered over stdio, Claude Code via its CLI, Codex as a marked block in config.toml.
- 명령줄로도 된다 · CLI: `python servers/app_register.py register cursor` (`status` · `unregister`)

| 앱 · App | 설정 파일 · Settings file (Windows / macOS) |
|---|---|
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` · `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Code | `claude mcp add --scope user` |
| Cursor | `~/.cursor/mcp.json` |
| VS Code | `%APPDATA%\Code\User\mcp.json` · `~/Library/Application Support/Code/User/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| Gemini CLI | `~/.gemini/settings.json` |
| Codex CLI | `~/.codex/config.toml` |
| LM Studio | `~/.lmstudio/mcp.json` |

## 3. 직접 붙이기 · Per-app settings by hand (2026-10)

앱 쪽 설정 방식은 바뀔 수 있습니다. 안 되면 그 앱의 MCP 안내를 따르세요. 안내 페이지에는 지금 켜진 포트로 바뀐 설정이 고른 언어로 나옵니다.
Client settings change over time; follow each app's MCP documentation if these stop working. The setup page shows these with the actual port.

### Claude Code

`터미널에서 · In a terminal`

```bash
claude mcp add --transport http listen-check http://127.0.0.1:8730/listen-check/mcp
claude mcp add --transport http ledger http://127.0.0.1:8730/ledger/mcp
claude mcp add --transport http survey-template http://127.0.0.1:8730/survey-template/mcp

# Diagnose can take minutes on large tables; the setting below waits up to 30 minutes.
# environment variable MCP_TOOL_TIMEOUT=1800000
```

### Cursor

`~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "listen-check": {
      "url": "http://127.0.0.1:8730/listen-check/mcp"
    },
    "ledger": {
      "url": "http://127.0.0.1:8730/ledger/mcp"
    },
    "survey-template": {
      "url": "http://127.0.0.1:8730/survey-template/mcp"
    }
  }
}
```

### VS Code

`.vscode/mcp.json`

```json
{
  "servers": {
    "listen-check": {
      "url": "http://127.0.0.1:8730/listen-check/mcp",
      "type": "http"
    },
    "ledger": {
      "url": "http://127.0.0.1:8730/ledger/mcp",
      "type": "http"
    },
    "survey-template": {
      "url": "http://127.0.0.1:8730/survey-template/mcp",
      "type": "http"
    }
  }
}
```

### Windsurf

`~/.codeium/windsurf/mcp_config.json`

```json
{
  "mcpServers": {
    "listen-check": {
      "serverUrl": "http://127.0.0.1:8730/listen-check/mcp"
    },
    "ledger": {
      "serverUrl": "http://127.0.0.1:8730/ledger/mcp"
    },
    "survey-template": {
      "serverUrl": "http://127.0.0.1:8730/survey-template/mcp"
    }
  }
}
```

### Gemini CLI

`~/.gemini/settings.json`

```json
{
  "mcpServers": {
    "listen-check": {
      "httpUrl": "http://127.0.0.1:8730/listen-check/mcp",
      "timeout": 1800000
    },
    "ledger": {
      "httpUrl": "http://127.0.0.1:8730/ledger/mcp",
      "timeout": 1800000
    },
    "survey-template": {
      "httpUrl": "http://127.0.0.1:8730/survey-template/mcp",
      "timeout": 1800000
    }
  }
}
```

### Codex CLI

`~/.codex/config.toml`

```toml
# Diagnose can take minutes on large tables; the setting below waits up to 30 minutes.

[mcp_servers.listen-check]
url = "http://127.0.0.1:8730/listen-check/mcp"
tool_timeout_sec = 1800

[mcp_servers.ledger]
url = "http://127.0.0.1:8730/ledger/mcp"

[mcp_servers.survey-template]
url = "http://127.0.0.1:8730/survey-template/mcp"
```

### LM Studio

`mcp.json (Program → Edit mcp.json)`

```json
{
  "mcpServers": {
    "listen-check": {
      "url": "http://127.0.0.1:8730/listen-check/mcp"
    },
    "ledger": {
      "url": "http://127.0.0.1:8730/ledger/mcp"
    },
    "survey-template": {
      "url": "http://127.0.0.1:8730/survey-template/mcp"
    }
  }
}
```

### LibreChat

`librechat.yaml` — `mcpServers`

```yaml
# For LibreChat running in Docker (the usual install).
# For a direct (npm) install, replace host.docker.internal with 127.0.0.1. Restart LibreChat after saving.
mcpServers:
  listen-check:
    type: streamable-http
    url: http://host.docker.internal:8730/listen-check/mcp
    timeout: 1800000
  ledger:
    type: streamable-http
    url: http://host.docker.internal:8730/ledger/mcp
  survey-template:
    type: streamable-http
    url: http://host.docker.internal:8730/survey-template/mcp
```

LibreChat은 Docker로 돌리는 경우가 많아 `host.docker.internal`로 적었다. 이 서버는 그 이름으로 오는 요청도 받는다. 설치 위치마다 설정 파일이 달라 「등록」 버튼은 없다. · Written for Docker installs; the server accepts the `host.docker.internal` host name. No Register button, because the settings file location varies.

### Claude Desktop

`HTTP 대신 stdio로 등록 · Registered over stdio instead of HTTP`

```bash
python install.py --mcp

# Claude Desktop does not attach local HTTP URLs.
# This registers the same servers over stdio; the tools are identical.
```

### ChatGPT 등 인터넷 주소만 받는 앱 · Apps that only accept public URLs

인터넷에 열린 https 주소만 받는 앱은 이 PC 안의 주소에 닿지 못합니다. 서버를 인터넷에 여는 방법은 일부러 넣지 않았습니다. 원문을 PC 밖으로 내보내지 않는다는 원칙 때문입니다.
Apps that only accept a public https URL cannot reach a local server. Exposing these servers to the internet is deliberately not supported: raw text stays on the analyst's machine.

## 4. stdio로 쓰기 · Using stdio

앱이 서버를 직접 띄우는 방식(stdio)도 그대로 됩니다. Claude 데스크톱은 `python install.py --mcp`가 등록합니다. 다른 앱은 명령을 `python`, 인자를 `servers/<이름>/server.py`의 절대 경로로 적습니다.
Every server also runs over stdio: command `python`, argument the absolute path of `servers/<name>/server.py`.

## 5. 구현 · Implementation

MCP Streamable HTTP의 JSON 응답 방식만 씁니다(POST 한 번에 응답 하나, 일괄 요청 지원). 서버가 먼저 보내는 스트림(SSE)은 열지 않습니다(GET은 405). 세션은 `Mcp-Session-Id`를 주지만 저장하지 않습니다. 표준 라이브러리만 씁니다. 공식 MCP 파이썬 SDK 클라이언트로 세 서버의 initialize · tools/list · tools/call을 확인했습니다.
Uses the JSON-response mode of MCP Streamable HTTP (no server-initiated SSE; GET returns 405). Standard library only. Verified against the official MCP Python SDK client.
