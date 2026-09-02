from __future__ import annotations

import asyncio
import json
import math
import re
import time
import uuid
from typing import Any

from app.services.learning_teacher_router import learning_teacher_priority, _complete_provider, _scope_prompt, _problem_prompt


_LATEST_GENERATION_PROGRESS: dict[str, Any] = {}


def _set_generation_progress(**values: Any) -> None:
    _LATEST_GENERATION_PROGRESS.update(values)
    _LATEST_GENERATION_PROGRESS["updated_at_monotonic"] = time.monotonic()


def get_latest_generation_progress() -> dict[str, Any]:
    return dict(_LATEST_GENERATION_PROGRESS)


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


async def _json_completion(provider: str, model: str, prompt: str, expected: str) -> tuple[Any, list[dict], int]:
    events: list[dict] = []
    calls = 1
    raw = await _complete_provider(provider, prompt, model)
    parsed = _loads_relaxed(raw, expected)
    if parsed is not None:
        events.append({'step': 'parse', 'ok': True})
        return parsed, events, calls
    events.append({'step': 'parse', 'ok': False, 'error': 'invalid_json', 'sample': str(raw or '')[:1000]})
    calls += 1
    repaired_raw = await _complete_provider(provider, _repair_prompt(raw, expected), model)
    repaired = _loads_relaxed(repaired_raw, expected)
    if repaired is None:
        events.append({'step': 'repair', 'ok': False, 'error': 'invalid_json_after_repair', 'sample': str(repaired_raw or '')[:1000]})
        raise ValueError('Teacher JSON 응답 복구에 실패했습니다.')
    events.append({'step': 'repair', 'ok': True})
    return repaired, events, calls


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


