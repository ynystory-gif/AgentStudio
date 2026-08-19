@echo off
setlocal EnableExtensions
title THEANOVA AgentStudio - Diagnostic Launcher
cd /d "%~dp0"

echo Running PowerShell controller directly...
echo Script: "%~dp0SYSTEM_ADMIN.ps1"
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0SYSTEM_ADMIN.ps1"

endlocal
