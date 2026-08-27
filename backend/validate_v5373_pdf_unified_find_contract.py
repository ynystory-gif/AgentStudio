from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
VIEWERS = (ROOT / 'frontend/src/components/viewers/DocumentViewers.tsx').read_text(encoding='utf-8')
LOCAL = (ROOT / 'backend/app/services/local_control.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
PS1 = (ROOT / 'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8-sig')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.374'" in APP,
    'backend version': 'version="5.374"' in MAIN,
    'health version': '"version": "5.374"' in ROUTES,
    'launcher version': '$FallbackAgentStudioVersion = "5.374"' in PS1,
    'pdf current search branch': "if(isPdfFile(selected)){" in APP and "relative_path:normalizeProjectRelativePath(selected)" in APP,
    'pdf extraction helper': 'def _search_pdf_source(' in LOCAL and 'from pypdf import PdfReader' in LOCAL,
    'pdf page coordinates': "'page_number': page_index + 1" in LOCAL,
    'project-wide pdf protected': 'Project-wide search intentionally keeps' in LOCAL,
    'pdf result location': '페이지 ${Number(row.page_number)}' in APP,
    'pdf navigation state': 'setPdfSearchNavigation' in APP,
    'viewer page-authoritative navigation': 'const targetPage' in VIEWERS and '? `page=${targetPage}`' in VIEWERS,
    'viewer search fallback': '`search=${encodeURIComponent(String(searchQuery || \'\').trim())}`' in VIEWERS,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.374 PDF Unified Find compatibility contract: ' + ', '.join(failed))
print('PASS v5.374 PDF Unified Find compatibility contract')
