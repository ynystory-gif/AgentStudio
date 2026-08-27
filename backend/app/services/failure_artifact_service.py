from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

EXCLUDE={"venv",".venv","node_modules",".git","logs","reports","debug","__pycache__"}
SUFFIXES={".py",".js",".jsx",".ts",".tsx",".json",".md",".txt",".html",".css",".yml",".yaml",".toml",".cmd",".bat",".ps1",".sh"}
SPECIAL_FILES={
    ".env.example",
    ".gitignore",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "vite.config.js",
    "vite.config.ts",
}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _jsonable(v):
    try:
        json.dumps(v,ensure_ascii=False)
        return v
    except Exception:
        if isinstance(v,dict):
            return {str(k):_jsonable(x) for k,x in v.items()}
        if isinstance(v,(list,tuple)):
            return [_jsonable(x) for x in v]
        return str(v)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data=json.loads(path.read_text(encoding="utf-8",errors="replace"))
        return data if isinstance(data,dict) else {}
    except Exception:
        return {}


def _write_text(path: Path, text: str) -> None:
    """부분 파일이 보이지 않도록 같은 폴더의 임시 파일에 쓴 뒤 교체합니다."""
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".tmp")
    temp.write_text(text,encoding="utf-8")
    temp.replace(path)


def _write_json(path: Path, v) -> None:
    _write_text(
        path,
        json.dumps(_jsonable(v),ensure_ascii=False,indent=2)+"\n",
    )


def _actual_files(root:Path):
    out=[]
    if not root.exists():
        return out
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel=p.relative_to(root)
        if any(part.casefold() in EXCLUDE for part in rel.parts[:-1]):
            continue
        if rel.parts and rel.parts[0].casefold() in EXCLUDE:
            continue
        name=p.name.casefold()
        if p.suffix.casefold() not in SUFFIXES and name not in SPECIAL_FILES:
            continue
        out.append(rel.as_posix())
    return sorted(set(out))


def _planned(state):
    out=[]
    for x in (state.get("file_plan") or {}).get("new_files") or []:
        path=x if isinstance(x,str) else str((x or {}).get("path") or "")
        if path.strip():
            out.append(path.replace("\\","/"))
    return sorted(set(out))


def _patch_files(state):
    out=[]
    for x in state.get("patch_result") or []:
        if isinstance(x,dict) and (x.get("created") or x.get("changed")) and x.get("path"):
            out.append(str(x["path"]).replace("\\","/"))
    return sorted(set(out))


def _stage(state):
    status=str(state.get("status") or "UNKNOWN").upper()
    if status == "VALIDATION_BLOCKED":
        history=state.get("debug_history") or []
        latest=history[-1] if history and isinstance(history[-1],dict) else {}
        source=str(latest.get("source_status") or "").upper()
        if source == "SETTINGS_VALIDATION_FAILED":
            return "settings_validation"
        if source == "TEST_FAILED":
            return "test"
        return "debug/repair"
    for token,stage in [
        ("LAUNCHER_GENERATION","package/launcher"),
        ("FILE_APPLY","file_apply"),
        ("REQUIREMENT_COVERAGE","requirement_coverage"),
        ("SETTINGS_GENERATION","settings_generation"),
        ("SETTINGS_VALIDATION","settings_validation"),
        ("BUILD_ARTIFACT_STALLED","build_artifact_validation"),
        ("BUILD_ARTIFACT","build_artifact_validation"),
        ("DEBUG","debug/repair"),
        ("TEST","test"),
        ("CODE","code_generation"),
        ("APPROVAL","approval"),
        ("CHECKPOINT","checkpoint"),
        ("REQUIREMENT","requirement_analysis"),
        ("WORKFLOW_EXCEPTION","agent_factory"),
    ]:
        if token in status:
            return stage
    h=state.get("debug_history") or []
    if h and isinstance(h[-1],dict) and h[-1].get("type"):
        return str(h[-1]["type"])
    return "agent_factory"


