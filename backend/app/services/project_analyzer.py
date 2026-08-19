from __future__ import annotations

import re
from pathlib import Path

from app.core.config import get_settings
from app.services.local_control import _allowed, _is_ignored_project_dir_name

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

async def scan_project(root: str) -> dict:
    base = _allowed(root)
    files = []

    for p in base.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS or _is_ignored_project_dir_name(part) for part in p.parts):
            continue
        if p.suffix.lower() not in TEXT_EXTS and p.name not in IMPORTANT_NAMES:
            continue

        try:
            size = p.stat().st_size
            if size > 1_000_000:
                continue
            content = p.read_text(encoding="utf-8", errors="replace")
            relative = str(p.relative_to(base))
            files.append({
                "path": str(p),
                "relative": relative,
                "language": _language(p),
                "size_bytes": size,
                "symbols": _symbols(p, content),
                "preview": content[:4000],
                "model_references": _extract_model_references(content[:20000]),
                "agent_related": _detect_agent_related(relative, content),
            })
        except Exception:
            continue

    return {"root": str(base), "files": files}

def _terms(request: str) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}|[가-힣]{2,}", (request or "").lower())
    stop = {"수정","추가","만들어","기능","프로그램","코드","해줘","해주세요","사용","파일","프로젝트","분석"}
    return [w for w in words if w not in stop][:30]

async def find_related_files(root: str, request: str, limit: int | None = None) -> dict:
    data = await scan_project(root)
    limit = limit or get_settings().project_analyzer_max_files
    terms = _terms(request)
    ranked = []

    for f in data["files"]:
        haystack = (f["relative"] + " " + " ".join(f["symbols"]) + " " + f["preview"]).lower()
        score = 0
        matched = []
        for term in terms:
            count = haystack.count(term)
            if count:
                score += min(count, 5)
                if term in f["relative"].lower():
                    score += 5
                matched.append(term)
        if f["agent_related"]:
            score += 2
        if Path(f["relative"]).name in IMPORTANT_NAMES:
            score += 2
        ranked.append({**f, "score": score, "matched": matched})

    ranked.sort(key=lambda x: (-x["score"], x["relative"].lower()))
    return {
        "root": data["root"],
        "related_files": ranked[:limit],
        "total_scanned_files": len(data["files"]),
    }

async def local_project_summary(root: str, request: str) -> dict:
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

    related = await find_related_files(root, request, limit=20)
    tech_stack = [name for name, count in sorted(languages.items(), key=lambda x: (-x[1], x[0])) if count > 0]
    project_name = Path(data["root"]).name

    summary = (
        f"{project_name}: 소스 파일 {len(files)}개를 로컬 규칙으로 분석했습니다. "
        f"주요 기술: {', '.join(tech_stack[:8]) if tech_stack else '확인되지 않음'}. "
        "모델은 실행하지 않았으며 소스에 명시된 모델명만 참고 정보로 수집했습니다."
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
        "analysis_mode": "SOURCE_ONLY",
        "llm_called": False,
    }
