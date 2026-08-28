from __future__ import annotations

import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.high_speed_analysis import analyze_project_candidates
from app.services.local_control import _allowed, _is_ignored_project_dir_name, _iter_project_tree

SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".next",
    "dist", "build", "bin", "obj",
    # AgentStudio가 생성하는 실행/진단 산출물은 다음 Agent 설계의 소스 Context가 아닙니다.
    "reports", "debug", "logs", "history", "cache", "temp", "output",
}

TEXT_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".cs", ".java", ".kt",
    ".go", ".rs", ".php", ".rb", ".cpp", ".c", ".h", ".hpp",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".env", ".md",
    ".txt", ".ps1", ".cmd", ".bat", ".sql", ".html", ".css", ".scss",
}

ENTRY_NAMES = {
    "main.py", "app.py", "server.py", "agent.py", "manage.py",
    "index.js", "index.ts", "main.js", "main.ts", "server.js",
    "server.ts", "Program.cs", "Startup.cs", "package.json",
    "docker-compose.yml", "docker-compose.yaml", "pyproject.toml",
}

IMPORTANT_NAMES = {
    "requirements.txt", "pyproject.toml", "package.json",
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
    ".env", ".env.example", "README.md", "readme.md",
    "settings.py", "config.py", "config.json",
}

MODEL_PATTERNS = [
    re.compile(r'(?i)\b(?:model|model_name|llm_model|embedding_model)\b\s*[:=]\s*["\']?([A-Za-z0-9_.:/-]{3,80})["\']?'),
    re.compile(r'(?i)\b(gpt-[A-Za-z0-9_.-]+|qwen[A-Za-z0-9_.:-]*|llama[A-Za-z0-9_.:-]*|mistral[A-Za-z0-9_.:-]*|gemma[A-Za-z0-9_.:-]*|nomic-embed-[A-Za-z0-9_.:-]+|text-embedding-[A-Za-z0-9_.:-]+)\b'),
]

# v5.407: project scanning is now incremental.  Repeated design/build passes usually
# touch only a few files, so unchanged files reuse their parsed preview/symbol metadata.
_SCAN_CACHE: dict[str, dict[str, Any]] = {}
_SCAN_CACHE_LOCK = threading.RLock()


def _language(path: Path) -> str:
    mapping = {
        ".py": "Python", ".js": "JavaScript", ".jsx": "React/JavaScript",
        ".ts": "TypeScript", ".tsx": "React/TypeScript", ".cs": "C#",
        ".java": "Java", ".kt": "Kotlin", ".go": "Go", ".rs": "Rust",
        ".php": "PHP", ".rb": "Ruby", ".cpp": "C++", ".c": "C",
        ".sql": "SQL",
    }
    return mapping.get(path.suffix.lower(), path.suffix.lower().lstrip(".") or "text")


def _symbols(path: Path, content: str) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return re.findall(r"(?m)^\s*(?:async\s+def|def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", content)[:100]
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return re.findall(r"(?m)\b(?:function|class|const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)", content)[:100]
    if suffix == ".cs":
        return re.findall(r"(?m)\b(?:class|interface|record|struct|void|Task|async\s+Task)\s+([A-Za-z_][A-Za-z0-9_]*)", content)[:100]
    return []


def _extract_model_references(content: str) -> list[str]:
    found = []
    seen = set()
    for pattern in MODEL_PATTERNS:
        for match in pattern.findall(content):
            value = match if isinstance(match, str) else match[0]
            value = value.strip().strip("\"'")
            if value and value.casefold() not in seen:
                seen.add(value.casefold())
                found.append(value)
    return found[:30]


def _detect_agent_related(relative: str, content: str) -> bool:
    hay = (relative + "\n" + content[:8000]).lower()
    return any(token in hay for token in (
        "mcp", "model context protocol", "langgraph", "langchain",
        "agent", "tool_call", "tool_calls", "fastapi",
    ))


