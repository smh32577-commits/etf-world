# ETF 월드 · 서울 WM센터 — Claude Code 작업 안내

국내 상장 ETF 1,172개의 시세·순위·테마 흐름과, 장 마감 후 미국 시세·환율로 계산한 **추정 iNAV**, Claude가 뉴스를 읽고 쓰는 **브리핑**을 보여주는 내부 공유용 정적 사이트다.
종료된 ETFnow(etfnow.co.kr)를 참고했다. 처음 설치·인계는 `HANDOVER.md`, 브리핑 작성은 `BRIEFING.md`를 따른다.

## 구조
```
pipeline/            Python 표준 라이브러리만 사용 (pip 설치 없음)
  common.py          HTTP·KST·JSON 저장, ETF 테마 분류(이름 키워드)
  daily.py           하루 1번: ETF 목록·구성종목·기본정보·1년 차트, 1주/1개월 수익률, 종목→ETF 역검색 (약 2분)
  live.py            10분마다: ETF 시세, 미국 구성종목 시세, 환율 → 추정 iNAV, 순위, 등락 이유, 테마, 트렌드 (약 6초)
  brief_targets.py   브리핑 대상 ETF 선정 + 재료(JSON 출력)
site/                빌드 없는 정적 SPA (index.html, app.js, styles.css)
  data/              파이프라인 출력. git에 올리지 않음(.gitignore). Actions가 매번 생성
  briefs/            Claude가 쓰는 브리핑 JSON. git에 올림
    latest.json, index.json, YYYY-MM-DD-{pre|mid|close}.json, trends.json
.github/workflows/update.yml   매시 05분 예약 실행 + push 시 실행
ops/loop.py          Actions 안에서 live.py를 10분 간격으로 돌리고 gh-pages 브랜치로 배포 (예약 실행이면 6회, 그 외 1회)
ops/routines.md      장 전·장 마감 자동 브리핑(Claude 예약 실행) 설정 원본
```

## 자주 쓰는 명령 (Windows Git Bash 기준, 저장소 루트에서)
```bash
cd pipeline && python -X utf8 daily.py        # 최초 1회 또는 구성종목 갱신
cd pipeline && python -X utf8 live.py         # 실시간 데이터
cd pipeline && python -X utf8 live.py --force --anchor 2026-10-09   # 장중 테스트: 기준일 지정해 추정 경로 실행
cd site && python -m http.server 8765         # 로컬 확인 http://localhost:8765
git push origin main                          # 푸시하면 Actions가 바로 배포
```
`-X utf8`은 Windows 콘솔(cp949)에서 한글 출력 오류를 막는다. 우리 스크립트를 실행할 때는 `python -I`를 쓰지 않는다(같은 폴더 모듈 import가 막힘).

## 데이터 소스 (모두 공개 API, 키 없음)
| 용도 | URL | 비고 |
|---|---|---|
| ETF 전체 목록·시세·iNAV | finance.naver.com/api/sise/etfItemList.nhn | **cp949 인코딩**. `amonut`=거래대금(백만원), `marketSum`=시총(억), `nav`=장중 iNAV |
| 구성종목·비중 | stock.naver.com/api/domestic/detail/{code}/ETFComponent | 해외는 로이터코드(NVDA.O), 국내는 종목코드. `componentMarketType` 0=KOSPI/현금 1=KOSDAQ 2=해외 |
| ETF 기본정보·수익률 | m.stock.naver.com/api/stock/{code}/etfAnalysis | 운용사, 총보수(%), 순자산, 배당 |
| 일봉 | api.stock.naver.com/chart/domestic/item/{code}/day | |
| 해외 실시간 | polling.finance.naver.com/api/realtime/worldstock/stock/{로이터코드,…} | 100개씩 묶음. `overMarketPriceInfo`=프리/애프터 |
| 국내 실시간 | polling.finance.naver.com/api/realtime/domestic/stock/{코드,…} | 100개씩 묶음 |
| 지수 | polling…/domestic/index/KOSPI,KOSDAQ, polling…/worldstock/index/.INX,.IXIC,.SOX | |
| 환율 | query1.finance.yahoo.com/v8/finance/chart/KRW=X | 15분봉으로 기준 시점 환율 조회 |
| 미국 일봉(보조) | query1.finance.yahoo.com/v7/finance/spark?symbols=…(20개) | 연휴 뒤 기준가 확인용 |

