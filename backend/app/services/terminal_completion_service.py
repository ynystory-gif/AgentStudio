from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_MAX_ITEMS = 80
_COMMAND_CACHE: tuple[str, list[str]] | None = None

_POWERSHELL_WORDS = [
    "Get-ChildItem", "Get-Location", "Set-Location", "Get-Content",
    "Set-Content", "Add-Content", "Copy-Item", "Move-Item", "Remove-Item",
    "New-Item", "Test-Path", "Resolve-Path", "Get-Command", "Get-Process",
    "Stop-Process", "Get-Service", "Start-Service", "Stop-Service",
    "Select-String", "Where-Object", "ForEach-Object", "Write-Host",
    "Write-Output", "Clear-Host", "Invoke-WebRequest", "Invoke-RestMethod",
    "python", "py", "pip", "pytest", "node", "npm", "npx", "git",
    "docker", "docker-compose", "uvicorn", "ollama", "code", "cls",
    "cd", "dir", "ls", "cat", "type", "echo", "mkdir", "rmdir",
]

_TOKEN_BREAK_RE = re.compile(r"[\s;|&]", re.UNICODE)


def _safe_cwd(root: str, cwd: str | None) -> Path:
    candidate = Path(cwd or root).expanduser()
    try:
        candidate = candidate.resolve()
    except Exception:
        candidate = Path(root).expanduser().resolve()
    if not candidate.exists() or not candidate.is_dir():
        candidate = Path(root).expanduser().resolve()
    return candidate


def _token_range(buffer: str, cursor: int) -> tuple[int, int, str]:
    cursor = max(0, min(int(cursor), len(buffer)))
    start = cursor
    while start > 0 and not _TOKEN_BREAK_RE.match(buffer[start - 1]):
        start -= 1
    end = cursor
    while end < len(buffer) and not _TOKEN_BREAK_RE.match(buffer[end]):
        end += 1
    return start, end, buffer[start:cursor]


def _path_commands() -> list[str]:
    global _COMMAND_CACHE
    path_value = os.environ.get("PATH", "")
    if _COMMAND_CACHE and _COMMAND_CACHE[0] == path_value:
        return _COMMAND_CACHE[1]

    names: set[str] = set(_POWERSHELL_WORDS)
    pathext = [x.lower() for x in os.environ.get("PATHEXT", ".EXE;.CMD;.BAT;.COM;.PS1").split(";") if x]

    for raw_dir in path_value.split(os.pathsep):
        raw_dir = raw_dir.strip().strip('"')
        if not raw_dir:
            continue
        directory = Path(raw_dir)
        try:
            if not directory.is_dir():
                continue
            for item in directory.iterdir():
                if not item.is_file():
                    continue
                suffix = item.suffix.lower()
                if os.name == "nt":
                    if suffix not in pathext:
                        continue
                    names.add(item.stem if suffix in {".exe", ".com"} else item.name)
                elif os.access(item, os.X_OK):
                    names.add(item.name)
        except Exception:
            continue

    result = sorted(names, key=str.casefold)
    _COMMAND_CACHE = (path_value, result)
    return result


def _is_command_position(buffer: str, start: int) -> bool:
    before = buffer[:start].rstrip()
    if not before:
        return True
    # New command after common PowerShell separators.
    return before.endswith((";", "|", "&&", "||"))


def _looks_like_path(token: str) -> bool:
    if token == "":
        return True
    lowered = token.lower()
    return (
        "\\" in token
        or "/" in token
        or lowered.startswith((".", "~", "'", '"'))
        or bool(re.match(r"^[a-zA-Z]:", token))
    )


def _path_suggestions(cwd: Path, token: str) -> list[dict[str, Any]]:
    quote = ""
    clean = token
    if clean.startswith(("'", '"')):
        quote, clean = clean[0], clean[1:]

    normalized = clean.replace("/", os.sep).replace("\\", os.sep)
    expanded = os.path.expandvars(os.path.expanduser(normalized))

    if os.path.isabs(expanded):
        target = Path(expanded)
    else:
        target = cwd / expanded

    partial = target.name if clean and not clean.endswith(("\\", "/")) else ""
    parent = target.parent if partial else target

    # Preserve the exact prefix typed by the user (./ vs .\\ etc.).
    typed_parent = clean[:-len(partial)] if partial else clean

    items: list[dict[str, Any]] = []
    try:
        children = sorted(parent.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))
    except Exception:
        return []

    for child in children:
        if partial and not child.name.casefold().startswith(partial.casefold()):
            continue
        is_dir = child.is_dir()
        separator = "\\" if "\\" in clean or os.name == "nt" else "/"
        inserted = typed_parent + child.name + (separator if is_dir else "")
        if quote:
            inserted = quote + inserted
        items.append({
            "label": child.name + (separator if is_dir else ""),
            "insert_text": inserted,
            "kind": "folder" if is_dir else "file",
            "detail": str(child),
        })
        if len(items) >= _MAX_ITEMS:
            break
    return items


def complete_terminal_input(
    *,
    root: str,
    cwd: str | None,
    buffer: str,
    cursor: int,
) -> dict[str, Any]:
    project_root = Path(root).expanduser().resolve()
    if not project_root.exists() or not project_root.is_dir():
        raise FileNotFoundError(str(project_root))

    current_dir = _safe_cwd(str(project_root), cwd)
    start, end, token = _token_range(str(buffer or ""), int(cursor or 0))

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    if _looks_like_path(token):
        for item in _path_suggestions(current_dir, token):
            key = (item["kind"], item["insert_text"].casefold())
            if key not in seen:
                seen.add(key)
                items.append(item)

    if _is_command_position(str(buffer or ""), start) and not any(ch in token for ch in "\\/"):
        needle = token.strip("'\"").casefold()
        for command in _path_commands():
            if needle and not command.casefold().startswith(needle):
                continue
            key = ("command", command.casefold())
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "label": command,
                "insert_text": command,
                "kind": "command",
                "detail": "PowerShell / PATH command",
            })
            if len(items) >= _MAX_ITEMS:
                break

    # Keep folders/files first for path-like tokens, otherwise commands first.
    if not _looks_like_path(token):
        rank = {"command": 0, "folder": 1, "file": 2}
        items.sort(key=lambda x: (rank.get(x.get("kind"), 9), str(x.get("label", "")).casefold()))

    return {
        "ok": True,
        "cwd": str(current_dir),
        "buffer": str(buffer or ""),
        "cursor": max(0, min(int(cursor or 0), len(str(buffer or "")))),
        "replace_start": start,
        "replace_end": end,
        "token": token,
        "items": items[:_MAX_ITEMS],
    }
