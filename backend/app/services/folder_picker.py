from __future__ import annotations

import asyncio
import os
import subprocess
import traceback


def _escape_ps_single(value: str) -> str:
    return (value or "").replace("'", "''")


def _pick_folder_windows(
    title: str = "폴더를 선택하세요.",
    initial_path: str = "",
) -> dict:
    """
    Windows Forms FolderBrowserDialog를 사용합니다.

    중요:
    Backend가 별도 PowerShell process에서 실행되므로
    소유창(owner)이 없으면 선택창이 Browser 뒤쪽에 뜨거나
    작업표시줄에서만 깜빡이는 경우가 있습니다.

    따라서 작은 TopMost Form을 owner로 만든 뒤 ShowDialog(owner)를
    호출하여 사용자가 누른 직후 전면에 표시되도록 합니다.
    """
    safe_title = _escape_ps_single(title)
    safe_initial = _escape_ps_single(initial_path)

    script = rf"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$owner = New-Object System.Windows.Forms.Form
$owner.Text = 'THEANOVA AgentStudio'
$owner.Width = 1
$owner.Height = 1
$owner.ShowInTaskbar = $false
$owner.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedToolWindow
$owner.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$owner.TopMost = $true
$owner.Opacity = 0

$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '{safe_title}'
$dialog.ShowNewFolderButton = $true

if ('{safe_initial}' -ne '' -and (Test-Path -LiteralPath '{safe_initial}')) {{
    $dialog.SelectedPath = '{safe_initial}'
}}

try {{
    $owner.Show()
    $owner.Activate()
    $owner.BringToFront()

    $result = $dialog.ShowDialog($owner)

    if ($result -eq [System.Windows.Forms.DialogResult]::OK) {{
        Write-Output ('__THEANOVA_FOLDER__=' + $dialog.SelectedPath)
    }} else {{
        Write-Output '__THEANOVA_CANCELLED__=1'
    }}
}}
finally {{
    try {{ $dialog.Dispose() }} catch {{}}
    try {{ $owner.Close() }} catch {{}}
    try {{ $owner.Dispose() }} catch {{}}
}}
"""

    creationflags = 0
    if os.name == "nt":
        # Console window는 숨기되 WinForms GUI는 표시됩니다.
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "cancelled": False,
            "path": "",
            "message": "폴더 선택창 응답 시간이 초과되었습니다.",
        }
    except Exception as e:
        return {
            "ok": False,
            "cancelled": False,
            "path": "",
            "message": f"폴더 선택 프로세스 실행 실패: {e}",
            "traceback": traceback.format_exc()[-4000:],
        }

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    if proc.returncode != 0:
        return {
            "ok": False,
            "cancelled": False,
            "path": "",
            "message": (
                stderr
                or stdout
                or f"폴더 선택 프로세스 종료 코드: {proc.returncode}"
            ),
        }

    selected = ""

    for line in stdout.splitlines():
        if line.startswith("__THEANOVA_FOLDER__="):
            selected = line.split("=", 1)[1].strip()
            break

    if selected:
        return {
            "ok": True,
            "cancelled": False,
            "path": selected,
            "message": "폴더를 선택했습니다.",
        }

    if "__THEANOVA_CANCELLED__=1" in stdout:
        return {
            "ok": True,
            "cancelled": True,
            "path": "",
            "message": "폴더 선택을 취소했습니다.",
        }

    return {
        "ok": False,
        "cancelled": False,
        "path": "",
        "message": (
            "폴더 선택 프로세스가 경로를 반환하지 않았습니다."
            + (f" PowerShell 출력: {stdout}" if stdout else "")
        ),
    }


async def pick_folder(
    title: str = "폴더를 선택하세요.",
    initial_path: str = "",
) -> dict:
    if os.name != "nt":
        return {
            "ok": False,
            "cancelled": False,
            "path": "",
            "message": "현재 폴더 선택 기능은 Windows에서 지원합니다.",
        }

    return await asyncio.to_thread(
        _pick_folder_windows,
        title,
        initial_path,
    )
