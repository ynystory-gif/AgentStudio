from __future__ import annotations

import json
from pathlib import Path

from app.services.local_control import read_file
from app.services.patch_service import apply_patch, create_patch


RUNTIME_DIRS = {
    "reports", "debug", "logs", "history", "cache", "temp", "output",
    ".venv", "venv", "node_modules", ".git", "__pycache__",
}


def _project_file_map(project_root: str) -> dict[str, Path]:
    root = Path(project_root).resolve()
    result: dict[str, Path] = {}
    if not root.exists():
        return result
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part.casefold() in RUNTIME_DIRS for part in rel.parts[:-1]):
            continue
        result[rel.as_posix().casefold()] = path
    return result


def _settings_relative_paths(settings_plan: dict) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for group in ("backend", "frontend"):
        for value in (settings_plan.get(group) or {}).values():
            if not isinstance(value, str) or not value.strip():
                continue
            rel = value.replace("\\", "/").lstrip("./")
            key = rel.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(rel)
    return result


def _planned_paths(project_root: str, settings_plan: dict, file_plan: dict) -> list[str]:
    root = Path(project_root).resolve()
    # v5.168: reports/history 등 기존 프로젝트 전체 파일을 Settings Context에 섞지 않습니다.
    return [str((root / rel).resolve()) for rel in _settings_relative_paths(settings_plan)]


async def _read_settings_context(project_root: str, paths: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths[:16]:
        try:
            result[path] = await read_file(path)
        except (FileNotFoundError, IsADirectoryError):
            continue
    return result


async def generate_settings_artifacts(
    project_root: str,
    request: str,
    settings_plan: dict,
    file_plan: dict,
    provider: str | None = None,
) -> dict:
    if not settings_plan.get("enabled"):
        return {
            "enabled": False,
            "changes": [],
            "ok": True,
            "message": "생성 대상 Agent에 별도 Settings UI가 필요하지 않습니다.",
        }

    root = Path(project_root).resolve()
    targets = _settings_relative_paths(settings_plan)
    existing_map = _project_file_map(project_root)
    missing = [rel for rel in targets if rel.casefold() not in existing_map]

    # Code Generation이 Settings 파일까지 이미 만들었다면 같은 코드를 다시 LLM에 생성시키지 않습니다.
    if not missing:
        return {
            "enabled": True,
            "changes": [],
            "ok": True,
            "skipped": True,
            "existing_target_count": len(targets),
            "missing_targets": [],
            "message": "Code Generation에서 Settings 파일이 이미 생성되어 중복 LLM 생성을 생략했습니다.",
        }

    existing_paths = [
        str(existing_map[rel.casefold()])
        for rel in targets
        if rel.casefold() in existing_map
    ]
    files = await _read_settings_context(project_root, existing_paths)

    prompt = (
        request
        + "\n\n[Settings Generator 전용 설계]\n"
        + json.dumps(settings_plan, ensure_ascii=False, indent=2)
        + "\n\n[이번 실행에서 누락된 Settings 파일]\n"
        + json.dumps(missing, ensure_ascii=False, indent=2)
        + "\n\n[절대 규칙]\n"
        "1. 위 누락 파일만 생성/수정합니다. 이미 존재하는 Settings 파일을 중복 생성하지 않습니다.\n"
        "2. Backend는 Settings Model/Schema/Service/Router 책임을 분리합니다.\n"
        "3. React Settings Page와 API Client를 Backend Settings API와 연결합니다.\n"
        "4. Secret은 GET에서 평문 반환하지 말고 masked/has_value 방식으로 처리합니다.\n"
        "5. .env.example에는 실제 Secret을 쓰지 않습니다.\n"
        "6. settings_plan 경로는 프로젝트 루트 기준 상대경로이며 대소문자까지 그대로 사용합니다.\n"
        "7. 신규 파일은 create_file=true와 content를 사용합니다.\n"
    )

    plan = await create_patch(prompt, files, provider, project_scope=True)
    # apply_patch에 project_root를 반드시 전달해 잘못된 절대경로 생성을 차단합니다.
    changes = await apply_patch(plan, project_root=project_root)

    return {
        "enabled": True,
        "plan": plan,
        "changes": changes,
        "ok": True,
        "skipped": False,
        "missing_targets": missing,
        "message": "누락된 Settings Generator 코드 생성이 완료되었습니다.",
    }


async def validate_settings_artifacts(project_root: str, settings_plan: dict) -> dict:
    if not settings_plan.get("enabled"):
        return {"ok": True, "enabled": False, "checks": []}

    root = Path(project_root).resolve()
    existing_map = _project_file_map(project_root)
    checks = []

    for group in ("backend", "frontend"):
        values = settings_plan.get(group) or {}
        for key, value in values.items():
            if not isinstance(value, str) or not value.strip():
                continue
            rel = value.replace("\\", "/").lstrip("./")
            actual = existing_map.get(rel.casefold())
            checks.append({
                "type": "file_exists",
                "group": group,
                "key": key,
                "relative_path": rel,
                "path": str(actual or (root / rel).resolve()),
                "ok": actual is not None and actual.is_file(),
            })

    env_example = root / ".env.example"
    if env_example.exists():
        text = env_example.read_text(encoding="utf-8", errors="replace")
        suspicious = [
            line for line in text.splitlines()
            if (
                "=" in line
                and not line.lstrip().startswith("#")
                and any(token in line.upper() for token in ("API_KEY", "PASSWORD", "TOKEN", "SECRET"))
                and line.split("=", 1)[1].strip() not in ("", "your-key-here", "change-me")
            )
        ]
        checks.append({
            "type": "env_example_secret_scan",
            "path": str(env_example),
            "ok": not suspicious,
            "detail": suspicious,
        })

    return {
        "ok": all(item.get("ok") for item in checks),
        "enabled": True,
        "checks": checks,
    }
