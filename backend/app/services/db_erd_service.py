from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


_SQL_EXTS = {'.sql', '.ddl'}
_TEXT_EXTS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.cs', '.java', '.json', '.yaml', '.yml', '.toml', '.env', '.md', '.txt'}
_SKIP_DIRS = {'.git', '.svn', '.hg', 'node_modules', '.venv', 'venv', '__pycache__', '.pytest_cache', 'dist', 'build', 'bin', 'obj'}
_MAX_FILE_BYTES = 1_500_000
_MAX_SCAN_FILES = 700
_MAX_TABLES_PER_DATABASE = 120
_MAX_REDIS_KEYS = 80
_MAX_COLLECTIONS = 80


def _text(value: Any) -> str:
    return str(value or '').strip()


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = _text(item)
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _safe_identifier(value: str) -> str:
    value = _text(value).strip('`"[]')
    return value or 'public'


def _split_qualified(value: str, default_schema: str = 'public') -> tuple[str, str]:
    raw = _text(value).replace('[', '').replace(']', '').replace('`', '').replace('"', '')
    bits = [bit for bit in raw.split('.') if bit]
    if len(bits) >= 2:
        return _safe_identifier(bits[-2]), _safe_identifier(bits[-1])
    return _safe_identifier(default_schema), _safe_identifier(bits[-1] if bits else raw)


def _split_top_level(value: str, delimiter: str = ',') -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    quote = ''
    i = 0
    while i < len(value):
        ch = value[i]
        if quote:
            if ch == quote:
                if i + 1 < len(value) and value[i + 1] == quote and quote in {'\'', '"'}:
                    i += 1
                else:
                    quote = ''
            i += 1
            continue
        if ch in {'\'', '"', '`'}:
            quote = ch
        elif ch == '[':
            quote = ']'
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        elif ch == delimiter and depth == 0:
            result.append(value[start:i].strip())
            start = i + 1
        i += 1
    tail = value[start:].strip()
    if tail:
        result.append(tail)
    return result


def _extract_create_table_blocks(sql: str) -> list[tuple[str, str]]:
    """Return (qualified_table_name, body) while respecting nested parentheses."""
    pattern = re.compile(r'(?is)\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>(?:[\w$#]+\.)?[\w$#]+|(?:"[^"]+"\.)?"[^"]+"|(?:\[[^\]]+\]\.)?\[[^\]]+\])\s*\(')
    result: list[tuple[str, str]] = []
    for match in pattern.finditer(sql):
        depth = 1
        quote = ''
        i = match.end()
        start = i
        while i < len(sql) and depth > 0:
            ch = sql[i]
            if quote:
                if ch == quote:
                    if i + 1 < len(sql) and sql[i + 1] == quote and quote in {'\'', '"'}:
                        i += 1
                    else:
                        quote = ''
                i += 1
                continue
            if ch in {'\'', '"', '`'}:
                quote = ch
            elif ch == '[':
                quote = ']'
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    result.append((match.group('name'), sql[start:i]))
                    break
            i += 1
    return result


def _column_type(definition: str) -> str:
    # Remove column name then keep tokens until a constraint keyword.
    value = definition.strip()
    value = re.sub(r'^(?:"[^"]+"|\[[^\]]+\]|`[^`]+`|[\w$#]+)\s+', '', value, count=1)
    marker = re.search(r'(?is)\s+(?:NOT\s+NULL|NULL\b|PRIMARY\s+KEY|UNIQUE\b|DEFAULT\b|REFERENCES\b|CHECK\b|CONSTRAINT\b|COLLATE\b|GENERATED\b|IDENTITY\b)', value)
    if marker:
        value = value[:marker.start()]
    return re.sub(r'\s+', ' ', value.strip())[:90]


