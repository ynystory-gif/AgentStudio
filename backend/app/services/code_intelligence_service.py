from __future__ import annotations

import ast
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DOTTED_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\.]*")
_SKIP_DIRS = {
    ".git", ".idea", ".vscode", "node_modules", "dist", "build", "coverage",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}
_PROJECT_SOURCE_DIRS = ("", "src", "app", "backend", "frontend")


@dataclass
class SymbolDefinition:
    symbol: str
    kind: str
    line: int
    column: int
    signature: str = ""
    documentation: str = ""
    type_hint: str = ""
    value_preview: str = ""
    parameters: list[dict[str, str]] | None = None
    source_line: str = ""
    module: str = ""
    relative_path: str = ""
    absolute_path: str = ""
    external: bool = False
    cell_index: int | None = None
    content: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "kind": self.kind,
            "line": self.line,
            "column": self.column,
            "signature": self.signature,
            "documentation": self.documentation,
            "type_hint": self.type_hint,
            "value_preview": self.value_preview,
            "parameters": self.parameters or [],
            "source_line": self.source_line,
            "module": self.module,
            "relative_path": self.relative_path,
            "absolute_path": self.absolute_path,
            "external": self.external,
            "cell_index": self.cell_index,
            "content": self.content,
        }


def _safe_read_text(path: Path, limit: int = 2_000_000) -> str:
    try:
        if not path.is_file() or path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _source_line(content: str, line: int) -> str:
    rows = str(content or "").splitlines()
    if 1 <= line <= len(rows):
        return rows[line - 1].strip()
    return ""


def _identifier_at(content: str, line: int, column: int) -> tuple[str, str]:
    rows = str(content or "").splitlines()
    if not rows:
        return "", ""
    row_index = max(0, min(len(rows) - 1, int(line or 1) - 1))
    row = rows[row_index]
    cursor = max(0, min(len(row), int(column or 1) - 1))
    probe = cursor
    if probe >= len(row) and row:
        probe = len(row) - 1
    if probe < len(row) and not (row[probe].isalnum() or row[probe] in "_.") and probe > 0:
        probe -= 1

    start = probe
    while start > 0 and (row[start - 1].isalnum() or row[start - 1] in "_."):
        start -= 1
    end = max(probe, start)
    while end < len(row) and (row[end].isalnum() or row[end] in "_."):
        end += 1
    expression = row[start:end].strip(".")
    if not expression:
        return "", ""
    symbol = expression.split(".")[-1]
    if not _IDENTIFIER_RE.fullmatch(symbol):
        return "", ""
    return symbol, expression


def _offset_for_position(content: str, line: int, column: int) -> int:
    rows = str(content or "").splitlines(keepends=True)
    if not rows:
        return 0
    target = max(0, min(len(rows) - 1, int(line or 1) - 1))
    return sum(len(rows[i]) for i in range(target)) + max(0, int(column or 1) - 1)


def _call_context_before_position(content: str, line: int, column: int) -> tuple[str, int, int, str]:
    """Return callable expression, active parameter, open-paren offset and arg text.

    This intentionally works with incomplete Python such as ``fn(``, where AST
    parsing is not possible yet. It scans backwards to the nearest unmatched
    opening parenthesis and counts top-level commas inside that call. The raw
    argument text is also returned so completion can detect already-used keyword
    arguments without executing user code.
    """
    text = str(content or "")
    cursor = max(0, min(len(text), _offset_for_position(text, line, column)))
    stack = 0
    quote = ""
    escaped = False
    open_index = -1
    for index in range(cursor - 1, -1, -1):
        ch = text[index]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
            continue
        if ch == ")":
            stack += 1
        elif ch == "(":
            if stack:
                stack -= 1
            else:
                open_index = index
                break
    if open_index < 0:
        return "", 0, -1, ""

    prefix = text[:open_index].rstrip()
    match = re.search(r"([A-Za-z_][A-Za-z0-9_\.]*)$", prefix)
    if not match:
        return "", 0, -1, ""
    callable_expr = match.group(1)

    active_parameter = 0
    nested = 0
    quote = ""
    escaped = False
    arg_text = text[open_index + 1:cursor]
    for ch in arg_text:
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
        elif ch in "([{":
            nested += 1
        elif ch in ")]}":
            nested = max(0, nested - 1)
        elif ch == "," and nested == 0:
            active_parameter += 1
    return callable_expr, active_parameter, open_index, arg_text


def _callable_before_position(content: str, line: int, column: int) -> tuple[str, int]:
    callable_expr, active_parameter, _open_index, _arg_text = _call_context_before_position(content, line, column)
    return callable_expr, active_parameter


def _annotation_text(annotation: ast.expr | None) -> str:
    if annotation is None:
        return ""
    try:
        return ast.unparse(annotation)
    except Exception:
        return ""


def _value_text(value: ast.AST | None, limit: int = 220) -> str:
    if value is None:
        return ""
    try:
        rendered = ast.unparse(value)
    except Exception:
        return ""
    return rendered if len(rendered) <= limit else rendered[:limit - 1] + "…"


