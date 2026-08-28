from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any

from app.services.learning_teacher_router import learning_teacher_priority, _complete_provider, _scope_prompt, _problem_prompt


def _content_slice(value: str, opener: str, closer: str) -> str:
    text = str(value or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.I)
        text = re.sub(r'\s*```$', '', text)
    start = text.find(opener)
    end = text.rfind(closer)
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


def _loads_relaxed(text: str, expected: str) -> Any:
    opener, closer = ('{', '}') if expected == 'object' else ('[', ']')
    value = _content_slice(text, opener, closer)
    try:
        return json.loads(value)
    except Exception:
        pass
    # Common LLM JSON defects: trailing comma and raw control chars.
    value = re.sub(r',\s*([}\]])', r'\1', value)
    value = value.replace('\r', '\\r').replace('\t', '\\t')
    try:
        return json.loads(value)
    except Exception:
        return None


def _repair_prompt(raw: str, expected: str) -> str:
    shape = 'JSON 객체' if expected == 'object' else 'JSON 배열'
    return f'''아래 응답은 JSON 파싱에 실패했습니다. 의미를 바꾸지 말고 완전한 {shape} 하나로만 다시 작성하세요.
설명, Markdown, 코드펜스, 앞뒤 문장은 절대 쓰지 마세요.
문자열 내부 줄바꿈은 \\n 으로 escape하고 모든 따옴표를 정상적으로 닫으세요.

원본 응답:
{str(raw or '')[:12000]}'''


async def _json_completion(provider: str, model: str, prompt: str, expected: str) -> tuple[Any, list[dict]]:
    events: list[dict] = []
    raw = await _complete_provider(provider, prompt, model)
    parsed = _loads_relaxed(raw, expected)
    if parsed is not None:
        events.append({'step': 'parse', 'ok': True})
        return parsed, events
    events.append({'step': 'parse', 'ok': False, 'error': 'invalid_json', 'sample': str(raw or '')[:1000]})
    repaired_raw = await _complete_provider(provider, _repair_prompt(raw, expected), model)
    repaired = _loads_relaxed(repaired_raw, expected)
    if repaired is None:
        events.append({'step': 'repair', 'ok': False, 'error': 'invalid_json_after_repair', 'sample': str(repaired_raw or '')[:1000]})
        raise ValueError('Teacher JSON 응답 복구에 실패했습니다.')
    events.append({'step': 'repair', 'ok': True})
    return repaired, events


def _validate_problem(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    instruction = str(item.get('instruction') or '').strip()
    output = str(item.get('output') or '').strip()
    if len(instruction) < 8 or len(output) < 2:
        return None
    return {
        'id': uuid.uuid4().hex,
        'instruction': instruction,
        'input': str(item.get('input') or '').strip(),
        'output': output,
        'domain': str(item.get('domain') or '').strip(),
        'topic': str(item.get('topic') or '').strip(),
        'subtopic': str(item.get('subtopic') or '').strip(),
        'difficulty': str(item.get('difficulty') or 'medium').strip().lower(),
        'problem_type': str(item.get('problem_type') or 'scenario').strip().lower(),
        'source': 'expanded_from_confirmed_misjudgment',
        'validated': False,
    }


async def generate_dataset_with_priority_v2(case: dict, target_count: int) -> dict[str, Any]:
    policy = await learning_teacher_priority()
    attempts: list[dict[str, Any]] = []
    for provider in policy['priority']:
        model = str(policy['models'].get(provider) or '')
        if provider == 'codex' and not policy['codex_enabled']:
            attempts.append({'provider': provider, 'model': model, 'ok': False, 'error': 'Codex 사용 설정 OFF'})
            continue
        if provider == 'openai' and not policy['openai_enabled']:
            attempts.append({'provider': provider, 'model': model, 'ok': False, 'error': 'OpenAI 사용 설정 OFF'})
            continue
        provider_trace: list[dict] = []
        try:
            scope, trace = await _json_completion(provider, model, _scope_prompt(case), 'object')
            provider_trace.extend(trace)
            if not isinstance(scope, dict):
                raise ValueError('학습 범위 분석 결과가 JSON 객체가 아닙니다.')
            generated: list[dict] = []
            fingerprints: set[str] = set()
            # Smaller batches reduce truncation on local 4B models.
            batch_size = 8 if provider == 'ollama' else 16
            rounds = 0
            max_rounds = max(6, (target_count // batch_size) + 8)
            while len(generated) < target_count and rounds < max_rounds:
                rounds += 1
                need = min(batch_size, target_count - len(generated))
                parsed, trace = await _json_completion(provider, model, _problem_prompt(case, scope, need, len(generated)), 'array')
                provider_trace.extend(trace)
                if not isinstance(parsed, list):
                    raise ValueError('문제 생성 결과가 JSON 배열이 아닙니다.')
                for raw in parsed:
                    item = _validate_problem(raw)
                    if not item:
                        continue
                    fp = re.sub(r'\s+', ' ', (item['instruction'] + ' ' + item['input']).casefold()).strip()[:700]
                    if fp in fingerprints:
                        continue
                    fingerprints.add(fp)
                    generated.append(item)
                    if len(generated) >= target_count:
                        break
            if len(generated) < min(10, target_count):
                raise RuntimeError(f'유효한 학습 문제를 충분히 생성하지 못했습니다: {len(generated)}/{target_count}')
            attempts.append({'provider': provider, 'model': model, 'ok': True, 'trace': provider_trace[-20:]})
            return {
                'scope': scope,
                'problems': generated,
                'teacher_provider': provider,
                'teacher_model': model,
                'teacher_strategy': policy['strategy'],
                'teacher_priority': list(policy['priority']),
                'teacher_attempts': attempts,
            }
        except Exception as exc:
            attempts.append({'provider': provider, 'model': model, 'ok': False, 'error': str(exc) or type(exc).__name__, 'trace': provider_trace[-20:]})
    detail = ' | '.join(f"{r['provider']}({r.get('model','')}): {r.get('error','실패')}" for r in attempts)
    raise RuntimeError('설정된 상위 모델 우선순위의 모든 Teacher 호출이 실패했습니다. ' + detail)
