import json
import logging
import re
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.model_router import model_for_task, LLMTask
from app.services.local_control import read_file, write_file
from app.services.coding_rule_selector import coding_rules_for_request
from app.services.code_template_registry import select_code_templates


logger = logging.getLogger(__name__)


class PatchApplyError(ValueError):
    """Patch 적용 실패 위치와 이미 적용된 결과를 보존하는 구조화 예외입니다."""

    def __init__(
        self,
        message: str,
        *,
        target: str = "",
        change_index: int = -1,
        replacement_index: int = -1,
        old: str = "",
        new: str = "",
        partial_results: list[dict] | None = None,
        current_excerpt: str = "",
        match_strategy: str = "",
    ):
        super().__init__(message)
        self.target = target
        self.change_index = change_index
        self.replacement_index = replacement_index
        self.old = old
        self.new = new
        self.partial_results = list(partial_results or [])
        self.current_excerpt = current_excerpt
        self.match_strategy = match_strategy

    def to_dict(self) -> dict:
        return {
            "message": str(self),
            "target": self.target,
            "change_index": self.change_index,
            "replacement_index": self.replacement_index,
            "old": self.old,
            "new": self.new,
            "partial_results": self.partial_results,
            "current_excerpt": self.current_excerpt,
            "match_strategy": self.match_strategy,
        }


def _newline_normalize(text: str) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")


def _restore_newline_style(original: str, normalized: str) -> str:
    """Patch matching용 LF 정규화 후에도 원본 파일의 주된 줄바꿈 스타일을 보존합니다."""
    source = str(original or "")
    if "\r\n" in source:
        return str(normalized or "").replace("\n", "\r\n")
    return str(normalized or "")


def _unique_flexible_whitespace_span(content: str, old: str):
    """
    old의 비공백 토큰은 그대로 보존하고 공백/줄바꿈만 유연하게 허용합니다.
    한 곳에서만 유일하게 일치할 때만 안전하게 span을 반환합니다.
    """
    old_text = _newline_normalize(old)
    content_text = _newline_normalize(content)
    stripped = old_text.strip()
    if not stripped:
        return None

    tokens = re.split(r"(\s+)", stripped)
    pattern_parts: list[str] = []
    for token in tokens:
        if not token:
            continue
        if token.isspace():
            pattern_parts.append(r"\s+")
        else:
            pattern_parts.append(re.escape(token))

    pattern = "".join(pattern_parts)
    try:
        matches = list(re.finditer(pattern, content_text, flags=re.MULTILINE))
    except re.error:
        return None

    if len(matches) != 1:
        return None

    match = matches[0]

    # CRLF 원본으로 위치를 다시 계산해야 할 수 있으므로, normalize된 앞부분 길이를
    # 원문에 직접 사용하지 않습니다. 앞/일치/뒤를 normalize 기준으로 재구성해서 반환합니다.
    return content_text[:match.start()], content_text[match.start():match.end()], content_text[match.end():]


def _safe_replacement(content: str, old: str, new: str) -> tuple[str, str] | None:
    """
    Patch replacement를 안전한 순서로 적용합니다.
    1) exact, 2) newline-normalized exact, 3) 유일한 whitespace-flexible match,
    4) 이미 new가 반영된 idempotent no-op.
    의미가 다른 문자열을 추측해서 바꾸지는 않습니다.
    """
    old_text = str(old or "")
    new_text = str(new or "")

    if not old_text:
        return None

    if old_text in content:
        return content.replace(old_text, new_text, 1), "exact"

    normalized_content = _newline_normalize(content)
    normalized_old = _newline_normalize(old_text)
    normalized_new = _newline_normalize(new_text)

    if normalized_old and normalized_old in normalized_content:
        replaced = normalized_content.replace(normalized_old, normalized_new, 1)
        return _restore_newline_style(content, replaced), "newline_normalized"

    flexible = _unique_flexible_whitespace_span(content, old_text)
    if flexible is not None:
        before, _matched, after = flexible
        replaced = before + normalized_new + after
        return _restore_newline_style(content, replaced), "whitespace_flexible"

    # 같은 Patch를 재실행하는 경우 이전 단계에서 이미 new가 적용됐을 수 있습니다.
    # 너무 짧은 토큰은 우연히 존재할 수 있으므로 충분한 길이의 변경만 idempotent로 봅니다.
    new_probe = normalized_new.strip()
    if len(new_probe) >= 16 and new_probe in normalized_content:
        return content, "already_applied"

    return None


