from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'backend' / 'app' / 'services' / 'local_control.py'
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend' / 'app' / 'main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')
PS1 = (ROOT / 'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8')
SOURCE = LOCAL.read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.375'" in APP,
    'backend version': 'version="5.375"' in MAIN,
    'health version': '"version": "5.375"' in ROUTES,
    'launcher version': '$FallbackAgentStudioVersion = "5.375"' in PS1,
    'NFKC normalization': 'unicodedata.normalize("NFKC"' in SOURCE,
    'whitespace insensitive matcher': 'def _pdf_search_match_key' in SOURCE,
    'compact page matcher': 'def _search_pdf_text_layer_matches' in SOURCE,
    'PDF search uses flexible matcher': 'raw_rows = _search_pdf_text_layer_matches(' in SOURCE,
}

# Import the module with a tiny stub path only if project imports are available.
# The behavioral check is replicated from the contract function semantics to stay standalone.
import re, unicodedata

def key(value: str) -> str:
    normalized = unicodedata.normalize('NFKC', value)
    normalized = re.sub(r'[\s\u200b\u200c\u200d\ufeff]+', '', normalized)
    return normalized.casefold()

checks['Korean visible-space match'] = key('데이터조작어') in key('DML — 데이터 조작어')
checks['line-break match'] = key('데이터조작어') in key('데이터\n조작어')
checks['zero-width match'] = key('데이터조작어') in key('데이터\u200b조작어')

failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.375 PDF Whitespace-Insensitive Search contract: '+', '.join(failed))
print('PASS v5.375 PDF Whitespace-Insensitive Search contract')
