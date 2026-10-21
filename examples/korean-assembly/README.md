# 예시 — 대한민국 국회 회의록 · Korean National Assembly minutes

국회의원의 회의 발언은 공인의 공개 기록이므로 `text_policy=public`(대표 발언·발언자 이름 공개)으로 쓴다.

## 자료 받기

| 길 | 상태 |
|---|---|
| 국회도서관 「국회회의록 빅데이터」 엑셀 내려받기 → `prepare_nanet.py` | 작동함. 다만 검색으로 받는 묶음이라 **전수가 아니고**, 내려받기 옵션에 따라 무관한 발언이 섞인다. 발언자는 숫자 ID |
| 국회사무처 회의록 OpenAPI (공공데이터포털·열린국회정보, 무료 인증키, 이용허락범위 제한 없음) | 기간을 정해 재현 가능하게 받는 길. **발언 단위 본문과 발언자 이름이 들어 있는지는 아직 확인하지 않았다** |

## 쓰는 법 (엑셀 경로)

```bash
python prepare_nanet.py 국회회의록.xlsx minutes.csv
python infer_speaker_names.py minutes.csv speaker_names.csv     # 이름 「추정」 — 공식 목록과 대조할 것
who-was-heard report minutes.csv --text text --group kind --speaker speaker_id \
    --speaker-names speaker_names.csv --context committee,date \
    --preset none --text-policy public --out run --name r1 \
    --source "국회도서관 국회회의록 빅데이터, 검색어 …, 기간 …"
```

1차 결과를 보면 「수고하셨습니다」 「마이크」 같은 의사진행 발언이 큰 묶음을 이룬다. 그것을 채점자들이 「공론 아님」으로 고르고 2차를 돌린다. `whowasheard/presets/korean-assembly.json`은 그렇게 정한 규칙의 예시다.

## 아직 남은 것

- OpenAPI로 받는 스크립트 (인증키 필요) — 발언자 이름 포함 여부 확인 후
- 발언자 ID→이름 공식 대조
- 공개 예시 보고서 — 위 둘이 끝나면 싣는다. 검색으로 받은 묶음은 「그 기간 국회의 공론」이라 부를 수 없어서 지금은 싣지 않는다.
