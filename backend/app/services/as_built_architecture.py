from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

_SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".json", ".toml", ".yaml", ".yml", ".sql", ".md",
}
_EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "logs", "cache", "temp", "tmp", "output", "reports", "debug",
}
_MAX_FILES = 320
_MAX_TEXT_PER_FILE = 32_000


def _norm(path: str) -> str:
    return str(path or "").replace("\\", "/").strip("/")


def _label(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("label", "name", "component", "title", "path"):
            value = str(item.get(key) or "").strip()
            if value:
                return value
    return ""


def _tokens(value: str) -> set[str]:
    stop = {
        "agent", "service", "component", "layer", "manager", "core", "the", "and",
        "에이전트", "서비스", "구성", "요소", "계층", "관리", "모듈",
    }
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9_가-힣]+", value or "")
        if len(token) >= 2 and token.casefold() not in stop
    }


def _text_match(expected: str, actual_values: list[str]) -> bool:
    expected_tokens = _tokens(expected)
    if not expected_tokens:
        return False
    for actual in actual_values:
        actual_tokens = _tokens(actual)
        if expected_tokens & actual_tokens:
            return True
        if expected.casefold() in actual.casefold() or actual.casefold() in expected.casefold():
            return True
    return False


def _iter_project_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    for path in root.rglob("*"):
        if len(rows) >= _MAX_FILES:
            break
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part.casefold() in _EXCLUDED_DIRS for part in rel.parts[:-1]):
            continue
        if path.suffix.casefold() not in _SOURCE_EXTENSIONS:
            continue
        rows.append(path)
    return rows


def _python_symbols(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {"classes": [], "functions": [], "imports": [], "routes": []}
    try:
        tree = ast.parse(text)
    except Exception:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            out["classes"].append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out["functions"].append(node.name)
            for deco in node.decorator_list:
                try:
                    rendered = ast.unparse(deco)
                except Exception:
                    rendered = ""
                if any(x in rendered for x in (".get", ".post", ".put", ".delete", ".patch", ".websocket")):
                    out["routes"].append(f"{node.name}:{rendered}")
        elif isinstance(node, ast.Import):
            out["imports"].extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out["imports"].append(node.module)
    return out


def _file_evidence(root: Path, path: Path) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:_MAX_TEXT_PER_FILE]
    except Exception:
        text = ""
    lowered = text.casefold()
    symbols: dict[str, Any] = {}
    if path.suffix.casefold() == ".py":
        symbols = _python_symbols(text)
    else:
        symbols = {
            "classes": re.findall(r"\bclass\s+([A-Za-z_$][\w$]*)", text)[:30],
            "functions": re.findall(r"\b(?:function\s+|const\s+)([A-Za-z_$][\w$]*)", text)[:50],
            "imports": re.findall(r"(?:from\s+['\"]([^'\"]+)|require\(['\"]([^'\"]+))", text)[:40],
            "routes": re.findall(r"\.(?:get|post|put|delete|patch)\(['\"]([^'\"]+)", text)[:30],
        }

    markers: list[str] = []
    marker_patterns = {
        "FastAPI": ["fastapi", "apirouter", "uvicorn"],
        "React": ["react", "usestate", "useeffect", "jsx"],
        "Vite": ["vite"],
        "LangGraph": ["langgraph", "stategraph", "add_conditional_edges"],
        "LangChain": ["langchain"],
        "MCP": ["mcp", "stdio", "streamablehttp"],
        "PostgreSQL": ["psycopg", "postgresql", "sqlalchemy"],
        "pgvector": ["pgvector", "vector("],
        "Redis": ["redis"],
        "Firestore": ["firestore"],
        "OpenAI": ["openai"],
        "Ollama": ["ollama"],
        "WebSocket": ["websocket"],
        "SSE": ["eventsource", "text/event-stream", "sse"],
        "Pydantic": ["pydantic", "basemodel"],
        "Secrets/Env": ["os.getenv", "dotenv", "secret", "api_key", "password"],
    }
    for label, needles in marker_patterns.items():
        if any(needle in lowered for needle in needles):
            markers.append(label)

    return {
        "path": rel,
        "size": path.stat().st_size,
        "markers": markers,
        "classes": list(symbols.get("classes") or [])[:20],
        "functions": list(symbols.get("functions") or [])[:30],
        "imports": [x for x in (symbols.get("imports") or []) if x][:30],
        "routes": list(symbols.get("routes") or [])[:20],
    }


