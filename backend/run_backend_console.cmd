@echo off
chcp 65001 >nul
cd /d "C:\AI\AgentStudio\backend"
echo [START] FastAPI Backend
echo Log: C:\AI\AgentStudio\logs\backend_console.log
echo.
".\.venv\Scripts\python.exe" ".\run_server.py" --host 127.0.0.1 --port 8000 >> "C:\AI\AgentStudio\logs\backend_console.log" 2>&1
set EXITCODE=%ERRORLEVEL%
echo.
if not "%EXITCODE%"=="0" echo [FAILED] Backend exited. ExitCode=%EXITCODE%
if not "%EXITCODE%"=="0" echo Log: C:\AI\AgentStudio\logs\backend_console.log
if "%EXITCODE%"=="0" echo [DONE] Backend exited normally.
pause
exit /b %EXITCODE%