def _parse_sql_schema(sql: str, *, db_type: str, database: str = '', default_schema: str = 'public') -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    table_ids: set[str] = set()

    for qualified, body in _extract_create_table_blocks(sql):
        schema, name = _split_qualified(qualified, default_schema)
        table_id = f'{schema}.{name}'
        if table_id.casefold() in table_ids:
            continue
        table_ids.add(table_id.casefold())
        pieces = _split_top_level(body)
        columns: list[dict[str, Any]] = []
        primary_columns: set[str] = set()
        pending_fks: list[tuple[list[str], str, list[str], str]] = []

        # Table-level constraints first.
        for piece in pieces:
            normalized = re.sub(r'\s+', ' ', piece.strip())
            pk_match = re.search(r'(?is)(?:CONSTRAINT\s+[^\s]+\s+)?PRIMARY\s+KEY\s*\(([^)]+)\)', normalized)
            if pk_match:
                for col in _split_top_level(pk_match.group(1)):
                    primary_columns.add(_safe_identifier(col))
            fk_match = re.search(
                r'(?is)(?:CONSTRAINT\s+([^\s]+)\s+)?FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+([^\s(]+)\s*\(([^)]+)\)',
                normalized,
            )
            if fk_match:
                from_cols = [_safe_identifier(v) for v in _split_top_level(fk_match.group(2))]
                ref_table = fk_match.group(3)
                to_cols = [_safe_identifier(v) for v in _split_top_level(fk_match.group(4))]
                pending_fks.append((from_cols, ref_table, to_cols, _safe_identifier(fk_match.group(1) or '')))

        for piece in pieces:
            normalized = re.sub(r'\s+', ' ', piece.strip())
            if not normalized or re.match(r'(?is)^(?:CONSTRAINT\b|PRIMARY\s+KEY\b|FOREIGN\s+KEY\b|UNIQUE\s*\(|CHECK\s*\()', normalized):
                continue
            col_match = re.match(r'(?is)^(?P<name>"[^"]+"|\[[^\]]+\]|`[^`]+`|[\w$#]+)\s+(?P<rest>.+)$', normalized)
            if not col_match:
                continue
            col_name = _safe_identifier(col_match.group('name'))
            rest = col_match.group('rest')
            data_type = _column_type(normalized)
            inline_pk = bool(re.search(r'(?is)\bPRIMARY\s+KEY\b', rest))
            inline_fk = re.search(r'(?is)\bREFERENCES\s+([^\s(]+)\s*\(([^)]+)\)', rest)
            if inline_pk:
                primary_columns.add(col_name)
            if inline_fk:
                pending_fks.append(([col_name], inline_fk.group(1), [_safe_identifier(v) for v in _split_top_level(inline_fk.group(2))], ''))
            columns.append({
                'name': col_name,
                'data_type': data_type,
                'nullable': not bool(re.search(r'(?is)\bNOT\s+NULL\b', rest)),
                'primary_key': inline_pk,
                'foreign_key': bool(inline_fk),
                'vector': bool(re.search(r'(?is)\bvector(?:\s*\(|\b)', data_type)),
            })

        for column in columns:
            if column['name'] in primary_columns:
                column['primary_key'] = True
        fk_cols = {col for cols, *_ in pending_fks for col in cols}
        for column in columns:
            if column['name'] in fk_cols:
                column['foreign_key'] = True

        tables.append({'id': table_id, 'schema': schema, 'name': name, 'columns': columns})
        for from_cols, ref_table, to_cols, fk_name in pending_fks:
            ref_schema, ref_name = _split_qualified(ref_table, schema)
            relationships.append({
                'name': fk_name or f'fk_{name}_{"_".join(from_cols)}',
                'from_table': table_id,
                'from_columns': from_cols,
                'to_table': f'{ref_schema}.{ref_name}',
                'to_columns': to_cols,
            })

    return {
        'version': 1,
        'kind': 'database_schema_diagram',
        'db_type': db_type,
        'database': database,
        'schema_name': default_schema,
        'root_table': tables[0]['id'] if tables else '',
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'tables': tables[:_MAX_TABLES_PER_DATABASE],
        'relationships': relationships,
    }


