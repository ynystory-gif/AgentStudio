from __future__ import annotations

import asyncio
import traceback
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.terminal_manager import terminal_manager


router = APIRouter()


def _terminal_error_log_path(root: str) -> Path:
    project_root = Path(root).expanduser().resolve()
    log_dir = project_root / ".agentstudio" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "terminal_ws.log"


def _write_terminal_error_log(root: str, title: str, detail: str) -> str:
    try:
        log_path = _terminal_error_log_path(root)
        text = (
            f"{title}\n"
            f"{'=' * 80}\n"
            f"PROJECT_ROOT: {root}\n\n"
            f"{detail}\n"
        )
        log_path.write_text(text, encoding="utf-8")
        return str(log_path)
    except Exception:
        return ""


@router.websocket("/ws/terminal/{session_id}")
async def terminal_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()

    root = websocket.query_params.get("root", "")
    project_name = websocket.query_params.get("project_name", "")

    try:
        session = await terminal_manager.create(
            root,
            project_name,
            session_id,
        )
    except Exception as e:
        detail = traceback.format_exc()
        log_path = _write_terminal_error_log(
            root,
            "TERMINAL SESSION CREATE ERROR",
            detail,
        )

        await websocket.send_json({
            "type": "error",
            "stage": "session_create",
            "message": str(e),
            "detail": detail,
            "log_path": log_path,
            "session_id": session_id,
            "root": root,
        })

        await websocket.close(
            code=1011,
            reason="terminal session create failed",
        )
        return

    async def sender():
        try:
            while True:
                data = await session.queue.get()

                if data.startswith("__THEANOVA_PROCESS_EXIT__="):
                    raw_code = data.split("=", 1)[1].strip()
                    try:
                        exit_code = int(raw_code)
                    except Exception:
                        exit_code = None

                    await websocket.send_json({
                        "type": "process_exit",
                        "session_id": session_id,
                        "exit_code": exit_code,
                        "root": root,
                    })
                    continue

                await websocket.send_json({
                    "type": "output",
                    "data": data,
                    "session_id": session_id,
                })

        except asyncio.CancelledError:
            raise

        except Exception as e:
            detail = traceback.format_exc()
            log_path = _write_terminal_error_log(
                root,
                "TERMINAL OUTPUT SENDER ERROR",
                detail,
            )

            try:
                await websocket.send_json({
                    "type": "error",
                    "stage": "output_sender",
                    "message": str(e),
                    "detail": detail,
                    "log_path": log_path,
                    "session_id": session_id,
                    "root": root,
                })
            except Exception:
                pass

    task = asyncio.create_task(sender())

    try:
        await websocket.send_json({
            "type": "ready",
            "session_id": session_id,
            "root": session.root,
            "project_name": session.project_name,
            "has_venv": bool(getattr(session, "has_venv", False)),
            "elevated": bool(getattr(session, "elevated", False)),
        })

        history_text = terminal_manager.get_history(session_id)
        if history_text:
            await websocket.send_json({
                "type": "history",
                "session_id": session_id,
                "data": history_text,
            })

        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "command":
                await terminal_manager.send_command(
                    session_id,
                    str(msg.get("data") or ""),
                )

            elif msg_type == "input":
                await terminal_manager.send_command(
                    session_id,
                    str(msg.get("data") or ""),
                )

            elif msg_type == "raw_input":
                await terminal_manager.send_raw(
                    session_id,
                    str(msg.get("data") or ""),
                )

            elif msg_type == "interrupt":
                await terminal_manager.interrupt(session_id)

                await websocket.send_json({
                    "type": "interrupted",
                    "session_id": session_id,
                })

            elif msg_type == "clear":
                terminal_manager.clear_history(session_id)
                await websocket.send_json({
                    "type": "cleared",
                    "session_id": session_id,
                })

            elif msg_type == "close":
                await terminal_manager.close(session_id)
                await websocket.close()
                break

    except WebSocketDisconnect:
        pass

    except Exception as e:
        detail = traceback.format_exc()
        log_path = _write_terminal_error_log(
            root,
            "TERMINAL WEBSOCKET ERROR",
            detail,
        )

        try:
            await websocket.send_json({
                "type": "error",
                "stage": "websocket_loop",
                "message": str(e),
                "detail": detail,
                "log_path": log_path,
                "session_id": session_id,
                "root": root,
            })
        except Exception:
            pass

    finally:
        task.cancel()
