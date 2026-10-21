# 사전등록 틀 · Pre-registration template

결과를 보기 전에 쓴다. 다 쓴 뒤 날짜를 적고 고치지 않는다. 결과를 본 뒤 더한 분석은 「사후 추가」로 따로 밝힌다.
Write this before seeing results. Date it and do not edit it afterwards. Anything added after seeing results is labelled "post hoc".

---

**작성일 · Date:**
**작성자 · Author:**

## 0. 왜 하는가 · Why

무엇을 알고 싶은가. 이 분석이 아니면 무엇을 구분할 수 없는가.

## 1. 가설 · Hypotheses

| | 내용 | 기각되면 무엇을 쓰나 · If rejected |
|---|---|---|
| H1 | | |
| H2 | | |

기각되는 결과도 보고한다. Rejected hypotheses are reported too.

## 2. 자료 — 실행 전 고정 · Data (fixed before running)

| | 값 |
|---|---|
| 출처 · Source | |
| 기간 · Period | |
| 단위 · Unit (글·발언·사람) | |
| 집단 열 · Group column | |
| 원문 공개 정책 · Text policy | private / public — 이유 |
| 쓰지 않는 것 · Not used | |

## 3. 절차 — 실행 전 고정 · Procedure (fixed)

1. 규칙 파일 · Preset: (1차는 none 권장)
2. 표본 · Sample: 집단마다 최대 ___건, 출발점 번호 ___
3. 임베딩 모델 · Embedding model:
4. 묶기 · Clustering: 차원 ___, 최소 묶음 ___
5. 무작위 출발점 · Random starts: ___가지
6. 채점자 · Reviewers: ___명, 합의 기준 majority / all

## 4. 판정 규칙 — 결과를 보기 전에 · Decision rules (before results)

- 「주제가 섰다」: 예) 무작위 출발점 ___가지 중 ___번 이상 다시 나온 묶음
- 「흔들린다」:
- 「빠졌다」: 예) 집단 간 탈락률 차이가 ___배 이상
- 채점 일치도 기준: 예) κ ≥ 0.6이면 합의로 규칙에 넣음, 미만이면 다시 채점

## 5. 쓰지 않을 것 · What we will not claim

- 기계가 붙인 특징어를 주제 이름으로 쓰지 않는다.
- 분모가 다른 값을 한 표에 넣지 않는다.
- (자료에 맞게 더한다)

## 6. 한계 · Limitations

## 7. 실행 기록 · Run log

| 차수 | 날짜 | 규칙 파일(지문) | 채점자·κ | 보고서 |
|---|---|---|---|---|
| 1 | | none | | |
