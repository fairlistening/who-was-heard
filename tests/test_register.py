"""앱 자동 등록 — 백업, 다른 서버 보존, 같은 이름 충돌, 주석 든 파일 거절. App registration."""
import glob
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "servers"))
import app_register as R  # noqa: E402
import http_hub  # noqa: E402

BASE = "http://127.0.0.1:8730"


def rd(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def rj(path):
    return json.loads(rd(path))


class Register(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.environ["WWH_TEST_HOME"] = self.home

    def tearDown(self):
        os.environ.pop("WWH_TEST_HOME", None)
        shutil.rmtree(self.home, ignore_errors=True)

    def mk(self, *parts, content=None):
        path = os.path.join(self.home, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if content is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content if isinstance(content, str) else json.dumps(content))
        return path

    def test_app_missing(self):
        r = R.register("cursor", BASE)
        self.assertFalse(r["ok"])
        self.assertFalse(os.path.exists(os.path.join(self.home, ".cursor")))  # 폴더를 만들지 않는다

    def test_roundtrip_keeps_others_and_backs_up(self):
        p = self.mk(".cursor", "mcp.json", content={"mcpServers": {"other": {"url": "http://x/mcp"}}, "keep": 1})
        r = R.register("cursor", BASE)
        self.assertTrue(r["ok"], r)
        cfg = rj(p)
        self.assertEqual(cfg["mcpServers"]["other"], {"url": "http://x/mcp"})
        self.assertEqual(cfg["keep"], 1)
        self.assertEqual(cfg["mcpServers"]["ledger"]["url"], BASE + "/ledger/mcp")
        self.assertTrue(r["backup"] and os.path.exists(r["backup"]))
        self.assertTrue(R.status("cursor")["registered"])
        r = R.unregister("cursor")
        self.assertTrue(r["ok"])
        cfg = rj(p)
        self.assertEqual(set(cfg["mcpServers"]), {"other"})
        self.assertFalse(R.status("cursor")["registered"])

    def test_register_twice_is_idempotent(self):
        p = self.mk(".cursor", "mcp.json", content={})
        R.register("cursor", BASE)
        R.register("cursor", "http://127.0.0.1:8731")
        cfg = rj(p)
        self.assertEqual(cfg["mcpServers"]["ledger"]["url"], "http://127.0.0.1:8731/ledger/mcp")

    def test_name_clash_not_overwritten(self):
        p = self.mk(".cursor", "mcp.json", content={"mcpServers": {"ledger": {"url": "https://someone-else/mcp"}}})
        r = R.register("cursor", BASE)
        self.assertFalse(r["ok"])
        self.assertEqual(rj(p)["mcpServers"]["ledger"]["url"], "https://someone-else/mcp")
        self.assertEqual(glob.glob(p + ".backup_*"), [])
        R.unregister("cursor")  # 남의 ledger는 지우지 않는다
        self.assertIn("ledger", rj(p)["mcpServers"])

    def test_jsonc_refused(self):
        p = self.mk(".gemini", "settings.json", content='{\n  // comment\n  "theme": "x"\n}')
        before = rd(p)
        r = R.register("gemini", BASE)
        self.assertFalse(r["ok"])
        self.assertEqual(rd(p), before)
        self.assertTrue(R.status("gemini").get("unreadable"))

    def test_vscode_and_gemini_shapes(self):
        self.mk("AppData", "Code", "User", "x")  # 폴더만
        self.assertTrue(R.register("vscode", BASE)["ok"])
        v = rj(os.path.join(self.home, "AppData", "Code", "User", "mcp.json"))
        self.assertEqual(v["servers"]["listen-check"], {"type": "http", "url": BASE + "/listen-check/mcp"})
        self.mk(".gemini", "x")
        self.assertTrue(R.register("gemini", BASE)["ok"])
        g = rj(os.path.join(self.home, ".gemini", "settings.json"))
        self.assertEqual(g["mcpServers"]["ledger"]["httpUrl"], BASE + "/ledger/mcp")

    def test_claude_desktop_stdio(self):
        p = self.mk("AppData", "Claude", "claude_desktop_config.json", content={"mcpServers": {"x": {"command": "y"}}})
        self.assertTrue(R.register("claude-desktop", BASE)["ok"])
        e = rj(p)["mcpServers"]["listen-check"]
        self.assertTrue(e["args"][0].replace("\\", "/").endswith("servers/listen-check/server.py"))
        self.assertIn("x", rj(p)["mcpServers"])

    def test_codex_toml_block(self):
        p = self.mk(".codex", "config.toml", content='model = "x"\n\n[mcp_servers.other]\nurl = "http://o"\n')
        self.assertTrue(R.register("codex", BASE)["ok"])
        t = rd(p)
        self.assertIn('[mcp_servers.listen-check]', t)
        self.assertIn("tool_timeout_sec = 1800", t)
        self.assertTrue(R.register("codex", BASE)["ok"])  # 두 번 눌러도 한 벌
        self.assertEqual(rd(p).count("[mcp_servers.ledger]"), 1)
        try:
            import tomllib
            tomllib.loads(rd(p))
        except ImportError:
            pass
        R.unregister("codex")
        t = rd(p)
        self.assertNotIn("who-was-heard", t)
        self.assertIn("[mcp_servers.other]", t)
        self.assertIn('model = "x"', t)


class RegisterOverHTTP(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.environ["WWH_TEST_HOME"] = self.home
        os.makedirs(os.path.join(self.home, ".cursor"))
        self.httpd = http_hub.make_server(0)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        os.environ.pop("WWH_TEST_HOME", None)
        shutil.rmtree(self.home, ignore_errors=True)

    def post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, None

    def test_needs_token(self):
        code, _ = self.post("/apps/register", {"app": "cursor", "token": "nope"})
        self.assertEqual(code, 403)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".cursor", "mcp.json")))

    def test_register_via_page_token(self):
        page = urllib.request.urlopen(self.base + "/").read().decode("utf-8")
        token = re.search(r'token:"([^"]+)"', page).group(1)
        code, res = self.post("/apps/register", {"app": "cursor", "token": token})
        self.assertEqual(code, 200)
        self.assertTrue(res["ok"], res)
        cfg = rj(os.path.join(self.home, ".cursor", "mcp.json"))
        self.assertEqual(cfg["mcpServers"]["ledger"]["url"], self.base + "/ledger/mcp")
        req = urllib.request.Request(self.base + "/apps", headers={"X-WWH-Token": token})
        st = {a["app"]: a for a in json.load(urllib.request.urlopen(req))}
        self.assertTrue(st["cursor"]["registered"])
        self.assertFalse(st["windsurf"]["found"])


if __name__ == "__main__":
    unittest.main()
