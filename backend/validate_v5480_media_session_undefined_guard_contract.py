from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

checks: list[tuple[str, bool]] = []
def check(name: str, condition: bool) -> None:
    checks.append((name, bool(condition)))

app = text('frontend/src/App.jsx')
provider = text('frontend/src/components/media/MediaSessionProvider.tsx')
routes = text('backend/app/api/routes.py')
main = text('backend/app/main.py')
codex = text('backend/app/services/codex_app_server_service.py')
readme = text('README_V5_480.md')
requirements = text('backend/requirements.txt')
service = text('backend/app/services/live_stt_service.py')

check('frontend version 5.480', "AGENTSTUDIO_FRONTEND_VERSION='5.480'" in app)
check('backend version 5.480', 'version="5.480"' in main)
check('health version 5.480', '"version": "5.480"' in routes)
check('Codex client version 5.480', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.480"' in codex)
check('health build marker', '+MediaSessionLastSegmentUndefinedGuard' in routes)
check('reported TS2532 line guarded', "segments[segments.length - 1]?.createdAt" in provider)
check('unsafe last-segment access removed', "segments[segments.length - 1].createdAt" not in provider)
check('faster-whisper dependency retained', 'faster-whisper>=1.1.1' in requirements)
check('backend STT service retained', 'WhisperModel' in service and 'LIVE_OVERLAP_SECONDS = 1.2' in service)
check('stop-time refinement retained', '_refine_sync' in service and 'beam_size=3' in service)
check('README documents real build error', 'TS2532' in readme and "possibly 'undefined'" in readme)

failed=[name for name,ok in checks if not ok]
for name,ok in checks:
    print(f"{'PASS' if ok else 'FAIL'} - {name}")
print(f"\n{len(checks)-len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit('FAILED: '+', '.join(failed))