def _diagram_from_database_plan(plan: dict[str, Any], *, db_type: str, database: str = '') -> dict[str, Any]:
    schema = _text(plan.get('schema_name')) or 'public'
    tables: list[dict[str, Any]] = []
    for raw in plan.get('tables') or []:
        if not isinstance(raw, dict):
            continue
        name = _text(raw.get('name'))
        if not name:
            continue
        columns: list[dict[str, Any]] = []
        for col in raw.get('columns') or []:
            if not isinstance(col, dict):
                continue
            data_type = _text(col.get('type') or col.get('data_type'))
            columns.append({
                'name': _text(col.get('name')),
                'data_type': data_type,
                'nullable': bool(col.get('nullable', True)),
                'primary_key': bool(col.get('primary_key')),
                'foreign_key': bool(col.get('references')),
                'vector': bool(re.search(r'(?is)\bvector(?:\s*\(|\b)', data_type)),
            })
        tables.append({'id': f'{schema}.{name}', 'schema': schema, 'name': name, 'columns': columns})

    relationships: list[dict[str, Any]] = []
    for index, raw in enumerate(plan.get('relationships') or []):
        if not isinstance(raw, dict):
            continue
        from_ref = _text(raw.get('from'))
        to_ref = _text(raw.get('to'))
        if not from_ref or not to_ref:
            continue
        from_table_raw, _, from_col = from_ref.rpartition('.')
        to_table_raw, _, to_col = to_ref.rpartition('.')
        from_schema, from_table = _split_qualified(from_table_raw or from_ref, schema)
        to_schema, to_table = _split_qualified(to_table_raw or to_ref, schema)
        relationships.append({
            'name': f'fk_{index+1}',
            'from_table': f'{from_schema}.{from_table}',
            'from_columns': [from_col] if from_col else [],
            'to_table': f'{to_schema}.{to_table}',
            'to_columns': [to_col] if to_col else [],
        })

    return {
        'version': 1,
        'kind': 'database_schema_diagram',
        'db_type': db_type,
        'database': database,
        'schema_name': schema,
        'root_table': tables[0]['id'] if tables else '',
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'tables': tables,
        'relationships': relationships,
    }


def _detect_requested_engines(text: str, technologies: list[str]) -> list[str]:
    hay = f"{text}\n{' '.join(technologies)}".casefold()
    result: list[str] = []
    checks = [
        ('postgresql', ('postgresql', 'postgres', 'psycopg', 'supabase')),
        ('mssql', ('mssql', 'sql server', 'sqlserver', 'pyodbc')),
        ('oracle', ('oracle', 'oracledb', 'cx_oracle')),
        ('sqlite3', ('sqlite', 'sqlite3')),
        ('mysql', ('mysql', 'mariadb')),
    ]
    for engine, markers in checks:
        if any(marker in hay for marker in markers):
            result.append(engine)
    if not result and ('database' in hay or 'db' in hay or 'sql' in hay):
        result.append('postgresql')
    return result


def _classify_sql_file(path: Path, text: str, detected_engines: list[str]) -> str:
    hay = f'{path.as_posix()}\n{text[:6000]}'.casefold()
    if any(v in hay for v in ('sql server', 'mssql', 'nvarchar', 'identity(', 'go\n')):
        return 'mssql'
    if any(v in hay for v in ('oracle', 'varchar2', 'number(', 'from dual', 'tablespace')):
        return 'oracle'
    if any(v in hay for v in ('sqlite', 'autoincrement', 'pragma ')):
        return 'sqlite3'
    if any(v in hay for v in ('postgresql', 'postgres', 'jsonb', 'serial', 'timestamptz', '::json', 'create extension')):
        return 'postgresql'
    if any(v in hay for v in ('mysql', 'mariadb', 'engine=innodb', 'auto_increment')):
        return 'mysql'
    if len(detected_engines) == 1:
        return detected_engines[0]
    return 'sql'


