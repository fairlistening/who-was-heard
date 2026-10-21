# 예시 — Polis 시민 온라인 토론 · Polis citizen deliberation

**자료**: Polis 공개 데이터 `american-assembly.bowling-green` — 2018년 미국 켄터키주 볼링그린 주민들이 Polis에 직접 쓴 의견 896개와 찬반 투표. 참여자는 숫자 ID로 익명화돼 있다.
**라이선스**: CC BY 4.0 — Data was gathered using the Polis software (compdemocracy.org/polis) and is sub-licensed under CC BY 4.0 with Attribution to The Computational Democracy Project. <https://github.com/compdemocracy/openData>

일반 시민의 글이므로 보고서는 기본값 `text_policy=private`(공개판에 원문 없음)로 돌렸다. 집단은 Polis가 투표로 나눈 **의견 집단**(작성자 기준)이다.

## 재현

```bash
python fetch_polis.py american-assembly.bowling-green bowling-green.csv
who-was-heard report bowling-green.csv --text text --group opinion_group --speaker author_id \
    --drop moderation=rejected --min-chars 20 --preset none --per-group 0 \
    --selection leaf --min-cluster-size 10 --group-order "Group A,Group B,no group" \
    --out run --name r1
```

`report/r1_public.html`이 그 결과다(공개판).

## 이 예시가 보여 주는 것

**1. 사람이 거르는 단계에서 누가 빠졌나.** 운영자가 거부(rejected)한 의견을 지우지 않고 「지정 제외」로 셌다.

| 의견 집단 | 의견 | 운영자가 거부 | 몫 |
|---|---:|---:|---:|
| Group A | 460 | 119 | 25.9% |
| Group B | 334 | 133 | **39.8%** |
| no group | 102 | 37 | 36.3% |

Group B의 의견이 Group A보다 1.5배 많이 걸러졌다. 지도에서 Group B가 덜 보인다면, 덜 말해서가 아니라 덜 담겨서일 수 있다. (거부 사유는 자료에 없다. 중복·주제 이탈 등 정당한 사유일 수 있다 — 이 표는 판단이 아니라 판단 재료다.)

**2. 설정 하나로 지도가 바뀐다.** 같은 606개 의견을 HDBSCAN 기본 설정(`eom`)으로 묶으면 주제가 **2개**(하나가 573개를 삼킨다), 잘게 고르는 설정(`leaf`, 최소 묶음 10)으로 묶으면 **20개**가 나왔다. 이 예시는 뒤쪽을 썼고, 그 선택이 보고서 「선택」 칸에 찍혀 있다.

**3. 흔들림.** 무작위 출발점 다섯 가지에서 주제 수는 매번 20개였지만, 결과끼리 일치도(ARI)는 0.50~0.63(평균 0.57)이었다. 안 묶인 몫은 32.8~38.3%.

주제 이름은 붙이지 않았다 — 공개판의 특징어는 기계가 뽑은 잠정 단어다. 이름은 내부 검토판을 읽고 사람이 붙인다.
