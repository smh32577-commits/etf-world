@echo off
chcp 65001 >nul
rem ETF 월드 로컬 실행: 최신 시세를 받고 브라우저로 화면을 엽니다. 창을 닫으면 종료됩니다.
set PY=C:\Users\smh32\AppData\Local\Programs\Python\Python315\python.exe
cd /d "%~dp0pipeline"
if not exist "..\site\data\universe.json" (
  echo 구성종목 수집 중... 약 2분 걸려요.
  "%PY%" -X utf8 daily.py
)
echo 최신 시세 받는 중...
"%PY%" -X utf8 live.py
start "" http://127.0.0.1:8780/
echo.
"%PY%" -X utf8 "%~dp0ops\serve.py" 8780
