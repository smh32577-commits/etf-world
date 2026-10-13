# ETF 월드 (서울 WM센터)

> 처음 받으셨다면 **[HANDOVER.md](HANDOVER.md)** 부터 보세요. Claude Code 작업 안내는 [CLAUDE.md](CLAUDE.md), 브리핑 작성법은 [BRIEFING.md](BRIEFING.md), 자동 브리핑 설정은 [ops/routines.md](ops/routines.md).

장 마감 후에도 국내 상장 ETF의 가치를 추정하는 실시간 iNAV 트래커. 종료된 ETFnow(etfnow.co.kr)를 참고한 개인·내부용 프로젝트.

## 구조
- `pipeline/daily.py`: 하루 1번 실행. ETF 1,172개의 구성종목·기본정보·1년 차트, 종목→ETF 역검색 인덱스 (약 2분)
- `pipeline/live.py`: 10분마다 실행. ETF 시세 + 미국 구성종목 시세(프리/정규/애프터) + 환율 → 추정 iNAV, 랭킹 (약 5초)
- `site/`: 빌드 없는 정적 SPA. `site/data/*.json`을 읽음
- `.github/workflows/update.yml` + `ops/loop.py`: 매시 실행, 그 안에서 10분 간격 갱신 후 gh-pages 브랜치로 배포. 일간 데이터는 Actions 캐시에 보관

## 추정 iNAV
```
추정 iNAV = iNAV(15:30) × (1 + Σ 비중 × [(1+종목 변동)(1+환율 변동) − 1])
```
- 기준점은 마지막 KRX 거래일 15:30. 미국 종목은 그 시점의 최신 정규장 종가를 기준가로 씀 (상태 저장 없이 계산)
- 환헤지(H)는 환율 미반영, 국내·비미국 종목·현금은 변동 0
- 레버리지·인버스·합성·선물형, 미국 비중 30% 미만 ETF는 추정 안 함
- 국내 휴장일에 미국장이 2회 이상 열린 경우(예: 한글날)는 추정을 멈춤

## 로컬 실행
```
cd pipeline
python daily.py          # 최초 1회
python live.py           # 장중엔 공식 iNAV 모드
python live.py --force --anchor 2026-10-09   # 테스트: 기준일 지정해 추정 경로 실행
cd ../site && python -m http.server 8765
```

데이터: 네이버 금융, Yahoo Finance(환율) 공개 API. 모든 추정값은 참고용.