def _eligible_file(base: Path, path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        relative_parts = path.relative_to(base).parts
    except Exception:
        relative_parts = path.parts
    if any(part in SKIP_DIRS or _is_ignored_project_dir_name(part) for part in relative_parts):
        return False
    return path.suffix.lower() in TEXT_EXTS or path.name in IMPORTANT_NAMES


def _read_index_item(base: Path, path: Path, size: int, mtime_ns: int) -> dict[str, Any] | None:
    if size > 1_000_000:
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        relative = str(path.relative_to(base))
        return {
            "path": str(path),
            "relative": relative,
            "language": _language(path),
            "size_bytes": size,
            "symbols": _symbols(path, content),
            "preview": content[:4000],
            "model_references": _extract_model_references(content[:20000]),
            "agent_related": _detect_agent_related(relative, content),
            "_index_mtime_ns": mtime_ns,
        }
    except Exception:
        return None


async def scan_project(root: str) -> dict:
    started = time.perf_counter()
    base = _allowed(root)
    cache_key = str(base.resolve()).casefold()

    with _SCAN_CACHE_LOCK:
        previous = _SCAN_CACHE.get(cache_key) or {}
        previous_files = previous.get("by_relative") if isinstance(previous.get("by_relative"), dict) else {}

    by_relative: dict[str, dict[str, Any]] = {}
    reused = 0
    skipped_large = 0
    pending: list[tuple[Path, int, int, str]] = []

    # First pass only walks/stats files.  Unchanged source is reused immediately.
    for kind, path, relative_posix in _iter_project_tree(base):
        if kind != "file" or not _eligible_file(base, path):
            continue
        try:
            stat = path.stat()
            size = int(stat.st_size)
            if size > 1_000_000:
                skipped_large += 1
                continue
            relative = str(Path(relative_posix))
            old = previous_files.get(relative)
            if (
                isinstance(old, dict)
                and int(old.get("size_bytes") if old.get("size_bytes") is not None else -1) == size
                and int(old.get("_index_mtime_ns") if old.get("_index_mtime_ns") is not None else -1) == int(stat.st_mtime_ns)
            ):
                by_relative[relative] = old
                reused += 1
                continue
            pending.append((path, size, int(stat.st_mtime_ns), relative))
        except Exception:
            continue

    # Changed files are independent I/O/parse jobs.  Parallel parsing is reserved for
    # genuinely large source sets; on small/medium projects thread scheduling/GIL cost
    # can exceed the I/O saved, so the faster sequential path is selected automatically.
    workers = max(1, min(8, int(os.cpu_count() or 4))) if len(pending) >= 2000 else 1
    reindexed = 0
    if pending and workers == 1:
        for path, size, mtime_ns, relative in pending:
            item = _read_index_item(base, path, size, mtime_ns)
            if item is not None:
                by_relative[relative] = item
                reindexed += 1
    elif pending:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="agentstudio-index") as pool:
            future_map = {
                pool.submit(_read_index_item, base, path, size, mtime_ns): relative
                for path, size, mtime_ns, relative in pending
            }
            for future in as_completed(future_map):
                relative = future_map[future]
                try:
                    item = future.result()
                except Exception:
                    item = None
                if item is not None:
                    by_relative[relative] = item
                    reindexed += 1

    removed = len(set(previous_files) - set(by_relative))
    ordered = [by_relative[key] for key in sorted(by_relative, key=str.casefold)]
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    cache_info = {
        "hit": bool(previous_files) and reindexed == 0 and removed == 0,
        "reused_files": reused,
        "reindexed_files": reindexed,
        "removed_files": removed,
        "skipped_large_files": skipped_large,
        "indexed_files": len(ordered),
        "parallel_workers": workers,
        "elapsed_ms": round(elapsed_ms, 3),
        "mode": "incremental_mtime_size_parallel",
    }

    with _SCAN_CACHE_LOCK:
        _SCAN_CACHE[cache_key] = {
            "by_relative": by_relative,
            "cache": cache_info,
        }

    # Internal index timestamps are not useful to API/LLM consumers.
    public_files = [
        {key: value for key, value in item.items() if not key.startswith("_index_")}
        for item in ordered
    ]
    return {"root": str(base), "files": public_files, "cache": cache_info}


