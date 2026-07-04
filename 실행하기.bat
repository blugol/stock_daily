@echo off
title 영웅문 종목 감시기 및 매매일지 V2.0
echo ==================================================
echo  영웅문 종목 감시기 및 매매일지 V2.0을 실행합니다.
echo ==================================================
echo.
echo 1. 로컬 웹 서버를 구동합니다...
start /b python server.py
timeout /t 2 >nul
echo 2. 웹 브라우저를 엽니다...
start http://localhost:8000
echo.
echo 프로그램이 가동되었습니다. 종료하려면 이 창을 닫아주세요.
echo.
pause