def _function_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict[str, str]]:
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    rows: list[dict[str, str]] = []
    for item, default in zip(positional, defaults):
        rows.append({
            "name": item.arg,
            "kind": "positional",
            "annotation": _annotation_text(item.annotation),
            "default": _value_text(default),
            "documentation": "",
        })
    if args.vararg:
        rows.append({"name": f"*{args.vararg.arg}", "kind": "vararg", "annotation": _annotation_text(args.vararg.annotation), "default": "", "documentation": ""})
    for item, default in zip(args.kwonlyargs, args.kw_defaults):
        rows.append({
            "name": item.arg,
            "kind": "keyword_only",
            "annotation": _annotation_text(item.annotation),
            "default": _value_text(default),
            "documentation": "",
        })
    if args.kwarg:
        rows.append({"name": f"**{args.kwarg.arg}", "kind": "kwarg", "annotation": _annotation_text(args.kwarg.annotation), "default": "", "documentation": ""})
    return rows


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    pieces: list[str] = []
    for row in _function_parameters(node):
        label = row["name"]
        if row["annotation"]:
            label += f": {row['annotation']}"
        if row["default"]:
            label += f" = {row['default']}"
        pieces.append(label)
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    returns = _annotation_text(node.returns)
    suffix = f" -> {returns}" if returns else ""
    return f"{prefix}{node.name}({', '.join(pieces)}){suffix}"


def _field_alias(value: ast.AST | None) -> str:
    """Extract a Pydantic-style ``Field(alias=...)`` keyword when statically visible."""
    if not isinstance(value, ast.Call):
        return ""
    try:
        func_name = ast.unparse(value.func)
    except Exception:
        func_name = ""
    if not (func_name == "Field" or func_name.endswith(".Field")):
        return ""
    for keyword in value.keywords:
        if keyword.arg not in {"alias", "validation_alias"}:
            continue
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return str(keyword.value.value)
    return ""


def _class_parameters(node: ast.ClassDef) -> list[dict[str, str]]:
    """Return constructor-like parameters discoverable from a class body.

    Preference order:
    1. Explicit ``__init__``/``__new__`` parameters.
    2. Typed class fields (including Pydantic ``Field(alias=...)`` fields).

    Inherited fields are merged later when module resolution has access to the
    project/site-package source tree.
    """
    explicit: list[dict[str, str]] = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name in {"__init__", "__new__"}:
            explicit = [
                row for row in _function_parameters(item)
                if row.get("name", "").lstrip("*") not in {"self", "cls"}
            ]
            if explicit:
                return explicit

    fields: list[dict[str, str]] = []
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            source_name = item.target.id
            if source_name.startswith("_"):
                continue
            annotation = _annotation_text(item.annotation)
            if "ClassVar" in annotation:
                continue
            public_name = _field_alias(item.value) or source_name
            fields.append({
                "name": public_name,
                "kind": "keyword_only",
                "annotation": annotation,
                "default": _value_text(item.value),
                "documentation": "",
            })
        elif isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
            source_name = item.targets[0].id
            if source_name.startswith("_"):
                continue
            alias = _field_alias(item.value)
            # Untyped assignments are only constructor-like when they expose an
            # explicit Field alias. This avoids suggesting constants as kwargs.
            if alias:
                fields.append({
                    "name": alias,
                    "kind": "keyword_only",
                    "annotation": "",
                    "default": _value_text(item.value),
                    "documentation": "",
                })
    return fields


def _parameter_signature(name: str, parameters: list[dict[str, str]], limit: int = 14) -> str:
    pieces: list[str] = []
    visible = [row for row in parameters if str(row.get("name") or "").lstrip("*") not in {"self", "cls"}]
    for row in visible[:limit]:
        label = str(row.get("name") or "")
        if not label:
            continue
        annotation = str(row.get("annotation") or "")
        default = str(row.get("default") or "")
        if annotation:
            label += f": {annotation}"
        if default:
            label += f" = {default}"
        pieces.append(label)
    if len(visible) > limit:
        pieces.append("…")
    return f"{name}({', '.join(pieces)})"


def _definition_from_node(
    node: ast.AST,
    content: str,
    *,
    symbol: str,
    relative_path: str = "",
    absolute_path: str = "",
    external: bool = False,
    cell_index: int | None = None,
    module: str = "",
) -> SymbolDefinition | None:
    line = int(getattr(node, "lineno", 1) or 1)
    column = int(getattr(node, "col_offset", 0) or 0) + 1
    common = dict(
        symbol=symbol,
        line=line,
        column=column,
        source_line=_source_line(content, line),
        relative_path=relative_path,
        absolute_path=absolute_path,
        external=external,
        cell_index=cell_index,
        module=module,
        content=content if len(content) <= 1_000_000 else "",
    )
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return SymbolDefinition(
            kind="function",
            signature=_function_signature(node),
            documentation=ast.get_docstring(node) or "",
            type_hint=_annotation_text(node.returns),
            parameters=_function_parameters(node),
            **common,
        )
    if isinstance(node, ast.ClassDef):
        parameters = _class_parameters(node)
        if parameters:
            signature = _parameter_signature(node.name, parameters)
        else:
            bases = []
            for base in node.bases:
                bases.append(_value_text(base))
            signature = f"class {node.name}" + (f"({', '.join(filter(None, bases))})" if bases else "")
        return SymbolDefinition(
            kind="class",
            signature=signature,
            documentation=ast.get_docstring(node) or "",
            parameters=parameters,
            **common,
        )
    if isinstance(node, ast.arg):
        return SymbolDefinition(kind="parameter", type_hint=_annotation_text(node.annotation), **common)
    if isinstance(node, ast.Assign):
        return SymbolDefinition(kind="variable", value_preview=_value_text(node.value), **common)
    if isinstance(node, ast.AnnAssign):
        return SymbolDefinition(kind="variable", type_hint=_annotation_text(node.annotation), value_preview=_value_text(node.value), **common)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return SymbolDefinition(kind="import", **common)
    return None


