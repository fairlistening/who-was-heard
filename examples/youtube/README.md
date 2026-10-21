# 예시 — 유튜브 댓글 · YouTube comments

유튜브 댓글은 일반인의 글이고, 유튜브 약관상 받은 자료를 다시 배포할 수 없다. 그래서 이 예시는 **자료 없이 받는 스크립트만** 둔다. 각자 자기 API 키로 받아 자기 PC에서만 쓴다. 이 도구가 원래 겨냥한 쓰임새다.

YouTube comments are written by ordinary people and may not be redistributed. This example ships only a fetch script; run it with your own key and keep the data on your machine.

```bash
export YOUTUBE_API_KEY=...                       # 자기 키 · your own key
python fetch_youtube_comments.py videos.csv comments.csv
who-was-heard report comments.csv --text text --group group --speaker author --out run --name r1
```

- 작성자 채널 ID는 받는 즉시 이 PC에만 있는 비밀값으로 해시한다. `_salt.txt`는 공유하지 않는다(.gitignore에 들어 있다).
- 보고서는 기본값 `text_policy=private` — 공개판에 댓글이 한 줄도 들어가지 않는다. 표본은 내부 검토판에서만 읽는다.
- 생방송 실시간 채팅은 방송이 끝나면 공식 API로 받을 수 없다.