def _friendly_workflow_error(value: str) -> str:
    text = str(value or "")
    lowered = text.casefold()
    if (
        "context_length_exceeded" in lowered
        or "maximum context length" in lowered
        or "contextoverflow" in lowered
    ):
        numbers = re.findall(r"(?:maximum context length is|resulted in)\s+(\d+)\s+tokens", text, re.I)
        if len(numbers) >= 2:
            return (
                "LLM 입력 Context가 모델 한도를 초과했습니다. "
                f"모델 한도 {int(numbers[0]):,} tokens / 요청 {int(numbers[1]):,} tokens. "
                "AgentStudio v5.166에서는 Code Generation 입력을 자동 축약하고, "
                "그래도 초과하면 더 작은 Emergency Context로 1회 자동 재시도합니다."
            )
        return (
            "LLM 입력 Context가 모델의 최대 Context Window를 초과했습니다. "
            "AgentStudio v5.166에서는 Code Generation 입력을 자동 축약하고 "
            "Emergency Context로 재시도합니다."
        )
    return text




def _test_failure_summary(output: str, limit: int = 900) -> str:
    """긴 compile/test 로그에서 사용자가 바로 이해할 수 있는 마지막 핵심 오류를 추출합니다."""
    text = str(output or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    important = [
        line for line in lines
        if re.search(
            r"(?i)(indentationerror|syntaxerror|modulenotfounderror|importerror|nameerror|typeerror|attributeerror|assertionerror|error:|failed|exception|traceback|sorry:)",
            line,
        )
    ]
    selected = important[-4:] if important else lines[-4:]
    summary = " | ".join(selected)
    return summary[-limit:]

def _reason(state,actual):
    if not actual:
        return "실제 Agent 소스/설정 산출물이 0개입니다. venv/logs/reports/debug는 생성 산출물로 계산하지 않습니다."
    code_plan=state.get("code_plan_validation") or {}
    missing_required=code_plan.get("missing_required_paths") or []
    if missing_required:
        preview=", ".join(str(x) for x in missing_required[:5])
        suffix=(f" 외 {len(missing_required)-5}개" if len(missing_required)>5 else "")
        return f"Code Plan 필수 파일 누락 {len(missing_required)}개: {preview}{suffix}"
    art=state.get("build_artifact_validation") or {}
    if art and not art.get("ok",True):
        parts=[]
        if art.get("missing_files"):
            parts.append(f"필수 파일 누락 {len(art['missing_files'])}개")
        if art.get("placeholder_files"):
            parts.append(f"Placeholder {len(art['placeholder_files'])}개")
        if art.get("coding_style_errors"):
            parts.append(f"Coding Style 오류 {len(art['coding_style_errors'])}개")
        if art.get("architecture_errors"):
            parts.append(f"Architecture 계약 오류 {len(art['architecture_errors'])}개")
        if parts:
            return ", ".join(parts)
    fallback=state.get("validation_fallback") or {}
    if str(state.get("status") or "").upper()=="VALIDATION_BLOCKED":
        codex=(fallback.get("codex") or {}) if isinstance(fallback,dict) else {}
        runtime=(codex.get("last_runtime_error") or {}) if isinstance(codex,dict) else {}
        message=str(runtime.get("message") or codex.get("last_error") or "")
        if fallback.get("sandbox_infrastructure_blocked"):
            return (
                "Agent 코드 실패가 아니라 생성 후 검증 인프라가 차단되었습니다. "
                "Codex Windows sandbox helper 실행 문제를 감지했고 로컬 fallback 검증을 수행했습니다."
                + (f" 원문: {message[:900]}" if message else "")
            )
        return "Agent 파일은 생성되었지만 검증을 완료할 근거가 부족하여 VALIDATION_BLOCKED로 중단했습니다."
    tr=state.get("test_result") or {}
    if tr.get("returncode") not in (None,0):
        detail = _test_failure_summary(str(tr.get("output") or ""))
        if detail:
            return f"테스트 실패(ReturnCode={tr.get('returncode')}): {detail}"
        return f"테스트 실패(ReturnCode={tr.get('returncode')})"
    h=state.get("debug_history") or []
    diagnosis=(h[-1].get("diagnosis") if h and isinstance(h[-1],dict) else "")
    raw_error = str(
        state.get("error")
        or diagnosis
        or f"Workflow가 완료 상태에 도달하지 못했습니다: {state.get('status') or 'UNKNOWN'}"
    )
    return _friendly_workflow_error(raw_error)


def _archive_previous_diagnostics(root: Path, previous_run: dict) -> str:
    """새 실행이 시작될 때 직전 진단 파일을 history로 보존합니다."""
    reports=root/"reports"
    debug=root/"debug"
    candidates=[
        reports/"failure_report.md",
        reports/"workflow_state.json",
        reports/"requirements_snapshot.json",
        reports/"generated_artifacts.json",
        debug/"debug_patch.json",
        debug/"recovery_plan.md",
    ]
    existing=[p for p in candidates if p.is_file()]
    if not existing:
        return ""

    previous_id=str(previous_run.get("run_id") or previous_run.get("thread_id") or "previous")
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_id="".join(c if c.isalnum() or c in "-_" else "_" for c in previous_id)[:80]
    archive=(reports/"history"/f"{stamp}_{safe_id}").resolve()
    archive.mkdir(parents=True,exist_ok=True)

    for source in existing:
        relative=source.relative_to(root)
        target=archive/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)

    return str(archive)


