# -*- coding: utf-8 -*-
"""MCP 공용 러너 — 모든 서버가 이걸 쓴다. 표준 라이브러리만.
Minimal MCP (JSON-RPC) runner shared by all servers. Standard library only.

 · stdio  — 앱이 server.py를 직접 띄울 때 (Claude 데스크톱 등)
 · http   — start.py가 세 서버를 이 PC 안(127.0.0.1)의 주소 하나로 띄울 때 → http_hub.py
"""
import json
import re
import sys


def _norm_ver(v):
    return v if isinstance(v, str) and re.fullmatch(r"[\d-]{8,12}", v) else "2024-11-05"


def make_handler(server_name, instructions, tools):
    """tools: [{name, description, inputSchema, fn}] · fn(args) -> str
    돌려주는 handle(msg)는 JSON-RPC 메시지 하나를 받아 응답(또는 알림이면 None)을 낸다."""
    by_name = {t["name"]: t for t in tools}
    listed = [{k: t[k] for k in ("name", "description", "inputSchema")} for t in tools]

    def handle(msg):
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": _norm_ver(params.get("protocolVersion")),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": server_name, "version": "0.1.0"},
                "instructions": instructions}}
        if method in ("notifications/initialized", "initialized"):
            return None
        if method == "ping":
            return {"jsonrpc": "2.0", "id": mid, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": mid, "result": {"tools": listed}}
        if method == "tools/call":
            t = by_name.get(params.get("name"))
            if not t:
                return {"jsonrpc": "2.0", "id": mid,
                        "error": {"code": -32601, "message": f"그런 도구가 없습니다 / unknown tool: {params.get('name')}"}}
            try:
                text = t["fn"](params.get("arguments") or {})
            except Exception as e:
                return {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": f"오류 / error: {e}"}], "isError": True}}
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"content": [{"type": "text", "text": str(text)}]}}
        if mid is None:
            return None
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"지원하지 않는 요청 / unsupported: {method}"}}

    def safe(msg):
        if not isinstance(msg, dict):
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request"}}
        try:
            return handle(msg)
        except Exception as e:
            return {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32603, "message": str(e)}}

    return safe


def run(server_name, instructions, tools):
    """stdio로 돈다 — 한 줄에 메시지 하나. Serve over stdio, one message per line."""
    handle = make_handler(server_name, instructions, tools)
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
