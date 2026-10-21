# 광청AI 공개 코드 읽기 · Reading the kouchou-ai source

광청AI(広聴AI · kouchou-ai)는 일본 디지털민주주의2030이 2025년 3월 공개한 브로드리스닝 도구다. 코드가 AGPL-3.0으로 공개돼 있어 누구나 읽을 수 있다. 이 문서는 **공개 코드에서 확인되는 것만** 적는다. 우리 도구가 왜 다르게 설계됐는지의 배경이다.

kouchou-ai is a broad-listening tool released in March 2025 by Japan's Digital Democracy 2030, under AGPL-3.0. This note records only what can be verified in the public code; it explains why this tool was designed differently.

- 저장소 · Repository: <https://github.com/digitaldemocracy2030/kouchou-ai>
- 읽은 위치 · Files read: `packages/analysis-core/src/analysis_core/steps/` · `specs/hierarchical_specs.json`
- 읽은 날 · Read on: 2026-10-18 (main 브랜치)

## 1. 흐름 · Pipeline

| 단계 | 코드에서 확인되는 것 |
|---|---|
| 의견 추출 · extraction | LLM으로 원문에서 「의견」 문장을 뽑는다 (모델은 설정) |
| 임베딩 · embedding | 기본값 `text-embedding-3-small` (OpenAI) |
| 배치 · layout | UMAP 2차원, `n_neighbors` 기본 15 |
| 묶기 · clustering | **2차원 좌표 위에서** k-means(하위 묶음 수) → 그 중심들을 Ward 계층 병합(상위 묶음 수) |
| 라벨 · labels | LLM이 묶음 이름·요지·전체 개요를 쓴다 |

## 2. 묶음 수에 상한이 있다 · A hard cap on the number of top-level clusters

```python
lv1 = max(2, min(10, round(argument_count ** (1 / 3))))
lv2 = max(2, min(1000, argument_count, lv1 * lv1))
```

세제곱근 규칙에 **상위 묶음 상한 10**이 걸려 있다. 의견이 1,158건을 넘으면 어떤 자료든 상위 묶음은 10개다(2,914건이든 10만 건이든 같다). 사용자가 값을 직접 주면 바꿀 수 있지만, 기본값으로 돌리면 리포트에 이 사실이 드러나지 않는다.

The cube-root rule is capped at 10 top-level clusters: above 1,158 arguments, any dataset gets exactly 10 unless the user overrides it, and the report does not say so.

## 3. 「안 묶임」이 없다 · No "unclustered"

k-means는 모든 점을 반드시 어느 묶음엔가 넣는다. 그래서 「이 글은 어디에도 속하지 않는다」는 답이 구조적으로 나올 수 없다. 파일 첫 줄 주석에는 `UMAP + HDBSCAN`이라고 적혀 있지만, 그 파일이 실제로 불러오는 것은 UMAP·`scipy.cluster.hierarchy`·`KMeans`뿐이다(뿌리인 Talk to the City에서 물려받은 주석으로 보인다).

k-means assigns every point to some cluster, so "belongs nowhere" is impossible by construction. A docstring mentions HDBSCAN, but the file imports only UMAP, scipy's hierarchy and KMeans.

## 4. 2차원 위에서 묶는다 · Clustering on the 2-D map

고차원(1,536차원)을 2차원으로 줄인 그림 위에서 묶는다. 줄이면서 버린 정보로는 다시 묶을 수 없다. 우리 도구는 5차원에서 묶고 2차원은 그림에만 쓴다.

## 5. 이 도구가 다르게 한 것 · What this tool does differently

| 광청AI 기본값 | who-was-heard |
|---|---|
| 상위 묶음 10개 상한 | 상한 없음 — 자료가 정한다 (원칙 ⑥) |
| 안 묶임 없음 | 안 묶인 몫을 회색으로 남기고 집단별로 보고 (①) |
| 한 번 돌린 결과 | 무작위 출발점을 바꿔 여러 번 — 흔들림 보고 (②) |
| LLM이 이름·요지 작성 | 특징어만 기계가, 이름은 사람이 — 채점자 일치도 (⓪ ⑧) |
| 2차원에서 묶기 | 5차원에서 묶고 2차원은 그림만 |

광청AI가 설정과 프롬프트를 공개해 이런 검증을 가능하게 한 점은 높이 살 만하다. 이 문서는 그 공개 덕분에 쓸 수 있었다.

The fact that kouchou-ai publishes its code and settings is what made this reading possible — and deserves credit.