def _detected_component_rows(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[tuple[str, str, tuple[str, ...]]] = [
        ("Frontend UI", "사용자 화면 / Client 인터페이스", ("React", "Vite")),
        ("FastAPI Backend", "HTTP API / Backend 실행 계층", ("FastAPI",)),
        ("LangGraph Orchestrator", "State / Branch / Retry Workflow", ("LangGraph",)),
        ("LLM Integration", "LLM Provider 호출 계층", ("OpenAI", "Ollama", "LangChain")),
        ("MCP / Tool Layer", "MCP Server/Client 또는 Tool 실행", ("MCP",)),
        ("Persistence Layer", "DB / Cache / Vector 영속성", ("PostgreSQL", "pgvector", "Redis", "Firestore")),
        ("Realtime Layer", "WebSocket / SSE 실시간 통신", ("WebSocket", "SSE")),
        ("Validation / Schema", "입력 Schema / Validation", ("Pydantic",)),
        ("Configuration / Secret", "환경설정 / Secret 처리", ("Secrets/Env",)),
    ]
    rows: list[dict[str, Any]] = []
    for name, purpose, markers in groups:
        files = [item["path"] for item in evidence if any(marker in item.get("markers", []) for marker in markers)]
        if files:
            rows.append({"name": name, "purpose": purpose, "files": files[:12], "evidence_count": len(files)})
    return rows


def build_as_built_architecture(
    project_root: str,
    design_architecture: dict | None = None,
    file_plan: dict | None = None,
) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"프로젝트 경로를 찾을 수 없습니다: {root}")

    files = _iter_project_files(root)
    evidence = [_file_evidence(root, path) for path in files]
    fingerprint_source = "\n".join(
        f"{item.get('path','')}|{item.get('size',0)}|{(root / item.get('path','')).stat().st_mtime_ns if (root / item.get('path','')).is_file() else 0}"
        for item in evidence
    )
    source_fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8", errors="replace")).hexdigest()
    existing = {item["path"].casefold(): item for item in evidence}

    component_file_map = list((file_plan or {}).get("component_file_map") or [])
    mapped_components: list[dict[str, Any]] = []
    for row in component_file_map:
        if not isinstance(row, dict):
            continue
        component = str(row.get("component") or "").strip()
        planned_files = [_norm(x) for x in row.get("files") or [] if str(x or "").strip()]
        found = [path for path in planned_files if path.casefold() in existing or (root / path).is_file()]
        mapped_components.append({
            "name": component or "Unnamed component",
            "purpose": "Design Architecture의 component_file_map 기반 실제 구현 확인",
            "planned_files": planned_files,
            "files": found,
            "status": "implemented" if found else "missing",
        })

    detected = _detected_component_rows(evidence)
    component_names = {str(row.get("name") or "").casefold() for row in mapped_components}
    for row in detected:
        if str(row.get("name") or "").casefold() not in component_names:
            mapped_components.append(row | {"status": "detected"})

    marker_to_files: dict[str, list[str]] = {}
    for item in evidence:
        for marker in item.get("markers", []):
            marker_to_files.setdefault(marker, []).append(item["path"])

    interfaces: list[dict[str, Any]] = []
    for marker, label, purpose in [
        ("FastAPI", "HTTP API", "FastAPI route/interface"),
        ("React", "React UI", "사용자 화면"),
        ("MCP", "MCP", "Tool/MCP interface"),
        ("WebSocket", "WebSocket", "양방향 실시간 interface"),
        ("SSE", "SSE", "서버 이벤트 스트림"),
    ]:
        if marker_to_files.get(marker):
            interfaces.append({"name": label, "purpose": purpose, "files": marker_to_files[marker][:10]})

    persistence: list[dict[str, Any]] = []
    for marker in ("PostgreSQL", "pgvector", "Redis", "Firestore"):
        if marker_to_files.get(marker):
            persistence.append({"name": marker, "purpose": "실제 소스에서 감지된 영속성/데이터 계층", "files": marker_to_files[marker][:10]})

    security: list[dict[str, Any]] = []
    if marker_to_files.get("Secrets/Env"):
        security.append({"name": "Environment / Secret handling", "purpose": "환경변수/Secret 처리 코드 감지", "files": marker_to_files["Secrets/Env"][:10]})

    state: list[dict[str, Any]] = []
    if marker_to_files.get("LangGraph"):
        state.append({"name": "LangGraph State", "purpose": "StateGraph/분기 기반 상태 관리", "files": marker_to_files["LangGraph"][:10]})
    if marker_to_files.get("Redis"):
        state.append({"name": "Redis Runtime State", "purpose": "실행/세션 상태 저장 가능성", "files": marker_to_files["Redis"][:10]})

    required_rows = []
    for row in (file_plan or {}).get("new_files") or []:
        if not isinstance(row, dict) or not row.get("required", True):
            continue
        path = _norm(row.get("path") or "")
        if not path:
            continue
        required_rows.append({
            "path": path,
            "purpose": row.get("purpose") or "",
            "exists": (root / path).is_file(),
        })

    return {
        "project_root": str(root),
        "scan": {
            "source_file_count": len(evidence),
            "truncated": len(files) >= _MAX_FILES,
            "excluded_dirs": sorted(_EXCLUDED_DIRS),
        },
        "components": mapped_components,
        "interfaces": interfaces,
        "persistence": persistence,
        "security": security,
        "state": state,
        "frameworks": sorted(marker_to_files),
        "files": evidence,
        "required_files": required_rows,
        "design_component_count": len(list((design_architecture or {}).get("components") or [])),
        "analysis_mode": "deterministic_static_scan",
        "source_fingerprint": source_fingerprint,
    }


