"""유튜브 댓글을 각자의 API 키로 받아 CSV로 만든다. 받은 자료는 각자 PC에만 둔다.
Fetch YouTube comments with YOUR OWN API key. Keep the data on your machine.

  set YOUTUBE_API_KEY=...            (Windows)   /   export YOUTUBE_API_KEY=...   (mac·linux)
  python fetch_youtube_comments.py videos.csv comments.csv

videos.csv — 두 열: video_id, group (예: 채널 이름이나 진영)
  video_id,group
  dQw4w9WgXcQ,Channel A

* 유튜브 약관상 받은 댓글을 다시 배포하지 않는다. 이 저장소에도 댓글 자료는 없다.
* 작성자 채널 ID는 받은 즉시 이 PC에서만 쓰는 비밀값(salt)으로 해시한다. 비밀값 파일(_salt.txt)은 공유하지 않는다.
* 일반인 글이므로 보고서는 기본값(text_policy=private, 원문 비공개)으로 돌린다.
* 생방송 실시간 채팅은 방송이 끝나면 이 API로 받을 수 없다. 이 스크립트는 댓글만 받는다.
* 표준 라이브러리만 쓴다. API 할당량(하루 10,000단위)에 주의.

YouTube's terms do not allow redistributing comments; this repository contains none.
Author channel IDs are hashed immediately with a local secret salt (_salt.txt — never share it).
"""
import csv
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.parse
import urllib.request

API = "https://www.googleapis.com/youtube/v3/commentThreads"
HERE = os.path.dirname(os.path.abspath(__file__))
SALT = os.path.join(HERE, "_salt.txt")


def salt():
    if not os.path.exists(SALT):
        with open(SALT, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
    with open(SALT, encoding="utf-8") as f:
        return f.read().strip()


def h(x, s):
    return hashlib.sha256((s + "|" + x).encode()).hexdigest()[:16] if x else ""


def fetch(video_id, key, max_pages=50):
    page, n = None, 0
    while n < max_pages:
        q = {"part": "snippet,replies", "videoId": video_id, "maxResults": 100, "textFormat": "plainText", "key": key}
        if page:
            q["pageToken"] = page
        with urllib.request.urlopen(API + "?" + urllib.parse.urlencode(q), timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
        for it in d.get("items", []):
            top = it["snippet"]["topLevelComment"]["snippet"]
            yield top
            for rep in (it.get("replies") or {}).get("comments", []):
                yield rep["snippet"]
        page = d.get("nextPageToken")
        n += 1
        if not page:
            break
        time.sleep(0.2)


def main(videos_csv, out):
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        sys.exit("YOUTUBE_API_KEY 환경변수에 자기 API 키를 넣으세요 · set YOUTUBE_API_KEY")
    s = salt()
    with open(videos_csv, encoding="utf-8-sig") as f:
        vids = list(csv.DictReader(f))
    n = 0
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["video_id", "group", "author", "published", "likes", "text"])
        for v in vids:
            for c in fetch(v["video_id"], key):
                author = (c.get("authorChannelId") or {}).get("value", "")
                w.writerow([v["video_id"], v["group"], h(author, s), c.get("publishedAt", ""),
                            c.get("likeCount", 0), c.get("textDisplay", "")])
                n += 1
            print(v["video_id"], "done", flush=True)
    print(f"{n:,} comments → {out}  (author IDs hashed with local salt)")


if __name__ == "__main__":
    main(*sys.argv[1:3])