def _merge_diagrams(diagrams: list[dict[str, Any]], *, db_type: str, database: str = '') -> dict[str, Any]:
    table_map: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, Any]] = []
    relation_keys: set[tuple] = set()
    schema_names: list[str] = []
    for diagram in diagrams:
        for table in diagram.get('tables') or []:
            if isinstance(table, dict) and _text(table.get('id')):
                table_map.setdefault(_text(table.get('id')).casefold(), table)
                schema_names.append(_text(table.get('schema')))
        for relation in diagram.get('relationships') or []:
            if not isinstance(relation, dict):
                continue
            key = (
                _text(relation.get('from_table')).casefold(),
                tuple(relation.get('from_columns') or []),
                _text(relation.get('to_table')).casefold(),
                tuple(relation.get('to_columns') or []),
            )
            if key not in relation_keys:
                relation_keys.add(key)
                relationships.append(relation)
    tables = list(table_map.values())[:_MAX_TABLES_PER_DATABASE]
    return {
        'version': 1,
        'kind': 'database_schema_diagram',
        'db_type': db_type,
        'database': database,
        'schema_name': _unique(schema_names)[0] if _unique(schema_names) else 'public',
        'root_table': tables[0]['id'] if tables else '',
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'tables': tables,
        'relationships': relationships,
    }


def _vector_diagram(source: dict[str, Any]) -> dict[str, Any] | None:
    tables = [
        table for table in source.get('tables') or []
        if any(bool(column.get('vector')) or 'vector' in _text(column.get('data_type')).casefold() for column in table.get('columns') or [])
    ]
    if not tables:
        return None
    ids = {_text(table.get('id')) for table in tables}
    relationships = [
        relation for relation in source.get('relationships') or []
        if _text(relation.get('from_table')) in ids or _text(relation.get('to_table')) in ids
    ]
    # Include directly related parent tables so the vector ownership/reference is understandable.
    related_ids = set(ids)
    for relation in relationships:
        related_ids.add(_text(relation.get('from_table')))
        related_ids.add(_text(relation.get('to_table')))
    table_index = {_text(table.get('id')): table for table in source.get('tables') or []}
    vector_tables = [table_index[item] for item in related_ids if item in table_index]
    return {
        **source,
        'db_type': 'pgvector',
        'database': source.get('database') or '',
        'tables': vector_tables,
        'relationships': relationships,
        'root_table': vector_tables[0]['id'] if vector_tables else '',
    }


def _extract_redis_keys(text: str) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Capture common redis-py calls with static or f-string key literals.
    regexes = [
        re.compile(r'(?is)\.(?:get|set|setex|hget|hset|lpush|rpush|sadd|zadd|delete|expire|incr|decr)\s*\(\s*f?[\'\"]([^\'\"]{1,180})[\'\"]'),
        re.compile(r'(?is)\b(?:redis_key|cache_key|key)\s*=\s*f?[\'\"]([^\'\"]{1,180})[\'\"]'),
    ]
    for regex in regexes:
        for match in regex.finditer(text):
            key = match.group(1).strip()
            key = re.sub(r'\{[^}]+\}', '{id}', key)
            if not key or key.casefold() in seen or any(ch in key for ch in ('\\n', '\\r')):
                continue
            seen.add(key.casefold())
            patterns.append({'key': key, 'purpose': '소스에서 감지한 Redis Key', 'ttl': '', 'data_type': 'key'})
            if len(patterns) >= _MAX_REDIS_KEYS:
                break
    return patterns


