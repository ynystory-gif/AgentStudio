from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import get_settings

_ORIGINAL_TEMP_ROOT = Path(tempfile.gettempdir()).expanduser().resolve()
_PATH_KEYS = {"DEFAULT_TEMP_ROOT", "DEFAULT_CACHE_ROOT", "DEFAULT_OUTPUT_ROOT"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _ensure_dir(value: str | Path | None) -> Path | None:
    raw = _clean(value)
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _env_paths() -> dict[str, str]:
    path = _env_path()
    if not path.exists():
        return {}
    out = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        if key in _PATH_KEYS:
            out[key] = value.strip()
    return out


def _project_root(project_root: str = "") -> Path | None:
    if _clean(project_root):
        return _ensure_dir(project_root)
    return _ensure_dir(get_settings().default_project_root)


def resolve_temp_root(project_root: str = "") -> Path:
    configured = _ensure_dir(get_settings().default_temp_root)
    if configured:
        return configured
    project = _project_root(project_root)
    if project:
        return _ensure_dir(project / "temp") or project / "temp"
    _ORIGINAL_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return _ORIGINAL_TEMP_ROOT


def resolve_cache_root(project_root: str = "") -> Path:
    configured = _ensure_dir(get_settings().default_cache_root)
    if configured:
        return configured
    project = _project_root(project_root)
    if project:
        return _ensure_dir(project / "cache") or project / "cache"
    return _ensure_dir(Path.home() / ".cache" / "theanova-agentstudio") or Path.home()


def resolve_output_root(project_root: str = "") -> Path:
    configured = _ensure_dir(get_settings().default_output_root)
    if configured:
        return configured
    project = _project_root(project_root)
    if project:
        return _ensure_dir(project / "output") or project / "output"
    return _ensure_dir(Path.cwd() / "output") or Path.cwd()


def _apply_cache(cache_root: Path) -> dict[str, str]:
    mapping = {
        "XDG_CACHE_HOME": cache_root,
        "HF_HOME": cache_root / "huggingface",
        "HUGGINGFACE_HUB_CACHE": cache_root / "huggingface" / "hub",
        "TRANSFORMERS_CACHE": cache_root / "huggingface" / "transformers",
        "TORCH_HOME": cache_root / "torch",
        "PIP_CACHE_DIR": cache_root / "pip",
        "NPM_CONFIG_CACHE": cache_root / "npm",
        "UV_CACHE_DIR": cache_root / "uv",
        "MPLCONFIGDIR": cache_root / "matplotlib",
        "NUMBA_CACHE_DIR": cache_root / "numba",
        "KERAS_HOME": cache_root / "keras",
        "EASYOCR_MODULE_PATH": cache_root / "easyocr",
        "AGENTSTUDIO_CACHE_ROOT": cache_root,
    }
    out = {}
    for key, value in mapping.items():
        path = _ensure_dir(value) or Path(value)
        os.environ[key] = str(path)
        out[key] = str(path)
    return out


def apply_runtime_path_policy(project_root: str = "") -> dict[str, Any]:
    temp_root = resolve_temp_root(project_root)
    cache_root = resolve_cache_root(project_root)
    output_root = resolve_output_root(project_root)
    for key in ("TEMP", "TMP", "TMPDIR"):
        os.environ[key] = str(temp_root)
    os.environ["AGENTSTUDIO_TEMP_ROOT"] = str(temp_root)
    os.environ["AGENTSTUDIO_OUTPUT_ROOT"] = str(output_root)
    tempfile.tempdir = str(temp_root)
    cache_env = _apply_cache(cache_root)
    return {"temp_root": str(temp_root), "cache_root": str(cache_root), "output_root": str(output_root), "cache_env": cache_env}


def bootstrap_runtime_paths_from_env_file() -> dict[str, str]:
    values = _env_paths()
    temp_root = _ensure_dir(values.get("DEFAULT_TEMP_ROOT"))
    cache_root = _ensure_dir(values.get("DEFAULT_CACHE_ROOT"))
    output_root = _ensure_dir(values.get("DEFAULT_OUTPUT_ROOT"))
    if temp_root:
        for key in ("TEMP", "TMP", "TMPDIR"):
            os.environ[key] = str(temp_root)
        os.environ["AGENTSTUDIO_TEMP_ROOT"] = str(temp_root)
        tempfile.tempdir = str(temp_root)
    if cache_root:
        _apply_cache(cache_root)
    if output_root:
        os.environ["AGENTSTUDIO_OUTPUT_ROOT"] = str(output_root)
    return {"temp_root": str(temp_root or ""), "cache_root": str(cache_root or ""), "output_root": str(output_root or "")}


def _safe_name(filename: str, default="download.bin") -> str:
    name = Path(str(filename or "").replace("\\", "/")).name.strip() or default
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip(" .")
    return (name or default)[:180]


def _safe_category(category: str) -> str:
    value = re.sub(r"[^a-z0-9._-]+", "_", str(category or "downloads").lower()).strip("._-")
    return value or "downloads"


def save_output_bytes(data: bytes, filename: str, category="downloads", project_root="") -> dict[str, Any]:
    root = resolve_output_root(project_root)
    folder = (root / _safe_category(category)).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    target = (folder / _safe_name(filename)).resolve()
    target.relative_to(root)
    stem, suffix, seq = target.stem, target.suffix, 2
    while target.exists():
        target = folder / f"{stem}_{seq}{suffix}"
        seq += 1
    temp_file = resolve_temp_root(project_root) / f".agentstudio-output-{os.getpid()}-{target.name}.tmp"
    temp_file.write_bytes(data)
    try:
        try:
            os.replace(temp_file, target)
        except OSError:
            shutil.copyfile(temp_file, target)
            temp_file.unlink(missing_ok=True)
    finally:
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)
    return {"ok": True, "path": str(target), "output_root": str(root), "relative_path": target.relative_to(root).as_posix(), "bytes": len(data)}


def save_output_text(text: str, filename: str, category="downloads", project_root="") -> dict[str, Any]:
    content = str(text or "")
    if content and not content.endswith("\n"):
        content += "\n"
    result = save_output_bytes(content.encode("utf-8"), filename, category, project_root)
    result["encoding"] = "utf-8"
    return result
