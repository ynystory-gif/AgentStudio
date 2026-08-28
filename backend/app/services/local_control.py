import asyncio
import hashlib
import json
import os
import sys
import uuid
import subprocess
import re
import unicodedata
from pathlib import Path
from threading import RLock

from watchfiles import Change, awatch

from app.core.config import get_settings
from app.services.gpu_runtime_manager import gpu_runtime_environment


_runtime_project_roots: set[Path] = set()
_runtime_roots_lock = RLock()

# v5.393: commands launched by Agent Factory validation/tests are tracked so an
# asyncio Job cancellation cannot leave a detached compiler/test subprocess
# running after the UI already shows FAILED/DEBUG_STOPPED/VALIDATION_BLOCKED.
_active_command_processes: dict[str, subprocess.Popen] = {}
_active_command_meta: dict[str, dict] = {}
_active_command_lock = RLock()


def _terminate_command_process_tree(process: subprocess.Popen) -> None:
    if not process or process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        else:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def active_command_processes(project_root: str = "") -> list[dict]:
    requested = str(Path(project_root).expanduser().resolve()) if project_root else ""
    rows = []
    with _active_command_lock:
        items = list(_active_command_processes.items())
        meta = {key: dict(_active_command_meta.get(key) or {}) for key, _ in items}
    for execution_id, process in items:
        running = process.poll() is None
        info = meta.get(execution_id) or {}
        if requested and str(info.get("cwd") or "") != requested:
            continue
        rows.append({
            "execution_id": execution_id,
            "pid": process.pid,
            "running": running,
            **info,
        })
    return rows


class InvalidNotebookContentError(ValueError):
    """Raised when a .ipynb save payload is not a valid Notebook document."""

    def __init__(self, path: Path, message: str):
        self.path = path
        self.validation_message = message
        super().__init__(f"유효하지 않은 Jupyter Notebook 저장을 차단했습니다: {path} / {message}")


def _validate_notebook_save_payload(path: Path, content: str) -> None:
    if path.suffix.casefold() != ".ipynb":
        return

    raw = str(content or "")
    try:
        notebook = json.loads(raw)
    except Exception as exc:
        raise InvalidNotebookContentError(path, f"JSON 해석 실패: {exc}") from exc

    if not isinstance(notebook, dict):
        raise InvalidNotebookContentError(path, "Notebook 최상위 값은 JSON object여야 합니다.")
    if not isinstance(notebook.get("cells"), list):
        raise InvalidNotebookContentError(path, "cells 배열이 없습니다.")
    metadata = notebook.get("metadata", {})
    if not isinstance(metadata, dict):
        raise InvalidNotebookContentError(path, "metadata는 JSON object여야 합니다.")

    for index, cell in enumerate(notebook.get("cells") or []):
        if not isinstance(cell, dict):
            raise InvalidNotebookContentError(path, f"Cell {index + 1} 형식이 object가 아닙니다.")
        if cell.get("cell_type") not in {"code", "markdown", "raw"}:
            raise InvalidNotebookContentError(path, f"Cell {index + 1}의 cell_type이 유효하지 않습니다.")
        source = cell.get("source", [])
        if not isinstance(source, (list, str)):
            raise InvalidNotebookContentError(path, f"Cell {index + 1}의 source 형식이 유효하지 않습니다.")


def _atomic_notebook_write(path: Path, payload: bytes) -> None:
    temp = path.with_name(f".{path.name}.agentstudio-{uuid.uuid4().hex}.tmp")
    try:
        temp.write_bytes(payload)
        # Verify the exact bytes that will replace the Notebook before os.replace.
        decoded = payload.decode("utf-8-sig")
        _validate_notebook_save_payload(path, decoded)
        os.replace(temp, path)
    finally:
        try:
            if temp.exists():
                temp.unlink()
        except Exception:
            pass


