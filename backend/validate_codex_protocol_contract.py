from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.codex_app_server_service import (  # noqa: E402
    CODEX_APPROVAL_POLICY,
    CODEX_THREAD_SANDBOX,
    CodexAppServerManager,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    manager = CodexAppServerManager()
    manager._models = [
        {
            "model": "gpt-test-codex",
            "supportedReasoningEfforts": [
                {"reasoningEffort": "low", "description": "fast"},
                {"reasoningEffort": "high", "description": "deep"},
            ],
            "defaultReasoningEffort": "high",
        }
    ]

    calls: list[tuple[str, dict[str, Any], float]] = []

    def fake_request(method: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
        row = dict(params or {})
        calls.append((method, row, timeout))
        if method == "thread/start":
            return {"thread": {"id": "thread-new"}}
        if method == "thread/resume":
            return {"thread": {"id": row.get("threadId")}}
        if method == "turn/start":
            return {"turn": {"id": "turn-new"}}
        return {}

    manager.request = fake_request  # type: ignore[method-assign]

    with tempfile.TemporaryDirectory(prefix="agentstudio-codex-contract-") as temp_root:
        root = str(Path(temp_root).resolve())

        manager.start_thread(root, "gpt-test-codex", "high")
        method, params, _ = calls[-1]
        require(method == "thread/start", "thread/start method mismatch")
        require(params.get("approvalPolicy") == CODEX_APPROVAL_POLICY == "untrusted", "thread/start approvalPolicy must be untrusted")
        require(params.get("sandbox") == CODEX_THREAD_SANDBOX == "workspace-write", "thread/start sandbox must be workspace-write")
        require("sandboxPolicy" not in params, "thread/start must use sandbox mode, not sandboxPolicy")
        require(params.get("config") == {"model_reasoning_effort": "high"}, "thread/start effort must be sent through config.model_reasoning_effort")

        manager.resume_thread("thread-old", root)
        method, params, _ = calls[-1]
        require(method == "thread/resume", "thread/resume method mismatch")
        require(params.get("approvalPolicy") == "untrusted", "thread/resume approvalPolicy must be untrusted")
        require(params.get("sandbox") == "workspace-write", "thread/resume sandbox must be workspace-write")
        require(params.get("cwd") == root, "thread/resume cwd mismatch")

        manager.start_turn("thread-old", "테스트", root, "gpt-test-codex", "low")
        method, params, _ = calls[-1]
        require(method == "turn/start", "turn/start method mismatch")
        require(params.get("approvalPolicy") == "untrusted", "turn/start approvalPolicy must be untrusted")
        require(params.get("model") == "gpt-test-codex", "turn/start model mismatch")
        require(params.get("effort") == "low", "turn/start effort mismatch")
        input_rows = params.get("input") or []
        require(bool(input_rows), "turn/start input missing")
        require(input_rows[0].get("type") == "text", "turn/start text input type mismatch")
        require(input_rows[0].get("text_elements") == [], "turn/start text input must include text_elements=[]")
        sandbox = params.get("sandboxPolicy") or {}
        require(sandbox.get("type") == "workspaceWrite", "turn/start sandboxPolicy.type mismatch")
        require(sandbox.get("writableRoots") == [root], "turn/start writableRoots mismatch")
        require(sandbox.get("networkAccess") is True, "turn/start networkAccess mismatch")
        require(sandbox.get("excludeTmpdirEnvVar") is False, "turn/start excludeTmpdirEnvVar must be explicit")
        require(sandbox.get("excludeSlashTmp") is False, "turn/start excludeSlashTmp must be explicit")

        before = len(calls)
        try:
            manager.start_turn("thread-old", "invalid", root, "gpt-test-codex", "medium")
        except ValueError as exc:
            require("지원하지 않습니다" in str(exc), "unsupported effort error should be clear")
        else:
            raise AssertionError("unsupported model/effort combination must fail before RPC")
        require(len(calls) == before, "unsupported effort must not call app-server")

        manager._initialized = True
        manager._account = {"email": "contract@example.test", "planType": "plus"}
        ephemeral = manager._start_ephemeral_readonly_thread(root, "gpt-test-codex", "low")
        require(ephemeral.get("id") == "thread-new", "ephemeral thread id mismatch")
        method, params, _ = calls[-1]
        require(method == "thread/start", "ephemeral thread/start method mismatch")
        require(params.get("ephemeral") is True, "fallback Codex thread must be ephemeral")
        require(params.get("approvalPolicy") == "never", "fallback Codex thread must never request write approval")
        require(params.get("sandbox") == "read-only", "fallback Codex thread must be read-only")

        def fake_rate_request(method: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
            calls.append((method, dict(params or {}), timeout))
            if method == "account/rateLimits/read":
                return {
                    "rateLimits": {
                        "limitId": "primary",
                        "primary": {"usedPercent": 25, "resetsAt": 2000000000},
                    },
                    "rateLimitsByLimitId": {},
                }
            return {}

        manager.request = fake_rate_request  # type: ignore[method-assign]
        limits = manager.refresh_rate_limits(force=True)
        require(calls[-1][0] == "account/rateLimits/read", "Codex usage must use account/rateLimits/read")
        require((limits.get("rateLimits") or {}).get("limitId") == "primary", "rate limit response must be preserved")

    wire: list[dict[str, Any]] = []
    manager._pending_server_requests["91"] = {
        "request_id": "91",
        "method": "item/tool/requestUserInput",
        "params": {},
    }
    manager._write_json = lambda payload: wire.append(payload)  # type: ignore[method-assign]
    manager.resolve_server_request(
        "91",
        "accept",
        {"answers": {"choice": {"answers": ["A"]}}},
    )
    require(
        wire == [{"id": 91, "result": {"answers": {"choice": {"answers": ["A"]}}}}],
        "requestUserInput JSON-RPC response shape mismatch",
    )

    print("[codex-contract] thread/start current v2 shape: OK")
    print("[codex-contract] thread/resume current v2 shape: OK")
    print("[codex-contract] turn/start UserInput + workspaceWrite schema: OK")
    print("[codex-contract] model/effort validation: OK")
    print("[codex-contract] requestUserInput response shape: OK")
    print("[codex-contract] read-only ephemeral fallback thread: OK")
    print("[codex-contract] account/rateLimits/read usage endpoint: OK")


if __name__ == "__main__":
    main()
