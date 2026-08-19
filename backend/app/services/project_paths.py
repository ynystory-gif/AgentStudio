from pathlib import Path
from app.core.config import get_settings


def _clean(value: str | None) -> str:
    return (value or "").strip()


def resolve_project_paths(
    project_root: str,
    cache_path: str = "",
    temp_path: str = "",
    output_path: str = "",
    venv_path: str = "",
    models_path: str = "",
    create: bool = True,
) -> dict:
    settings = get_settings()

    root_value = _clean(project_root) or _clean(settings.default_project_root)
    if not root_value:
        raise ValueError("프로젝트 경로를 입력하거나 시스템 기본 프로젝트 경로를 설정해야 합니다.")

    root = Path(root_value).expanduser()

    cache = (
        Path(cache_path).expanduser()
        if _clean(cache_path)
        else (
            Path(settings.default_cache_root).expanduser()
            if _clean(settings.default_cache_root)
            else root / "cache"
        )
    )

    temp = (
        Path(temp_path).expanduser()
        if _clean(temp_path)
        else (
            Path(settings.default_temp_root).expanduser()
            if _clean(settings.default_temp_root)
            else root / "temp"
        )
    )

    output = (
        Path(output_path).expanduser()
        if _clean(output_path)
        else (
            Path(settings.default_output_root).expanduser()
            if _clean(settings.default_output_root)
            else root / "output"
        )
    )

    venv = Path(venv_path).expanduser() if _clean(venv_path) else root / "venv"

    models = (
        Path(models_path).expanduser()
        if _clean(models_path)
        else (
            Path(settings.common_models_root).expanduser()
            if _clean(settings.common_models_root)
            else root / "models"
        )
    )

    resolved = {
        "project_root": root,
        "cache_path": cache,
        "temp_path": temp,
        "output_path": output,
        "venv_path": venv,
        "models_path": models,
    }

    if create:
        for p in resolved.values():
            p.mkdir(parents=True, exist_ok=True)

    return {k: str(v.resolve()) for k, v in resolved.items()}
