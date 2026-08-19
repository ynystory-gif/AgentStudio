from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Awaitable, Callable

import httpx

ProgressFn = Callable[[int, str], Awaitable[None]]
OFFICIAL_INSTALL_SCRIPT = "https://ollama.com/install.ps1"


async def _progress(cb: ProgressFn | None, value: int, message: str):
    if cb:
        await cb(value, message)


def detect_ollama_exe() -> Path | None:
    found = shutil.which("ollama")
    if found:
        return Path(found)

    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    if local_appdata:
        candidate = Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe"
        if candidate.exists():
            return candidate
    return None


def _set_user_env(name: str, value: str):
    os.environ[name] = value
    result = subprocess.run(
        ["setx", name, value],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{name} 사용자 환경변수 저장 실패: "
            + ((result.stderr or result.stdout or "").strip())
        )


async def install_ollama_windows(
    progress_cb: ProgressFn | None = None,
    common_models_root: str = "",
) -> dict:
    if os.name != "nt":
        raise RuntimeError("Ollama 자동 설치는 현재 Windows용입니다.")

    models_root = (common_models_root or "").strip()

    # 이미 설치되어 있어도 모델 경로 설정은 적용
    existing = detect_ollama_exe()
    if models_root:
        model_dir = Path(models_root).expanduser()
        model_dir.mkdir(parents=True, exist_ok=True)
        await _progress(progress_cb, 5, f"공용 모델 경로 설정: {model_dir}")
        await asyncio.to_thread(_set_user_env, "OLLAMA_MODELS", str(model_dir.resolve()))
    else:
        await _progress(
            progress_cb,
            5,
            "공용 모델 경로가 비어 있어 Ollama 기본 모델 저장 경로를 사용합니다.",
        )

    if existing:
        await _progress(progress_cb, 100, f"Ollama가 이미 설치되어 있습니다: {existing}")
        return {
            "ok": True,
            "already_installed": True,
            "ollama_exe": str(existing),
            "models_path": models_root or "Ollama 기본 모델 경로",
            "message": "Ollama가 이미 설치되어 있습니다.",
        }

    await _progress(progress_cb, 15, "Ollama 공식 Windows 설치 스크립트를 다운로드합니다.")

    temp_dir = Path(tempfile.mkdtemp(prefix="agentstudio_ollama_"))
    script = temp_dir / "install_ollama.ps1"

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(60.0, connect=15.0),
            headers={"User-Agent": "THEANOVA-AgentStudio"},
        ) as client:
            res = await client.get(OFFICIAL_INSTALL_SCRIPT)
            res.raise_for_status()
            script.write_bytes(res.content)

        await _progress(
            progress_cb,
            35,
            "Ollama 설치를 시작합니다. 설치/UAC 화면이 나오면 허용하세요.",
        )

        def _run_install():
            return subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
            )

        proc = await asyncio.to_thread(_run_install)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(
                "Ollama 설치 실패: "
                + (detail[-3000:] if detail else f"종료코드 {proc.returncode}")
            )

        await _progress(progress_cb, 85, "Ollama 설치 파일을 확인합니다.")
        exe = detect_ollama_exe()

        if not exe:
            local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
            candidate = Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe" if local_appdata else None
            if candidate and candidate.exists():
                exe = candidate

        if not exe:
            raise RuntimeError(
                "설치 프로세스는 종료되었지만 ollama.exe를 확인하지 못했습니다. "
                "Windows에서 Ollama 앱을 한 번 실행한 뒤 다시 확인하세요."
            )

        await _progress(progress_cb, 100, "Ollama 설치 완료")
        return {
            "ok": True,
            "already_installed": False,
            "ollama_exe": str(exe),
            "models_path": models_root or "Ollama 기본 모델 경로",
            "message": "Ollama 설치가 완료되었습니다.",
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
