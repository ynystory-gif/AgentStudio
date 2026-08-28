from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
EDITOR = (ROOT / 'frontend/src/components/notebook/NotebookEditor.tsx').read_text(encoding='utf-8')
RENDERERS = (ROOT / 'frontend/src/components/notebook/NotebookRenderers.tsx').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
SERVICE = (ROOT / 'backend/app/services/python_execution_service.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
TYPES = (ROOT / 'frontend/src/types/notebook.ts').read_text(encoding='utf-8')
DOC = (ROOT / 'docs/NOTEBOOK_SMOOTH_LIVE_OUTPUT_RENDERING_V5412.md').read_text(encoding='utf-8')

checks = {
    'version': "AGENTSTUDIO_FRONTEND_VERSION='5.412'" in APP and 'version="5.412"' in MAIN and '"version": "5.412"' in ROUTES,
    'build_marker': 'NotebookSmoothLiveOutputRendering' in ROUTES,
    'wait_flag_type': 'wait?: boolean' in TYPES,
    'frontend_pending_wait_ref': 'pendingLiveClearWaitRef' in EDITOR,
    'frontend_replace_next_ref': 'replaceLiveOutputOnNextEventRef' in EDITOR,
    'frontend_wait_clear_deferred': "if (Boolean(event?.wait))" in EDITOR and 'pendingLiveClearWaitRef.current[index] = true' in EDITOR,
    'frontend_atomic_replace': 'const replaceCurrent = Boolean(' in EDITOR and '? []' in EDITOR,
    'frontend_preserve_previous_frame': 'const previousOutputs = Array.isArray(cell.outputs) ? cell.outputs : []' in EDITOR,
    'frontend_handoff_delay': '}, 80)' in EDITOR,
    'image_preload': 'const loader = new Image()' in RENDERERS and "loader.decoding = 'async'" in RENDERERS,
    'image_decode_before_swap': "if (typeof loader.decode === 'function') await loader.decode()" in RENDERERS and 'setDisplaySrc(src)' in RENDERERS,
    'backend_pending_wait': 'pending_clear_wait = False' in SERVICE and 'if bool(event.get("wait")):' in SERVICE,
    'backend_deferred_clear': 'pending_clear_wait = True' in SERVICE and 'if pending_clear_wait:' in SERVICE,
    'documentation': '빈 출력 영역이 나타나지 않습니다' in DOC,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.412 contract FAIL: ' + ', '.join(failed))
print(f'v5.412 Notebook Smooth Live Output Rendering contract PASS {len(checks)}/{len(checks)}')
