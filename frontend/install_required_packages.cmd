@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo [진행] AgentStudio Frontend 필수 패키지 설치
call npm install
if errorlevel 1 (
    echo [실패] npm install 실패
    pause
    exit /b 1
)

call npm run build
if errorlevel 1 (
    echo [실패] Frontend 빌드 실패
    pause
    exit /b 1
)

echo [완료] Frontend 필수 패키지 설치 및 빌드 검증
pause
exit /b 0