def begin_workflow_diagnostic_run(
    project_root: str,
    thread_id: str,
    request: str="",
) -> dict:
    """
    현재 실행을 디스크에 즉시 기록합니다.

    이전 버전은 /workflow/start 응답 연결이 끊기면 과거 실패 파일이 그대로 남아
    Frontend가 그것을 이번 실행의 진단으로 오인할 수 있었습니다. 새 실행 시작 시
    run marker와 RUNNING 진단 파일을 먼저 갱신해 파일 수정 시각과 실행 ID를 맞춥니다.
    """
    root=Path(project_root).expanduser().resolve()
    root.mkdir(parents=True,exist_ok=True)
    reports=root/"reports"
    reports.mkdir(parents=True,exist_ok=True)

    marker_path=reports/"current_run.json"
    previous=_read_json(marker_path)
    archive_dir=_archive_previous_diagnostics(root,previous)

    # 직전 실행의 per-run 디버그/테스트 파일을 현재 실행 자료처럼 보이지 않게 정리합니다.
    for stale_path in (
        root/"debug"/"debug_patch.json",
        root/"debug"/"recovery_plan.md",
        root/"logs"/"test.log",
        root/"logs"/"debug.log",
    ):
        try:
            stale_path.unlink(missing_ok=True)
        except Exception:
            pass

    started_at=_now_iso()
    marker={
        "run_id":thread_id,
        "thread_id":thread_id,
        "status":"RUNNING",
        "started_at":started_at,
        "updated_at":started_at,
        "diagnostics_generated_at":"",
        "archive_dir":archive_dir,
        "project_root":str(root),
    }
    _write_json(marker_path,marker)

    # 과거 진단을 현재 실행으로 오인하지 않도록 현재 run ID로 즉시 덮어씁니다.
    _write_json(reports/"workflow_state.json",{
        "thread_id":thread_id,
        "diagnostic_run_id":thread_id,
        "status":"RUNNING",
        "diagnostic_status":"RUNNING",
        "diagnostic_generated_at":"",
        "run_started_at":started_at,
        "project_root":str(root),
        "request":request,
    })
    _write_json(reports/"requirements_snapshot.json",{
        "diagnostic_run_id":thread_id,
        "run_started_at":started_at,
        "request":request,
        "diagnostic_pending":True,
    })
    _write_json(reports/"generated_artifacts.json",{
        "diagnostic_run_id":thread_id,
        "run_started_at":started_at,
        "diagnostic_pending":True,
        "actual_project_file_count":len(_actual_files(root)),
        "actual_project_files":_actual_files(root),
    })
    _write_text(
        reports/"failure_report.md",
        "# Agent Factory 실행 중\n\n"
        f"- 실행 ID: `{thread_id}`\n"
        f"- 시작 시각: {started_at}\n"
        "- 상태: `RUNNING`\n\n"
        "현재 실행의 최종 실패/성공 판정 전입니다. 이전 실행의 실패 자료는 reports/history 아래에 보존했습니다.\n",
    )

    logs=root/"logs"
    logs.mkdir(parents=True,exist_ok=True)
    start_event=f"[{started_at}] run_id={thread_id} status=RUNNING event=workflow_started\n"
    for name in ("agent_factory.log","workflow_execution.log"):
        with (logs/name).open("a",encoding="utf-8") as handle:
            handle.write(start_event)

    return marker


