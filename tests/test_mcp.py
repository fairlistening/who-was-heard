"""MCP 프로토콜 왕복 — 서버 셋이 initialize · tools/list 에 답하는지. Protocol round-trip."""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def talk(server, msgs):
    p = subprocess.run([sys.executable, os.path.join(ROOT, "servers", server, "server.py")],
                       input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True, timeout=120,
                       encoding="utf-8")
    return [json.loads(x) for x in p.stdout.splitlines() if x.strip()]


class MCP(unittest.TestCase):
    def test_servers(self):
        for s in ("listen-check", "ledger", "survey-template"):
            out = talk(s, [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
                           {"jsonrpc": "2.0", "method": "notifications/initialized"},
                           {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}])
            self.assertEqual(out[0]["result"]["serverInfo"]["name"], s)
            self.assertTrue(len(out[1]["result"]["tools"]) >= 3, s)

    def test_ledger_check(self):
        out = talk("ledger", [{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "fact_check", "arguments": {"text": "According to all media, 41.2% agree and 77% disagree."}}}])
        t = out[0]["result"]["content"][0]["text"]
        self.assertIn("all media", t)
        self.assertIn("77%", t)

    def test_survey_cross(self):
        out = talk("survey-template", [{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                        "params": {"name": "survey_cross", "arguments": {"question": "Q1", "options": "Strongly agree", "groups": "All,Camp A"}}}])
        self.assertIn("Camp A", out[0]["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