def _target_name_nodes(tree: ast.AST, symbol: str) -> list[ast.AST]:
    matches: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
            matches.append(node)
        elif isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == symbol for target in node.targets):
                matches.append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == symbol:
            matches.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
                if arg.arg == symbol:
                    matches.append(arg)
            if node.args.vararg and node.args.vararg.arg == symbol:
                matches.append(node.args.vararg)
            if node.args.kwarg and node.args.kwarg.arg == symbol:
                matches.append(node.args.kwarg)
    return matches


def _parse_python(content: str) -> ast.Module | None:
    try:
        return ast.parse(str(content or ""))
    except (SyntaxError, ValueError, TypeError):
        return None


def _find_local_python_definition(
    content: str,
    symbol: str,
    usage_line: int,
    *,
    relative_path: str = "",
    absolute_path: str = "",
    external: bool = False,
    cell_index: int | None = None,
    module: str = "",
) -> SymbolDefinition | None:
    tree = _parse_python(content)
    if tree is None:
        return None
    candidates = _target_name_nodes(tree, symbol)
    if not candidates:
        return None
    before = [node for node in candidates if int(getattr(node, "lineno", 0) or 0) <= max(1, usage_line)]
    target = max(before or candidates, key=lambda node: int(getattr(node, "lineno", 0) or 0))
    return _definition_from_node(
        target,
        content,
        symbol=symbol,
        relative_path=relative_path,
        absolute_path=absolute_path,
        external=external,
        cell_index=cell_index,
        module=module,
    )


