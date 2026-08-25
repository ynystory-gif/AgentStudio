import asyncio
import traceback
import uuid
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Any

from app.services.ws_hub import hub

JOB_LOG_DIR = (
    Path(__file__).resolve().parents[2] / "logs" / "jobs"
)


def _write_job_failure_log(
    job,
    exc: Exception,
    traceback_text: str,
) -> str:
    JOB_LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_kind = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in (job.kind or "JOB")
    )

    log_path = (
        JOB_LOG_DIR
        / f"{timestamp}_{safe_kind}_{job.id}.log"
    ).resolve()

    content = [
        f"timestamp={datetime.now().isoformat()}",
        f"job_id={job.id}",
        f"kind={job.kind}",
        f"status=FAILED",
        f"progress={job.progress}",
        f"error_type={type(exc).__name__}",
        f"error={exc}",
        "",
        "traceback:",
        traceback_text,
        "",
    ]

    log_path.write_text(
        "\n".join(content),
        encoding="utf-8",
    )

    return str(log_path)


@dataclass
class Job:
    id: str
    kind: str
    status: str = "QUEUED"
    progress: int = 0
    message: str = ""
    result: dict = field(default_factory=dict)
    # v5.345: lightweight build trace. Node-boundary events only; never token logs.
    events: list[dict] = field(default_factory=list)
    last_node: str = ""

class JobManager:
    """
    Background Job manager.

    핵심 원칙
    - create() 호출 즉시 asyncio.create_task()로 실제 실행을 예약합니다.
    - QUEUED → RUNNING → SUCCESS/FAILED/CANCELLED 상태를 명확히 관리합니다.
    - WebSocket으로 모든 상태 변경을 즉시 전송합니다.
    - 같은 kind의 활성 Job 중복 생성 여부를 조회할 수 있습니다.
    """
    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def update(
        self,
        job: Job,
        status: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        result: dict | None = None,
        node: str | None = None,
        event_detail: str | None = None,
    ):
        old_status = job.status
        old_progress = job.progress
        old_message = job.message
        old_node = job.last_node
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = max(0, min(100, int(progress)))
        if message is not None:
            job.message = message
        if result is not None:
            job.result = result
        if node is not None:
            job.last_node = str(node or "")

        # Keep only coarse state/node changes. This does not invoke an LLM and does
        # not write one line per token, so build performance and disk I/O stay stable.
        changed = (
            job.status != old_status
            or job.progress != old_progress
            or job.message != old_message
            or job.last_node != old_node
            or bool(event_detail)
        )
        if changed:
            event = {
                "at": datetime.now().isoformat(timespec="seconds"),
                "status": job.status,
                "progress": job.progress,
                "node": job.last_node,
                "message": job.message,
            }
            if event_detail:
                event["detail"] = str(event_detail)[:600]
            if not job.events or any(
                job.events[-1].get(key) != event.get(key)
                for key in ("status", "progress", "node", "message", "detail")
            ):
                job.events.append(event)
                if len(job.events) > 80:
                    del job.events[:-80]

        await hub.broadcast({
            "type": "job",
            "job": vars(job),
        })

    def active_job(self, kind: str) -> Job | None:
        for job in self.jobs.values():
            if job.kind == kind and job.status in {"QUEUED", "RUNNING", "WAITING_USER"}:
                return job
        return None

    def create(
        self,
        kind: str,
        runner: Callable[[Job], Awaitable[dict | None]],
    ) -> Job:
        job = Job(
            id=uuid.uuid4().hex,
            kind=kind,
            status="QUEUED",
            progress=0,
            message="작업이 대기열에 등록되었습니다.",
        )
        self.jobs[job.id] = job

        async def _run():
            try:
                # create_task가 실제 실행되었음을 가장 먼저 알려줍니다.
                await self.update(
                    job,
                    status="RUNNING",
                    progress=max(job.progress, 1),
                    message="작업을 시작했습니다.",
                )

                result = await runner(job)

                await self.update(
                    job,
                    status="SUCCESS",
                    progress=100,
                    message=(result or {}).get("message", "완료되었습니다."),
                    result=result or {},
                )

            except asyncio.CancelledError:
                await self.update(
                    job,
                    status="CANCELLED",
                    message="작업이 취소되었습니다.",
                )
                raise

            except Exception as e:
                tb = traceback.format_exc()

                try:
                    log_path = _write_job_failure_log(
                        job,
                        e,
                        tb,
                    )
                except Exception as log_error:
                    log_path = ""
                    tb = (
                        tb
                        + "\n\n[로그 파일 저장 실패]\n"
                        + f"{type(log_error).__name__}: {log_error}"
                    )

                await self.update(
                    job,
                    status="FAILED",
                    message=f"{type(e).__name__}: {e}",
                    result={
                        "ok": False,
                        "error_type": type(e).__name__,
                        "error": str(e),
                        "message": f"{type(e).__name__}: {e}",
                        "traceback": tb,
                        "log_path": log_path,
                    },
                )

            finally:
                self.tasks.pop(job.id, None)

        # 반드시 현재 이벤트 루프에 실제 Task를 등록합니다.
        task = asyncio.create_task(
            _run(),
            name=f"AgentStudio:{kind}:{job.id}",
        )
        self.tasks[job.id] = task
        return job

    async def cancel(self, job_id: str) -> bool:
        task = self.tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

job_manager = JobManager()
