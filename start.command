#!/bin/bash
# 맥에서 더블클릭 — 서버를 뒤에서 켜고 안내 페이지를 연다. 이 터미널 창은 닫아도 된다.
# Double-click on macOS: starts the servers in the background and opens the setup page. You can close this window.
cd "$(dirname "$0")" || exit 1
python3 start.py --background "$@"
