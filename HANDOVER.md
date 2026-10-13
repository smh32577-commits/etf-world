# ETF 월드 인계 가이드

서울 WM센터 내부 공유용 ETF 사이트 **ETF 월드**를 넘겨받아 운영하기 위한 안내입니다.
개발 지식이 없어도 됩니다. **직접 해야 하는 건 계정 만들기·프로그램 설치·로그인뿐이고, 나머지는 Claude Code에 말로 시키면 됩니다.**

---

## 이 사이트가 하는 일
- 국내 상장 ETF 1,172개의 등락·거래대금·거래량 급증 순위, 테마별 흐름(히트맵), 최근 1주·1개월 트렌드
- 장 마감 후 미국 시세·환율로 계산한 **추정 iNAV**와 "내일의 HOT ETF"(내일 시초가가 크게 움직일 ETF)
- ETF 상세(차트·구성종목·보수·배당), 종목으로 ETF 찾기(예: "엔비디아를 담은 ETF")
- **브리핑**: 장 전(08:00)·장 마감(15:40)에 Claude가 뉴스를 읽고 "왜 움직였나"를 정리

데이터는 네이버 금융·Yahoo Finance 공개 시세를 씁니다. 비용은 **0원**입니다(GitHub 무료 + 가지고 계신 Claude 구독).

---

## 1단계. 계정 준비 (직접)
| 계정 | 용도 | 비고 |
|---|---|---|
| **GitHub** (github.com) | 코드 보관, 10분마다 자동 갱신, 사이트 호스팅 | 무료. 계정 이름이 사이트 주소에 들어갑니다 → `https://<계정>.github.io/etf-world/` |
| **Claude** (claude.ai) | Claude Code 사용, 자동 브리핑 | **Pro 이상 유료 플랜** 필요 |

> ⚠️ 회사 이름(서울 WM센터)이 화면에 나오는 사이트가 공개 주소에 올라갑니다. 검색엔진 노출은 막아 두었지만 주소를 아는 사람은 볼 수 있습니다. **공유 전에 회사 준법감시(컴플라이언스) 기준을 확인**하세요.

## 2단계. 프로그램 설치 (직접, Windows 기준 약 10분)
PowerShell을 **관리자 권한**으로 열고 아래를 한 줄씩 붙여 넣습니다.

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.12 -e
winget install --id GitHub.cli -e
irm https://claude.ai/install.ps1 | iex
```
- 각각 Git, Python, GitHub CLI, Claude Code입니다.
- 설치 후 PowerShell을 **닫았다가 다시 엽니다.**
- VS Code를 쓰신다면 확장 프로그램에서 **"Claude Code"**를 설치해도 됩니다.

로그인(각각 브라우저 창이 뜹니다):
```powershell
gh auth login        # GitHub.com → HTTPS → Login with a web browser 선택
claude               # 처음 실행 시 Claude 계정으로 로그인
```

## 3단계. 파일 풀고 Claude Code에 맡기기
1. 전달받은 `etf-world-인계.zip`을 원하는 곳에 풉니다 (예: `C:\Users\<이름>\etf-world`).
2. 그 폴더에서 Claude Code를 엽니다.
   - PowerShell: `cd C:\Users\<이름>\etf-world` 후 `claude`
   - VS Code: 폴더 열기 → Claude Code 패널
3. 아래 문장을 **그대로 복사해서** 붙여 넣습니다.

```
이 폴더는 'ETF 월드' 프로젝트야. CLAUDE.md, HANDOVER.md, BRIEFING.md, ops/routines.md 를 먼저 읽어줘.
그다음 HANDOVER.md 의 "Claude Code가 하는 일" 순서대로 설치 확인부터 GitHub 배포, 자동 브리핑 설정까지 진행해줘.
내가 직접 해야 하는 단계(로그인, 승인, 결정)가 나오면 멈추고 무엇을 누르면 되는지 쉽게 알려줘.
GitHub 저장소 이름은 etf-world, 공개 저장소로 만들어줘.
```

### Claude Code가 하는 일 (Claude용 체크리스트)
1. `git`, `python`(3.8 이상), `gh auth status` 확인. 없으면 2단계 설치를 안내
2. `cd pipeline && python -X utf8 daily.py` → `python -X utf8 live.py` 로 데이터 생성 확인 (네이버 접속 가능 여부)
3. `cd site && python -m http.server 8765` 로 로컬 확인, 헤드리스 크롬 스크린샷으로 홈·상세 화면 점검
4. `git init -b main` → 커밋 → `gh repo create etf-world --public --source . --push`
5. 첫 Actions 실행이 끝나 `gh-pages` 브랜치가 생길 때까지 기다림(`gh run list`, `gh api repos/<계정>/etf-world/branches`)
6. Pages 켜기(브랜치 방식): `gh api -X POST repos/<계정>/etf-world/pages -f build_type=legacy -f "source[branch]=gh-pages" -f "source[path]=/"` → `gh api -X POST repos/<계정>/etf-world/pages/builds` → 1~2분 뒤 `https://<계정>.github.io/etf-world/` 접속 확인
   - 첫 실행의 Pages 빌드 요청은 Pages를 켜기 전이라 실패해도 정상. 다음 실행부터 자동