def _new_notebook_payload() -> bytes:
    """Return a minimal, immediately editable Jupyter Notebook document.

    A .ipynb file is JSON, so a zero-byte file is never a valid Notebook.
    AgentStudio creates one empty Python code cell so a newly-created Notebook
    can be opened and executed immediately without passing through the invalid
    JSON fallback editor. nbformat_minor=4 deliberately avoids requiring the
    cell ``id`` field introduced by nbformat 4.5.
    """
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [],
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }
    return (json.dumps(notebook, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


class ExternalFileChangedError(RuntimeError):
    """Raised when the file content changed on disk after the editor loaded it."""

    def __init__(
        self,
        path: Path,
        expected_mtime_ns: int | None = None,
        actual_mtime_ns: int | None = None,
        expected_sha256: str | None = None,
        actual_sha256: str | None = None,
    ):
        self.path = path
        self.expected_mtime_ns = expected_mtime_ns
        self.actual_mtime_ns = actual_mtime_ns
        self.expected_sha256 = expected_sha256
        self.actual_sha256 = actual_sha256
        super().__init__(
            f"파일이 AgentStudio 밖에서 변경되었습니다: {path}"
        )


def _resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _is_within(path: Path, root: Path) -> bool:
    """
    문자열 startswith가 아니라 Path.relative_to()로 실제 하위 경로인지 판정합니다.
    예: C:\\AI\\Proj2 가 C:\\AI\\Proj 로 잘못 허용되는 문제를 방지합니다.
    """
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def register_runtime_project_root(path: str) -> str:
    """
    사용자가 UI에서 명시적으로 선택/불러온 프로젝트 루트를
    현재 Backend 실행 세션의 허용 루트로 등록합니다.

    특정 드라이브나 폴더를 하드코딩하지 않습니다.
    """
    p = _resolve_path(path)

    if not p.exists():
        raise FileNotFoundError(f"프로젝트 경로가 존재하지 않습니다: {p}")

    if not p.is_dir():
        raise NotADirectoryError(f"프로젝트 경로가 폴더가 아닙니다: {p}")

    with _runtime_roots_lock:
        _runtime_project_roots.add(p)

    return str(p)


def unregister_runtime_project_root(path: str) -> None:
    p = _resolve_path(path)
    with _runtime_roots_lock:
        _runtime_project_roots.discard(p)


def get_runtime_project_roots() -> list[str]:
    with _runtime_roots_lock:
        return sorted(str(x) for x in _runtime_project_roots)


def _configured_project_roots() -> list[Path]:
    s = get_settings()
    roots: list[Path] = []

    for value in s.project_roots:
        try:
            roots.append(_resolve_path(value))
        except Exception:
            continue

    return roots


def _all_allowed_roots() -> list[Path]:
    configured = _configured_project_roots()

    with _runtime_roots_lock:
        runtime = list(_runtime_project_roots)

    # resolve된 Path 기준 중복 제거
    seen: set[str] = set()
    result: list[Path] = []

    for root in configured + runtime:
        key = str(root).casefold()
        if key not in seen:
            seen.add(key)
            result.append(root)

    return result


def _allowed(path: str) -> Path:
    p = _resolve_path(path)
    roots = _all_allowed_roots()

    if not any(_is_within(p, root) for root in roots):
        raise PermissionError(
            "허용된 프로젝트 경로 밖입니다: "
            f"{p} / 현재 허용 루트: "
            + (", ".join(str(x) for x in roots) if roots else "(없음)")
        )

    return p



# Project Explorer must not spend its file budget inside dependency/virtualenv
# directories.  Keep this list deliberately directory-only so files such as
# `.env` remain visible in the project tree.
_IGNORED_PROJECT_DIR_NAMES = {
    ".git",
    ".agentstudio",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".idea",
}


def _is_ignored_project_dir_name(name: str) -> bool:
    value = str(name or "").strip().casefold()
    if not value:
        return False
    if value in _IGNORED_PROJECT_DIR_NAMES:
        return True

    # Virtual environments are commonly renamed to .venv_old, venv312, etc.
    # Treat those as dependency directories as well, otherwise a single copied
    # venv can consume thousands of Explorer rows before real project files.
    if value == "env" or value == ".env":
        return True
    if value.startswith(".venv") or value.startswith("venv"):
        return True
    if value.startswith("virtualenv") or value.startswith(".virtualenv"):
        return True
    return False


def _iter_project_tree(base: Path):
    """Yield directories/files while pruning heavy dependency folders early.

    Path.rglob() still descends into ignored directories before the caller can
    skip returned items.  os.walk() lets us mutate ``dirs`` in-place, so
    virtualenv/node_modules contents are never traversed at all.  Root-level
    files are yielded before nested directories, preventing an arbitrary deep
    folder from hiding the project's own files when a safety limit is reached.
    """
    for current, dirs, filenames in os.walk(base):
        current_path = Path(current)
        dirs[:] = sorted(
            [d for d in dirs if not _is_ignored_project_dir_name(d)],
            key=str.casefold,
        )
        filenames = sorted(filenames, key=str.casefold)

        relative_dir = current_path.relative_to(base)
        for dirname in dirs:
            path = current_path / dirname
            yield "dir", path, path.relative_to(base).as_posix()
        for filename in filenames:
            path = current_path / filename
            yield "file", path, path.relative_to(base).as_posix()


async def list_files(root: str):
    p = _allowed(root)

    def _scan():
        rows: list[str] = []
        for kind, _item, relative in _iter_project_tree(p):
            if kind != "file":
                continue
            rows.append(relative)
            # Dependency folders are pruned, so this is now a guard for truly
            # enormous source trees rather than a normal-project truncation.
            if len(rows) >= 20000:
                break
        return rows

    return await asyncio.to_thread(_scan)


async def list_directories(root: str):
    """Return project folders, including empty folders, without dependency trees."""
    p = _allowed(root)

    def _scan():
        rows: list[str] = []
        for kind, _item, relative in _iter_project_tree(p):
            if kind != "dir":
                continue
            rows.append(relative)
            if len(rows) >= 10000:
                break
        return rows

    return await asyncio.to_thread(_scan)


_PROJECT_TEXT_SEARCH_EXTENSIONS = {
    "", ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv",
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".env", ".log", ".py", ".pyw", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mts", ".cts", ".mjs", ".cjs",
    ".java", ".kt", ".kts", ".cs", ".c", ".h", ".cpp", ".hpp", ".go",
    ".rs", ".php", ".rb", ".swift", ".dart", ".scala", ".sh", ".bash",
    ".zsh", ".ps1", ".psm1", ".psd1", ".cmd", ".bat", ".sql", ".html", ".htm",
    ".css", ".scss", ".sass", ".less", ".xml", ".svg", ".vue", ".svelte",
    ".graphql", ".gql", ".proto", ".properties", ".gradle", ".prisma", ".jsonc", ".dockerfile",
    ".ipynb",
}

_PROJECT_TEXT_SEARCH_MAX_FILE_BYTES = 4 * 1024 * 1024


def _decode_search_text(payload: bytes) -> str | None:
    if b"\x00" in payload[:8192]:
        # UTF-16 text contains NUL bytes, so try it before treating the file as binary.
        for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
            try:
                return payload.decode(encoding)
            except Exception:
                continue
        return None
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return payload.decode(encoding)
        except Exception:
            continue
    return None


def _search_line_matches(text: str, query: str, *, case_sensitive: bool, max_results: int) -> list[dict]:
    source = str(text or "")
    needle = str(query or "")
    if not needle:
        return []
    compare_needle = needle if case_sensitive else needle.casefold()
    results: list[dict] = []
    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        compare_line = raw_line if case_sensitive else raw_line.casefold()
        start = 0
        while True:
            column = compare_line.find(compare_needle, start)
            if column < 0:
                break
            snippet = raw_line.strip()
            if len(snippet) > 240:
                left = max(0, column - 80)
                snippet = raw_line[left:left + 220].strip()
            results.append({
                "line_number": line_number,
                "column": column + 1,
                "snippet": snippet,
            })
            if len(results) >= max_results:
                return results
            start = column + max(1, len(compare_needle))
    return results


def _search_notebook_source(text: str, query: str, *, case_sensitive: bool, max_results: int) -> list[dict]:
    try:
        notebook = json.loads(text)
    except Exception:
        return _search_line_matches(text, query, case_sensitive=case_sensitive, max_results=max_results)
    cells = notebook.get("cells") if isinstance(notebook, dict) else None
    if not isinstance(cells, list):
        return []
    results: list[dict] = []
    for cell_index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source_text = "".join(str(item) for item in source)
        else:
            source_text = str(source or "")
        remaining = max_results - len(results)
        if remaining <= 0:
            break
        for row in _search_line_matches(source_text, query, case_sensitive=case_sensitive, max_results=remaining):
            results.append({
                **row,
                "cell_index": cell_index,
                "cell_number": cell_index + 1,
                "cell_type": str(cell.get("cell_type") or ""),
            })
    return results


def _pdf_search_normalize(value: str) -> str:
    """Normalize extracted PDF text for duplicate detection and display grouping."""
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", normalized)
    return " ".join(normalized.split()).casefold()


def _pdf_search_match_key(
    value: str,
    *,
    case_sensitive: bool,
    aggressive: bool = False,
) -> str:
    """Build a PDF search key resilient to PDF text-layer fragmentation.

    The normal key removes whitespace and invisible characters while preserving
    punctuation.  The aggressive fallback additionally ignores punctuation and
    symbols.  The latter is intentionally used only after the normal match fails
    so queries such as Korean slide sentences still work when the embedded PDF
    text inserts quote/dash/bullet objects between visible words.
    """
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", normalized)
    normalized = normalized if case_sensitive else normalized.casefold()
    if aggressive:
        normalized = "".join(ch for ch in normalized if ch.isalnum())
    else:
        normalized = re.sub(r"\s+", "", normalized)
    return normalized


def _search_pdf_text_layer_matches(
    page_text: str,
    query: str,
    *,
    case_sensitive: bool,
    max_results: int,
) -> list[dict]:
    """Find PDF matches and map them back to a nearby extracted source line."""
    source = str(page_text or "")
    lines = source.splitlines()
    if not lines:
        return []

    def _search(aggressive: bool) -> list[dict]:
        needle = _pdf_search_match_key(
            query,
            case_sensitive=case_sensitive,
            aggressive=aggressive,
        )
        # Avoid excessively broad punctuation-insensitive fallback such as "C++"
        # becoming merely "c".
        if not needle or (aggressive and len(needle) < 3):
            return []

        compact_parts: list[str] = []
        line_spans: list[tuple[int, int, int]] = []
        cursor = 0
        for index, raw_line in enumerate(lines):
            key = _pdf_search_match_key(
                raw_line,
                case_sensitive=case_sensitive,
                aggressive=aggressive,
            )
            start = cursor
            compact_parts.append(key)
            cursor += len(key)
            line_spans.append((start, cursor, index))

        compact_page = "".join(compact_parts)
        if not compact_page:
            return []

        matches: list[dict] = []
        start_at = 0
        while len(matches) < max_results:
            match_at = compact_page.find(needle, start_at)
            if match_at < 0:
                break
            line_index = 0
            for span_start, span_end, candidate_index in line_spans:
                if span_end > match_at or (span_start == match_at and span_end > span_start):
                    line_index = candidate_index
                    break
            raw_line = lines[line_index] if line_index < len(lines) else ""
            matches.append({
                "line_number": line_index + 1,
                "column": 1,
                "snippet": raw_line.strip(),
                "match_mode": (
                    "pdf_punctuation_whitespace_insensitive"
                    if aggressive
                    else "pdf_whitespace_insensitive"
                ),
            })
            start_at = match_at + max(1, len(needle))
        return matches

    primary = _search(False)
    return primary if primary else _search(True)


def _pdf_search_context(lines: list[str], line_index: int, *, radius: int = 2) -> str:
    """Build neighboring context so visually repeated headings can be distinguished."""
    current = max(0, min(int(line_index), max(0, len(lines) - 1)))
    chosen: list[str] = []
    for distance in range(0, max(1, radius) + 1):
        indexes = [current] if distance == 0 else [current - distance, current + distance]
        for index in indexes:
            if index < 0 or index >= len(lines):
                continue
            text = " ".join(str(lines[index] or "").split()).strip()
            if not text:
                continue
            normalized = _pdf_search_normalize(text)
            if normalized and all(_pdf_search_normalize(item) != normalized for item in chosen):
                chosen.append(text)
        if len(chosen) >= 3:
            break
    context = "  ·  ".join(chosen[:3]).strip()
    return context[:520] if context else ""


def _pypdf_page_text_variants(page) -> list[tuple[str, str]]:
    """Return multiple pypdf extraction orders because slide PDFs vary widely."""
    variants: list[tuple[str, str]] = []
    try:
        layout = str(page.extract_text(extraction_mode="layout") or "")
        if layout.strip():
            variants.append(("pypdf_layout", layout))
    except Exception:
        pass
    try:
        plain = str(page.extract_text() or "")
        if plain.strip() and all(plain != text for _, text in variants):
            variants.append(("pypdf_plain", plain))
    except Exception:
        pass
    return variants


def _search_pdf_source(path: Path, query: str, *, case_sensitive: bool, max_results: int) -> dict:
    """Search a PDF using multiple text extractors with stale/duplicate suppression.

    pypdf layout/plain extraction and, when available, PyMuPDF sorted text are all
    considered.  This improves Korean slide/PDF search where one extractor can
    reorder, split or omit text objects even though Chromium visually renders the
    sentence correctly.  Results remain page-based because visual x/y coordinates
    are not reliably portable to Chromium's built-in PDF viewer.
    """
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError("PDF 텍스트 검색 모듈(pypdf)이 설치되어 있지 않습니다.") from exc

    reader = PdfReader(str(path))
    fitz_doc = None
    try:
        import fitz  # type: ignore
        fitz_doc = fitz.open(str(path))
    except Exception:
        fitz_doc = None

    results: list[dict] = []
    pages_scanned = 0
    text_pages = 0
    duplicate_matches_removed = 0
    extractors_used: set[str] = set()

    try:
        for page_index, page in enumerate(reader.pages):
            if len(results) >= max_results:
                break
            pages_scanned += 1
            variants = _pypdf_page_text_variants(page)
            if fitz_doc is not None and page_index < len(fitz_doc):
                try:
                    fitz_text = str(fitz_doc[page_index].get_text("text", sort=True) or "")
                    if fitz_text.strip() and all(fitz_text != text for _, text in variants):
                        variants.append(("pymupdf_sorted", fitz_text))
                except Exception:
                    pass
            if not variants:
                continue
            text_pages += 1

            remaining = max_results - len(results)
            page_candidates: list[dict] = []
            for extractor_name, page_text in variants:
                extractors_used.add(extractor_name)
                lines = page_text.splitlines()
                raw_rows = _search_pdf_text_layer_matches(
                    page_text,
                    query,
                    case_sensitive=case_sensitive,
                    max_results=max(remaining * 6, remaining),
                )
                for row in raw_rows:
                    line_number = max(1, int(row.get("line_number") or 1))
                    raw_line = lines[line_number - 1] if line_number - 1 < len(lines) else str(row.get("snippet") or "")
                    context = _pdf_search_context(lines, line_number - 1)
                    page_candidates.append({
                        **row,
                        "snippet": context or str(row.get("snippet") or "").strip(),
                        "match_line": " ".join(str(raw_line or "").split()).strip(),
                        "page_index": page_index,
                        "page_number": page_index + 1,
                        "extractor": extractor_name,
                    })

            # Chromium page navigation cannot jump to a reliable x/y text span,
            # only to the PDF page. Multiple extractor hits on the same page are
            # therefore not independently actionable and used to look like
            # duplicate search results. Return the single clearest hit per page.
            page_results: list[dict] = []
            if page_candidates and remaining > 0:
                query_key = _pdf_search_match_key(query, case_sensitive=False, aggressive=True)
                extractor_priority = {"pypdf_plain": 0, "pymupdf_sorted": 1, "pypdf_layout": 2}

                def _candidate_score(row: dict) -> tuple[int, int, int]:
                    line = str(row.get("match_line") or row.get("snippet") or "")
                    line_key = _pdf_search_match_key(line, case_sensitive=False, aggressive=True)
                    contains = 0 if query_key and query_key in line_key else 1
                    # Prefer a concise source line and then the extractor that
                    # usually preserves human reading order most naturally.
                    extra = max(0, len(line_key) - len(query_key)) if query_key else len(line_key)
                    priority = extractor_priority.get(str(row.get("extractor") or ""), 9)
                    return (contains, extra, priority)

                page_candidates.sort(key=_candidate_score)
                page_results.append(page_candidates[0])
                duplicate_matches_removed += max(0, len(page_candidates) - 1)

            for page_match_index, row in enumerate(page_results, start=1):
                results.append({
                    **row,
                    "page_match_index": page_match_index,
                    "match_id": f"p{page_index + 1}-m{page_match_index}",
                })
                if len(results) >= max_results:
                    break
    finally:
        if fitz_doc is not None:
            try:
                fitz_doc.close()
            except Exception:
                pass

    return {
        "results": results,
        "pdf_pages_scanned": pages_scanned,
        "pdf_text_pages": text_pages,
        "pdf_duplicate_matches_removed": duplicate_matches_removed,
        "pdf_extractors": sorted(extractors_used),
        "document_type": "pdf",
        "truncated": len(results) >= max_results,
    }


async def search_project_text(
    root: str,
    query: str,
    *,
    relative_path: str = "",
    case_sensitive: bool = False,
    max_results: int = 300,
    max_files: int = 5000,
):
    """Search project text on demand without introducing idle polling.

    Dependency/virtualenv directories reuse the Project Explorer pruning rules.
    Notebook files search only cell source content, not metadata/output blobs.
    """
    base = _allowed(root)
    needle = str(query or "").strip()
    if not needle:
        return {"query": "", "results": [], "files_scanned": 0, "truncated": False}
    max_results = max(1, min(int(max_results or 300), 1000))
    max_files = max(1, min(int(max_files or 5000), 20000))

    requested = str(relative_path or "").strip().replace("\\", "/")

    def _scan():
        candidates: list[tuple[Path, str]] = []
        if requested:
            target = _allowed(str(base / requested))
            if not _is_within(target, base):
                raise PermissionError(f"현재 프로젝트 root 밖의 파일은 검색할 수 없습니다: {requested}")
            if not target.exists() or not target.is_file():
                return {"query": needle, "results": [], "files_scanned": 0, "truncated": False}
            candidates.append((target, target.relative_to(base).as_posix()))
        else:
            for kind, item, relative in _iter_project_tree(base):
                if kind != "file":
                    continue
                candidates.append((item, relative))
                if len(candidates) >= max_files:
                    break

        # Explicit current-PDF search: extract text with pypdf and preserve page
        # coordinates for navigation. Project-wide search intentionally keeps
        # binary PDFs excluded to avoid expensive background scans.
        if requested and len(candidates) == 1 and candidates[0][0].suffix.casefold() == '.pdf':
            pdf_path, relative = candidates[0]
            pdf_result = _search_pdf_source(
                pdf_path,
                needle,
                case_sensitive=case_sensitive,
                max_results=max_results,
            )
            return {
                'query': needle,
                'results': [{'path': relative, **row} for row in pdf_result['results']],
                'files_scanned': 1,
                'skipped_large': 0,
                'skipped_binary': 0,
                **{key: value for key, value in pdf_result.items() if key != 'results'},
            }

        results: list[dict] = []
        scanned = 0
        skipped_large = 0
        skipped_binary = 0
        for path, relative in candidates:
            if len(results) >= max_results:
                break
            suffix = path.suffix.casefold()
            if path.name.casefold() == "dockerfile":
                suffix = ".dockerfile"
            if suffix not in _PROJECT_TEXT_SEARCH_EXTENSIONS:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > _PROJECT_TEXT_SEARCH_MAX_FILE_BYTES:
                skipped_large += 1
                continue
            try:
                payload = path.read_bytes()
            except OSError:
                continue
            text = _decode_search_text(payload)
            if text is None:
                skipped_binary += 1
                continue
            scanned += 1
            remaining = max_results - len(results)
            matches = (
                _search_notebook_source(text, needle, case_sensitive=case_sensitive, max_results=remaining)
                if suffix == ".ipynb"
                else _search_line_matches(text, needle, case_sensitive=case_sensitive, max_results=remaining)
            )
            for match in matches:
                results.append({"path": relative, **match})
                if len(results) >= max_results:
                    break

        return {
            "query": needle,
            "results": results,
            "files_scanned": scanned,
            "truncated": len(results) >= max_results or (not requested and len(candidates) >= max_files),
            "skipped_large": skipped_large,
            "skipped_binary": skipped_binary,
        }

    return await asyncio.to_thread(_scan)


def _is_ignored_project_item(item: Path) -> bool:
    # Kept for compatibility with helpers that receive a Path directly.
    return any(_is_ignored_project_dir_name(part) for part in item.parts)


def _safe_file_meta(path: Path) -> dict:
    stat = path.stat()
    return {
        "mtime_ns": int(stat.st_mtime_ns),
        "size": int(stat.st_size),
    }


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


async def get_file_meta(root: str, relative_path: str):
    base = _allowed(root)
    target = _allowed(str(base / relative_path))

    if not target.exists():
        return {
            "exists": False,
            "relative_path": Path(relative_path).as_posix(),
            "mtime_ns": 0,
            "size": 0,
        }

    if not target.is_file():
        raise IsADirectoryError(str(target))

    meta = await asyncio.to_thread(_safe_file_meta, target)
    sha256 = await asyncio.to_thread(_file_sha256, target)
    return {
        "exists": True,
        "relative_path": target.relative_to(base).as_posix(),
        **meta,
        "sha256": sha256,
    }


async def get_file_hash_states(root: str, relative_paths: list[str]):
    """Return SHA-256 based disk state for the currently opened files.

    This endpoint intentionally hashes only caller-supplied files instead of the
    entire project tree. It keeps external-change detection authoritative while
    avoiding expensive hashing of node_modules/venv/large repositories.
    """
    base = _allowed(root)
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in list(relative_paths or [])[:200]:
        rel = Path(str(raw or '')).as_posix().lstrip('/')
        if not rel or rel in seen:
            continue
        seen.add(rel)
        normalized.append(rel)

    def _scan() -> dict[str, dict]:
        rows: dict[str, dict] = {}
        for rel in normalized:
            target = _allowed(str(base / rel))
            try:
                if not target.exists() or not target.is_file():
                    rows[rel] = {
                        "exists": False,
                        "relative_path": rel,
                        "mtime_ns": 0,
                        "size": 0,
                        "sha256": "",
                    }
                    continue
                meta = _safe_file_meta(target)
                rows[rel] = {
                    "exists": True,
                    "relative_path": target.relative_to(base).as_posix(),
                    **meta,
                    "sha256": _file_sha256(target),
                }
            except (FileNotFoundError, PermissionError, OSError):
                rows[rel] = {
                    "exists": False,
                    "relative_path": rel,
                    "mtime_ns": 0,
                    "size": 0,
                    "sha256": "",
                }
        return rows

    return {"files": await asyncio.to_thread(_scan)}


def validate_project_root(root: str) -> str:
    """Validate and normalize a project root without scanning its contents."""
    return str(_allowed(root))


def _watch_project_path_allowed(base: Path, raw_path: str) -> tuple[bool, str]:
    """Return whether a native filesystem event belongs to the visible project tree."""
    try:
        relative = Path(os.path.relpath(str(raw_path), str(base))).as_posix()
    except (TypeError, ValueError, OSError):
        return False, ""

    if not relative or relative == "." or relative.startswith("../"):
        return False, ""

    parts = Path(relative).parts
    if any(_is_ignored_project_dir_name(part) for part in parts[:-1]):
        return False, ""

    name = str(parts[-1] if parts else "")
    # AgentStudio notebook atomic-save temporary files are implementation details.
    if ".agentstudio-" in name and name.endswith(".tmp"):
        return False, ""

    return True, relative


async def watch_project_changes(root: str):
    """Yield project filesystem changes from native OS notifications.

    v5.333 replaces the old 1.5 second whole-project snapshot polling. On
    Windows watchfiles uses native filesystem notifications, so an idle
    AgentStudio workspace no longer traverses the project tree or reads open
    files repeatedly just to discover whether something changed.
    """
    base = _allowed(root)

    def _filter(change: Change, path: str) -> bool:
        allowed, _relative = _watch_project_path_allowed(base, path)
        return allowed

    async for changes in awatch(
        str(base),
        recursive=True,
        watch_filter=_filter,
        debounce=300,
        step=50,
        raise_interrupt=False,
    ):
        merged: dict[str, str] = {}
        priority = {"modified": 1, "added": 2, "deleted": 3}

        for change, raw_path in changes:
            allowed, relative = _watch_project_path_allowed(base, raw_path)
            if not allowed or not relative:
                continue

            if change == Change.added:
                kind = "added"
            elif change == Change.deleted:
                kind = "deleted"
            else:
                kind = "modified"

            previous = merged.get(relative)
            if previous is None or priority[kind] >= priority[previous]:
                merged[relative] = kind

        if merged:
            yield [
                {"kind": kind, "path": relative}
                for relative, kind in sorted(merged.items())
            ]


async def project_file_snapshot(root: str):
    """Return a lightweight filesystem signature for external-change polling."""
    base = _allowed(root)

    def _scan():
        files: dict[str, dict] = {}
        directories: list[str] = []

        for kind, item, relative in _iter_project_tree(base):
            try:
                if kind == "dir":
                    directories.append(relative)
                elif kind == "file":
                    files[relative] = _safe_file_meta(item)
            except (FileNotFoundError, PermissionError, OSError):
                # A file can disappear while the directory is being scanned.
                continue

            # Keep polling lightweight but high enough for real source trees.
            # Root files are scanned first and dependency directories are pruned.
            if len(files) >= 20000 or len(directories) >= 10000:
                break

        return {
            "root": str(base),
            "files": files,
            "directories": directories,
        }

    return await asyncio.to_thread(_scan)


async def read_file(path: str) -> str:
    p = _allowed(path)
    return await asyncio.to_thread(
        p.read_text,
        encoding="utf-8",
        errors="replace",
    )


def _detect_existing_text_format(path: Path) -> tuple[str, bool]:
    """Return the existing newline style and whether UTF-8 BOM is present.

    TextIO on Windows translates ``\n`` to ``\r\n`` when ``newline=None``.
    If Monaco already sends CRLF, writing it through ``Path.write_text`` can
    therefore produce ``\r\r\n`` and the next load appears double-spaced.
    Detect the on-disk style first so saving can be deterministic.
    """
    if not path.exists() or not path.is_file():
        return (os.linesep, False)

    try:
        raw = path.read_bytes()
    except OSError:
        return (os.linesep, False)

    has_bom = raw.startswith(b"\xef\xbb\xbf")
    sample = raw[:1024 * 1024]

    if b"\r\n" in sample:
        return ("\r\n", has_bom)
    if b"\n" in sample:
        return ("\n", has_bom)
    if b"\r" in sample:
        return ("\r", has_bom)

    return (os.linesep, has_bom)


def _encode_editor_text(content: str, newline: str, with_bom: bool) -> bytes:
    """Normalize editor line endings once, then encode without TextIO translation."""
    normalized = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    if newline != "\n":
        normalized = normalized.replace("\n", newline)

    # Avoid duplicating a BOM if an existing UTF-8 BOM file is edited through
    # Monaco and the decoded content still contains U+FEFF at the beginning.
    if normalized.startswith("\ufeff"):
        normalized = normalized[1:]

    payload = normalized.encode("utf-8")
    if with_bom:
        payload = b"\xef\xbb\xbf" + payload
    return payload


async def write_file(
    path: str,
    content: str,
    expected_mtime_ns: int | None = None,
    expected_sha256: str | None = None,
    force: bool = False,
):
    p = _allowed(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    # v5.250: never allow an invalid Notebook buffer (including a previous
    # file-load error placeholder) to overwrite a real .ipynb file.
    _validate_notebook_save_payload(p, content)

    if p.exists() and not force:
        actual_mtime_ns = int(p.stat().st_mtime_ns)

        # v5.206: content identity is the authoritative optimistic-lock token.
        # mtime alone can change because of an editor/plugin/AV touch even when
        # the file bytes are identical, which caused false HTTP 409 responses
        # during a normal AgentStudio save.
        if expected_sha256:
            actual_sha256 = await asyncio.to_thread(_file_sha256, p)
            if actual_sha256 != str(expected_sha256):
                raise ExternalFileChangedError(
                    p,
                    expected_mtime_ns,
                    actual_mtime_ns,
                    str(expected_sha256),
                    actual_sha256,
                )
        elif expected_mtime_ns:
            if actual_mtime_ns != int(expected_mtime_ns):
                raise ExternalFileChangedError(
                    p,
                    int(expected_mtime_ns),
                    actual_mtime_ns,
                )

    newline, with_bom = await asyncio.to_thread(
        _detect_existing_text_format,
        p,
    )
    payload = _encode_editor_text(content, newline, with_bom)

    # Write bytes directly so Windows cannot apply a second newline
    # translation (CRLF -> CRCRLF). Notebook saves are additionally atomic:
    # validate a temporary file first, then replace the original in one step.
    if p.suffix.casefold() == ".ipynb":
        await asyncio.to_thread(_atomic_notebook_write, p, payload)
    else:
        await asyncio.to_thread(p.write_bytes, payload)
    meta = await asyncio.to_thread(_safe_file_meta, p)

    return {
        "ok": True,
        "path": str(p),
        "bytes": len(payload),
        "mtime_ns": meta["mtime_ns"],
        "size": meta["size"],
        "sha256": _sha256_bytes(payload),
        "line_ending": (
            "CRLF" if newline == "\r\n"
            else "CR" if newline == "\r"
            else "LF"
        ),
        "utf8_bom": with_bom,
    }


async def run_command(command: str, cwd: str):
    p = _allowed(cwd)
    s = get_settings()
    execution_id = uuid.uuid4().hex
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if sys.platform == "win32" else 0
    process = subprocess.Popen(
        command,
        cwd=str(p),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=flags,
        env=gpu_runtime_environment(os.environ.copy()),
    )
    with _active_command_lock:
        _active_command_processes[execution_id] = process
        _active_command_meta[execution_id] = {
            "cwd": str(p),
            "command": str(command),
        }

    try:
        try:
            stdout, _ = await asyncio.wait_for(
                asyncio.to_thread(process.communicate),
                timeout=s.max_command_seconds,
            )
        except asyncio.TimeoutError as exc:
            _terminate_command_process_tree(process)
            raise TimeoutError(
                f"명령 실행 제한시간 {s.max_command_seconds}초를 초과했습니다."
            ) from exc
        except asyncio.CancelledError:
            # Critical lifecycle rule: cancelling the Agent Factory Job must also
            # terminate the real compiler/test process tree, not only the asyncio Task.
            _terminate_command_process_tree(process)
            raise

        return {
            "returncode": process.returncode,
            "output": (stdout or b"").decode(
                "utf-8",
                errors="replace",
            ),
        }
    finally:
        if process.poll() is None:
            _terminate_command_process_tree(process)
        with _active_command_lock:
            _active_command_processes.pop(execution_id, None)
            _active_command_meta.pop(execution_id, None)


async def create_folder(root: str, relative_path: str):
    base = _allowed(root)
    target = _allowed(str(base / relative_path))
    target.mkdir(parents=True, exist_ok=False)
    return {
        "ok": True,
        "path": str(target),
        "relative_path": str(target.relative_to(base)),
    }


async def create_file(root: str, relative_path: str):
    """Create a project file on disk and verify it before returning.

    Creation is intentionally idempotent for an existing *file*. This avoids
    a duplicate frontend request turning a successful first create into a 409
    error. A directory with the same name is still a real conflict.

    v5.350: ``.ipynb`` is not a plain text file. Creating it as zero bytes
    makes the Notebook editor fail immediately with ``Unexpected end of JSON
    input``. New Notebooks are therefore initialized with a valid nbformat 4
    JSON document containing one empty Python code cell. A zero-byte Notebook
    left behind by an older AgentStudio build is repaired when the same create
    request is made again; non-empty existing files are never overwritten.
    """
    base = _allowed(root)
    target = _allowed(str(base / relative_path))
    target.parent.mkdir(parents=True, exist_ok=True)
    is_notebook = target.suffix.casefold() == ".ipynb"
    initial_payload = _new_notebook_payload() if is_notebook else b""

    def _create_atomic():
        repaired_empty_notebook = False
        try:
            with target.open("xb") as handle:
                if initial_payload:
                    handle.write(initial_payload)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            created = True
        except FileExistsError:
            created = False

        # A same-name directory is not an idempotent file create.
        if target.exists() and target.is_dir():
            raise FileExistsError(
                f"같은 이름의 폴더가 이미 존재합니다: {target.name}"
            )

        if not target.exists() or not target.is_file():
            raise OSError(
                "파일 생성/재확인 후 실제 디스크 파일을 찾지 못했습니다: "
                f"{target}"
            )

        # v5.350 migration guard: v5.349 and older could leave a zero-byte
        # .ipynb on disk. It is safe to repair because zero bytes cannot be a
        # valid Jupyter Notebook. Never replace a non-empty existing Notebook.
        if is_notebook and not created and target.stat().st_size == 0:
            _atomic_notebook_write(target, initial_payload)
            repaired_empty_notebook = True

        # Validate newly-created/repaired Notebook bytes before returning a
        # success response to the frontend.
        if is_notebook and (created or repaired_empty_notebook):
            _validate_notebook_save_payload(
                target,
                target.read_text(encoding="utf-8-sig"),
            )

        stat = target.stat()
        return created, repaired_empty_notebook, {
            "mtime_ns": int(stat.st_mtime_ns),
            "size": int(stat.st_size),
            "sha256": _file_sha256(target),
        }

    created, repaired_empty_notebook, meta = await asyncio.to_thread(_create_atomic)

    return {
        "ok": True,
        "exists": True,
        "created": created,
        "already_exists": not created,
        "repaired_empty_notebook": repaired_empty_notebook,
        "path": str(target),
        "relative_path": target.relative_to(base).as_posix(),
        "mtime_ns": meta["mtime_ns"],
        "size": meta["size"],
        "sha256": meta["sha256"],
    }


async def delete_files(root: str, relative_paths: list[str]):
    """Delete one or more project files from disk.

    The project root remains the trust boundary. Directories are intentionally
    rejected because the editor delete UX is file-only and must not silently
    remove a folder tree. Missing files are treated idempotently so an external
    delete between confirmation and execution does not turn into a second error.
    """
    base = _allowed(root)
    deleted: list[str] = []
    missing: list[str] = []

    clean_paths: list[str] = []
    seen: set[str] = set()
    for raw in relative_paths or []:
        rel = str(raw or "").strip().replace("\\", "/").lstrip("/")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        clean_paths.append(rel)

    if not clean_paths:
        raise ValueError("삭제할 파일을 선택하세요.")

    def _delete():
        for rel in clean_paths:
            target = _allowed(str(base / Path(rel)))
            if not target.exists():
                missing.append(rel)
                continue
            if not target.is_file():
                raise ValueError(f"폴더는 파일 삭제 기능으로 삭제할 수 없습니다: {rel}")
            target.unlink()
            deleted.append(rel)

    await asyncio.to_thread(_delete)
    return {
        "ok": True,
        "deleted": deleted,
        "missing": missing,
        "count": len(deleted),
    }


async def rename_path(root: str, relative_path: str, new_name: str):
    base = _allowed(root)
    source = _allowed(str(base / relative_path))

    clean_name = (new_name or "").strip()
    if not clean_name:
        raise ValueError("새 이름을 입력하세요.")

    if any(x in clean_name for x in ["/", "\\"]):
        raise ValueError("이름에는 경로 구분자를 사용할 수 없습니다.")

    if not source.exists():
        raise FileNotFoundError(f"이름을 변경할 항목이 없습니다: {source}")

    # Windows 파일명 비교는 대소문자를 구분하지 않는 경우가 일반적입니다.
    # 이름이 실제로 바뀌지 않았다면 파일 시스템 작업 없이 정상 종료합니다.
    if clean_name.casefold() == source.name.casefold():
        return {
            "ok": True,
            "old_relative_path": relative_path,
            "new_relative_path": relative_path,
            "path": str(source),
            "changed": False,
        }

    target = _allowed(str(source.parent / clean_name))

    # resolve() 비교도 한 번 더 수행해 동일 대상을 확실히 걸러냅니다.
    try:
        if source.resolve() == target.resolve():
            return {
                "ok": True,
                "old_relative_path": relative_path,
                "new_relative_path": relative_path,
                "path": str(source),
                "changed": False,
            }
    except Exception:
        pass

    if target.exists():
        raise FileExistsError(
            f"같은 이름의 항목이 이미 존재합니다: {target.name}"
        )

    source.rename(target)

    return {
        "ok": True,
        "old_relative_path": relative_path,
        "new_relative_path": str(target.relative_to(base)),
        "path": str(target),
        "changed": True,
    }
