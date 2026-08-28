from __future__ import annotations

import ast
import importlib.util
import math
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}|[가-힣]{2,}")
IMPORT_RE = re.compile(
    r"(?m)(?:import\s+(?:[^'\"\n]+?\s+from\s+)?|from\s+)[\"']([^\"']+)[\"']|require\(\s*[\"']([^\"']+)[\"']\s*\)"
)

STOP_TERMS = {
    "수정", "추가", "만들어", "기능", "프로그램", "코드", "해줘", "해주세요", "사용",
    "파일", "프로젝트", "분석", "설계", "진행", "개발", "생성", "적용", "관련", "확인",
    "the", "and", "for", "with", "from", "this", "that", "file", "project", "code",
}


_INDEX_CACHE_LOCK = threading.RLock()
_TOKEN_CACHE: dict[tuple[str, str, int, int], tuple[list[str], Counter[str]]] = {}
_GRAPH_CACHE: dict[str, tuple[int, dict[int, set[int]], dict[int, set[int]], str]] = {}


def _file_cache_key(root: str, item: dict[str, Any]) -> tuple[str, str, int, int]:
    relative = str(item.get("relative") or "")
    size = int(item.get("size_bytes") or 0)
    preview = str(item.get("preview") or "")
    # hash() is process-local and intentionally cheap; cache lifetime is process-local too.
    return (str(root or "").casefold(), relative.casefold(), size, hash(preview))


def _cached_doc_tokens(root: str, item: dict[str, Any]) -> tuple[list[str], Counter[str]]:
    key = _file_cache_key(root, item)
    with _INDEX_CACHE_LOCK:
        cached = _TOKEN_CACHE.get(key)
    if cached is not None:
        return cached
    tokens = _tokens(_doc_text(item))
    value = (tokens, Counter(tokens))
    with _INDEX_CACHE_LOCK:
        _TOKEN_CACHE[key] = value
        # Bound memory for long-running Studio sessions that open many projects.
        if len(_TOKEN_CACHE) > 50000:
            for old_key in list(_TOKEN_CACHE)[:10000]:
                _TOKEN_CACHE.pop(old_key, None)
    return value


def _project_fingerprint(files: list[dict[str, Any]]) -> int:
    return hash(tuple(
        (str(item.get("relative") or "").casefold(), int(item.get("size_bytes") or 0), hash(str(item.get("preview") or "")))
        for item in files
    ))

def _tokens(value: str) -> list[str]:
    return [
        token.casefold()
        for token in TOKEN_RE.findall(str(value or ""))
        if token.casefold() not in STOP_TERMS
    ]


def _query_terms(request: str) -> list[str]:
    # Order-preserving de-duplication keeps the first user wording as the dominant signal.
    return list(dict.fromkeys(_tokens(request)))[:40]


def _doc_text(item: dict[str, Any]) -> str:
    return "\n".join(
        [
            str(item.get("relative") or ""),
            " ".join(str(x) for x in (item.get("symbols") or [])),
            str(item.get("preview") or ""),
        ]
    )


