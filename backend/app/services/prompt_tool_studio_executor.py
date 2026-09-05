from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import text

from app.core.database import SessionLocal
from app.services.mcp_manager import call_stdio_tool, call_streamable_http_tool
from app.services.python_execution_service import python_execution_manager
from app.models.entities import MCPServer, ToolRecord


class StudioToolExecutionError(RuntimeError):
    pass


def _json_dict(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    raw = str(value or '').strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise StudioToolExecutionError(f'{label} JSON 형식을 확인하세요: {exc}') from exc
    if not isinstance(parsed, dict):
        raise StudioToolExecutionError(f'{label}은 JSON 객체여야 합니다.')
    return parsed



def _expand_env_value(value: Any) -> Any:
    if isinstance(value, str):
        missing: list[str] = []
        def repl(match: re.Match[str]) -> str:
            name = match.group(1)
            resolved = os.environ.get(name)
            if resolved is None:
                missing.append(name)
                return ''
            return resolved
        expanded = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', repl, value)
        if missing:
            raise StudioToolExecutionError('API 인증/설정 환경변수가 없습니다: ' + ', '.join(sorted(set(missing))))
        return expanded
    if isinstance(value, dict):
        return {str(k): _expand_env_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_value(v) for v in value]
    return value

def _tool_timeout(tool: dict[str, Any]) -> float:
    try:
        return float(max(1, min(120, int(tool.get('timeout') or 30))))
    except Exception:
        return 30.0


def _attempts(tool: dict[str, Any]) -> int:
    try:
        return max(1, min(3, int(tool.get('retry') or 0) + 1))
    except Exception:
        return 1


def _requires_confirmation(tool: dict[str, Any], *, registry: dict[str, Any] | None = None) -> bool:
    permissions = {str(x).strip().lower() for x in list(tool.get('permissions') or [])}
    tool_type = str(tool.get('type') or '').strip().upper()
    if tool_type in {'PYTHON', 'DATABASE'}:
        return True
    if tool_type == 'API':
        try:
            api_cfg = _json_dict(tool.get('source'), 'API Source')
            internal_path = str(api_cfg.get('path') or '').strip()
            if bool(api_cfg.get('agentstudio_internal')) and internal_path.startswith('/api/rag/tools/') and internal_path.endswith('/execute'):
                return False
            if str(api_cfg.get('method') or 'GET').strip().upper() not in {'GET', 'HEAD'}:
                return True
        except Exception:
            return True
    if bool(tool.get('requiresConfirmation')) or bool(tool.get('requires_confirmation')):
        return True
    if int(tool.get('riskLevel') or tool.get('risk_level') or 0) >= 2:
        return True
    if registry and (bool(registry.get('requires_confirmation')) or int(registry.get('risk_level') or 0) >= 2):
        return True
    return bool(permissions & {'write', 'execute', 'network', 'database.write', 'python.execute', 'api.write'})


def preview_database_sql(source: str, arguments: dict[str, Any]) -> dict[str, Any]:
    raw = str(source or '').strip()
    if not raw:
        raise StudioToolExecutionError('Database Tool Source에 SQL이 없습니다.')
    if raw.startswith('{'):
        cfg = _json_dict(raw, 'Database Source')
        sql = str(cfg.get('sql') or '').strip()
        params = dict(cfg.get('params') or {})
        params.update(arguments)
    else:
        sql = raw
        params = dict(arguments)
    if not sql:
        raise StudioToolExecutionError('실행할 SQL이 없습니다.')
    statements = [x.strip() for x in sql.split(';') if x.strip()]
    if len(statements) != 1:
        raise StudioToolExecutionError('Database Tool Test는 한 번에 SQL 한 문장만 허용합니다.')
    first = re.match(r'^\s*([a-zA-Z]+)', sql)
    verb = (first.group(1) if first else '').upper()
    read_only = verb in {'SELECT', 'WITH', 'EXPLAIN', 'SHOW'}
    return {'sql': sql, 'params': params, 'verb': verb or 'UNKNOWN', 'read_only': read_only}


async def _execute_mcp(
    tool: dict[str, Any],
    arguments: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    async with SessionLocal() as db:
        tool_row = await db.get(ToolRecord, int(registry['id']))
        server_row = await db.get(MCPServer, int(registry['server_id'])) if registry.get('server_id') else None
    if tool_row is None or server_row is None:
        raise StudioToolExecutionError('MCP Tool 또는 Server Registry를 찾을 수 없습니다.')
    try:
        from jsonschema import Draft202012Validator
        schema = dict(tool_row.input_schema or {})
        if schema:
            errors = sorted(Draft202012Validator(schema).iter_errors(arguments), key=lambda e: list(e.path))
            if errors:
                raise StudioToolExecutionError('Tool 입력 Schema 불일치: ' + '; '.join(e.message for e in errors[:5]))
    except ImportError:
        pass
    transport = str(server_row.transport or 'streamable_http').strip().casefold()
    if transport == 'stdio':
        payload = await call_stdio_tool(server_row.command, server_row.args or [], str(tool.get('name') or ''), arguments)
    else:
        payload = await call_streamable_http_tool(server_row.endpoint, str(tool.get('name') or ''), arguments)
    return {'ok': not bool(payload.get('is_error')), 'transport': transport, 'result': payload}


async def _execute_api(tool: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    cfg = _json_dict(tool.get('source'), 'API Source')
    internal_path = str(cfg.get('path') or '').strip()
    if bool(cfg.get('agentstudio_internal')):
        match = re.fullmatch(r'/api/rag/tools/(\d+)/execute', internal_path)
        if not match:
            raise StudioToolExecutionError('지원하지 않는 AgentStudio Internal API Tool 경로입니다.')
        from app.rag.agent_integration_service import execute_rag_tool
        payload = await execute_rag_tool(int(match.group(1)), arguments, test_mode='PROMPT_TOOL_STUDIO')
        return {'ok': bool(payload.get('ok', True)), 'method': 'INTERNAL', 'url': internal_path, 'status_code': 200, 'content_type': 'application/json', 'result': payload}
    url = str(cfg.get('url') or '').strip()
    if not url:
        raise StudioToolExecutionError('API Tool Source에 url이 없습니다.')
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        raise StudioToolExecutionError('API Tool은 http/https URL만 허용합니다.')
    method = str(cfg.get('method') or 'GET').strip().upper()
    if method not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'}:
        raise StudioToolExecutionError(f'지원하지 않는 HTTP method입니다: {method}')
    headers = _expand_env_value(_json_dict(cfg.get('headers') or {}, 'API headers'))
    query = _expand_env_value(dict(cfg.get('query') or {}))
    body = _expand_env_value(cfg.get('body'))
    if method in {'GET', 'HEAD'}:
        query.update(arguments)
    elif arguments:
        if isinstance(body, dict):
            body = {**body, **arguments}
        elif body in (None, ''):
            body = arguments
    timeout = httpx.Timeout(_tool_timeout(tool), connect=min(10.0, _tool_timeout(tool)))
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await client.request(method, url, headers={str(k): str(v) for k, v in headers.items()}, params=query or None, json=body if body is not None else None)
    content_type = str(response.headers.get('content-type') or '')
    if 'application/json' in content_type:
        try:
            response_body: Any = response.json()
        except Exception:
            response_body = response.text[:20000]
    else:
        response_body = response.text[:20000]
    return {
        'ok': 200 <= response.status_code < 400,
        'method': method,
        'url': url,
        'status_code': response.status_code,
        'content_type': content_type,
        'result': response_body,
    }


async def _execute_database(tool: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    preview = preview_database_sql(str(tool.get('source') or ''), arguments)
    if not preview['read_only']:
        raise StudioToolExecutionError('Studio Database Test는 안전을 위해 SELECT/WITH/EXPLAIN/SHOW 읽기 전용 SQL만 실제 실행합니다.')
    async with SessionLocal() as db:
        result = await db.execute(text(preview['sql']), preview['params'])
        rows = result.mappings().fetchmany(200) if result.returns_rows else []
    return {
        'ok': True,
        'preview': preview,
        'row_count': len(rows),
        'truncated': len(rows) >= 200,
        'result': [dict(row) for row in rows],
    }


async def _execute_python(tool: dict[str, Any], arguments: dict[str, Any], project_root: str) -> dict[str, Any]:
    root = str(project_root or '').strip()
    if not root:
        raise StudioToolExecutionError('Python Tool 실행에는 현재 Agent 프로젝트 경로가 필요합니다.')
    source = str(tool.get('source') or '').strip()
    if not source:
        raise StudioToolExecutionError('Python Tool Source에 실행 코드가 없습니다.')
    header = 'TOOL_ARGUMENTS = ' + repr(dict(arguments)) + '\n'
    result = await asyncio.to_thread(
        python_execution_manager.execute,
        root=root,
        code=header + source,
        relative_path='',
        session_id='prompt-tool-studio',
        reset=True,
        capture_last_expression=True,
        notebook_mode=False,
        cell_index=None,
        env_overrides={},
    )
    return {'ok': bool(result.get('ok', True)) if isinstance(result, dict) else True, 'result': result}


async def execute_studio_tool(
    tool: dict[str, Any],
    arguments: dict[str, Any],
    *,
    confirmation: bool,
    project_root: str = '',
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_type = str(tool.get('type') or '').strip().upper()
    if tool_type == 'AGENT':
        raise StudioToolExecutionError('Agent 타입은 현재 Tool Executor가 아니라 Agent Runtime/Workflow에서 실행해야 합니다.')
    if _requires_confirmation(tool, registry=registry) and not confirmation:
        return {'ok': False, 'blocked': True, 'requires_confirmation': True, 'error': '이 Tool은 실제 실행 전 사용자 확인이 필요합니다.'}

    started = time.perf_counter()
    attempts = _attempts(tool)
    last_error = ''
    for attempt in range(1, attempts + 1):
        try:
            if tool_type == 'MCP':
                if not registry:
                    raise StudioToolExecutionError('실제 AgentStudio MCP Registry에 연결되지 않은 Tool입니다.')
                payload = await asyncio.wait_for(_execute_mcp(tool, arguments, registry), timeout=_tool_timeout(tool))
            elif tool_type == 'API':
                payload = await asyncio.wait_for(_execute_api(tool, arguments), timeout=_tool_timeout(tool))
            elif tool_type == 'DATABASE':
                payload = await asyncio.wait_for(_execute_database(tool, arguments), timeout=_tool_timeout(tool))
            elif tool_type == 'PYTHON':
                payload = await asyncio.wait_for(_execute_python(tool, arguments, project_root), timeout=_tool_timeout(tool))
            else:
                raise StudioToolExecutionError(f'지원하지 않는 Tool 타입입니다: {tool_type or "UNKNOWN"}')
            return {
                'ok': bool(payload.get('ok', True)),
                'tool': str(tool.get('name') or ''),
                'type': tool_type,
                'arguments': arguments,
                'attempts': attempt,
                'elapsed_ms': round((time.perf_counter() - started) * 1000, 2),
                **payload,
            }
        except asyncio.TimeoutError:
            last_error = f'Tool 실행 시간이 {_tool_timeout(tool):g}초를 초과했습니다.'
        except Exception as exc:
            last_error = str(exc)
        if attempt < attempts:
            await asyncio.sleep(min(1.5, 0.25 * attempt))
    return {
        'ok': False,
        'tool': str(tool.get('name') or ''),
        'type': tool_type,
        'arguments': arguments,
        'attempts': attempts,
        'elapsed_ms': round((time.perf_counter() - started) * 1000, 2),
        'error': last_error or 'Tool 실행 실패',
    }