브라우저에서 네이버를 직접 부를 수 없어서(CORS) 모든 데이터는 파이프라인이 JSON으로 미리 만든다.

## 추정 iNAV 규칙 (live.py)
- 기준점 = 마지막 KRX 거래일 15:30. `추정 iNAV = iNAV(15:30) × (1 + Σ 비중 × [(1+종목 변동)(1+환율 변동) − 1])`
- 미국 종목만 반영. 국내·비미국 종목·현금은 변동 0. 환헤지(H)는 환율 미반영
- 대상: 미국 비중 30% 이상, 레버리지·인버스·합성·선물형 제외. 순위는 시총 100억 이상
- 모드: KRX 장중 `official`(공식 iNAV), 장 마감 후 `live`, 추정 불가 `idle`
- 알려진 한계: 국내 휴장 중 미국장이 2번 이상 열리면(예: 한글날) `idle`. Yahoo spark로 기준일 직전 미국 종가를 받아 보완하는 것이 다음 작업 후보

## 화면 (site/app.js, 해시 라우터)
`#/` 홈(시장 폭·테마 히트맵·순위 탭·요즘 트렌드·브리핑·내 ETF), `#/hot` 내일의 HOT, `#/find` 찾기·종목 역검색, `#/etf/{code}` 상세, `#/my` 즐겨찾기·예상 손익(localStorage), `#/brief` 브리핑.
- 디자인: 토스·애플풍 단순함. Pretendard, 회색 배경 + 흰 카드, 상승 빨강/하락 파랑(한국식), 다크모드 지원. 카드 늘리기보다 탭·접기로 압축
- 시장 폭 막대: ETF 개수 기준, 금리·채권형·레버리지·인버스 제외
- 테마 히트맵: 시총가중 평균 등락률, 변동폭 큰 순

## 배포·운영 메모
- GitHub 예약 실행은 10분 간격이면 자주 빠진다(실측: 하루 2회). 그래서 1시간마다 실행하고 `ops/loop.py`가 그 안에서 10분 간격으로 6번 갱신한다
- 배포: `gh-pages` 브랜치에 강제 푸시(커밋 1개만 유지) → Pages API로 빌드 요청. Pages 설정은 Branch: gh-pages / root (build_type=legacy)
- 일간 데이터는 Actions 캐시(`daily-v2-날짜`)에 보관. 데이터 필드를 바꾸면 캐시 키 버전을 올려 당일 재수집
- 배포 때 `app.js?v=커밋` 식으로 버전을 붙여 브라우저 캐시 문제를 막는다 (Pages 캐시 10분)
- 검색엔진 차단(robots.txt, noindex). URL을 아는 사람은 볼 수 있음
- 공개 저장소 전제(Actions 무료 분 무제한). 비공개로 바꾸면 월 2,000분을 넘고 Pages도 유료

## 작업 원칙
- 브리핑 수치는 우리 데이터, 원인은 기사 기준. 미확인 해석은 "(추정)". 매수·매도 권유 금지
- 사용자에게 보이는 문장은 자연스러운 해요체. 번역투 금지
- 화면 확인은 헤드리스 크롬 스크린샷으로 한다. 단, 헤드리스 크롬은 창 너비가 최소 500px라 그보다 좁게 찍히지 않는다
- 셸에서 경로에 `\U` 같은 문자열이 든 sed 치환을 하지 않는다(GNU sed가 대문자 변환으로 해석). 여러 줄 수정은 Python 스크립트 파일로
