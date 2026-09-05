from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, field


DEFAULT_CHUNK_CHARS = 1000
DEFAULT_OVERLAP_CHARS = 160


@dataclass(slots=True)
class ChunkDraft:
    content: str
    chunk_index: int = 0
    start_line: int | None = None
    end_line: int | None = None
    heading: str = ''
    symbol_name: str = ''
    metadata: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode('utf-8', errors='ignore')).hexdigest()

    @property
    def token_estimate(self) -> int:
        # Provider-neutral preview estimate. Exact billing tokenization belongs to provider layer.
        return max(1, (len(self.content) + 3) // 4)


def normalize_for_checksum(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def document_checksum(text: str) -> str:
    return hashlib.sha256(normalize_for_checksum(text).encode('utf-8', errors='ignore')).hexdigest()


def _line_number(text: str, char_offset: int) -> int:
    return text.count('\n', 0, max(0, char_offset)) + 1


def _recursive_chunks(text: str, *, max_chars: int = DEFAULT_CHUNK_CHARS, overlap: int = DEFAULT_OVERLAP_CHARS, metadata: dict | None = None, heading: str = '') -> list[ChunkDraft]:
    cleaned = str(text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [ChunkDraft(cleaned, start_line=1, end_line=cleaned.count('\n') + 1, heading=heading, metadata=metadata or {})]

    pieces = re.split(r'(\n\s*\n|(?<=[.!?。！？])\s+)', cleaned)
    segments: list[str] = []
    buffer = ''
    for piece in pieces:
        if not piece:
            continue
        if len(buffer) + len(piece) <= max_chars:
            buffer += piece
            continue
        if buffer.strip():
            segments.append(buffer.strip())
        # Very long indivisible piece: cut by character window.
        if len(piece) > max_chars:
            start = 0
            while start < len(piece):
                end = min(len(piece), start + max_chars)
                segments.append(piece[start:end].strip())
                if end >= len(piece):
                    break
                start = max(start + 1, end - overlap)
            buffer = ''
        else:
            buffer = piece
    if buffer.strip():
        segments.append(buffer.strip())

    result: list[ChunkDraft] = []
    search_from = 0
    previous_tail = ''
    for segment in segments:
        content = segment
        if previous_tail and len(content) + len(previous_tail) + 2 <= max_chars + overlap:
            content = previous_tail + '\n\n' + content
        pos = cleaned.find(segment[: min(80, len(segment))], search_from)
        if pos < 0:
            pos = search_from
        start_line = _line_number(cleaned, pos)
        end_line = start_line + content.count('\n')
        result.append(ChunkDraft(content.strip(), start_line=start_line, end_line=end_line, heading=heading, metadata=dict(metadata or {})))
        search_from = max(pos + len(segment), search_from)
        previous_tail = segment[-overlap:].strip() if overlap else ''
    return result


def _markdown_chunks(text: str) -> list[ChunkDraft]:
    lines = str(text or '').splitlines()
    sections: list[tuple[str, int, list[str]]] = []
    heading = ''
    start_line = 1
    buffer: list[str] = []
    for line_no, line in enumerate(lines, start=1):
        if re.match(r'^#{1,6}\s+\S', line):
            if buffer:
                sections.append((heading, start_line, buffer))
            heading = line.strip()
            start_line = line_no
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        sections.append((heading, start_line, buffer))

    result: list[ChunkDraft] = []
    for section_heading, section_start, section_lines in sections:
        section_text = '\n'.join(section_lines).strip()
        chunks = _recursive_chunks(section_text, heading=section_heading, metadata={'strategy': 'HEADER_AWARE'})
        for chunk in chunks:
            if chunk.start_line is not None:
                chunk.start_line += section_start - 1
            if chunk.end_line is not None:
                chunk.end_line += section_start - 1
            result.append(chunk)
    return result


def _python_code_chunks(text: str) -> list[ChunkDraft]:
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _generic_code_chunks(text)

    nodes: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nodes.append(node)

    chunks: list[ChunkDraft] = []
    cursor = 1
    for node in nodes:
        start = int(getattr(node, 'lineno', cursor))
        end = int(getattr(node, 'end_lineno', start))
        # Keep imports/module constants before the first symbol as a useful header chunk.
        if start > cursor:
            prefix = '\n'.join(lines[cursor - 1:start - 1]).strip()
            if prefix and len(prefix) >= 40:
                chunks.extend(_recursive_chunks(prefix, metadata={'strategy': 'PYTHON_MODULE'}, heading='Module', max_chars=900, overlap=80))
                for chunk in chunks[-1:]:
                    chunk.start_line = cursor
                    chunk.end_line = start - 1
        content = '\n'.join(lines[start - 1:end]).strip()
        symbol = getattr(node, 'name', '')
        kind = 'class' if isinstance(node, ast.ClassDef) else 'function'
        if len(content) <= 1600:
            chunks.append(ChunkDraft(content, start_line=start, end_line=end, symbol_name=symbol, metadata={'strategy': 'PYTHON_AST', 'symbol_type': kind}))
        else:
            sub = _recursive_chunks(content, max_chars=1200, overlap=120, metadata={'strategy': 'PYTHON_AST', 'symbol_type': kind}, heading=symbol)
            for item in sub:
                if item.start_line is not None:
                    item.start_line += start - 1
                if item.end_line is not None:
                    item.end_line += start - 1
                item.symbol_name = symbol
            chunks.extend(sub)
        cursor = max(cursor, end + 1)
    if cursor <= len(lines):
        tail = '\n'.join(lines[cursor - 1:]).strip()
        if tail:
            tail_chunks = _recursive_chunks(tail, metadata={'strategy': 'PYTHON_MODULE'}, heading='Module tail', max_chars=900, overlap=80)
            for item in tail_chunks:
                if item.start_line is not None:
                    item.start_line += cursor - 1
                if item.end_line is not None:
                    item.end_line += cursor - 1
            chunks.extend(tail_chunks)
    return chunks or _recursive_chunks(text, metadata={'strategy': 'RECURSIVE_FALLBACK'})


def _sql_chunks(text: str) -> list[ChunkDraft]:
    statements = re.split(r';\s*(?=\n|$)', text)
    result: list[ChunkDraft] = []
    search_from = 0
    for statement in statements:
        value = statement.strip()
        if not value:
            continue
        pos = text.find(value[: min(100, len(value))], search_from)
        if pos < 0:
            pos = search_from
        start_line = _line_number(text, pos)
        chunks = _recursive_chunks(value + (';' if not value.endswith(';') else ''), max_chars=1200, overlap=100, metadata={'strategy': 'SQL_STATEMENT'})
        for item in chunks:
            if item.start_line is not None:
                item.start_line += start_line - 1
            if item.end_line is not None:
                item.end_line += start_line - 1
            match = re.search(r'(?i)\b(?:CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|FUNCTION|PROCEDURE)|ALTER\s+TABLE)\s+([\w\.\[\]"]+)', value)
            if match:
                item.symbol_name = match.group(1)
        result.extend(chunks)
        search_from = pos + len(value)
    return result


def _generic_code_chunks(text: str) -> list[ChunkDraft]:
    lines = text.splitlines()
    symbol_re = re.compile(r'^\s*(?:export\s+)?(?:public\s+|private\s+|protected\s+|static\s+|async\s+)*(?:class|interface|enum|function|def|func|struct|record)\s+([A-Za-z_][\w$]*)')
    starts: list[tuple[int, str]] = []
    for line_no, line in enumerate(lines, start=1):
        match = symbol_re.search(line)
        if match:
            starts.append((line_no, match.group(1)))
    if not starts:
        return _recursive_chunks(text, max_chars=1100, overlap=140, metadata={'strategy': 'CODE_RECURSIVE'})

    result: list[ChunkDraft] = []
    for index, (start, symbol) in enumerate(starts):
        end = starts[index + 1][0] - 1 if index + 1 < len(starts) else len(lines)
        content = '\n'.join(lines[start - 1:end]).strip()
        sub = _recursive_chunks(content, max_chars=1200, overlap=120, metadata={'strategy': 'CODE_SYMBOL'}, heading=symbol)
        for item in sub:
            if item.start_line is not None:
                item.start_line += start - 1
            if item.end_line is not None:
                item.end_line += start - 1
            item.symbol_name = symbol
        result.extend(sub)
    return result


def _table_chunks(text: str) -> list[ChunkDraft]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    result: list[ChunkDraft] = []
    start = 0
    group_size = 40
    overlap_rows = 3
    while start < len(lines):
        end = min(len(lines), start + group_size)
        content = '\n'.join(lines[start:end])
        result.append(ChunkDraft(content, start_line=start + 1, end_line=end, metadata={'strategy': 'TABLE_ROW_GROUP'}))
        if end >= len(lines):
            break
        start = max(start + 1, end - overlap_rows)
    return result


def chunk_document(text: str, document_type: str, language: str = '') -> list[ChunkDraft]:
    kind = str(document_type or 'TEXT').upper()
    lang = str(language or '').lower()
    if kind == 'MARKDOWN':
        chunks = _markdown_chunks(text)
    elif kind == 'SQL' or lang == 'sql':
        chunks = _sql_chunks(text)
    elif kind == 'SOURCE_CODE':
        chunks = _python_code_chunks(text) if 'python' in lang else _generic_code_chunks(text)
    elif kind in {'CSV', 'EXCEL'}:
        chunks = _table_chunks(text)
    else:
        chunks = _recursive_chunks(text, metadata={'strategy': 'RECURSIVE'})

    clean: list[ChunkDraft] = []
    seen_hashes: set[str] = set()
    for item in chunks:
        content = item.content.strip()
        if not content:
            continue
        digest = hashlib.sha256(content.encode('utf-8', errors='ignore')).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        item.content = content
        item.chunk_index = len(clean)
        clean.append(item)
    return clean
