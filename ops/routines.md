# 자동 브리핑 예약 실행 (Claude Code Routines)

Claude Code에서 `/schedule` 로 만든다. 클라우드에서 실행되므로 PC를 꺼둬도 된다.
**사전 조건:** Claude 계정에 GitHub 연결 (`/web-setup` 또는 https://claude.ai/connect-github). 안 되어 있으면 생성 시 `github_token_missing` 오류가 난다.

Claude Code에 이렇게 말하면 된다:
> ops/routines.md 대로 자동 브리핑 예약 실행 두 개를 만들어줘. 저장소는 `<내 GitHub 계정>/etf-world` 야.

## 공통 설정
| 항목 | 값 |
|---|---|
| 저장소 | `https://github.com/<계정>/etf-world` |
| 모델 | `claude-sonnet-5-5` (더 꼼꼼하게: `claude-opus-5-5`) |
| 허용 도구 | Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch |
| 환경 | 계정의 기본(Default) 클라우드 환경 |

## 1) 장 전 브리핑 — 평일 08:00 KST
- cron (UTC): `0 23 * * 0-4`  (= 월~금 08:00 KST)
- 프롬프트:

```
너는 GitHub 저장소 <계정>/etf-world(작업 디렉터리에 체크아웃됨)의 '장 전' ETF 브리핑을 작성해서 main 브랜치에 푸시하는 에이전트다.
먼저 저장소 루트의 CLAUDE.md 와 BRIEFING.md 를 읽고 그 절차·작성 원칙·JSON 형식을 그대로 따른다.

회차: session "장 전", 파일 id YYYY-MM-DD-pre (YYYY-MM-DD = `TZ=Asia/Seoul date +%F`)
초점: 국내 장 시작 전, 밤사이 미국장 흐름과 환율이 오늘 국내 상장 ETF 시초가에 줄 영향. 특히 '내일의 HOT'(추정 iNAV 기준 종가 대비 예상 등락 상·하위).
실행 시점(약 08:00 KST) 이전의 정보·기사만 쓴다.

단계
1. `cd pipeline && python3 -X utf8 daily.py && python3 -X utf8 live.py`. 실패하면 원인을 출력하고 커밋 없이 종료.
2. `python3 -X utf8 brief_targets.py 8` 와 site/data/live.json 의 rank.up / rank.down(ex=예상 등락%, top=영향 큰 미국 종목), fx, indices 를 재료로 쓴다. 같은 이야기의 ETF는 한 항목(codes 여러 개)으로 묶고 항목은 4~6개.
3. live.json 의 mode 가 "idle"(국내 휴장 뒤 미국장이 2번 이상 열린 경우)이면 https://query1.finance.yahoo.com/v7/finance/spark?symbols=NVDA,MU,AMD,AVGO,PLTR,MSFT,AMZN,AAPL&range=5d&interval=1d (20종목씩, User-Agent 헤더 필요)로 주요 미국 종목의 기준일 이후 등락을 직접 확인해 설명하고, 그 사실을 시황 points 에 밝힌다.
4. WebSearch/WebFetch 로 밤사이 미국 증시 마감 기사(영문)와 국내 증시 전망 기사(한국어)를 찾아 원인을 확인한다. 기사 날짜를 반드시 확인.
5. site/briefs/YYYY-MM-DD-pre.json 작성, 같은 내용을 site/briefs/latest.json 에 저장, site/briefs/index.json 의 briefs 맨 앞에 {id,date,session,generatedAt} 추가(같은 id면 교체). python3 로 JSON 유효성 확인.
6. `git add site/briefs && git commit -m "브리핑: YYYY-MM-DD 장 전" && git push origin main`. site/data/ 는 커밋하지 않는다. 다른 파일은 수정하지 않는다.

마지막에 헤드라인, 항목 제목, 커밋 해시를 짧게 보고한다.
```

## 2) 장 마감 종합 — 평일 15:40 KST
- cron (UTC): `40 6 * * 1-5`  (= 월~금 15:40 KST)
- 프롬프트:

```
너는 GitHub 저장소 <계정>/etf-world(작업 디렉터리에 체크아웃됨)의 '장 마감 종합' ETF 브리핑과 '요즘 트렌드'를 작성해서 main 브랜치에 푸시하는 에이전트다.
먼저 저장소 루트의 CLAUDE.md 와 BRIEFING.md 를 읽고 그 절차·작성 원칙·JSON 형식을 그대로 따른다.

회차: session "장 마감 종합", 파일 id YYYY-MM-DD-close (YYYY-MM-DD = `TZ=Asia/Seoul date +%F`)

단계
1. `cd pipeline && python3 -X utf8 daily.py && python3 -X utf8 live.py`. 실패하면 원인을 출력하고 커밋 없이 종료.
2. site/data/live.json 의 anchor 가 오늘 날짜가 아니면 오늘은 KRX 휴장이다. 아무것도 커밋하지 말고 "휴장"이라고 보고하고 종료.
3. `python3 -X utf8 brief_targets.py 8` 로 대상(거래대금·등락률·거래량 급증 상위)을 확인한다. live.json 의 rank.gainers / losers / amount / surge 항목의 dr(등락을 이끈 구성종목)도 참고한다. 같은 이야기는 한 항목으로 묶고 항목은 4~6개.
4. WebSearch/WebFetch 로 오늘 국내 증시 마감 기사와 관련 종목 기사를 찾아 원인을 확인한다. 기사 날짜를 반드시 확인.
5. site/briefs/YYYY-MM-DD-close.json 작성, latest.json 에도 저장, index.json 맨 앞에 추가(같은 id면 교체).
6. BRIEFING.md 의 '요즘 트렌드' 절차대로 site/briefs/trends.json 을 갱신한다 (live.json 의 rank.trend.w1 / m1 기준, 4~6개 이야기, codes 에 순위에 오른 ETF 코드 모두 포함).
7. python3 로 JSON 유효성 확인 후 `git add site/briefs && git commit -m "브리핑: YYYY-MM-DD 장 마감" && git push origin main`. site/data/ 는 커밋하지 않는다.

마지막에 헤드라인, 항목 제목, 트렌드 이야기 제목, 커밋 해시를 짧게 보고한다.
```

## 확인·수정
- 목록·다음 실행 시각: Claude Code에서 `/schedule` → List
- 실행 기록·로그: https://claude.ai/code/routines
- 지금 바로 한 번 돌려보기: `/schedule` → Run now
- 삭제는 웹(https://claude.ai/code/routines)에서만 가능