def _extract_firestore_collections(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in re.finditer(r'(?is)\.collection\s*\(\s*[\'\"]([^\'\"]{1,160})[\'\"]\s*\)', text):
        name = match.group(1).strip()
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            found.append({'name': name, 'purpose': '소스에서 감지한 Firestore Collection', 'fields': []})
            if len(found) >= _MAX_COLLECTIONS:
                break
    return found


def _scan_project_sources(project_root: str) -> tuple[list[tuple[Path, str]], str]:
    root = Path(project_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return [], ''
    sources: list[tuple[Path, str]] = []
    merged_text: list[str] = []
    count = 0
    for path in root.rglob('*'):
        if count >= _MAX_SCAN_FILES:
            break
        if not path.is_file() or any(part.casefold() in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.casefold() not in (_SQL_EXTS | _TEXT_EXTS):
            continue
        try:
            size = path.stat().st_size
            if size > _MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        count += 1
        if path.suffix.casefold() in _SQL_EXTS:
            sources.append((path, text))
        # A bounded merged haystack is enough for key/collection/type evidence.
        if sum(len(item) for item in merged_text) < 2_500_000:
            merged_text.append(f'\n# FILE {path.as_posix()}\n{text[:14000]}')
    return sources, ''.join(merged_text)


def build_project_db_erd(
    project_root: str = '',
    *,
    database_plan: dict[str, Any] | None = None,
    project_profile: dict[str, Any] | None = None,
    workflow_request: str = '',
) -> dict[str, Any]:
    plan = database_plan or {}
    profile = project_profile or {}
    technologies = [_text(v) for v in (profile.get('technologies') or profile.get('tech_stack') or plan.get('technologies') or [])]
    sources, source_haystack = _scan_project_sources(project_root) if project_root else ([], '')
    context = f'{workflow_request}\n{source_haystack[:2_500_000]}'
    detected_engines = _detect_requested_engines(context, technologies)

    databases: list[dict[str, Any]] = []
    relational_added: set[str] = set()

    # New Agent design has the highest-quality schema before source generation.
    if plan.get('enabled') and (plan.get('tables') or []):
        plan_engine = _text(plan.get('engine')).casefold()
        if plan_engine in {'postgresql', 'postgres', 'supabase'}:
            main_engine = next((engine for engine in detected_engines if engine in {'postgresql', 'mssql', 'oracle', 'sqlite3', 'mysql'}), 'postgresql')
        elif plan_engine:
            main_engine = plan_engine
        else:
            main_engine = 'postgresql'
        diagram = _diagram_from_database_plan(plan, db_type=main_engine)
        databases.append({
            'id': main_engine,
            'engine': main_engine,
            'label': {'postgresql': 'PostgreSQL', 'mssql': 'Microsoft SQL Server', 'oracle': 'Oracle Database', 'sqlite3': 'SQLite', 'mysql': 'MySQL'}.get(main_engine, main_engine.upper()),
            'kind': 'relational',
            'source': 'AGENT_DATABASE_PLAN',
            'diagram': diagram,
            'table_count': len(diagram.get('tables') or []),
            'relationship_count': len(diagram.get('relationships') or []),
        })
        relational_added.add(main_engine)

    parsed_by_engine: dict[str, list[dict[str, Any]]] = {}
    for path, sql in sources:
        if 'create table' not in sql.casefold():
            continue
        engine = _classify_sql_file(path, sql, detected_engines)
        parsed = _parse_sql_schema(sql, db_type=engine)
        if parsed.get('tables'):
            parsed_by_engine.setdefault(engine, []).append(parsed)

    for engine, pieces in parsed_by_engine.items():
        merged = _merge_diagrams(pieces, db_type=engine)
        existing = next((item for item in databases if item.get('engine') == engine and item.get('kind') == 'relational'), None)
        if existing and len(merged.get('tables') or []) > len((existing.get('diagram') or {}).get('tables') or []):
            existing['diagram'] = merged
            existing['source'] = 'PROJECT_SQL_SOURCE'
            existing['table_count'] = len(merged.get('tables') or [])
            existing['relationship_count'] = len(merged.get('relationships') or [])
        elif not existing:
            label = {'postgresql': 'PostgreSQL', 'mssql': 'Microsoft SQL Server', 'oracle': 'Oracle Database', 'sqlite3': 'SQLite', 'mysql': 'MySQL', 'sql': 'SQL Database'}.get(engine, engine.upper())
            databases.append({'id': engine, 'engine': engine, 'label': label, 'kind': 'relational', 'source': 'PROJECT_SQL_SOURCE', 'diagram': merged, 'table_count': len(merged.get('tables') or []), 'relationship_count': len(merged.get('relationships') or [])})
            relational_added.add(engine)

    # Keep detected SQL providers visible even when source has no DDL yet.
    for engine in detected_engines:
        if engine in relational_added:
            continue
        label = {'postgresql': 'PostgreSQL', 'mssql': 'Microsoft SQL Server', 'oracle': 'Oracle Database', 'sqlite3': 'SQLite', 'mysql': 'MySQL'}.get(engine, engine.upper())
        empty = _parse_sql_schema('', db_type=engine)
        databases.append({'id': engine, 'engine': engine, 'label': label, 'kind': 'relational', 'source': 'TECHNOLOGY_DETECTED', 'diagram': empty, 'table_count': 0, 'relationship_count': 0, 'message': 'DB 사용은 감지했지만 CREATE TABLE / 설계 Schema를 아직 찾지 못했습니다.'})
        relational_added.add(engine)

    # pgvector is presented as its own logical ERD when vector storage is used.
    has_pgvector = any('pgvector' in tech.casefold() for tech in technologies) or 'pgvector' in context.casefold() or bool(re.search(r'(?is)\bvector\s*\(', context))
    vector_source = None
    for item in databases:
        if item.get('kind') == 'relational':
            candidate = _vector_diagram(item.get('diagram') or {})
            if candidate:
                vector_source = candidate
                break
    if has_pgvector or vector_source:
        vector_diagram = vector_source or {
            'version': 1, 'kind': 'database_schema_diagram', 'db_type': 'pgvector', 'database': '', 'schema_name': 'public', 'root_table': '',
            'generated_at': datetime.now().isoformat(timespec='seconds'), 'tables': [], 'relationships': [],
        }
        databases.append({'id': 'pgvector', 'engine': 'pgvector', 'label': 'pgvector / Vector Store', 'kind': 'vector', 'source': 'VECTOR_SCHEMA_INFERENCE', 'diagram': vector_diagram, 'table_count': len(vector_diagram.get('tables') or []), 'relationship_count': len(vector_diagram.get('relationships') or []), 'message': '' if vector_diagram.get('tables') else 'pgvector 사용은 감지했지만 VECTOR 컬럼 Schema를 아직 찾지 못했습니다.'})

    redis_plan = plan.get('redis_plan') or {}
    redis_keys = []
    if redis_plan.get('enabled'):
        for item in redis_plan.get('keys') or []:
            if isinstance(item, dict) and _text(item.get('key')):
                redis_keys.append({
                    'key': _text(item.get('key')),
                    'purpose': _text(item.get('purpose')),
                    'ttl': _text(item.get('ttl')),
                    'data_type': _text(item.get('data_type')) or 'key',
                })
    source_redis_keys = _extract_redis_keys(source_haystack)
    # Before source generation, infer a small logical Redis model from explicit requirements.
    if not redis_keys and 'redis' in workflow_request.casefold():
        redis_keys.append({'key': 'session:{session_id}', 'purpose': '사용자/Agent 세션 상태', 'ttl': '세션 정책', 'data_type': 'hash/string'})
        req_lower = workflow_request.casefold()
        if '검색' in req_lower or 'search' in req_lower:
            redis_keys.append({'key': 'search:{query_hash}', 'purpose': '검색 결과 캐시', 'ttl': '5분 권장', 'data_type': 'string/json'})
        if '장바구니' in req_lower or 'cart' in req_lower:
            redis_keys.append({'key': 'cart:{customer_id}', 'purpose': '임시 장바구니', 'ttl': '업무 정책', 'data_type': 'hash'})
        if '주문' in req_lower or 'order' in req_lower:
            redis_keys.append({'key': 'order_draft:{session_id}', 'purpose': '주문 확정 전 Draft', 'ttl': '30분 권장', 'data_type': 'hash/json'})
    known = {_text(item.get('key')).casefold() for item in redis_keys}
    redis_keys.extend(item for item in source_redis_keys if _text(item.get('key')).casefold() not in known)
    has_redis = bool(redis_plan.get('enabled')) or any('redis' in tech.casefold() for tech in technologies) or 'redis' in context.casefold()
    if has_redis:
        databases.append({
            'id': 'redis', 'engine': 'redis', 'label': 'Redis', 'kind': 'key-value', 'source': 'AGENT_REDIS_PLAN' if redis_plan.get('enabled') else 'PROJECT_SOURCE_INFERENCE',
            'keys': redis_keys[:_MAX_REDIS_KEYS], 'key_count': len(redis_keys[:_MAX_REDIS_KEYS]),
            'policy': _text(redis_plan.get('policy')) or 'Redis Key Pattern / TTL / 역할을 논리 데이터 모델로 표시합니다.',
        })

    collections = _extract_firestore_collections(source_haystack)
    has_firestore = any('firestore' in tech.casefold() for tech in technologies) or 'firestore' in context.casefold()
    if has_firestore:
        databases.append({'id': 'firestore', 'engine': 'firestore', 'label': 'Google Cloud Firestore', 'kind': 'document', 'source': 'PROJECT_SOURCE_INFERENCE', 'collections': collections, 'collection_count': len(collections)})

    total_tables = sum(int(item.get('table_count') or 0) for item in databases)
    total_relations = sum(int(item.get('relationship_count') or 0) for item in databases)
    return {
        'ok': True,
        'scope': 'AGENT',
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'project_root': project_root,
        'databases': databases,
        'summary': {
            'database_count': len(databases),
            'table_count': total_tables,
            'relationship_count': total_relations,
            'redis_key_count': sum(int(item.get('key_count') or 0) for item in databases),
            'collection_count': sum(int(item.get('collection_count') or 0) for item in databases),
        },
    }


def build_agentstudio_db_erd(agentstudio_root: str) -> dict[str, Any]:
    root = Path(agentstudio_root).expanduser().resolve()
    sql_path = root / 'backend' / 'sql' / 'supabase_agentstudio_full_schema.sql'
    sql = sql_path.read_text(encoding='utf-8', errors='replace') if sql_path.exists() else ''
    pg = _parse_sql_schema(sql, db_type='postgresql', database='AgentStudio / Supabase', default_schema='theanova_agentstudio')
    databases: list[dict[str, Any]] = [{
        'id': 'postgresql', 'engine': 'postgresql', 'label': 'AgentStudio PostgreSQL / Supabase', 'kind': 'relational', 'source': 'AGENTSTUDIO_SCHEMA_SQL',
        'diagram': pg, 'table_count': len(pg.get('tables') or []), 'relationship_count': len(pg.get('relationships') or []),
    }]
    vector = _vector_diagram(pg)
    if vector:
        databases.append({'id': 'pgvector', 'engine': 'pgvector', 'label': 'AgentStudio pgvector', 'kind': 'vector', 'source': 'AGENTSTUDIO_SCHEMA_SQL', 'diagram': vector, 'table_count': len(vector.get('tables') or []), 'relationship_count': len(vector.get('relationships') or [])})
    return {
        'ok': True,
        'scope': 'STUDIO',
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'project_root': str(root),
        'databases': databases,
        'summary': {
            'database_count': len(databases),
            'table_count': sum(int(item.get('table_count') or 0) for item in databases),
            'relationship_count': sum(int(item.get('relationship_count') or 0) for item in databases),
            'redis_key_count': 0,
            'collection_count': 0,
        },
        'notes': [
            'LangGraph Checkpointer 테이블은 설치된 langgraph-checkpoint-postgres의 setup()이 생성하므로 정적 SQL에 정의된 AgentStudio 소유 테이블을 기준으로 ERD를 구성합니다.'
        ],
    }
