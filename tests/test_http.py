"""로컬 HTTP 방식 — 세 서버가 주소 하나로 답하는지, 바깥 요청을 막는지. Local HTTP transport."""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "servers"))
import http_hub  # noqa: E402


class HTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http_hub.make_server(0, status=lambda: {"installing": True})  # 빈 포트 · any free port
        cls.port = cls.httpd.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def req(self, path, body=None, method=None, headers=None):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        r = urllib.request.Request(self.base + path, data=data, method=method or ("POST" if data is not None else "GET"),
                                   headers=dict({"Content-Type": "application/json",
                                                 "Accept": "application/json, text/event-stream"}, **(headers or {})))
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                raw = resp.read()
                return resp.status, dict(resp.headers), raw
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def test_three_servers(self):
        for s in http_hub.SERVERS:
            code, h, raw = self.req(f"/{s}/mcp", {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                                  "params": {"protocolVersion": "2025-06-18"}})
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(raw)["result"]["serverInfo"]["name"], s)
            self.assertTrue(h.get("Mcp-Session-Id"))
            code, _, raw = self.req(f"/{s}/mcp", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            self.assertTrue(len(json.loads(raw)["result"]["tools"]) >= 3)

    def test_notification_202(self):
        code, _, raw = self.req("/ledger/mcp", {"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(code, 202)
        self.assertEqual(raw, b"")

    def test_tool_call_and_batch(self):
        code, _, raw = self.req("/ledger/mcp", [
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "fact_check", "arguments": {"text": "According to all media, 77% disagree."}}}])
        out = json.loads(raw)
        self.assertEqual(len(out), 2)
        self.assertIn("77%", out[1]["result"]["content"][0]["text"])

    def test_refuses_outside(self):
        code, _, _ = self.req("/ledger/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                              headers={"Origin": "https://evil.example"})
        self.assertEqual(code, 403)
        code, _, _ = self.req("/ledger/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                              headers={"Host": "evil.example"})
        self.assertEqual(code, 403)
        code, _, _ = self.req("/stop", b"wrong-token")
        self.assertEqual(code, 403)

    def test_get_and_page(self):
        code, h, _ = self.req("/listen-check/mcp")
        self.assertEqual(code, 405)
        code, _, raw = self.req("/", headers={"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(code, 200)
        page = raw.decode("utf-8")
        for s in http_hub.SERVERS:
            self.assertIn(f"{self.base}/{s}/mcp", page)
        self.assertIn("Cursor", page)
        self.assertIn("LibreChat", page)
        self.assertIn("host.docker.internal", page)
        self.assertIn("한국어", page)
        self.assertIn("Stop MCP servers", page)        # 영문판 문구 · English strings
        self.assertIn("MCP 서버 끄기", page)
        self.assertIn("timeZone", page)                 # 지역으로 언어 고르기 · locale detection
        code, _, raw = self.req("/health")
        self.assertTrue(json.loads(raw)["installing"])

    def test_docker_host_name_allowed(self):
        code, _, _ = self.req("/ledger/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                              headers={"Host": f"host.docker.internal:{self.port}"})
        self.assertEqual(code, 200)

    def test_bound_to_loopback(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
