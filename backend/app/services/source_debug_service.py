from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SOURCE_RUNNERS: dict[str, dict[str, Any]] = {
    ".js": {"label": "Node.js", "commands": [["node", "{file}"]]},
    ".mjs": {"label": "Node.js", "commands": [["node", "{file}"]]},
    ".cjs": {"label": "Node.js", "commands": [["node", "{file}"]]},
    ".jsx": {"label": "JavaScript/JSX", "commands": [["tsx", "{file}"], ["npx", "--no-install", "tsx", "{file}"]]},
    ".ts": {"label": "TypeScript", "commands": [["tsx", "{file}"], ["npx", "--no-install", "tsx", "{file}"], ["ts-node", "{file}"]]},
    ".tsx": {"label": "TypeScript/TSX", "commands": [["tsx", "{file}"], ["npx", "--no-install", "tsx", "{file}"]]},
    ".mts": {"label": "TypeScript", "commands": [["tsx", "{file}"], ["npx", "--no-install", "tsx", "{file}"]]},
    ".cts": {"label": "TypeScript", "commands": [["tsx", "{file}"], ["npx", "--no-install", "tsx", "{file}"]]},
    ".cs": {"label": "C# Script", "commands": [["dotnet-script", "{file}"], ["csi", "{file}"]]},
    ".ps1": {"label": "PowerShell", "commands": [["pwsh", "-NoProfile", "-File", "{file}"], ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "{file}"]]},
    ".psm1": {"label": "PowerShell", "commands": [["pwsh", "-NoProfile", "-File", "{file}"], ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "{file}"]]},
    ".cmd": {"label": "Windows CMD", "commands": [["cmd", "/d", "/c", "{file}"]]},
    ".bat": {"label": "Windows CMD", "commands": [["cmd", "/d", "/c", "{file}"]]},
    ".sh": {"label": "Shell", "commands": [["bash", "{file}"]]},
    ".bash": {"label": "Bash", "commands": [["bash", "{file}"]]},
    ".zsh": {"label": "Zsh", "commands": [["zsh", "{file}"]]},
    ".php": {"label": "PHP", "commands": [["php", "{file}"]]},
    ".rb": {"label": "Ruby", "commands": [["ruby", "{file}"]]},
    ".pl": {"label": "Perl", "commands": [["perl", "{file}"]]},
    ".lua": {"label": "Lua", "commands": [["lua", "{file}"]]},
    ".go": {"label": "Go", "commands": [["go", "run", "{file}"]]},
    ".java": {"label": "Java source launcher", "commands": [["java", "{file}"]]},
    ".r": {"label": "R", "commands": [["Rscript", "{file}"]]},
    ".swift": {"label": "Swift", "commands": [["swift", "{file}"]]},
    ".kts": {"label": "Kotlin Script", "commands": [["kotlinc", "-script", "{file}"]]},
}

COMPILED_RUNNERS: dict[str, dict[str, Any]] = {
    ".c": {"label": "C", "compiler": ["gcc", "{file}", "-o", "{exe}"]},
    ".cc": {"label": "C++", "compiler": ["g++", "{file}", "-o", "{exe}"]},
    ".cpp": {"label": "C++", "compiler": ["g++", "{file}", "-o", "{exe}"]},
    ".cxx": {"label": "C++", "compiler": ["g++", "{file}", "-o", "{exe}"]},
    ".rs": {"label": "Rust", "compiler": ["rustc", "{file}", "-o", "{exe}"]},
}


def _safe_target(root: str, relative_path: str) -> tuple[Path, Path]:
    project_root = Path(root).expanduser().resolve()
    target = (project_root / Path(relative_path.replace("\\", "/"))).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise PermissionError("프로젝트 밖의 소스 파일은 실행할 수 없습니다.") from exc
    return project_root, target


def _which(command: str, cwd: Path) -> str | None:
    if command.lower() == "npx":
        return shutil.which(command)
    direct = shutil.which(command)
    if direct:
        return direct
    local_bin = cwd / "node_modules" / ".bin" / (command + (".cmd" if os.name == "nt" else ""))
    return str(local_bin) if local_bin.exists() else None


def source_debug_capability(relative_path: str) -> dict[str, Any]:
    suffix = Path(relative_path).suffix.casefold()
    if suffix in {".py", ".pyw"}:
        return {"source": True, "runnable": True, "step_debug": True, "adapter": "Python bdb", "mode": "step"}
    item = SOURCE_RUNNERS.get(suffix) or COMPILED_RUNNERS.get(suffix)
    return {
        "source": bool(item),
        "runnable": bool(item),
        "step_debug": False,
        "adapter": (item or {}).get("label", "Generic source"),
        "mode": "run" if item else "unsupported",
    }


def _run(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(1, min(int(timeout or 120), 600)),
        shell=False,
    )


def run_source_code(*, root: str, relative_path: str, code: str, timeout: int = 120) -> dict[str, Any]:
    project_root, original = _safe_target(root, relative_path)
    suffix = original.suffix.casefold()
    capability = source_debug_capability(relative_path)
    if suffix in {".py", ".pyw"}:
        raise ValueError("Python은 내장 Step Debugger를 사용하세요.")
    if not capability["runnable"]:
        raise ValueError(f"{suffix or '이 파일'}에 연결된 실행 Adapter가 없습니다.")

    original.parent.mkdir(parents=True, exist_ok=True)
    # Keep the temporary file next to the source so relative module/resource paths behave like the real file.
    fd, temp_name = tempfile.mkstemp(prefix=".__agentstudio_debug__", suffix=original.suffix, dir=str(original.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    temp_path.write_text(str(code or ""), encoding="utf-8")
    exe_path = temp_path.with_suffix(".exe" if os.name == "nt" else ".out")
    try:
        if suffix in COMPILED_RUNNERS:
            item = COMPILED_RUNNERS[suffix]
            compiler = [str(part).replace("{file}", str(temp_path)).replace("{exe}", str(exe_path)) for part in item["compiler"]]
            if not _which(compiler[0], project_root):
                raise FileNotFoundError(f"{item['label']} compiler '{compiler[0]}'를 찾지 못했습니다.")
            built = _run(compiler, original.parent, timeout)
            if built.returncode != 0:
                return {"ok": False, "returncode": built.returncode, "stdout": built.stdout, "stderr": built.stderr, "adapter": item["label"], "step_debug": False, "phase": "compile"}
            result = _run([str(exe_path)], original.parent, timeout)
            return {"ok": result.returncode == 0, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "adapter": item["label"], "step_debug": False, "phase": "run"}

        item = SOURCE_RUNNERS[suffix]
        last_missing: str | None = None
        for template in item["commands"]:
            command = [str(part).replace("{file}", str(temp_path)) for part in template]
            executable = _which(command[0], project_root)
            if not executable:
                last_missing = command[0]
                continue
            command[0] = executable
            result = _run(command, original.parent, timeout)
            return {"ok": result.returncode == 0, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "adapter": item["label"], "step_debug": False, "phase": "run", "command": command[:2]}
        raise FileNotFoundError(f"{item['label']} 실행기({last_missing or 'runtime'})를 찾지 못했습니다.")
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            exe_path.unlink(missing_ok=True)
        except Exception:
            pass