async def _generate_one_batch(
    provider: str,
    model: str,
    case: dict,
    scope: dict,
    need: int,
    offset: int,
    batch_no: int,
    total_batches: int,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    last_error: Exception | None = None
    trace: list[dict] = []
    llm_calls = 0
    for attempt in range(1, 3):
        try:
            async with semaphore:
                parsed, part_trace, calls = await _json_completion(
                    provider,
                    model,
                    _problem_prompt(case, scope, need, offset),
                    'array',
                )
            trace.extend(part_trace)
            llm_calls += calls
            if not isinstance(parsed, list):
                raise ValueError('문제 생성 결과가 JSON 배열이 아닙니다.')
            return {
                'batch_no': batch_no,
                'items': parsed,
                'trace': trace,
                'llm_calls': llm_calls,
                'attempts': attempt,
            }
        except Exception as exc:
            last_error = exc
            trace.append({'step': 'batch_retry', 'batch': batch_no, 'attempt': attempt, 'ok': False, 'error': str(exc)})
            if attempt < 2:
                await asyncio.sleep(0.35)
    raise RuntimeError(f'Batch {batch_no}/{total_batches} 생성 실패: {str(last_error) or type(last_error).__name__}')


async def generate_dataset_with_priority_v2(case: dict, target_count: int) -> dict[str, Any]:
    policy = await learning_teacher_priority()
    attempts: list[dict[str, Any]] = []
    started_at = time.monotonic()
    _set_generation_progress(
        stage='teacher_select', generated_count=0, target_count=target_count,
        completed_batches=0, total_batches=0, llm_calls=0, elapsed_seconds=0,
        eta_seconds=None, message='Teacher 모델을 선택하는 중...',
    )

    for provider in policy['priority']:
        model = str(policy['models'].get(provider) or '')
        if provider == 'codex' and not policy['codex_enabled']:
            attempts.append({'provider': provider, 'model': model, 'ok': False, 'error': 'Codex 사용 설정 OFF'})
            continue
        if provider == 'openai' and not policy['openai_enabled']:
            attempts.append({'provider': provider, 'model': model, 'ok': False, 'error': 'OpenAI 사용 설정 OFF'})
            continue

        provider_trace: list[dict] = []
        total_llm_calls = 0
        try:
            _set_generation_progress(
                provider=provider, model=model, stage='scope',
                message=f'{provider} · 오판 학습 범위 분석 중...',
                generated_count=0, target_count=target_count,
            )
            scope, trace, calls = await _json_completion(provider, model, _scope_prompt(case), 'object')
            total_llm_calls += calls
            provider_trace.extend(trace)
            if not isinstance(scope, dict):
                raise ValueError('학습 범위 분석 결과가 JSON 객체가 아닙니다.')

            # Cloud Teacher는 20문제 단위, 최대 2개 요청을 동시에 처리한다.
            # Ollama는 VRAM/로컬 안정성을 위해 기존처럼 작은 batch와 단일 동시성을 유지한다.
            batch_size = 8 if provider == 'ollama' else 20
            concurrency = 1 if provider == 'ollama' else 2
            total_batches = max(1, math.ceil(target_count / batch_size))
            semaphore = asyncio.Semaphore(concurrency)

            specs: list[tuple[int, int, int]] = []
            offset = 0
            for batch_no in range(1, total_batches + 1):
                need = min(batch_size, target_count - offset)
                specs.append((batch_no, need, offset))
                offset += need

            generated: list[dict] = []
            fingerprints: set[str] = set()
            completed_batches = 0
            _set_generation_progress(
                provider=provider, model=model, stage='generate',
                batch_size=batch_size, concurrency=concurrency,
                completed_batches=0, total_batches=total_batches,
                generated_count=0, target_count=target_count,
                llm_calls=total_llm_calls,
                message=f'{provider} · 문제 0/{target_count} 생성 중 · Batch 0/{total_batches}',
            )

            tasks = [
                asyncio.create_task(
                    _generate_one_batch(provider, model, case, scope, need, batch_offset, batch_no, total_batches, semaphore)
                )
                for batch_no, need, batch_offset in specs
            ]

            for future in asyncio.as_completed(tasks):
                batch = await future
                completed_batches += 1
                total_llm_calls += int(batch.get('llm_calls') or 0)
                provider_trace.extend(batch.get('trace') or [])
                for raw in batch.get('items') or []:
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

                elapsed = max(0.01, time.monotonic() - started_at)
                ratio = completed_batches / total_batches
                eta = max(0, int((elapsed / ratio) - elapsed)) if ratio > 0 else None
                _set_generation_progress(
                    provider=provider, model=model, stage='generate',
                    batch_size=batch_size, concurrency=concurrency,
                    completed_batches=completed_batches, total_batches=total_batches,
                    generated_count=min(len(generated), target_count), target_count=target_count,
                    llm_calls=total_llm_calls, elapsed_seconds=int(elapsed), eta_seconds=eta,
                    message=f'{provider} · 문제 {min(len(generated), target_count)}/{target_count} 생성 · Batch {completed_batches}/{total_batches}',
                )

            # 중복/형식탈락으로 목표보다 부족할 때만 부족분 batch를 재생성한다.
            supplemental_rounds = 0
            while len(generated) < target_count and supplemental_rounds < 3:
                supplemental_rounds += 1
                need = min(batch_size, target_count - len(generated))
                batch = await _generate_one_batch(
                    provider, model, case, scope, need, len(generated),
                    total_batches + supplemental_rounds, total_batches + 3, semaphore,
                )
                total_llm_calls += int(batch.get('llm_calls') or 0)
                provider_trace.extend(batch.get('trace') or [])
                for raw in batch.get('items') or []:
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
                _set_generation_progress(
                    provider=provider, model=model, stage='supplement',
                    generated_count=min(len(generated), target_count), target_count=target_count,
                    llm_calls=total_llm_calls,
                    message=f'{provider} · 중복/탈락 보충 생성 {min(len(generated), target_count)}/{target_count}',
                )

            if len(generated) < min(10, target_count):
                raise RuntimeError(f'유효한 학습 문제를 충분히 생성하지 못했습니다: {len(generated)}/{target_count}')

            generated = generated[:target_count]
            elapsed = int(time.monotonic() - started_at)
            _set_generation_progress(
                provider=provider, model=model, stage='complete',
                generated_count=len(generated), target_count=target_count,
                completed_batches=total_batches, total_batches=total_batches,
                llm_calls=total_llm_calls, elapsed_seconds=elapsed, eta_seconds=0,
                message=f'{provider} · 문제 {len(generated)}/{target_count} 생성 완료',
            )
            attempts.append({'provider': provider, 'model': model, 'ok': True, 'trace': provider_trace[-30:]})
            return {
                'scope': scope,
                'problems': generated,
                'teacher_provider': provider,
                'teacher_model': model,
                'teacher_strategy': policy['strategy'],
                'teacher_priority': list(policy['priority']),
                'teacher_attempts': attempts,
                'generation_metrics': {
                    'batch_size': batch_size,
                    'concurrency': concurrency,
                    'total_batches': total_batches,
                    'llm_calls': total_llm_calls,
                    'elapsed_seconds': elapsed,
                },
            }
        except Exception as exc:
            attempts.append({'provider': provider, 'model': model, 'ok': False, 'error': str(exc) or type(exc).__name__, 'trace': provider_trace[-30:]})
            _set_generation_progress(
                provider=provider, model=model, stage='fallback',
                llm_calls=total_llm_calls,
                message=f'{provider} 생성 실패 · 다음 Teacher로 전환: {str(exc) or type(exc).__name__}',
            )

    detail = ' | '.join(f"{r['provider']}({r.get('model','')}): {r.get('error','실패')}" for r in attempts)
    _set_generation_progress(stage='failed', message='모든 Teacher 호출이 실패했습니다.', eta_seconds=0)
    raise RuntimeError('설정된 상위 모델 우선순위의 모든 Teacher 호출이 실패했습니다. ' + detail)
