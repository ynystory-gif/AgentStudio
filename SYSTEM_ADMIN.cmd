@echo off
setlocal EnableExtensions
chcp 65001 >nul
title THEANOVA AgentStudio - System Manager

cd /d "%~dp0"

rem Windows PowerShell 5.1 can misread UTF-8 .ps1 files without BOM.
rem Repair a missing BOM before -File parsing. This preflight is ASCII-only.
set "SYSTEM_ADMIN_PS1=%~dp0SYSTEM_ADMIN.ps1"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$p=$env:SYSTEM_ADMIN_PS1; try { $b=[IO.File]::ReadAllBytes($p); if ($b.Length -ge 3 -and $b[0] -eq 239 -and $b[1] -eq 187 -and $b[2] -eq 191) { exit 0 }; $utf8 = New-Object Text.UTF8Encoding($false,$true); $t=$utf8.GetString($b); $utf8Bom = New-Object Text.UTF8Encoding($true); [IO.File]::WriteAllText($p,$t,$utf8Bom); exit 0 } catch { Write-Host '[ERROR] SYSTEM_ADMIN.ps1 UTF-8/BOM validation failed.' -ForegroundColor Red; Write-Host $_.Exception.Message -ForegroundColor Red; exit 87 }"
if errorlevel 1 (
    set "EXITCODE=%ERRORLEVEL%"
    echo.
    echo ============================================================
    echo SYSTEM_ADMIN failed before launch. ExitCode=%EXITCODE%
    echo ============================================================
    echo.
    echo SYSTEM_ADMIN.ps1 encoding could not be repaired safely.
    echo.
    pause
    endlocal
    exit /b %EXITCODE%
)

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
if not "%EXITCODE%"=="0" (
    echo Failure detail log : %~dp0logs\system_manager_failure.log
    echo System manager log : %~dp0logs\system_manager.log
    echo Backend log        : %~dp0logs\backend_console.log
    echo Frontend log       : %~dp0logs\frontend_console.log
    echo.
    if exist "%~dp0logs\system_manager_failure.log" (
        echo ================= FAILURE DETAIL =================
        type "%~dp0logs\system_manager_failure.log"
        echo ==================================================
        echo.
    ) else (
        echo Failure detail log was not created.
        echo The error may have happened before SYSTEM_ADMIN.ps1 entered its startup handler.
        echo.
    )
)
echo This window will remain open.
echo.
pause

endlocal
exit /b %EXITCODE%