def _excerpt_for_missing_target(content: str, old: str, limit: int = 1800) -> str:
    """Focused recovery가 현재 파일을 이해할 수 있도록 작은 근거 조각을 만듭니다."""
    text = str(content or "")
    if len(text) <= limit:
        return text

    old_first = next((line.strip() for line in str(old or "").splitlines() if line.strip()), "")
    if old_first:
        pos = text.find(old_first[:80])
        if pos >= 0:
            half = max(200, limit // 2)
            start = max(0, pos - half)
            end = min(len(text), start + limit)
            return text[start:end]

    return text[: limit // 2] + "\n... [중략] ...\n" + text[-limit // 2 :]

# v5.166: Patch/Code Generation 프롬프트가 모델 Context Window를 넘기지 않도록
# 문자 기준의 보수적인 입력 예산을 적용합니다. 정확한 tokenizer에 의존하지 않아
# OpenAI/Ollama Provider를 바꾸어도 동일한 보호 장치가 작동합니다.
PATCH_REQUEST_MAX_CHARS = 34_000
PATCH_FILES_MAX_CHARS = 22_000
PATCH_STYLE_MAX_CHARS = 14_000
PATCH_TEMPLATE_MAX_CHARS = 7_000
PATCH_TOTAL_MESSAGE_MAX_CHARS = 82_000

PATCH_EMERGENCY_REQUEST_MAX_CHARS = 18_000
PATCH_EMERGENCY_FILES_MAX_CHARS = 9_000
PATCH_EMERGENCY_STYLE_MAX_CHARS = 7_000
PATCH_EMERGENCY_TEMPLATE_MAX_CHARS = 3_000
PATCH_EMERGENCY_TOTAL_MESSAGE_MAX_CHARS = 44_000


SYSTEM = """당신은 코드 수정 전문 에이전트입니다.
반드시 JSON만 반환합니다.
형식:
{
  "changes": [
    {
      "path": "절대경로",
      "reason": "수정 이유",
      "create_file": false,
      "replace_entire_file": false,
      "content": "신규 파일 또는 전체 파일 교체가 명시된 경우의 전체 내용",
      "replacements": [
        {"old": "기존 코드 정확한 문자열", "new": "변경 코드"}
      ]
    }
  ]
}
규칙:
- 기존 파일은 전체 재작성보다 최소 교체를 우선합니다.
- 기존 파일의 old 문자열은 실제 파일에 존재하는 정확한 내용이어야 합니다.
- 신규 파일이 필요하면 create_file=true와 content를 사용합니다.
- 기존 파일의 정확한 old 문자열을 만들 수 없거나 [Focused Patch Recovery] 지시가 있으면 replace_entire_file=true와 content에 현재 파일의 수정 완료 전체 내용을 반환할 수 있습니다.
- 신규 파일 경로는 반드시 현재 프로젝트 루트 안이어야 합니다.
- 한 변경은 가능한 작게 만듭니다.
- 사용자가 등록한 Coding Style Registry의 required/recommended/conditional 규칙을 생성 코드에 실제 적용합니다.
- 설계에 필요한 신규 파일을 일부만 만들고 종료하지 않습니다.
- TODO, "여기에 구현", "Summary of the file content" 같은 placeholder/stub로 핵심 기능을 대신하지 않습니다.
- 외부 연동이 요구되면 실제 Client/Service/Tool 호출 구조를 작성합니다.
- 비밀값은 코드에 직접 넣지 않고 설정/환경변수로 분리합니다.
"""


def _clip_middle(value: str, limit: int, label: str = "내용") -> str:
    """중요한 시작/끝 지시를 모두 남기면서 긴 문자열의 중간만 축약합니다."""
    text = str(value or "")
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text

    marker = f"\n\n... [AgentStudio: {label} {len(text) - limit:,}자 축약] ...\n\n"
    usable = max(0, limit - len(marker))
    head = max(0, usable // 3)
    tail = max(0, usable - head)
    return text[:head] + marker + text[-tail:]


def _compact_file_context(
    files: dict[str, str],
    total_limit: int,
) -> str:
    """
    기존 파일 Context를 전체 예산 안에서 구성합니다.
    파일 경로는 모두 보존하고, 큰 파일은 앞/뒤 내용을 남기는 방식으로 축약합니다.
    """
    if not files or total_limit <= 0:
        return "(현재 파일 Context 없음)"

    rows = list(files.items())
    # 파일 수가 많아도 각 파일의 최소적인 앞/뒤 문맥을 볼 수 있도록 분배합니다.
    per_file = max(1_500, min(9_000, total_limit // max(1, len(rows))))
    parts: list[str] = []
    used = 0

    for path, content in rows:
        header = f"### {path}\n"
        remaining = total_limit - used - len(header)
        if remaining <= 120:
            parts.append(f"### {path}\n... [AgentStudio: Context 예산으로 파일 내용 생략]")
            continue

        piece_limit = min(per_file, remaining)
        piece = _clip_middle(
            str(content or ""),
            piece_limit,
            label=f"파일 {Path(str(path)).name}",
        )
        block = header + piece
        parts.append(block)
        used += len(block) + 2

        if used >= total_limit:
            break

    if len(parts) < len(rows):
        omitted = len(rows) - len(parts)
        parts.append(f"... [AgentStudio: Context 예산으로 {omitted}개 파일 생략]")

    return "\n\n".join(parts)


def _build_patch_messages(
    request: str,
    files: dict[str, str],
    coding_style: dict,
    templates: list[dict],
    emergency: bool = False,
):
    if emergency:
        request_limit = PATCH_EMERGENCY_REQUEST_MAX_CHARS
        files_limit = PATCH_EMERGENCY_FILES_MAX_CHARS
        style_limit = PATCH_EMERGENCY_STYLE_MAX_CHARS
        template_limit = PATCH_EMERGENCY_TEMPLATE_MAX_CHARS
        total_limit = PATCH_EMERGENCY_TOTAL_MESSAGE_MAX_CHARS
    else:
        request_limit = PATCH_REQUEST_MAX_CHARS
        files_limit = PATCH_FILES_MAX_CHARS
        style_limit = PATCH_STYLE_MAX_CHARS
        template_limit = PATCH_TEMPLATE_MAX_CHARS
        total_limit = PATCH_TOTAL_MESSAGE_MAX_CHARS

    request_context = _clip_middle(
        request,
        request_limit,
        label="요청/설계 Context",
    )
    file_context = _compact_file_context(files, files_limit)
    style_context = _clip_middle(
        coding_style.get("prompt") or "(등록된 적용 규칙 없음)",
        style_limit,
        label="Coding Style 규칙",
    )

    # 템플릿 전체를 그대로 넣지 않고 현재 요청과 관련된 상위 템플릿만 제한합니다.
    template_rows = []
    for item in templates[:8]:
        template_rows.append(
            f"[{item.get('id')}] {item.get('name')}\n{item.get('template')}"
        )
    template_context = _clip_middle(
        "\n\n".join(template_rows) or "(적용 가능한 코드 템플릿 없음)",
        template_limit,
        label="Code Template",
    )

    system_text = (
        SYSTEM
        + "\n\n[AgentStudio Coding Style Registry - 반드시 적용]\n"
        + style_context
        + "\n\n[선택된 Code Templates - 구조 참고]\n"
        + template_context
    )
    human_text = (
        f"요청:\n{request_context}"
        f"\n\n현재 파일:\n{file_context}"
        "\n\n반환하는 모든 변경 코드는 위 Coding Style 규칙을 준수해야 합니다."
    )

    # 개별 예산의 조합이 예상보다 커지는 경우 마지막 안전망으로 Human Message를 축약합니다.
    total_chars = len(system_text) + len(human_text)
    if total_chars > total_limit:
        overflow = total_chars - total_limit
        human_target = max(8_000, len(human_text) - overflow - 1_000)
        human_text = _clip_middle(
            human_text,
            human_target,
            label="최종 Patch Message",
        )
        total_chars = len(system_text) + len(human_text)

    return [
        SystemMessage(content=system_text),
        HumanMessage(content=human_text),
    ], {
        "emergency": emergency,
        "system_chars": len(system_text),
        "human_chars": len(human_text),
        "total_chars": total_chars,
        "request_original_chars": len(str(request or "")),
        "file_count": len(files or {}),
    }


def _is_context_overflow(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".casefold()
    return (
        "contextoverflow" in text
        or "context_length_exceeded" in text
        or "maximum context length" in text
        or "reduce the length of the messages" in text
    )


def _parse_patch_result(result) -> dict:
    text = str(result.content).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def _patch_task_for_request(
    request: str,
    files: dict[str, str],
    project_scope: bool,
    task_override: LLMTask | None = None,
) -> LLMTask:
    if task_override is not None:
        return task_override

    text = str(request or "").casefold()
    debug_markers = (
        "test failure", "test_failed", "debug", "디버그", "디버깅",
        "오류 수정", "실행 오류", "실패 진단", "repair", "복구",
    )
    if any(marker in text for marker in debug_markers):
        return LLMTask.EXECUTION_DEBUG_REPAIR

    multi_file_markers = (
        "다중 파일", "여러 파일", "프로젝트 전체", "대규모", "전체 코드",
        "agent factory 설계 결과", "필수 code plan", "code plan 자동 보강",
        "architecture", "아키텍처", "refactor", "리팩터", "migration", "마이그레이션",
    )
    if len(files or {}) >= 2 or (project_scope and any(marker in text for marker in multi_file_markers)):
        return LLMTask.MULTI_FILE_CODE_CHANGE

    return LLMTask.PATCH_GENERATION


async def create_patch(
    request: str,
    files: dict[str, str],
    provider: str | None = None,
    project_scope: bool = True,
    task_override: LLMTask | None = None,
) -> dict:
    task = _patch_task_for_request(request, files, project_scope, task_override)
    llm = model_for_task(task, provider)

    coding_style = coding_rules_for_request(
        request=request,
        project_scope=project_scope,
    )
    templates = select_code_templates(
        coding_style.get("tags") or []
    )

    messages, budget = _build_patch_messages(
        request=request,
        files=files,
        coding_style=coding_style,
        templates=templates,
        emergency=False,
    )
    logger.info(
        "Patch context budget: total=%s system=%s human=%s request_original=%s files=%s",
        budget["total_chars"],
        budget["system_chars"],
        budget["human_chars"],
        budget["request_original_chars"],
        budget["file_count"],
    )

    try:
        result = await llm.ainvoke(messages)
    except Exception as exc:
        if not _is_context_overflow(exc):
            raise

        # 모델/토크나이저 차이로 보수 예산에서도 Overflow가 발생하면 한 번 더 강하게 축약합니다.
        emergency_messages, emergency_budget = _build_patch_messages(
            request=request,
            files=files,
            coding_style=coding_style,
            templates=templates,
            emergency=True,
        )
        logger.warning(
            "Patch context overflow detected; retrying compact mode: total=%s original_error=%s",
            emergency_budget["total_chars"],
            exc,
        )
        result = await llm.ainvoke(emergency_messages)

    return _parse_patch_result(result)

def _resolve_patch_path(
    raw_path: str,
    project_root: str | None,
) -> Path:
    raw = Path(str(raw_path or "").strip()).expanduser()

    if not str(raw):
        raise ValueError("Patch 파일 경로가 비어 있습니다.")

    if raw.is_absolute():
        target = raw.resolve()
    else:
        if not project_root:
            raise ValueError(
                f"상대 경로 Patch에는 project_root가 필요합니다: {raw}"
            )
        target = (
            Path(project_root).expanduser().resolve()
            / raw
        ).resolve()

    if project_root:
        root = Path(project_root).expanduser().resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise PermissionError(
                f"Patch 경로가 프로젝트 Root 밖입니다: {target}"
            ) from exc

    return target


async def _verified_write(
    target: Path,
    content: str,
) -> dict:
    result = await write_file(str(target), content)

    # write_file 성공 반환만 신뢰하지 않고 실제 파일 시스템을 재확인합니다.
    if not target.is_file():
        raise RuntimeError(
            f"FILE_APPLY_FAILED: 파일이 생성되지 않았습니다: {target}"
        )

    stat = target.stat()

    if content and stat.st_size <= 0:
        raise RuntimeError(
            f"FILE_APPLY_FAILED: 파일은 존재하지만 크기가 0입니다: {target}"
        )

    actual = await read_file(str(target))

    # 텍스트 파일 생성 단계에서는 read-back 내용이 정확히 같아야 성공입니다.
    if actual != content:
        raise RuntimeError(
            f"FILE_APPLY_FAILED: 저장 후 내용 검증이 실패했습니다: {target}"
        )

    return {
        **(result or {}),
        "verified": True,
        "actual_bytes": stat.st_size,
    }


async def apply_patch(
    plan: dict,
    project_root: str | None = None,
):
    results = []

    for change_index, change in enumerate(plan.get("changes", [])):
        target = _resolve_patch_path(
            change.get("path", ""),
            project_root,
        )
        create_file = bool(change.get("create_file"))
        replace_entire_file = bool(change.get("replace_entire_file"))

        if create_file or replace_entire_file:
            new_content = str(change.get("content") or "")

            write_result = await _verified_write(
                target,
                new_content,
            )

            results.append({
                "path": str(target),
                "changed": True,
                "created": bool(create_file and not replace_entire_file),
                "replaced_entire_file": replace_entire_file,
                "verified": True,
                "bytes": write_result.get("actual_bytes", 0),
                "reason": change.get("reason", ""),
                "replacement_strategies": [
                    "create_file" if create_file and not replace_entire_file else "replace_entire_file"
                ],
            })
            continue

        content = await read_file(str(target))
        original = content
        strategies: list[str] = []

        for replacement_index, rep in enumerate(change.get("replacements", [])):
            old = str(rep.get("old") or "")
            new = str(rep.get("new") or "")

            applied = _safe_replacement(content, old, new)
            if applied is None:
                raise PatchApplyError(
                    f"Patch 대상 문자열을 찾지 못했습니다: {target}",
                    target=str(target),
                    change_index=change_index,
                    replacement_index=replacement_index,
                    old=old,
                    new=new,
                    partial_results=results,
                    current_excerpt=_excerpt_for_missing_target(content, old),
                    match_strategy="not_found",
                )

            content, strategy = applied
            strategies.append(strategy)

        changed = content != original

        if changed:
            write_result = await _verified_write(
                target,
                content,
            )
            verified = bool(write_result.get("verified"))
            size = write_result.get("actual_bytes", 0)
        else:
            verified = target.is_file()
            size = target.stat().st_size if target.is_file() else 0

        results.append({
            "path": str(target),
            "changed": changed,
            "created": False,
            "verified": verified,
            "bytes": size,
            "reason": change.get("reason", ""),
            "replacement_strategies": strategies,
        })

    return results

