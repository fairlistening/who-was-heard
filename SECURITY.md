# 보안 문제 알리기 · Security

이 도구는 분석자의 PC 안(`127.0.0.1`)에서만 열리는 서버와 MCP 서버를 띄웁니다. 그 경계를 넘는 문제를 찾으셨다면 **공개 Issues가 아니라 비공개로** 알려 주세요.

- 저장소 위 **Security → Report a vulnerability** (비공개 제보)
- 무엇을, 어떤 환경(운영체제·실행 방법·버전)에서, 어떻게 재현했는지 적어 주세요
- 분석한 자료의 원문이나 API 키는 보내지 마세요

이런 것이 보안 문제입니다 — 다른 기기나 다른 웹사이트에서 이 PC의 서버에 닿는 경우, 원문이나 내부 검토판이 밖으로 나가는 경우, 작업 폴더 밖의 파일을 읽거나 쓸 수 있는 경우, 앱 등록이 다른 앱의 설정을 망가뜨리는 경우.

보존판이라 정해진 응답 기한은 없지만, 확인되면 고치고 [정정기록](CORRECTIONS.md)에 남깁니다.

---

This tool runs servers that listen only on this computer (`127.0.0.1`). If you find a way past that boundary, please report it **privately, not in public Issues**: use **Security → Report a vulnerability** on this repository, describe what, where (OS, how you run it, version) and how to reproduce, and never send raw texts from your data or API keys.

Examples: reaching the local server from another device or website; raw texts or internal reports leaving the computer; reading or writing files outside the work folder; app registration damaging another app's settings. This is an archival release with no fixed response time; confirmed issues are fixed and logged in [CORRECTIONS.md](CORRECTIONS.md).