def _merge_unique_rows(base: list[dict[str, Any]], incoming: Any) -> list[dict[str, Any]]:
    rows = list(base)
    seen = {_label(row).casefold() for row in rows if _label(row)}
    for item in incoming or []:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            continue
        label = _label(item)
        if not label or label.casefold() in seen:
            continue
        rows.append(item)
        seen.add(label.casefold())
    return rows


async def analyze_as_built_architecture(
    project_root: str,
    design_architecture: dict | None = None,
    file_plan: dict | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Create an evidence-backed As-Built Architecture.

    A deterministic scan is authoritative. A high-performance provider may add
    semantic labels, but it is explicitly forbidden to invent components without
    file evidence. Provider failure never blocks the static analyzer.
    """
    base = build_as_built_architecture(project_root, design_architecture, file_plan)
    compact = {
        "design_architecture": design_architecture or {},
        "detected_components": base.get("components") or [],
        "interfaces": base.get("interfaces") or [],
        "persistence": base.get("persistence") or [],
        "state": base.get("state") or [],
        "frameworks": base.get("frameworks") or [],
        "files": [
            {k: row.get(k) for k in ("path", "markers", "classes", "functions", "routes")}
            for row in (base.get("files") or [])[:120]
        ],
    }
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.services.model_router import LLMTask, model_for_task

        llm = model_for_task(LLMTask.ARCHITECTURE_CONFORMANCE, provider)
        result = await llm.ainvoke([
            SystemMessage(content=(
                "당신은 생성 완료된 Agent 코드의 As-Built Architecture 분석기입니다. "
                "반드시 제공된 파일 증거만 사용하고 존재하지 않는 구성요소를 추측하지 마십시오. "
                "JSON 하나만 반환하십시오. 형식: "
                '{"components":[],"interfaces":[],"persistence":[],"security":[],"state":[],"notes":[]}. '
                "각 항목은 name, purpose, files를 포함할 수 있으며 files는 제공된 실제 경로만 사용하십시오."
            )),
            HumanMessage(content=json.dumps(compact, ensure_ascii=False)),
        ])
        text = str(getattr(result, "content", "") or "").strip()
        match = re.search(r"\{.*\}", text, re.S)
        parsed = json.loads(match.group(0) if match else text)
        for key in ("components", "interfaces", "persistence", "security", "state"):
            base[key] = _merge_unique_rows(list(base.get(key) or []), parsed.get(key))
        base["notes"] = list(parsed.get("notes") or [])
        base["analysis_mode"] = "deterministic_static_scan+llm_semantic_review"
        base["analysis_provider"] = getattr(llm, "last_provider", "")
    except Exception as exc:
        base["analysis_provider"] = "deterministic_fallback"
        base["analysis_error"] = f"{type(exc).__name__}: {exc}"
    return base


def compare_architectures(
    design_architecture: dict | None,
    as_built: dict | None,
    file_plan: dict | None,
) -> dict[str, Any]:
    design = design_architecture or {}
    actual = as_built or {}
    file_plan = file_plan or {}

    actual_components = list(actual.get("components") or [])
    actual_component_labels = [_label(row) for row in actual_components if _label(row)]
    actual_interfaces = [_label(row) for row in actual.get("interfaces") or [] if _label(row)]
    actual_persistence = [_label(row) for row in actual.get("persistence") or [] if _label(row)]
    actual_security = [_label(row) for row in actual.get("security") or [] if _label(row)]
    actual_state = [_label(row) for row in actual.get("state") or [] if _label(row)]

    mapped = {str(row.get("name") or "").casefold(): row for row in actual_components if isinstance(row, dict)}
    component_results = []
    for item in design.get("components") or []:
        expected = _label(item)
        if not expected:
            continue
        direct = mapped.get(expected.casefold())
        implemented = bool(direct and direct.get("status") in {"implemented", "detected"})
        if not implemented:
            implemented = _text_match(expected, actual_component_labels)
        component_results.append({"expected": expected, "status": "matched" if implemented else "missing"})

    def semantic_results(category: str, expected_rows: Any, actual_labels: list[str]) -> list[dict[str, str]]:
        rows = []
        for item in expected_rows or []:
            expected = _label(item)
            if expected:
                rows.append({
                    "category": category,
                    "expected": expected,
                    "status": "matched" if _text_match(expected, actual_labels) else "missing",
                })
        return rows

    interface_results = semantic_results("interface", design.get("interfaces"), actual_interfaces)
    persistence_results = semantic_results("persistence", design.get("persistence"), actual_persistence)
    security_results = semantic_results("security", design.get("security"), actual_security)
    state_results = semantic_results("state", design.get("state"), actual_state)

    required_files = []
    for row in file_plan.get("new_files") or []:
        if not isinstance(row, dict) or not row.get("required", True):
            continue
        path = _norm(row.get("path") or "")
        if path:
            required_files.append(path)
    actual_required = {str(row.get("path") or "").casefold(): bool(row.get("exists")) for row in actual.get("required_files") or [] if isinstance(row, dict)}
    file_results = [
        {"path": path, "status": "matched" if actual_required.get(path.casefold(), False) else "missing"}
        for path in required_files
    ]

    categories = [
        ("components", component_results, 35),
        ("required_files", file_results, 30),
        ("interfaces", interface_results, 10),
        ("persistence", persistence_results, 10),
        ("state", state_results, 10),
        ("security", security_results, 5),
    ]
    weighted_total = 0.0
    active_weight = 0
    for _name, rows, weight in categories:
        if not rows:
            continue
        active_weight += weight
        matched = sum(1 for row in rows if row.get("status") == "matched")
        weighted_total += weight * (matched / len(rows))
    score = round((weighted_total / active_weight * 100) if active_weight else 100.0, 1)

    mismatches: list[dict[str, Any]] = []
    for row in component_results:
        if row["status"] == "missing":
            mismatches.append({"type": "missing_component", "severity": "critical", **row})
    for row in file_results:
        if row["status"] == "missing":
            mismatches.append({"type": "missing_required_file", "severity": "critical", **row})
    for rows in (interface_results, persistence_results, state_results, security_results):
        for row in rows:
            if row["status"] == "missing":
                mismatches.append({"type": f"missing_{row['category']}", "severity": "warning", **row})

    critical = [row for row in mismatches if row.get("severity") == "critical"]
    passed = score >= 85 and not critical
    return {
        "ok": passed,
        "score": score,
        "threshold": 85,
        "status": "PASS" if passed else "FAIL",
        "component_results": component_results,
        "required_file_results": file_results,
        "interface_results": interface_results,
        "persistence_results": persistence_results,
        "state_results": state_results,
        "security_results": security_results,
        "mismatches": mismatches,
        "critical_count": len(critical),
        "warning_count": len(mismatches) - len(critical),
    }
