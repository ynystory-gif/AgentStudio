from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWERS = (ROOT / 'frontend/src/components/viewers/DocumentViewers.tsx').read_text(encoding='utf-8')
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks = {
    'frontend version 5.438': "AGENTSTUDIO_FRONTEND_VERSION='5.438'" in APP,
    'backend version 5.438': 'version="5.438"' in MAIN,
    'health version 5.438': '"version": "5.438"' in ROUTES,
    'codex version 5.438': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.438"' in CODEX,
    'viewer imports apiFetch': "apiFetch" in VIEWERS.splitlines()[1],
    'pdf uses authenticated apiFetch': 'apiFetch(`/files/pdf?${params.toString()}`)' in VIEWERS,
    'pdf builds local blob url': 'URL.createObjectURL(pdfBlob)' in VIEWERS,
    'pdf revokes local blob url': 'URL.revokeObjectURL(objectUrl)' in VIEWERS,
    'pdf no direct backend iframe source': '`${apiBase}/files/pdf?' not in VIEWERS,
    'presentation uses authenticated apiFetch': 'apiFetch(`/files/presentation/pdf?${params.toString()}`)' in VIEWERS,
    'presentation no direct backend iframe source': '`${apiBase}/files/presentation/pdf?' not in VIEWERS,
    'binary save as uses apiFetch': 'apiFetch(`/files/raw?${params.toString()}`)' in APP,
    'binary save as no unauthenticated direct fetch': 'fetch(`${info.apiBase}/files/raw?${params.toString()}`)' not in APP,
    'protected backend PDF endpoint remains': '@router.get("/files/pdf")' in ROUTES,
    'PDF media type remains correct': 'media_type="application/pdf"' in ROUTES,
}
failed=[name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
if failed:
    raise SystemExit('v5.438 authenticated PDF preview contract failed: ' + ', '.join(failed))
print(f'v5.438 authenticated PDF preview contract PASS {len(checks)}/{len(checks)}')
