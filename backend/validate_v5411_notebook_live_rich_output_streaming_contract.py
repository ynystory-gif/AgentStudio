from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
EDITOR = (ROOT / 'frontend/src/components/notebook/NotebookEditor.tsx').read_text(encoding='utf-8')
TYPES = (ROOT / 'frontend/src/types/notebook.ts').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
SERVICE = (ROOT / 'backend/app/services/python_execution_service.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')

checks = {
    'version': "AGENTSTUDIO_FRONTEND_VERSION='5.411'" in APP and 'version="5.411"' in MAIN and '"version": "5.411"' in ROUTES,
    'stream_route': '@router.post("/python/execute/stream")' in ROUTES and 'StreamingResponse' in ROUTES,
    'worker_event_protocol': "__AGENTSTUDIO_PY_EVENT_V1__" in SERVICE and '_agentstudio_emit_notebook_event' in SERVICE,
    'ipython_display_hook': '_agentstudio_install_notebook_display_hooks' in SERVICE and '_agentstudio_notebook_display' in SERVICE,
    'clear_output_hook': '_agentstudio_notebook_clear_output' in SERVICE and '"event": "clear_output"' in SERVICE,
    'matplotlib_png_capture': 'value.savefig(buffer, format="png"' in SERVICE and 'base64.b64encode' in SERVICE,
    'manager_streaming': 'def execute_stream(' in SERVICE and '"type": "event"' in SERVICE and '"rich_outputs"' in SERVICE,
    'frontend_ndjson_reader': "/python/execute/stream" in APP and 'streamResponse.body.getReader()' in APP and 'TextDecoder' in APP,
    'frontend_event_callback': 'onOutputEvent?.(packet.event||{})' in APP and 'onOutputEvent?:' in TYPES,
    'live_cell_output_state': 'liveOutputsByCell' in EDITOR and 'handleLiveOutputEvent' in EDITOR,
    'persist_last_rich_output': 'result?.rich_outputs' in EDITOR and 'rich_outputs?: NotebookOutputData[]' in TYPES,
    'clear_then_replace': "eventName === 'clear_output'" in EDITOR and '[index]: []' in EDITOR,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.411 contract FAIL: ' + ', '.join(failed))
print(f'v5.411 Notebook Live Rich Output Streaming contract PASS {len(checks)}/{len(checks)}')
