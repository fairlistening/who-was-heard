# -*- coding: utf-8 -*-
"""윈도에서 더블클릭 — 검은 창 없이 MCP 서버를 뒤에서 켜고 안내 페이지를 연다.
Double-click on Windows: starts the MCP servers in the background (no console) and opens the setup page.
끄기는 안내 페이지의 「MCP 서버 끄기」 버튼. Stop with the button on the setup page.
기록 · log: _logs/start.log"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import start  # noqa: E402

if __name__ == "__main__":
    try:
        start.main([a for a in sys.argv[1:] if a != "--background"])
    except Exception as e:  # 창이 없으니 기록에만 남긴다
        start._log("오류 · error:", repr(e))
