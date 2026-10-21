# 원칙 · Principles

> 이 도구는 AI 의견 지도를 얼마나 믿을 수 있는지까지만 말한다. 무엇을 뜻하는지는 말하지 않는다.
> *It tells you how far to trust an AI opinion map — not what it means.*

공론을 모으는 일에 AI를 쓸 때, 기계가 그은 선은 사람이 고른 설정에 따라 크게 흔들린다. 이 도구는 그 흔들림을 숨기지 않고, 판단에 필요한 재료를 사람에게 넘기도록 설계했다. 아래 원칙은 「유튜브 부족주의」 취재에서 실제로 잰 문제에서 나왔다.

When AI is used to gather public discourse, the lines the machine draws move a lot with choices people make. This tool is designed not to hide that, and to hand the judgment — with its evidence — back to people. Each principle below comes from a problem actually measured while reporting.

| | 원칙 | Principle | 왜 · Why |
|---|---|---|---|
| ⓪ | 지도를 얼마나 믿을 수 있는지까지만 말한다. 무엇을 쓸지는 사람이 정한다. 판단에 필요한 재료는 빠짐없이 낸다. | Say how far to trust the map, not what it means. Hand over all the evidence. | 기존 도구는 이름·요지·개요까지 붙여 완성된 결론처럼 보인다. 그중 상당 부분은 모델과 코드가 정한 것이다. |
| ① | 어느 주제에도 안 묶인 몫을 숨기지 않는다. | Never hide what was not clustered. | k-means 방식은 모든 글을 반드시 어딘가에 넣는다. 「모르겠다」고 답할 수 없다. |
| ② | 흔들림을 같이 낸다. | Report instability. | 같은 자료에서 무작위 출발점만 바꿔도 묶음 수가 6·5·2개로 달라졌다. 모델을 바꾸면 결과끼리 일치도(ARI)가 0.1대까지 떨어졌다. |
| ③ | 누가 빠졌는지 낸다. | Report who dropped out. | 의견 추출 단계에서 한 진영의 글이 다른 진영보다 1.7~2.0배 더 많이 버려졌다. 길이로 설명되지 않았다. |
| ④ | 규모 맞춤판과 원래 비율판을 둘 다 낸다. | Show both equal-sample and original-proportion views. | 진영 규모가 15:1로 차이 나는 자료를 그대로 넣으면 모든 묶음이 큰 쪽 차지가 된다. |
| ⑤ | 소수가 판을 채우는지 잰다. | Measure whether a few people fill the room. | 상위 1%가 글의 24.9~40.5%를 썼고, 한 사례에서는 상위 10명이 절반을 썼다. |
| ⑥ | 주제 수를 코드가 몰래 정하지 않는다. | No hidden cap on the number of topics. | 한 공개 도구는 의견이 1,158건을 넘으면 상위 묶음을 무조건 10개로 정한다. |
| ⑦ | 원문은 밖으로 나가지 않게 한다. 공인의 공개 발언만 예외. | Raw text does not leave the analyst's machine — except public officials' on-record statements. | 화면에 안 띄웠지만 파일 데이터에 문장 1만여 개가 실려 나간 일이 있었다. 분석자가 원문을 못 보게 막는 게 아니라, 밖으로 못 나가게 막는다. |
| ⑧ | 규칙은 결과를 보고 사람이 정한다. 여러 사람이 따로 판단해 일치도를 잰다. 차수에는 제한이 없다. | Rules are set by people after seeing results; several reviewers judge independently and agreement is measured; any number of rounds. | 무엇이 「공론이 아닌가」를 결과를 보기 전에 정하면 판단이 숨는다. 우리 채점도 3·4차까지 갔고, 여러 사람이 따로 채점해 κ를 쟀다. |

## 판단이 숨지 않게 · Keeping judgment visible

판단을 안 한다고 도구가 중립이 되는 건 아니다. 길이 기준, 모델, 규칙 하나하나가 이미 판단이다. 그래서 보고서마다 **「이 결과를 만든 선택」**을 모두 찍는다: 자료, 원문 공개 정책, 규칙 파일 이름·버전·지문(sha256)·패턴 전체, 표본, 임베딩 모델, 차원, 묶기 설정, 무작위 출발점, 차수 사슬, 채점자와 일치도.

Refusing to interpret does not make a tool neutral — every default is a choice. So every report prints all the choices that produced it.
