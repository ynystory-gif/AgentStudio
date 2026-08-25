import asyncio
import hashlib
import json
import os
import uuid
import subprocess
from pathlib import Path
from threading import RLock

from watchfiles import Change, awatch

from app.core.config import get_settings


_runtime_project_roots: set[Path] = set()
_runtime_roots_lock = RLock()




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

    def _execute():
        return subprocess.run(
            command,
            cwd=str(p),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=s.max_command_seconds,
        )

    try:
        proc = await asyncio.to_thread(_execute)
    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"명령 실행 제한시간 {s.max_command_seconds}초를 초과했습니다."
        )

    return {
        "returncode": proc.returncode,
        "output": (proc.stdout or b"").decode(
            "utf-8",
            errors="replace",
        ),
    }


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
    """
    base = _allowed(root)
    target = _allowed(str(base / relative_path))
    target.parent.mkdir(parents=True, exist_ok=True)

    def _create_atomic():
        # ``xb`` maps to O_CREAT|O_EXCL and therefore makes the disk the
        # source of truth. It also avoids the check-then-create race of
        # Path.exists() followed by write_bytes().
        try:
            with target.open("xb") as handle:
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

        stat = target.stat()
        return created, {
            "mtime_ns": int(stat.st_mtime_ns),
            "size": int(stat.st_size),
        }

    created, meta = await asyncio.to_thread(_create_atomic)

    return {
        "ok": True,
        "exists": True,
        "created": created,
        "already_exists": not created,
        "path": str(target),
        "relative_path": target.relative_to(base).as_posix(),
        "mtime_ns": meta["mtime_ns"],
        "size": meta["size"],
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
