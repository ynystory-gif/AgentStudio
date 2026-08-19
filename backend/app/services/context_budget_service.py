from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


# Keep a conservative request-side budget below a 128k context window.  The
# actual tokenizer differs by provider/model and Korean text can tokenize more
# densely than ASCII, so the gate intentionally leaves a large output/system
# reserve instead of attempting to fill the advertised context length.
MAX_FILE_EDIT_PROMPT_CHARS = 180_000
MAX_STYLE_PROMPT_CHARS = 30_000
MAX_NOTEBOOK_CONTEXT_CHARS = 90_000
MAX_NOTEBOOK_NEARBY_CELLS = 10
MAX_NOTEBOOK_BOOTSTRAP_CELLS = 4


@dataclass
class NotebookEditContext:
    notebook: dict[str, Any]
    active_cell_index: int
    active_cell_source: str
    context_text: str
    total_cells: int
    included_cells: list[int]
    original_chars: int
    compact_chars: int


def approximate_tokens(text: str) -> int:
    """Conservative tokenizer-free estimate for UI/guard messages."""
    source = str(text or "")
    if not source:
        return 0
    # Korean/CJK generally consumes tokens more densely than English.  Using
    # 2 chars/token is intentionally conservative for a preflight gate.
    return max(1, (len(source) + 1) // 2)


def trim_style_prompt(value: str, max_chars: int = MAX_STYLE_PROMPT_CHARS) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    suffix = "\n\n[Context Budget] 나머지 코딩 스타일 규칙은 입력 예산 보호를 위해 생략되었습니다."
    return text[: max(0, max_chars - len(suffix))] + suffix


def _source_text(cell: Any) -> str:
    if not isinstance(cell, dict):
        return ""
    source = cell.get("source")
    if isinstance(source, list):
        return "".join(str(item) for item in source)
    return str(source or "")


def _resolve_code_cell(cells: list[Any], requested: int | None) -> int:
    if requested is not None and 0 <= requested < len(cells):
        if isinstance(cells[requested], dict) and cells[requested].get("cell_type") == "code":
            return requested

    # When the active index is unavailable, prefer the first non-empty code
    # cell; if all code cells are empty, use the first code cell.
    first_code = None
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        if first_code is None:
            first_code = index
        if _source_text(cell).strip():
            return index
    if first_code is not None:
        return first_code
    raise ValueError("Notebook에 수정 가능한 Code 셀이 없습니다.")


def build_notebook_edit_context(
    raw_content: str,
    active_cell_index: int | None,
    *,
    max_chars: int = MAX_NOTEBOOK_CONTEXT_CHARS,
) -> NotebookEditContext:
    try:
        notebook = json.loads(str(raw_content or ""))
    except Exception as exc:
        raise ValueError(f"Notebook JSON을 해석할 수 없습니다: {exc}") from exc

    cells = notebook.get("cells") if isinstance(notebook, dict) else None
    if not isinstance(cells, list):
        raise ValueError("유효한 Jupyter Notebook이 아닙니다: cells 배열이 없습니다.")

    active = _resolve_code_cell(cells, active_cell_index)

    # Useful context has three parts:
    #   1) a few early code cells (imports/helpers/DB setup),
    #   2) nearby cells around the active exercise,
    #   3) the active cell itself (always included).
    bootstrap: list[int] = []
    for index, cell in enumerate(cells[: max(active, 0)]):
        if isinstance(cell, dict) and cell.get("cell_type") == "code" and _source_text(cell).strip():
            bootstrap.append(index)
            if len(bootstrap) >= MAX_NOTEBOOK_BOOTSTRAP_CELLS:
                break

    half = MAX_NOTEBOOK_NEARBY_CELLS // 2
    start = max(0, active - half)
    end = min(len(cells), active + half + 1)
    nearby = list(range(start, end))

    ordered: list[int] = []
    for index in [*bootstrap, *nearby, active]:
        if index not in ordered:
            ordered.append(index)

    chunks: list[str] = []
    included: list[int] = []
    compact_chars = 0

    for index in ordered:
        cell = cells[index]
        if not isinstance(cell, dict):
            continue
        cell_type = str(cell.get("cell_type") or "unknown")
        source = _source_text(cell)
        # Empty neighboring cells add no useful context, but the active cell is
        # retained even when empty so the model knows exactly where to write.
        if index != active and not source.strip():
            continue

        marker = "TARGET" if index == active else "CONTEXT"
        chunk = (
            f"\n--- Notebook Cell {index + 1} [{cell_type}] [{marker}] ---\n"
            f"{source}\n"
        )

        if index != active and compact_chars + len(chunk) > max_chars:
            continue

        chunks.append(chunk)
        included.append(index)
        compact_chars += len(chunk)

    if active not in included:
        source = _source_text(cells[active])
        chunk = (
            f"\n--- Notebook Cell {active + 1} [code] [TARGET] ---\n"
            f"{source}\n"
        )
        chunks.append(chunk)
        included.append(active)
        compact_chars += len(chunk)

    # Metadata and outputs are deliberately omitted.  This is the key size
    # reduction for notebooks containing large tracebacks/dataframes/images.
    context_text = "".join(chunks)

    return NotebookEditContext(
        notebook=notebook,
        active_cell_index=active,
        active_cell_source=_source_text(cells[active]),
        context_text=context_text,
        total_cells=len(cells),
        included_cells=sorted(included),
        original_chars=len(str(raw_content or "")),
        compact_chars=len(context_text),
    )


def notebook_source_lines(text: str) -> list[str]:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return []
    parts = normalized.split("\n")
    result: list[str] = []
    for index, line in enumerate(parts):
        if index < len(parts) - 1:
            result.append(line + "\n")
        elif line:
            result.append(line)
    return result


def merge_notebook_cell(context: NotebookEditContext, replacement: str) -> str:
    notebook = json.loads(json.dumps(context.notebook, ensure_ascii=False))
    cell = notebook["cells"][context.active_cell_index]
    cell["source"] = notebook_source_lines(replacement)
    # A changed code cell no longer has a valid execution result.
    cell["execution_count"] = None
    cell["outputs"] = []
    return json.dumps(notebook, ensure_ascii=False, indent=1) + "\n"