def _import_map(content: str) -> dict[str, tuple[str, str]]:
    tree = _parse_python(content)
    result: dict[str, tuple[str, str]] = {}
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                prefix = "." * int(node.level or 0)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    result[alias.asname or alias.name] = (prefix + module, alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    exposed = alias.asname or alias.name.split(".")[0]
                    result[exposed] = (alias.name, "")
        return result

    # v5.470: an editor buffer is often intentionally incomplete while the user
    # has just typed ``ChatOpenAI(``. Keep imports resolvable with a conservative
    # line parser so Ctrl+Space can still offer callable keyword arguments.
    for raw_line in str(content or "").splitlines():
        line = raw_line.strip()
        from_match = re.match(r"^from\s+([\.A-Za-z_][\w\.]*)\s+import\s+(.+)$", line)
        if from_match:
            module = from_match.group(1)
            for chunk in from_match.group(2).split(","):
                piece = chunk.strip().strip("()")
                match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?$", piece)
                if not match or match.group(1) == "*":
                    continue
                original, alias = match.group(1), match.group(2)
                result[alias or original] = (module, original)
            continue
        import_match = re.match(r"^import\s+(.+)$", line)
        if import_match:
            for chunk in import_match.group(1).split(","):
                piece = chunk.strip()
                match = re.match(r"^([A-Za-z_][A-Za-z0-9_\.]*)(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?$", piece)
                if not match:
                    continue
                module, alias = match.group(1), match.group(2)
                result[alias or module.split(".")[0]] = (module, "")
    return result


def _site_package_roots(project_root: Path) -> list[Path]:
    roots: list[Path] = []
    patterns = [
        ".venv/Lib/site-packages", "venv/Lib/site-packages",
        ".venv/lib/python*/site-packages", "venv/lib/python*/site-packages",
    ]
    for pattern in patterns:
        for path in project_root.glob(pattern):
            if path.is_dir() and path not in roots:
                roots.append(path)
    for raw in sys.path:
        try:
            path = Path(raw).resolve()
        except Exception:
            continue
        if path.is_dir() and path not in roots:
            roots.append(path)
    return roots


def _module_candidates(project_root: Path, module: str) -> Iterable[Path]:
    clean = str(module or "").strip(".")
    if not clean:
        return []
    rel = Path(*clean.split("."))
    bases: list[Path] = []
    for source_dir in _PROJECT_SOURCE_DIRS:
        base = (project_root / source_dir).resolve()
        if base.is_dir() and base not in bases:
            bases.append(base)
    bases.extend(path for path in _site_package_roots(project_root) if path not in bases)
    candidates: list[Path] = []
    for base in bases:
        py = base / rel.with_suffix(".py")
        init = base / rel / "__init__.py"
        if py.is_file():
            candidates.append(py)
        if init.is_file():
            candidates.append(init)
    return candidates


def _resolve_relative_module(current_module: str, imported_module: str) -> str:
    if not imported_module.startswith("."):
        return imported_module
    level = len(imported_module) - len(imported_module.lstrip("."))
    suffix = imported_module[level:]
    parts = current_module.split(".") if current_module else []
    if parts:
        parts = parts[:-1]
    keep = max(0, len(parts) - max(0, level - 1))
    base = parts[:keep]
    if suffix:
        base.extend(suffix.split("."))
    return ".".join(filter(None, base))


def _resolve_relative_module_for_file(project_root: Path, file_path: Path, fallback_module: str, imported_module: str) -> str:
    if not str(imported_module or "").startswith("."):
        return str(imported_module or "")
    current_module = _module_name_for_file(project_root, file_path) or fallback_module
    level = len(imported_module) - len(imported_module.lstrip("."))
    suffix = imported_module[level:]
    parts = current_module.split(".") if current_module else []
    # ``pkg/__init__.py`` represents the package itself, while ``pkg/mod.py``
    # represents a module whose relative imports start from its parent package.
    if file_path.name != "__init__.py" and parts:
        parts = parts[:-1]
    keep = max(0, len(parts) - max(0, level - 1))
    base = parts[:keep]
    if suffix:
        base.extend(suffix.split("."))
    return ".".join(filter(None, base))


def _module_name_for_file(project_root: Path, file_path: Path) -> str:
    # Prefer virtualenv/site-package roots before the project root. Otherwise a
    # project-local ``.venv/Lib/site-packages/pkg`` path is misidentified as
    # ``.venv.Lib.site-packages.pkg`` and relative re-exports cannot be resolved.
    roots = list(_site_package_roots(project_root))
    roots.extend(project_root / source for source in _PROJECT_SOURCE_DIRS)
    for base in roots:
        try:
            rel = file_path.resolve().relative_to(base.resolve())
        except Exception:
            continue
        parts = list(rel.parts)
        if not parts:
            continue
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        elif parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        return ".".join(parts)
    return ""


def _definition_path_fields(project_root: Path, file_path: Path) -> tuple[str, str, bool]:
    absolute = str(file_path.resolve())
    try:
        relative_path = file_path.resolve().relative_to(project_root.resolve())
        parts = {part.casefold() for part in relative_path.parts}
        # Project virtualenv sources are library definitions, not editable project
        # files. Keep them in the read-only Definition Preview instead of opening
        # .venv files as normal project tabs.
        if ".venv" in parts or "venv" in parts or "site-packages" in parts:
            return "", absolute, True
        return relative_path.as_posix(), absolute, False
    except Exception:
        return "", absolute, True


def _class_node(content: str, symbol: str) -> ast.ClassDef | None:
    tree = _parse_python(content)
    if tree is None:
        return None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == symbol:
            return node
    return None


def _base_class_target(content: str, current_module: str, base: ast.expr) -> tuple[str, str]:
    imports = _import_map(content)
    try:
        rendered = ast.unparse(base)
    except Exception:
        rendered = ""
    rendered = str(rendered or "").strip()
    if not rendered:
        return "", ""

    parts = rendered.split(".")
    exposed = parts[0]
    imported = imports.get(exposed)
    if imported:
        imported_module, original = imported
        imported_module = _resolve_relative_module(current_module, imported_module)
        if original:
            base_symbol = original
            if len(parts) > 1:
                # ``Alias.Inner`` style references are rare for base classes, but
                # retain the trailing symbol rather than dropping it.
                base_symbol = parts[-1]
            return imported_module, base_symbol
        # ``import package as alias``: append remaining dotted path and split the
        # final name as the class symbol.
        module_parts = [imported_module, *parts[1:-1]]
        return ".".join(filter(None, module_parts)), parts[-1]

    if len(parts) == 1:
        return current_module, parts[0]
    return ".".join(parts[:-1]), parts[-1]


def _merge_parameters(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    order: list[str] = []
    merged: dict[str, dict[str, str]] = {}
    for group in groups:
        for row in group:
            name = str(row.get("name") or "")
            key = name.lstrip("*")
            if not key or key in {"self", "cls"}:
                continue
            if key not in merged:
                order.append(key)
            merged[key] = dict(row)
    return [merged[key] for key in order]


def _collect_class_parameters_from_file(
    project_root: Path,
    file_path: Path,
    module: str,
    class_name: str,
    *,
    visited: set[tuple[str, str]] | None = None,
    depth: int = 0,
) -> list[dict[str, str]]:
    """Collect constructor/Pydantic field kwargs across a class hierarchy.

    This is static source analysis only. It never imports or executes project or
    third-party code. That keeps Ctrl+Space safe inside notebooks while still
    exposing kwargs such as ``model=`` and ``temperature=`` for ChatOpenAI.
    """
    if depth > 8:
        return []
    visited = visited or set()
    key = (str(file_path.resolve()), class_name)
    if key in visited:
        return []
    visited.add(key)

    content = _safe_read_text(file_path)
    node = _class_node(content, class_name)
    if not node:
        return []

    inherited: list[dict[str, str]] = []
    for base in node.bases:
        base_module, base_symbol = _base_class_target(content, module, base)
        if not base_symbol or base_symbol in {"object", "ABC"}:
            continue

        # Same-module class (common for BaseChatOpenAI -> ChatOpenAI).
        if base_module == module and _class_node(content, base_symbol):
            inherited = _merge_parameters(
                inherited,
                _collect_class_parameters_from_file(
                    project_root,
                    file_path,
                    module,
                    base_symbol,
                    visited=visited,
                    depth=depth + 1,
                ),
            )
            continue

        for candidate in _module_candidates(project_root, base_module):
            candidate_content = _safe_read_text(candidate)
            if not _class_node(candidate_content, base_symbol):
                continue
            candidate_module = _module_name_for_file(project_root, candidate) or base_module
            inherited = _merge_parameters(
                inherited,
                _collect_class_parameters_from_file(
                    project_root,
                    candidate,
                    candidate_module,
                    base_symbol,
                    visited=visited,
                    depth=depth + 1,
                ),
            )
            break

    direct = _class_parameters(node)
    return _merge_parameters(inherited, direct)


def _resolve_symbol_in_module(
    project_root: Path,
    module: str,
    symbol: str,
    *,
    visited: set[tuple[str, str]] | None = None,
    depth: int = 0,
) -> SymbolDefinition | None:
    if depth > 8:
        return None
    key = (module, symbol)
    visited = visited or set()
    if key in visited:
        return None
    visited.add(key)

    for file_path in _module_candidates(project_root, module):
        content = _safe_read_text(file_path)
        if not content:
            continue
        relative, absolute, external = _definition_path_fields(project_root, file_path)
        local = _find_local_python_definition(
            content,
            symbol,
            usage_line=10**9,
            relative_path=relative,
            absolute_path=absolute,
            external=external,
            module=module,
        )
        if local:
            if local.kind == "class":
                parameters = _collect_class_parameters_from_file(
                    project_root,
                    file_path,
                    _module_name_for_file(project_root, file_path) or module,
                    symbol,
                )
                if parameters:
                    local.parameters = parameters
                    local.signature = _parameter_signature(symbol, parameters)
            return local

        imports = _import_map(content)
        imported = imports.get(symbol)
        if imported:
            imported_module, original = imported
            imported_module = _resolve_relative_module_for_file(project_root, file_path, module, imported_module)
            target_symbol = original or symbol
            nested = _resolve_symbol_in_module(
                project_root,
                imported_module,
                target_symbol,
                visited=visited,
                depth=depth + 1,
            )
            if nested:
                return nested
    return None


def _resolve_imported_python_symbol(
    project_root: Path,
    contents: Iterable[str],
    symbol: str,
) -> SymbolDefinition | None:
    merged: dict[str, tuple[str, str]] = {}
    for content in contents:
        merged.update(_import_map(content))
    imported = merged.get(symbol)
    if not imported:
        return None
    module, original = imported
    module = module.lstrip(".")
    target_symbol = original or symbol
    return _resolve_symbol_in_module(project_root, module, target_symbol)


def _iter_project_source_files(project_root: Path, language: str) -> Iterable[Path]:
    extensions = {
        "python": {".py", ".pyw"},
        "javascript": {".js", ".jsx", ".mjs", ".cjs"},
        "typescript": {".ts", ".tsx", ".mts", ".cts"},
        "csharp": {".cs"},
        "java": {".java"},
    }.get(language, {".py", ".js", ".ts", ".tsx", ".cs", ".java"})
    count = 0
    for directory, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [
            name for name in dirnames
            if name not in _SKIP_DIRS
            and name not in {"venv", ".venv"}
            and not name.startswith(".venv")
        ]
        for filename in filenames:
            if count >= 1600:
                return
            path = Path(directory) / filename
            if path.suffix.lower() not in extensions:
                continue
            count += 1
            yield path


def _search_python_project_symbol(project_root: Path, symbol: str) -> SymbolDefinition | None:
    pattern = re.compile(rf"(?m)^\s*(?:async\s+def|def|class)\s+{re.escape(symbol)}\b|^\s*{re.escape(symbol)}\s*(?::[^=\n]+)?=")
    for path in _iter_project_source_files(project_root, "python"):
        content = _safe_read_text(path, limit=750_000)
        if not content or not pattern.search(content):
            continue
        relative, absolute, external = _definition_path_fields(project_root, path)
        definition = _find_local_python_definition(
            content,
            symbol,
            usage_line=10**9,
            relative_path=relative,
            absolute_path=absolute,
            external=external,
        )
        if definition:
            return definition
    return None


def _parse_notebook_code_cells(notebook_content: str) -> list[tuple[int, str]]:
    try:
        notebook = json.loads(str(notebook_content or ""))
    except Exception:
        return []
    rows: list[tuple[int, str]] = []
    for index, cell in enumerate(notebook.get("cells") or []):
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            text = "".join(str(item) for item in source)
        else:
            text = str(source or "")
        rows.append((index, text))
    return rows


def _resolve_python(
    project_root: Path,
    *,
    relative_path: str,
    content: str,
    line: int,
    column: int,
    notebook_content: str = "",
    cell_index: int | None = None,
    action: str = "all",
) -> dict[str, Any]:
    symbol, expression = _identifier_at(content, line, column)
    active_parameter = 0
    if action == "signature" or not symbol:
        callable_expression, active_parameter = _callable_before_position(content, line, column)
        if callable_expression:
            expression = callable_expression
            symbol = callable_expression.split(".")[-1]
    if not symbol:
        return {"ok": False, "code": "NO_SYMBOL", "message": "현재 위치에서 코드 심볼을 찾지 못했습니다."}

    notebook_cells = _parse_notebook_code_cells(notebook_content) if notebook_content else []
    definition: SymbolDefinition | None = None

    # Notebook variables/functions are resolved across code cells. Prefer the
    # latest definition before the active cell, which matches normal notebook
    # authoring expectations without executing user code.
    if notebook_cells and cell_index is not None:
        ordered = [row for row in notebook_cells if row[0] <= cell_index]
        for target_index, cell_source in reversed(ordered):
            usage_line = line if target_index == cell_index else 10**9
            definition = _find_local_python_definition(
                content if target_index == cell_index else cell_source,
                symbol,
                usage_line,
                relative_path=relative_path,
                cell_index=target_index,
            )
            if definition:
                break
    else:
        definition = _find_local_python_definition(
            content,
            symbol,
            line,
            relative_path=relative_path,
        )

    import_sources = [row[1] for row in notebook_cells if cell_index is None or row[0] <= cell_index] if notebook_cells else [content]
    if not definition:
        definition = _resolve_imported_python_symbol(project_root, import_sources, symbol)
    if not definition:
        definition = _search_python_project_symbol(project_root, symbol)

    if not definition:
        return {
            "ok": True,
            "symbol": symbol,
            "expression": expression or symbol,
            "kind": "symbol",
            "active_parameter": active_parameter,
            "definition": None,
            "signature": "",
            "parameters": [],
            "documentation": "",
            "message": "정의를 찾지 못했습니다.",
        }

    return {
        "ok": True,
        "symbol": symbol,
        "expression": expression or symbol,
        "kind": definition.kind,
        "active_parameter": active_parameter,
        "definition": definition.as_dict(),
        "signature": definition.signature,
        "parameters": definition.parameters or [],
        "documentation": definition.documentation,
        "type_hint": definition.type_hint,
        "value_preview": definition.value_preview,
        "module": definition.module,
    }


def _generic_definition(content: str, symbol: str, relative_path: str) -> SymbolDefinition | None:
    patterns = [
        ("class", re.compile(rf"(?m)^\s*(?:export\s+)?(?:public\s+|private\s+|protected\s+|internal\s+)?class\s+{re.escape(symbol)}\b")),
        ("function", re.compile(rf"(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+{re.escape(symbol)}\s*\([^\n]*")),
        ("function", re.compile(rf"(?m)^\s*(?:public\s+|private\s+|protected\s+|internal\s+|static\s+|async\s+)*[A-Za-z_][\w<>,\[\]?\. ]*\s+{re.escape(symbol)}\s*\([^\n]*")),
        ("variable", re.compile(rf"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+{re.escape(symbol)}\b[^\n]*")),
    ]
    for kind, pattern in patterns:
        match = pattern.search(content)
        if not match:
            continue
        line = content.count("\n", 0, match.start()) + 1
        line_start = content.rfind("\n", 0, match.start()) + 1
        column = max(1, match.start() - line_start + 1)
        source = _source_line(content, line)
        return SymbolDefinition(
            symbol=symbol,
            kind=kind,
            line=line,
            column=column,
            signature=source if kind in {"function", "class"} else "",
            value_preview=source if kind == "variable" else "",
            relative_path=relative_path,
            source_line=source,
            content=content if len(content) <= 1_000_000 else "",
        )
    return None


def _resolve_generic(project_root: Path, *, relative_path: str, content: str, line: int, column: int, language: str) -> dict[str, Any]:
    symbol, expression = _identifier_at(content, line, column)
    if not symbol:
        return {"ok": False, "code": "NO_SYMBOL", "message": "현재 위치에서 코드 심볼을 찾지 못했습니다."}
    definition = _generic_definition(content, symbol, relative_path)
    if not definition:
        for path in _iter_project_source_files(project_root, language):
            candidate = _safe_read_text(path, limit=750_000)
            if symbol not in candidate:
                continue
            try:
                rel = path.relative_to(project_root).as_posix()
            except Exception:
                rel = ""
            definition = _generic_definition(candidate, symbol, rel)
            if definition:
                definition.absolute_path = str(path.resolve())
                break
    return {
        "ok": True,
        "symbol": symbol,
        "expression": expression or symbol,
        "kind": definition.kind if definition else "symbol",
        "active_parameter": 0,
        "definition": definition.as_dict() if definition else None,
        "signature": definition.signature if definition else "",
        "parameters": [],
        "documentation": "",
        "value_preview": definition.value_preview if definition else "",
        "message": "" if definition else "정의를 찾지 못했습니다.",
    }



def _completion_prefix(content: str, line: int, column: int) -> str:
    rows = str(content or "").splitlines()
    if not rows or line < 1 or line > len(rows):
        return ""
    row = rows[line - 1]
    before = row[: max(0, column - 1)]
    match = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", before)
    return match.group(0) if match else ""


def _python_completion_symbols(source: str, *, cell_index: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        tree = ast.parse(str(source or ""))
    except SyntaxError:
        tree = None

    def add(name: str, kind: str, line: int = 1, detail: str = "", documentation: str = "") -> None:
        value = str(name or "").strip()
        if not value or not _IDENTIFIER_RE.fullmatch(value):
            return
        rows.append({
            "label": value,
            "kind": kind,
            "detail": detail or _source_line(source, line),
            "documentation": documentation,
            "insert_text": value,
            "line": max(1, int(line or 1)),
            "cell_index": cell_index,
        })

    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add(node.name, "function", getattr(node, "lineno", 1), _source_line(source, getattr(node, "lineno", 1)), ast.get_docstring(node) or "")
                for arg in list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs):
                    add(arg.arg, "parameter", getattr(arg, "lineno", getattr(node, "lineno", 1)), f"parameter of {node.name}")
                if node.args.vararg:
                    add(node.args.vararg.arg, "parameter", getattr(node.args.vararg, "lineno", getattr(node, "lineno", 1)), f"* parameter of {node.name}")
                if node.args.kwarg:
                    add(node.args.kwarg.arg, "parameter", getattr(node.args.kwarg, "lineno", getattr(node, "lineno", 1)), f"** parameter of {node.name}")
            elif isinstance(node, ast.ClassDef):
                add(node.name, "class", getattr(node, "lineno", 1), _source_line(source, getattr(node, "lineno", 1)), ast.get_docstring(node) or "")
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                add(node.id, "variable", getattr(node, "lineno", 1))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    add(alias.asname or alias.name.split(".")[0], "module", getattr(node, "lineno", 1), f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    add(alias.asname or alias.name, "module", getattr(node, "lineno", 1), f"from {node.module or ''} import {alias.name}")
    else:
        # Even while the current line is incomplete, keep common assignment/function
        # names available for Ctrl+Space without executing user code.
        for number, row in enumerate(str(source or "").splitlines(), start=1):
            match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", row)
            if match:
                add(match.group(1), "variable", number, row.strip())
            match = re.match(r"\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", row)
            if match:
                add(match.group(1), "function", number, row.strip())
            match = re.match(r"\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b", row)
            if match:
                add(match.group(1), "class", number, row.strip())
    return rows


def _top_level_argument_chunks(arg_text: str) -> list[str]:
    chunks: list[str] = []
    start = 0
    nested = 0
    quote = ""
    escaped = False
    text = str(arg_text or "")
    for index, ch in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
        elif ch in "([{":
            nested += 1
        elif ch in ")]}":
            nested = max(0, nested - 1)
        elif ch == "," and nested == 0:
            chunks.append(text[start:index])
            start = index + 1
    chunks.append(text[start:])
    return chunks


def _used_keyword_arguments(arg_text: str) -> set[str]:
    used: set[str] = set()
    for chunk in _top_level_argument_chunks(arg_text):
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", chunk)
        if match:
            used.add(match.group(1))
    return used


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _best_value_symbol(parameter_name: str, candidates: list[dict[str, Any]]) -> str:
    """Pick a visible variable/constant that plausibly supplies a keyword value."""
    param = str(parameter_name or "").lstrip("*")
    if not param:
        return ""
    param_norm = _normalized_name(param)
    scored: list[tuple[int, int, str]] = []
    for index, item in enumerate(candidates):
        if str(item.get("kind") or "") not in {"variable", "parameter"}:
            continue
        label = str(item.get("label") or "")
        if not label or not _IDENTIFIER_RE.fullmatch(label):
            continue
        label_norm = _normalized_name(label)
        score = 50
        if label == param:
            score = 0
        elif label.lower() == param.lower():
            score = 1
        elif label == param.upper():
            score = 2
        elif label_norm == param_norm:
            score = 3
        elif label_norm.startswith(param_norm) or param_norm.startswith(label_norm):
            score = 5
        elif param_norm and param_norm in label_norm:
            score = 7
        else:
            continue
        # Constants such as MODEL_NAME / TEMPERATURE are especially useful in
        # constructor calls and should beat unrelated lowercase locals.
        if label.isupper():
            score -= 1
        scored.append((score, index, label))
    if not scored:
        return ""
    scored.sort(key=lambda row: (row[0], row[1], len(row[2])))
    return scored[0][2]


def _keyword_argument_completions(
    callable_expression: str,
    parameters: list[dict[str, Any]],
    visible_candidates: list[dict[str, Any]],
    *,
    prefix: str,
    used_keywords: set[str],
) -> list[dict[str, Any]]:
    rows: list[tuple[int, int, dict[str, Any]]] = []
    for index, parameter in enumerate(parameters):
        raw_name = str(parameter.get("name") or "")
        name = raw_name.lstrip("*")
        if not name or raw_name.startswith("*") or name in {"self", "cls"} or name in used_keywords:
            continue
        if prefix and not name.startswith(prefix):
            continue
        value_symbol = _best_value_symbol(name, visible_candidates)
        insert_text = f"{name}={value_symbol}" if value_symbol else f"{name}="
        annotation = str(parameter.get("annotation") or "")
        default = str(parameter.get("default") or "")
        details = [f"{callable_expression} parameter"]
        if annotation:
            details.append(annotation)
        if default:
            details.append(f"default={default}")
        item = {
            "label": insert_text,
            "kind": "keyword",
            "detail": " · ".join(details),
            "documentation": str(parameter.get("documentation") or ""),
            "insert_text": insert_text,
            "parameter_name": name,
        }
        # Suggestions that can immediately bind to an existing variable appear
        # first. This yields model=MODEL_NAME / temperature=TEMPERATURE in the
        # common ChatOpenAI notebook setup instead of a global-symbol dump.
        rows.append((0 if value_symbol else 1, index, item))
    rows.sort(key=lambda row: (row[0], row[1]))
    return [item for _matched, _index, item in rows]


def _python_completions(
    project_root: Path,
    *,
    relative_path: str,
    content: str,
    line: int,
    column: int,
    notebook_content: str = "",
    cell_index: int | None = None,
) -> dict[str, Any]:
    prefix = _completion_prefix(content, line, column)
    candidates: list[dict[str, Any]] = []

    notebook_cells = _parse_notebook_code_cells(notebook_content) if notebook_content else []
    if notebook_cells and cell_index is not None:
        for target_index, cell_source in notebook_cells:
            if target_index > cell_index:
                continue
            source = content if target_index == cell_index else cell_source
            candidates.extend(_python_completion_symbols(source, cell_index=target_index))
    else:
        candidates.extend(_python_completion_symbols(content, cell_index=cell_index))

    # v5.470: Ctrl+Space inside a call is context-sensitive. Resolve the current
    # callable and suggest its keyword arguments before considering global symbols.
    callable_expression, active_parameter, _open_index, arg_text = _call_context_before_position(content, line, column)
    if callable_expression:
        signature_result = _resolve_python(
            project_root,
            relative_path=relative_path,
            content=content,
            line=line,
            column=column,
            notebook_content=notebook_content,
            cell_index=cell_index,
            action="signature",
        )
        parameters = list(signature_result.get("parameters") or []) if isinstance(signature_result, dict) else []
        keyword_items = _keyword_argument_completions(
            callable_expression,
            parameters,
            candidates,
            prefix=prefix,
            used_keywords=_used_keyword_arguments(arg_text),
        )
        if keyword_items:
            return {
                "ok": True,
                "prefix": prefix,
                "completion_context": "call_arguments",
                "callable": callable_expression,
                "active_parameter": active_parameter,
                "signature": str(signature_result.get("signature") or ""),
                "completions": keyword_items[:120],
                "message": "",
            }

    # A small safe builtin set makes manual Ctrl+Space useful outside callable
    # arguments. No project code is imported/executed.
    for name in (
        "print", "len", "range", "enumerate", "zip", "list", "dict", "set", "tuple",
        "str", "int", "float", "bool", "sum", "min", "max", "sorted", "open",
        "isinstance", "getattr", "hasattr", "Exception", "ValueError", "TypeError",
    ):
        candidates.append({
            "label": name, "kind": "builtin", "detail": "Python built-in",
            "documentation": "", "insert_text": name, "line": 1, "cell_index": None,
        })

    # Later Notebook cells/definitions win so a redefinition mirrors normal
    # Notebook authoring expectations. Local variables are ranked before builtins.
    dedup: dict[str, dict[str, Any]] = {}
    for item in candidates:
        dedup[str(item.get("label") or "")] = item
    filtered = [item for label, item in dedup.items() if label and (not prefix or label.startswith(prefix))]
    priority = {"variable": 0, "parameter": 1, "function": 2, "class": 3, "module": 4, "builtin": 8}
    filtered.sort(key=lambda item: (priority.get(str(item.get("kind") or ""), 6), str(item.get("label") or "").lower()))
    return {
        "ok": True,
        "prefix": prefix,
        "completion_context": "symbols",
        "completions": filtered[:200],
        "message": "" if filtered else "현재 위치에서 추천 가능한 심볼을 찾지 못했습니다.",
    }


def _generic_completions(content: str, line: int, column: int) -> dict[str, Any]:
    prefix = _completion_prefix(content, line, column)
    candidates: list[dict[str, Any]] = []
    patterns = [
        ("class", re.compile(r"(?m)^\s*(?:export\s+)?(?:public\s+|private\s+|protected\s+|internal\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)\b")),
        ("function", re.compile(r"(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")),
        ("variable", re.compile(r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\b")),
    ]
    for kind, pattern in patterns:
        for match in pattern.finditer(str(content or "")):
            label = match.group(1)
            if prefix and not label.startswith(prefix):
                continue
            line_no = str(content or "").count("\n", 0, match.start()) + 1
            candidates.append({"label": label, "kind": kind, "detail": _source_line(content, line_no), "documentation": "", "insert_text": label, "line": line_no})
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in candidates:
        if item["label"] in seen:
            continue
        seen.add(item["label"]); unique.append(item)
    return {"ok": True, "prefix": prefix, "completions": unique[:200]}

def resolve_code_intelligence(payload: dict[str, Any]) -> dict[str, Any]:
    project_root = Path(str(payload.get("root") or "")).expanduser().resolve()
    relative_path = str(payload.get("relative_path") or "").replace("\\", "/")
    content = str(payload.get("content") or "")
    language = str(payload.get("language") or "").strip().lower()
    line = max(1, int(payload.get("line") or 1))
    column = max(1, int(payload.get("column") or 1))
    action = str(payload.get("action") or "all").strip().lower()
    notebook_content = str(payload.get("notebook_content") or "")
    raw_cell_index = payload.get("cell_index")
    cell_index = int(raw_cell_index) if raw_cell_index is not None and str(raw_cell_index) != "" else None

    if action == "completion":
        if language == "python" or relative_path.lower().endswith((".py", ".pyw", ".ipynb")):
            return _python_completions(
                project_root,
                relative_path=relative_path,
                content=content,
                line=line,
                column=column,
                notebook_content=notebook_content,
                cell_index=cell_index,
            )
        return _generic_completions(content, line, column)

    if language == "python" or relative_path.lower().endswith((".py", ".pyw", ".ipynb")):
        return _resolve_python(
            project_root,
            relative_path=relative_path,
            content=content,
            line=line,
            column=column,
            notebook_content=notebook_content,
            cell_index=cell_index,
            action=action,
        )
    return _resolve_generic(
        project_root,
        relative_path=relative_path,
        content=content,
        line=line,
        column=column,
        language=language,
    )