7. 사용자에게 `/web-setup` 실행 요청(Claude 계정 ↔ GitHub 연결) → `ops/routines.md` 대로 예약 실행 2개 생성 → Run now로 시험 실행
8. 끝나면 사이트 주소, 예약 실행 링크, 남은 할 일을 정리해 보고

## 4단계. 직접 눌러야 하는 것 (Claude가 대신 못 함)
- **로그인 창:** GitHub와 Claude 로그인 창이 뜨면 로그인합니다.
- **권한 확인 창:** Claude Code가 명령 실행이나 파일 수정 허락을 물으면 내용을 보고 허용합니다. 특히 "공개 저장소 만들기"와 "GitHub Pages 켜기"는 외부에 공개되는 작업이라 꼭 확인을 묻습니다.
- **`/web-setup` 입력:** 자동 브리핑을 쓰려면 Claude Code 입력창에 `/web-setup`을 입력해 Claude 계정과 GitHub을 연결합니다. 한 번만 하면 됩니다.

---

## 평소 운영: 이렇게 말하면 됩니다
| 하고 싶은 것 | Claude Code에 이렇게 |
|---|---|
| 지금 시점 브리핑 | "BRIEFING.md 대로 지금 장중 브리핑 만들어서 올려줘" |
| 장 마감 정리 다시 | "오늘 장 마감 브리핑이랑 요즘 트렌드 다시 써줘" |
| 자동 브리핑 상태 확인 | "/schedule 로 예약 실행 목록이랑 최근 실행 결과 보여줘" |
| 화면 수정 | "홈 화면에서 ○○를 △△로 바꿔줘. 바꾸고 스크린샷으로 확인한 뒤 배포해줘" |
| 오류가 날 때 | "GitHub Actions 최근 실행이 실패했는지 보고, 원인 찾아서 고쳐줘" |
| 구성종목 강제 재수집 | "update 워크플로를 daily=true 로 수동 실행해줘" |

## 자동으로 돌아가는 것
| 무엇 | 언제 | 어디서 |
|---|---|---|
| 시세·순위·추정 iNAV 갱신 | 평일 1시간마다 실행, 그 안에서 10분 간격 (월 09:05 ~ 토 08:55) | GitHub Actions |
| 구성종목·차트 재수집 | 매일 07시 이후 첫 실행 | GitHub Actions |
| 장 전 브리핑 | 평일 08:00 | Claude 예약 실행 |
| 장 마감 브리핑 + 요즘 트렌드 | 평일 15:40 (휴장일은 건너뜀) | Claude 예약 실행 |

PC를 꺼 두어도 모두 돌아갑니다.

## 자주 묻는 것
- **화면이 안 바뀌어요.** 배포 후 1~2분 기다린 뒤 새로고침(PC는 Ctrl+F5)하세요.
- **"추정 대기"라고 나와요.** 국내 휴장일(예: 한글날)에 미국장이 2번 이상 열리면 자동 추정이 멈춥니다. 장 전 브리핑이 대신 직접 계산해 설명합니다.
- **내일의 HOT이 비어 있어요.** 미국 프리마켓이 열리는 17:00(겨울 18:00)부터 계산을 시작합니다.
- **숫자가 공식 값과 달라요.** 추정 iNAV와 브리핑은 참고용입니다. 공식 iNAV는 장중에만 나옵니다.
- **비공개로 바꾸고 싶어요.** 비공개 저장소는 GitHub 무료 사용량(월 2,000분)을 넘고 Pages도 유료 플랜이 필요합니다. 필요하면 Claude Code에 "비공개로 운영하는 방법을 비용과 함께 비교해줘"라고 물어보세요.

## 전 담당자가 정리할 것
- 기존 사이트(`eunsik3451.github.io/etf-world`)와 예약 실행은 새 사이트가 정상 동작하는 것을 확인한 뒤 보관하거나 끕니다.
  - 저장소: Settings → Archive
  - 예약 실행: claude.ai/code/routines