def _terms(request: str) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}|[가-힣]{2,}", (request or "").lower())
    stop = {"수정","추가","만들어","기능","프로그램","코드","해줘","해주세요","사용","파일","프로젝트","분석"}
    return [w for w in words if w not in stop][:30]


async def find_related_files(
    root: str,
    request: str,
    limit: int | None = None,
    *,
    scan_data: dict[str, Any] | None = None,
) -> dict:
    data = scan_data or await scan_project(root)
    limit = limit or get_settings().project_analyzer_max_files
    accelerated = analyze_project_candidates(data, request, limit=limit)
    return {
        "root": data["root"],
        "related_files": accelerated.get("related_files") or [],
        "total_scanned_files": len(data.get("files") or []),
        "analysis_mode": accelerated.get("analysis_mode") or "HIGH_SPEED_LOCAL",
        "high_speed_pipeline": accelerated.get("pipeline") or {},
        "cache": data.get("cache") or {},
    }


async def local_project_summary(root: str, request: str) -> dict:
    # v5.407: one scan per analysis pass.  Previous versions scanned the same project once
    # for the summary and again in find_related_files(), doubling file I/O on every pass.
    data = await scan_project(root)
    files = data["files"]

    languages = {}
    entry_points = []
    major_files = []
    mcp_tools = []
    model_refs = []
    model_seen = set()

    for f in files:
        lang = f.get("language", "")
        if lang:
            languages[lang] = languages.get(lang, 0) + 1

        rel = f["relative"]
        name = Path(rel).name

        if name in ENTRY_NAMES:
            entry_points.append(rel)
        if name in IMPORTANT_NAMES or f.get("agent_related") or f.get("symbols"):
            major_files.append(rel)
        # agent_related 전체를 MCP Tool로 오인하지 않습니다.
        rel_cf = rel.replace("\\", "/").casefold()
        if (
            "/mcp/" in f"/{rel_cf}/"
            or rel_cf.startswith("mcp_")
            or "/tools/" in f"/{rel_cf}/"
            or rel_cf.endswith("_tool.py")
        ):
            mcp_tools.append(rel)

        for model in f.get("model_references", []):
            key = model.casefold()
            if key not in model_seen:
                model_seen.add(key)
                model_refs.append(model)

    related = await find_related_files(root, request, limit=20, scan_data=data)
    tech_stack = [name for name, count in sorted(languages.items(), key=lambda x: (-x[1], x[0])) if count > 0]
    project_name = Path(data["root"]).name
    pipeline = related.get("high_speed_pipeline") or {}
    candidate_count = len(related.get("related_files") or [])
    cache = data.get("cache") or {}

    summary = (
        f"{project_name}: 소스 파일 {len(files)}개를 로컬 고속 분석 Pipeline으로 분석했습니다. "
        f"주요 기술: {', '.join(tech_stack[:8]) if tech_stack else '확인되지 않음'}. "
        f"LLM 전달 전 관련 후보를 {candidate_count}개로 압축했습니다. "
        f"Index Cache 재사용 {int(cache.get('reused_files') or 0)}개 / 재분석 {int(cache.get('reindexed_files') or 0)}개. "
        "1차 분석에서는 LLM/Embedding API를 호출하지 않았습니다."
    )

    return {
        "project_name": project_name,
        "summary": summary,
        "tech_stack": tech_stack,
        "entry_points": entry_points[:30],
        "major_files": list(dict.fromkeys(major_files))[:100],
        "mcp_tools": list(dict.fromkeys(mcp_tools))[:50],
        "model_references": model_refs[:30],
        "related_files": related["related_files"],
        "total_scanned_files": len(files),
        "analysis_mode": "HIGH_SPEED_LOCAL",
        "llm_called": False,
        "embedding_called": False,
        "high_speed_pipeline": pipeline,
        "scan_cache": cache,
    }
