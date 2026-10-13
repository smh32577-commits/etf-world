# 브리핑 작성 절차 (Claude용)

`site/briefs/latest.json`을 갱신해 사이트의 "오늘의 브리핑" 카드, `#/brief` 페이지, 관련 ETF 상세의 "오늘 왜 움직였나"에 반영한다.
API 키 없이 Claude Code 세션(또는 예약 실행)이 직접 뉴스를 찾아 읽고 작성한다.

## 언제
| 회차 | 시각(KST) | session 값 | 초점 |
|---|---|---|---|
| 장 마감 종합 | 15:40 | `장 마감 종합` | 오늘 하루 국내 ETF 흐름 정리 (종가 기준) |
| 장 전 | 08:00 | `장 전` | 밤사이 미국장 + 내일의 HOT(추정 iNAV) 상·하위가 시초가에 줄 영향 |
| 수시 | 요청 시 | `장중` | 지금까지의 흐름 |

## 순서
1. `cd pipeline && python -X utf8 live.py` 로 최신 데이터 생성 (daily 데이터가 없으면 `daily.py` 먼저)
2. `python -X utf8 brief_targets.py 8` → 대상 ETF와 재료(JSON). 같은 이야기의 ETF는 한 항목으로 묶는다 (`codes`에 여러 개)
3. 대상마다 뉴스 검색: 국내 종목은 한국어 기사, 미국 종목은 영문 기사. 당일 기사를 우선하고 날짜를 반드시 확인
4. 아래 형식으로 `site/briefs/YYYY-MM-DD-{pre|mid|close}.json` 작성 (장 전 pre, 장중 mid, 장 마감 close)
   - 같은 내용을 `site/briefs/latest.json`에도 저장
   - `site/briefs/index.json`의 `briefs` 맨 앞에 `{id, date, session, generatedAt}` 추가 (같은 id가 있으면 교체)
5. 커밋·푸시 → 다음 10분 주기 배포에 반영

## 요즘 트렌드 (site/briefs/trends.json)
장 마감 종합 회차에서 함께 갱신한다 (최소 주 1회).
1. `site/data/live.json`의 `rank.trend.w1 / m1`(최근 1주·1개월 수익률 상·하위 ETF, 테마별 시총가중 평균)을 확인
2. 상위·하위에 몰린 테마를 4~6개 이야기로 묶고, 각 이야기의 원인을 기사로 확인
3. 형식: `{generatedAt, dataAsOf, note, items:[{codes, period:"1주"|"1개월"|"1주 · 1개월", title, tone, summary, points, sources}]}`
   - `codes`에는 순위에 오른 ETF 코드를 모두 넣는다 (홈에서 해당 ETF 옆에 이유가 표시됨)

## 작성 원칙
- 수치(등락률, 거래대금, 비중)는 우리 데이터 기준, 원인은 기사 기준. 둘을 섞지 않는다
- 기사로 확인되지 않은 해석은 문장 끝에 `(추정)`
- 매수·매도 권유 표현 금지. "볼 포인트"는 확인할 이벤트·지표만
- 문장은 짧은 해요체, 항목당 points 2~3개
- 출처는 항목당 1~3개, 실제로 읽은 기사만

## 형식
```json
{
  "generatedAt": "ISO8601+09:00",
  "dataAsOf": "live.json의 updated",
  "session": "장 마감 종합 | 장 전 | 장중",
  "market": { "headline": "한 줄 제목", "points": ["시황 3~4줄"] },
  "items": [{
    "codes": ["069500"], "title": "표시 이름", "tone": "up | down | flat",
    "summary": "한 문장", "points": ["2~3개"], "watch": "볼 포인트",
    "sources": [{ "t": "매체 · 기사 제목", "u": "URL" }]
  }]
}
```