def _bm25_scores(root: str, files: list[dict[str, Any]], query_terms: list[str]) -> list[float]:
    if not files or not query_terms:
        return [0.0] * len(files)

    cached_docs = [_cached_doc_tokens(root, item) for item in files]
    docs = [entry[0] for entry in cached_docs]
    lengths = [len(doc) for doc in docs]
    avgdl = sum(lengths) / max(1, len(lengths))
    frequencies = [entry[1] for entry in cached_docs]
    document_frequency: Counter[str] = Counter()
    for freq in frequencies:
        for term in set(freq):
            document_frequency[term] += 1

    k1 = 1.5
    b = 0.75
    total = len(files)
    scores: list[float] = []
    for freq, doc_len in zip(frequencies, lengths):
        score = 0.0
        for term in query_terms:
            tf = freq.get(term, 0)
            if not tf:
                continue
            df = document_frequency.get(term, 0)
            idf = math.log(1.0 + (total - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1.0 - b + b * doc_len / max(avgdl, 1.0))
            score += idf * (tf * (k1 + 1.0) / denom)
        scores.append(score)
    return scores


def _normalized(values: list[float]) -> list[float]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if high <= low:
        return [1.0 if high > 0 else 0.0 for _ in values]
    return [(value - low) / (high - low) for value in values]


def _path_aliases(relative: str) -> set[str]:
    normalized = relative.replace("\\", "/")
    p = PurePosixPath(normalized)
    aliases = {normalized.casefold(), p.name.casefold(), p.stem.casefold()}
    suffixless = str(p.with_suffix(""))
    aliases.add(suffixless.casefold())
    if p.name.casefold() in {"index.ts", "index.tsx", "index.js", "index.jsx", "__init__.py"}:
        aliases.add(str(p.parent).casefold())
        aliases.add(p.parent.name.casefold())
    return aliases


def _python_imports(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except Exception:
        return []
    result: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = "." * int(node.level or 0) + str(node.module or "")
            if module:
                result.append(module)
    return result


def _script_imports(source: str) -> list[str]:
    values: list[str] = []
    for match in IMPORT_RE.finditer(source):
        value = match.group(1) or match.group(2)
        if value:
            values.append(value)
    return values


def _candidate_import_aliases(relative: str, import_name: str) -> set[str]:
    import_name = str(import_name or "").strip().replace("\\", "/")
    if not import_name:
        return set()

    current = PurePosixPath(relative.replace("\\", "/"))
    candidates: set[str] = {import_name.casefold()}

    if import_name.startswith("."):
        base = current.parent
        # Resolve ./ and ../ without touching the host filesystem.
        parts = list(base.parts)
        for part in import_name.split("/"):
            if part in {"", "."}:
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        resolved = "/".join(parts)
        candidates.add(resolved.casefold())
        candidates.add(PurePosixPath(resolved).name.casefold())
    else:
        dotted = import_name.lstrip(".").replace(".", "/")
        candidates.add(dotted.casefold())
        candidates.add(PurePosixPath(dotted).name.casefold())
    return candidates


def _build_dependency_graph_uncached(files: list[dict[str, Any]]) -> tuple[dict[int, set[int]], dict[int, set[int]], str]:
    alias_map: dict[str, set[int]] = defaultdict(set)
    for index, item in enumerate(files):
        for alias in _path_aliases(str(item.get("relative") or "")):
            alias_map[alias].add(index)

    outgoing: dict[int, set[int]] = defaultdict(set)
    incoming: dict[int, set[int]] = defaultdict(set)
    parser_modes: set[str] = set()

    for index, item in enumerate(files):
        relative = str(item.get("relative") or "")
        suffix = Path(relative).suffix.casefold()
        source = str(item.get("preview") or "")
        if suffix == ".py":
            imports = _python_imports(source)
            parser_modes.add("python_ast")
        elif suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            imports = _script_imports(source)
            parser_modes.add("js_ts_import_parser")
        else:
            continue

        for import_name in imports:
            aliases = _candidate_import_aliases(relative, import_name)
            matched: set[int] = set()
            for alias in aliases:
                matched.update(alias_map.get(alias, set()))
                # Extension-less imports commonly point to a concrete source file.
                for ext in (".py", ".ts", ".tsx", ".js", ".jsx"):
                    matched.update(alias_map.get(alias + ext, set()))
            for target in matched:
                if target == index:
                    continue
                outgoing[index].add(target)
                incoming[target].add(index)

    parser_mode = "+".join(sorted(parser_modes)) if parser_modes else "lightweight"
    return outgoing, incoming, parser_mode


def _build_dependency_graph(root: str, files: list[dict[str, Any]]) -> tuple[dict[int, set[int]], dict[int, set[int]], str, bool]:
    fingerprint = _project_fingerprint(files)
    cache_key = str(root or "").casefold()
    with _INDEX_CACHE_LOCK:
        cached = _GRAPH_CACHE.get(cache_key)
    if cached is not None and cached[0] == fingerprint:
        return cached[1], cached[2], cached[3], True
    outgoing, incoming, parser_mode = _build_dependency_graph_uncached(files)
    with _INDEX_CACHE_LOCK:
        _GRAPH_CACHE[cache_key] = (fingerprint, outgoing, incoming, parser_mode)
    return outgoing, incoming, parser_mode, False


def _torch_status(*, load_runtime: bool = False) -> dict[str, Any]:
    available = importlib.util.find_spec("torch") is not None
    result: dict[str, Any] = {
        "available": available,
        "cuda_available": None if available else False,
        "device": "python",
        "mode": "lazy_not_loaded" if available else "python_fallback",
    }
    if not available:
        return result
    # Importing torch can cost more than a small project analysis itself.  Do not pay
    # that startup cost unless a large candidate matrix actually benefits from Tensor
    # fusion, or torch is already loaded by another AgentStudio feature.
    if not load_runtime and "torch" not in sys.modules:
        return result
    try:
        import torch

        cuda = bool(torch.cuda.is_available())
        result.update(
            {
                "cuda_available": cuda,
                "cuda_device_name": torch.cuda.get_device_name(0) if cuda else "",
                "version": str(getattr(torch, "__version__", "")),
                "mode": "runtime_loaded",
            }
        )
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _fuse_with_tensor(features: list[list[float]]) -> tuple[list[float], dict[str, Any]]:
    # Matrix multiplication is intentionally optional.  For small/medium projects,
    # importing PyTorch is slower than five scalar multiplications per file, so the
    # engine remains on the lightweight Python path.  Large projects (or an already
    # loaded torch runtime) use Tensor fusion automatically.
    weights = [0.42, 0.20, 0.15, 0.10, 0.13]
    if not features:
        return [], _torch_status()

    should_load_torch = len(features) >= 2000 or "torch" in sys.modules
    status = _torch_status(load_runtime=should_load_torch)
    if should_load_torch and status.get("available"):
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
            use_cuda = cuda_available and len(features) >= 5000
            device = torch.device("cuda" if use_cuda else "cpu")
            matrix = torch.tensor(features, dtype=torch.float32, device=device)
            weight_tensor = torch.tensor(weights, dtype=torch.float32, device=device)
            fused = torch.mv(matrix, weight_tensor).detach().cpu().tolist()
            status["cuda_available"] = cuda_available
            status["device"] = str(device)
            status["mode"] = "torch_tensor_fusion"
            if cuda_available and not use_cuda:
                status["device_reason"] = "GPU 전송비용보다 CPU Tensor가 유리한 규모라 CPU를 선택했습니다."
            return [float(value) for value in fused], status
        except Exception as exc:
            status["mode"] = "python_fallback"
            status["error"] = str(exc)

    status["mode"] = "python_fast_path" if status.get("available") else "python_fallback"
    status["device"] = "python"
    status["device_reason"] = "작은/중간 프로젝트는 PyTorch import/전송 오버헤드를 피합니다."
    return [sum(value * weight for value, weight in zip(row, weights)) for row in features], status


def high_speed_analysis_status() -> dict[str, Any]:
    return {
        "enabled": True,
        "pipeline": [
            "incremental_file_cache",
            "bm25_local_ranking",
            "path_and_symbol_matching",
            "python_ast_or_js_ts_structure_parser",
            "dependency_graph_expansion",
            "optional_pytorch_tensor_score_fusion",
            "candidate_compression_before_llm",
        ],
        "torch": _torch_status(load_runtime=False),
        "tree_sitter_available": importlib.util.find_spec("tree_sitter") is not None,
        "pgvector_available": importlib.util.find_spec("pgvector") is not None,
        "notes": [
            "PyTorch는 설치되어 있을 때만 사용하며 미설치 환경에서는 동일한 점수식을 Python으로 실행합니다.",
            "코드 구조는 Python AST와 JS/TS import parser를 즉시 사용하고 tree-sitter는 설치 시 확장 가능한 선택 계층입니다.",
            "LLM/Embedding 호출 없이 1차 후보를 압축하므로 API 토큰을 소비하지 않습니다.",
        ],
    }


def analyze_project_candidates(
    scan_data: dict[str, Any],
    request: str,
    *,
    limit: int = 24,
) -> dict[str, Any]:
    started = time.perf_counter()
    files = list(scan_data.get("files") or [])
    terms = _query_terms(request)
    if not files:
        return {
            "root": scan_data.get("root") or "",
            "related_files": [],
            "total_scanned_files": 0,
            "pipeline": high_speed_analysis_status(),
            "elapsed_ms": 0.0,
        }

    bm25_raw = _bm25_scores(str(scan_data.get("root") or ""), files, terms)
    exact_raw: list[float] = []
    path_raw: list[float] = []
    symbol_raw: list[float] = []
    matched_terms: list[list[str]] = []

    for item in files:
        relative = str(item.get("relative") or "").casefold()
        symbols = " ".join(str(x) for x in (item.get("symbols") or [])).casefold()
        text = _doc_text(item).casefold()
        matched = [term for term in terms if term in text]
        matched_terms.append(matched)
        exact_raw.append(float(sum(min(text.count(term), 5) for term in terms)))
        path_raw.append(float(sum(1 for term in terms if term in relative)))
        symbol_raw.append(float(sum(1 for term in terms if term in symbols)))

    # Dependency expansion starts from strong textual candidates so an implementation
    # file that does not contain the user's exact wording can still be selected when it
    # imports/is imported by a strong candidate.
    outgoing, incoming, parser_mode, graph_cache_hit = _build_dependency_graph(str(scan_data.get("root") or ""), files)
    bm25_norm = _normalized(bm25_raw)
    exact_norm = _normalized(exact_raw)
    path_norm = _normalized(path_raw)
    symbol_norm = _normalized(symbol_raw)
    seed_order = sorted(
        range(len(files)),
        key=lambda idx: (
            -(bm25_norm[idx] * 0.65 + exact_norm[idx] * 0.20 + path_norm[idx] * 0.10 + symbol_norm[idx] * 0.05),
            str(files[idx].get("relative") or "").casefold(),
        ),
    )[: min(16, len(files))]
    seed_set = set(seed_order)
    dependency_raw = [0.0] * len(files)
    for seed_rank, seed in enumerate(seed_order):
        seed_weight = max(0.25, 1.0 - seed_rank * 0.05)
        for target in outgoing.get(seed, set()):
            dependency_raw[target] += 0.75 * seed_weight
        for source in incoming.get(seed, set()):
            dependency_raw[source] += 1.0 * seed_weight
        if seed in seed_set:
            dependency_raw[seed] += 0.15
    dependency_norm = _normalized(dependency_raw)

    features = [
        [bm25_norm[i], exact_norm[i], path_norm[i], symbol_norm[i], dependency_norm[i]]
        for i in range(len(files))
    ]
    fused, tensor_status = _fuse_with_tensor(features)

    ranked: list[dict[str, Any]] = []
    for index, item in enumerate(files):
        neighbors = sorted(
            {
                str(files[target].get("relative") or "")
                for target in outgoing.get(index, set()) | incoming.get(index, set())
                if 0 <= target < len(files)
            }
        )[:12]
        relative_value = str(item.get("relative") or "").replace("\\", "/")
        suffix = Path(relative_value).suffix.casefold()
        source_suffixes = {".py", ".js", ".jsx", ".ts", ".tsx", ".cs", ".java", ".kt", ".go", ".rs", ".php", ".rb", ".cpp", ".c", ".h", ".hpp", ".sql"}
        request_cf = str(request or "").casefold()
        documentation_request = any(token in request_cf for token in ("문서", "readme", "ppt", "가이드", "documentation", "document"))
        importance_bonus = 0.025 if item.get("agent_related") else 0.0
        if suffix in source_suffixes:
            importance_bonus += 0.035
        elif (relative_value.casefold().startswith("docs/") or suffix == ".md") and not documentation_request:
            importance_bonus -= 0.035
        final = min(1.0, max(0.0, fused[index] + importance_bonus))
        ranked.append(
            {
                **item,
                "score": round(final * 100.0, 4),
                "matched": matched_terms[index],
                "score_breakdown": {
                    "bm25": round(bm25_norm[index], 5),
                    "exact": round(exact_norm[index], 5),
                    "path": round(path_norm[index], 5),
                    "symbol": round(symbol_norm[index], 5),
                    "dependency": round(dependency_norm[index], 5),
                },
                "dependency_neighbors": neighbors,
            }
        )

    ranked.sort(key=lambda item: (-float(item.get("score") or 0), str(item.get("relative") or "").casefold()))
    # If the request has no searchable terms, retain a small deterministic project skeleton
    # rather than pretending semantic confidence exists.
    if not terms:
        ranked.sort(
            key=lambda item: (
                0 if Path(str(item.get("relative") or "")).name in {
                    "README.md", "package.json", "pyproject.toml", "requirements.txt", "main.py", "App.tsx", "App.jsx"
                } else 1,
                str(item.get("relative") or "").casefold(),
            )
        )

    selected = ranked[: max(1, min(int(limit or 24), len(ranked)))]
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    status = high_speed_analysis_status()
    status.update(
        {
            "structure_parser": parser_mode,
            "tensor": tensor_status,
            "query_terms": terms,
            "candidate_count": len(selected),
            "compression_ratio": round(len(selected) / max(1, len(files)), 5),
            "llm_called": False,
            "embedding_called": False,
            "elapsed_ms": round(elapsed_ms, 3),
            "scan_cache": scan_data.get("cache") or {},
            "structure_cache_hit": graph_cache_hit,
        }
    )

    return {
        "root": scan_data.get("root") or "",
        "related_files": selected,
        "total_scanned_files": len(files),
        "pipeline": status,
        "analysis_mode": "HIGH_SPEED_LOCAL",
        "llm_called": False,
        "embedding_called": False,
        "elapsed_ms": round(elapsed_ms, 3),
    }
