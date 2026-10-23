# 정정기록 · Corrections and changes

고친 것과 이유를 여기에 남긴다. 수치나 판단을 바꾼 경우 무엇이 왜 바뀌었는지 적는다.
Record every correction and why. When a figure or a judgment changes, say what changed and why.

## 0.1.0 — 2026-10 (보존판 · archival release)

- 첫 공개판. First public release.
- 묶기는 5차원 UMAP 공간, 지도는 2차원 — 2차원 위에서 묶던 시안에서 바꿈.
  Clustering moved from the 2-D map to a 5-D UMAP space; 2-D is for drawing only.
- 정리 규칙을 코드에서 규칙 파일(presets/)로 분리.
  Cleaning rules moved out of code into readable preset files.
- 파이썬 없이 도는 설치판(윈도·맥) — `packaging/`과 깃허브 자동 빌드(`.github/workflows/build.yml`)로 만들어 Releases에 붙인다.
  Python-free builds for Windows and macOS, built by GitHub Actions and attached to Releases.
