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
    'pdf layout extraction': "page.extract_text(extraction_mode='layout')" in LOCAL,
    'pdf duplicate normalization': 'def _pdf_search_normalize(' in LOCAL and 'pdf_duplicate_matches_removed' in LOCAL,
    'pdf contextual result': 'def _pdf_search_context(' in LOCAL and "'match_line':" in LOCAL,
    'pdf match identity': "'match_id': f\"p{page_index + 1}-m{page_match_index}\"" in LOCAL,
    'page authoritative viewer': 'Keep navigation page-only' in VIEWERS and 'const targetPage' in VIEWERS,
    'page search override blocked': "targetPage > 0" in VIEWERS and "? `page=${targetPage}`" in VIEWERS,
    'selected match toolbar': '통합 찾기 결과 · 페이지 ${targetPage}' in VIEWERS,
    'pdf location avoids fake line': '페이지 ${Number(row.page_number)}${Number(row?.page_match_index||0)>1' in APP,
    'duplicate count summary': 'pdf_duplicate_matches_removed' in APP,
    'navigation carries match': 'matchId:String(result?.match_id||\'\')' in APP and 'snippet:String(result?.match_line||result?.snippet||\'\')' in APP,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.374 PDF Search Dedup + Page Navigation contract: ' + ', '.join(failed))
print('PASS v5.374 PDF Search Dedup + Page Navigation contract')
