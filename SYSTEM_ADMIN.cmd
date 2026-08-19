@echo off
setlocal EnableExtensions
chcp 65001 >nul
title THEANOVA AgentStudio - System Manager

cd /d "%~dp0"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0SYSTEM_ADMIN.ps1"
set "EXITCODE=%ERRORLEVEL%"

echo.
echo ============================================================
if "%EXITCODE%"=="0" (
    echo SYSTEM_ADMIN completed successfully.
) else (
    echo SYSTEM_ADMIN failed. ExitCode=%EXITCODE%
)
echo ============================================================
echo.
echo This window will remain open.
echo Check the log paths printed above.
echo.
pause

endlocal
exit /b %EXITCODE%