def _update_run_marker(
    root: Path,
    run_id: str,
    status: str,
    diagnostics_generated_at: str="",
) -> dict:
    path=root/"reports"/"current_run.json"
    marker=_read_json(path)
    if run_id and marker.get("run_id") and str(marker.get("run_id"))!=str(run_id):
        # 더 최신 실행의 marker를 과거 실행이 덮어쓰지 못하게 합니다.
        return marker
    marker.update({
        "run_id":run_id or marker.get("run_id") or "",
        "thread_id":run_id or marker.get("thread_id") or "",
        "status":status,
        "updated_at":_now_iso(),
    })
    if diagnostics_generated_at:
        marker["diagnostics_generated_at"]=diagnostics_generated_at
    _write_json(path,marker)
    return marker


def mark_workflow_run_completed(project_root: str, thread_id: str, status: str="COMPLETED") -> dict:
    root=Path(project_root).expanduser().resolve()
    return _update_run_marker(root,thread_id,status)


def create_failure_diagnostics(project_root:str,state:dict,request:str="",thread_id:str=""):
    root=Path(project_root).expanduser().resolve()
    root.mkdir(parents=True,exist_ok=True)
    actual=_actual_files(root)
    planned=_planned(state)
    patched=_patch_files(state)
    original=str(state.get("status") or "UNKNOWN")
    status="FAILED_NO_ARTIFACTS" if not actual else original
    stage=_stage(state)
    reason=_reason(state,actual)
    reports=root/"reports"
    debug=root/"debug"
    logs=root/"logs"
    actual_keys={item.casefold() for item in actual}
    missing=sorted(item for item in planned if item.casefold() not in actual_keys)
    generated_at=_now_iso()
    current_marker=_read_json(reports/"current_run.json")
    run_id=(thread_id or state.get("thread_id") or current_marker.get("run_id") or "")
    started_at=str(current_marker.get("started_at") or state.get("run_started_at") or "")

    req={
        "diagnostic_run_id":run_id,
        "diagnostic_generated_at":generated_at,
        "run_started_at":started_at,
        "request":request or state.get("request") or "",
        "requirement_spec":state.get("requirement_spec") or {},
        "capability_plan":state.get("capability_plan") or {},
        "tool_mcp_plan":state.get("tool_mcp_plan") or {},
        "agent_architecture":state.get("agent_architecture") or {},
        "target_agent_workflow":state.get("target_agent_workflow") or {},
        "file_plan":state.get("file_plan") or {},
        "environment_plan":state.get("environment_plan") or {},
        "settings_plan":state.get("settings_plan") or {},
    }
    artifacts={
        "diagnostic_run_id":run_id,
        "diagnostic_generated_at":generated_at,
        "run_started_at":started_at,
        "actual_project_file_count":len(actual),
        "actual_project_files":actual,
        "patch_generated_file_count":len(patched),
        "patch_generated_files":patched,
        "planned_file_count":len(planned),
        "planned_files":planned,
        "missing_planned_files":missing,
        "code_plan_validation":state.get("code_plan_validation") or {},
        "build_artifact_validation":state.get("build_artifact_validation") or {},
        "settings_validation":state.get("settings_validation_result") or {},
        "validation_fallback":state.get("validation_fallback") or {},
    }
    hist=state.get("debug_history") or []
    dbg={
        "diagnostic_run_id":run_id,
        "diagnostic_generated_at":generated_at,
        "thread_id":run_id,
        "status":original,
        "debug_iteration":int(state.get("debug_iteration") or 0),
        "latest_debug":hist[-1] if hist else {},
        "debug_history":hist,
        "last_patch_plan":state.get("plan") or {},
        "code_plan_validation":state.get("code_plan_validation") or {},
        "patch_result":state.get("patch_result") or [],
        "test_result":state.get("test_result") or {},
        "validation_fallback":state.get("validation_fallback") or {},
    }
    steps=[
        "reports/failure_report.md에서 실패 단계와 원인을 확인합니다.",
        "reports/generated_artifacts.json에서 계획 파일과 실제 파일을 비교합니다.",
        "debug/debug_patch.json에서 마지막 디버그 진단과 Patch 계획을 확인합니다.",
    ]
    if not actual:
        steps += [
            "code_generation이 실제 create/apply까지 수행됐는지 확인합니다.",
            "LLM Patch 응답이 빈 계획 또는 JSON 파싱 실패로 끝났는지 확인합니다.",
            "file_plan을 유지한 채 code_generation부터 재실행합니다.",
        ]
    lines=[
        "# Agent Factory 실패 리포트","",
        f"- 생성 시각: {generated_at}",
        f"- 실행 ID: {run_id or '-'}",
        f"- 시작 시각: {started_at or '-'}",
        f"- 원래 상태: `{original}`",
        f"- 최종 판정: `{status}`",
        f"- 실패/중단 단계: `{stage}`",
        f"- 실제 Agent 파일: **{len(actual)}개**",
        f"- 계획 파일: **{len(planned)}개**",
        f"- 디버그 반복: **{int(state.get('debug_iteration') or 0)}회**",
        "","## 실패 원인","",reason,"","## 마지막 오류","",str(state.get("error") or "-"),
        "","## 실제 생성/존재 파일","",
    ]
    lines += [f"- `{x}`" for x in actual] if actual else ["- **없음**"]
    lines += ["","## 계획됐지만 누락된 파일",""]
    lines += [f"- `{x}`" for x in missing] if missing else ["- 없음"]
    code_plan=state.get("code_plan_validation") or {}
    code_missing=code_plan.get("missing_required_paths") or []
    lines += ["","## Code Plan 완전성",""]
    lines += [
        f"- Required 파일: **{code_plan.get('required_count', 0)}개**",
        f"- 기존 존재 파일: **{code_plan.get('existing_count', 0)}개**",
        f"- Code Plan 변경 파일: **{code_plan.get('planned_change_count', 0)}개**",
        f"- 자동 보강 횟수: **{code_plan.get('supplement_rounds', 0)}회**",
        f"- 남은 누락 파일: **{len(code_missing)}개**",
    ]
    if code_missing:
        lines += [f"- 누락: `{x}`" for x in code_missing]

    build_artifact=state.get("build_artifact_validation") or {}
    placeholder_details=build_artifact.get("placeholder_details") or []
    if placeholder_details:
        lines += ["","## Placeholder 상세 진단",""]
        for item in placeholder_details:
            if not isinstance(item,dict):
                continue
            path=str(item.get("path") or "-")
            lines.append(f"### `{path}`")
            findings=item.get("findings") or []
            if not findings:
                lines.append("- 상세 위치 정보 없음")
            for finding in findings:
                if not isinstance(finding,dict):
                    continue
                line_no=finding.get("line","-")
                reason=str(finding.get("reason") or "placeholder")
                snippet=str(finding.get("snippet") or "").replace("`","'")
                lines.append(f"- Line {line_no} · {reason}: `{snippet}`")
            lines.append("")

    file_apply_validation=state.get("file_apply_validation") or {}
    file_apply_failure=file_apply_validation.get("failure") or {}
    file_apply_recoveries=file_apply_validation.get("focused_recoveries") or []
    if file_apply_failure or file_apply_recoveries:
        lines += ["","## Patch 적용 상세",""]
        if file_apply_failure:
            lines += [
                f"- 실패 대상: `{file_apply_failure.get('target') or '-'}`",
                f"- Change Index: {file_apply_failure.get('change_index', '-')}",
                f"- Replacement Index: {file_apply_failure.get('replacement_index', '-')}",
                f"- Match Strategy: `{file_apply_failure.get('match_strategy') or 'not_found'}`",
            ]
            old_excerpt=str(file_apply_failure.get("old") or "")[:800].replace("`", "'")
            new_excerpt=str(file_apply_failure.get("new") or "")[:800].replace("`", "'")
            if old_excerpt:
                lines.append(f"- 찾지 못한 old: `{old_excerpt}`")
            if new_excerpt:
                lines.append(f"- 적용 의도 new: `{new_excerpt}`")
        if file_apply_recoveries:
            lines.append(f"- Focused Recovery: **{len(file_apply_recoveries)}회**")
            for item in file_apply_recoveries:
                if isinstance(item,dict):
                    lines.append(
                        f"  - `{item.get('target') or '-'}` · {item.get('strategy') or 'recovery'}"
                    )

    attempts=code_plan.get("supplement_attempts") or []
    if attempts:
        lines += ["","### Code Plan 자동 보강 기록",""]
        for attempt in attempts:
            lines.append(
                "- Round {round}: 요청 {requested} / 추가 {added} / 남음 {remaining}".format(
                    round=attempt.get("round", "-"),
                    requested=len(attempt.get("requested_paths") or []),
                    added=len(attempt.get("added_paths") or []),
                    remaining=attempt.get("remaining_count", "-"),
                )
            )
            if attempt.get("error"):
                lines.append(f"  - 오류: {attempt.get('error')}")
    fallback=state.get("validation_fallback") or {}
    if fallback:
        lines += ["","## 검증 Fallback 진단",""]
        lines += [
            f"- 프로젝트 존재: **{bool(fallback.get('project_exists'))}**",
            f"- 실제 파일 수: **{fallback.get('actual_file_count', 0)}개**",
            f"- Sandbox 인프라 차단: **{bool(fallback.get('sandbox_infrastructure_blocked'))}**",
        ]
        codex=fallback.get("codex") or {}
        runtime=codex.get("last_runtime_error") or {}
        if codex.get("path"):
            lines.append(f"- Codex 실행 파일: `{codex.get('path')}`")
        if codex.get("last_command"):
            lines.append(f"- Codex 실행 명령: `{codex.get('last_command')}`")
        if runtime.get("message"):
            lines.append(f"- Codex 원본 오류: `{str(runtime.get('message'))[:1800].replace('`', "'")}`")
        helper=runtime.get("sandbox_helper") or {}
        if helper:
            if helper.get("path"):
                lines.append(f"- Sandbox Helper: `{helper.get('path')}` · exists={bool(helper.get('exists'))}")
            if helper.get("winerror") is not None:
                lines.append(f"- Windows WinError: `{helper.get('winerror')}`")
            if helper.get("exit_code") is not None:
                lines.append(f"- Helper ExitCode: `{helper.get('exit_code')}`")
        for row in fallback.get("commands") or []:
            if not isinstance(row,dict):
                continue
            lines.append(
                f"- Local Validation: `{row.get('command')}` · ReturnCode={row.get('returncode')}"
            )
            if row.get("execution_error"):
                lines.append(f"  - 실행 오류: `{row.get('execution_error')}`")
            elif row.get("output"):
                summary=_test_failure_summary(str(row.get("output") or ""),limit=1200)
                if summary:
                    lines.append(f"  - 결과: `{summary.replace('`', "'")}`")

    lines += ["","## 다음 조치",""]+[f"{i}. {x}" for i,x in enumerate(steps,1)]
    lines += ["","## 관련 파일","",
              "- `reports/workflow_state.json`","- `reports/requirements_snapshot.json`",
              "- `reports/generated_artifacts.json`","- `debug/debug_patch.json`",
              "- `debug/recovery_plan.md`","- `logs/agent_factory.log`","- `logs/workflow_execution.log`"]

    reports.mkdir(parents=True,exist_ok=True)
    debug.mkdir(parents=True,exist_ok=True)
    logs.mkdir(parents=True,exist_ok=True)

    _write_text(reports/"failure_report.md","\n".join(lines)+"\n")
    wf={
        **_jsonable(state),
        "diagnostic_run_id":run_id,
        "diagnostic_generated_at":generated_at,
        "run_started_at":started_at,
        "original_status":original,
        "diagnostic_status":status,
        "diagnostic_failure_stage":stage,
        "diagnostic_failure_reason":reason,
        "diagnostic_actual_file_count":len(actual),
    }
    _write_json(reports/"workflow_state.json",wf)
    _write_json(reports/"requirements_snapshot.json",req)
    _write_json(reports/"generated_artifacts.json",artifacts)
    _write_json(debug/"debug_patch.json",dbg)
    _write_text(
        debug/"recovery_plan.md",
        "# Agent Factory 복구 계획\n\n"
        +f"실행 ID: `{run_id or '-'}`\n\n"
        +f"생성 시각: {generated_at}\n\n"
        +f"현재 상태: `{status}`\n\n"
        +"\n".join(f"{i}. {x}" for i,x in enumerate(steps,1))+"\n",
    )

    event=f"[{generated_at}] run_id={run_id} status={status} original={original} stage={stage} actual_files={len(actual)} reason={reason}\n"
    for n in ("agent_factory.log","workflow_execution.log"):
        with (logs/n).open("a",encoding="utf-8") as f:
            f.write(event)
    if state.get("test_result"):
        _write_text(logs/"test.log",str((state.get("test_result") or {}).get("output") or state.get("test_result")))
    if hist:
        _write_json(logs/"debug.log",hist)
    if state.get("validation_fallback"):
        _write_json(logs/"validation_fallback.json",state.get("validation_fallback"))

    _update_run_marker(root,run_id,status,generated_at)

    diagnostic_paths={
        "current_run": reports/"current_run.json",
        "failure_report": reports/"failure_report.md",
        "workflow_state": reports/"workflow_state.json",
        "requirements_snapshot": reports/"requirements_snapshot.json",
        "generated_artifacts": reports/"generated_artifacts.json",
        "debug_patch": debug/"debug_patch.json",
        "recovery_plan": debug/"recovery_plan.md",
        "agent_factory_log": logs/"agent_factory.log",
        "workflow_execution_log": logs/"workflow_execution.log",
        "test_log": logs/"test.log",
        "debug_log": logs/"debug.log",
        "validation_fallback": logs/"validation_fallback.json",
    }
    file_info={}
    for key,path in diagnostic_paths.items():
        exists=path.is_file()
        stat=path.stat() if exists else None
        file_info[key]={
            "path":str(path),
            "exists":exists,
            "size":stat.st_size if stat else 0,
            "modified_at":(
                datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()
                if stat else ""
            ),
            "modified_epoch":stat.st_mtime if stat else 0,
        }

    return {
        "ok":True,
        "project_root":str(root),
        "run_id":run_id,
        "run_started_at":started_at,
        "diagnostic_generated_at":generated_at,
        "diagnostics_fresh":True,
        "original_status":original,
        "status":status,
        "failure_stage":stage,
        "failure_reason":reason,
        "actual_file_count":len(actual),
        "planned_file_count":len(planned),
        "file_apply":{
            "executed":bool(state.get("patch_result")),
            "count":len(state.get("patch_result") or []),
        },
        "test":{
            "executed":bool(state.get("test_result")),
            "returncode":(state.get("test_result") or {}).get("returncode"),
        },
        "debug":{
            "executed":bool(state.get("debug_history")),
            "count":len(state.get("debug_history") or []),
        },
        "validation_fallback":state.get("validation_fallback") or {},
        "code_plan_validation":state.get("code_plan_validation") or {},
        "missing_required_paths":((state.get("code_plan_validation") or {}).get("missing_required_paths") or []),
        "failure_report":str(reports/"failure_report.md"),
        "workflow_state":str(reports/"workflow_state.json"),
        "requirements_snapshot":str(reports/"requirements_snapshot.json"),
        "generated_artifacts":str(reports/"generated_artifacts.json"),
        "debug_patch":str(debug/"debug_patch.json"),
        "recovery_plan":str(debug/"recovery_plan.md"),
        "report_dir":str(reports),
        "debug_dir":str(debug),
        "logs_dir":str(logs),
        "files":file_info,
    }


def normalize_workflow_result(project_root:str,state:dict,request:str="",thread_id:str=""):
    result=dict(state or {})
    actual=_actual_files(Path(project_root).expanduser().resolve())
    status=str(result.get("status") or "").upper()
    completed=(status=="COMPLETED" and bool((result.get("build_artifact_validation") or {}).get("ok")) and len(actual)>0)
    if completed:
        mark_workflow_run_completed(project_root,thread_id or str(result.get("thread_id") or ""),"COMPLETED")
        return result,None
    d=create_failure_diagnostics(project_root,result,request,thread_id)
    if d["status"]=="FAILED_NO_ARTIFACTS":
        result["original_status"]=result.get("status")
        result["status"]="FAILED_NO_ARTIFACTS"
        result["error"]=d["failure_reason"]
    result["failure_diagnostics"]=d
    return result,d
