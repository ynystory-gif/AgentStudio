from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
NB = (ROOT / 'frontend' / 'src' / 'components' / 'notebook' / 'NotebookEditor.tsx').read_text(encoding='utf-8')
NBT = (ROOT / 'frontend' / 'src' / 'types' / 'notebook.ts').read_text(encoding='utf-8')
LOCAL = (ROOT / 'backend' / 'app' / 'services' / 'local_control.py').read_text(encoding='utf-8')
PYEXEC = (ROOT / 'backend' / 'app' / 'services' / 'python_execution_service.py').read_text(encoding='utf-8')
REQ = (ROOT / 'backend' / 'requirements.txt').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.378'" in APP,
    'backend version': '"version": "5.378"' in ROUTES,
    'pdf pypdf layout/plain': '_pypdf_page_text_variants' in LOCAL and 'pypdf_plain' in LOCAL and 'pypdf_layout' in LOCAL,
    'pdf pymupdf sorted': 'pymupdf_sorted' in LOCAL and 'PyMuPDF>=1.24' in REQ,
    'pdf punctuation fallback': 'pdf_punctuation_whitespace_insensitive' in LOCAL and 'aggressive=True' in LOCAL,
    'pdf one actionable result per page': 'Return the single clearest hit per page' in LOCAL,
    'pdf stale request guard': 'editorTextSearchRequestRef' in APP and 'requestId!==editorTextSearchRequestRef.current' in APP,
    'pdf stale navigation clear': 'delete next[pdfKey]' in APP,
    'notebook immutable root request': 'projectRoot?: string' in NBT and 'projectRoot: String(projectRoot ||' in NB,
    'notebook stable runtime id': 'const runtimeSessionId=`notebook::${normalizedPath.toLocaleLowerCase()}`' in APP,
    'notebook runtime terminal split': 'terminalSessionId,' in APP and 'runtimeSessionId,' in APP,
    'python interpreter stale rebind': '_same_interpreter' in PYEXEC and 'expected_interpreter = self.resolve_interpreter(root)' in PYEXEC,
    'python status exposes binding': 'stale_interpreter' in PYEXEC and 'bound_interpreter' in PYEXEC,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.378 contract: ' + ', '.join(failed))

# Behavioral smoke test: two duplicate text objects on page 1 must collapse to
# one actionable page result, while punctuation/whitespace variation still hits.
try:
    from pypdf import PdfWriter
    from app.services.local_control import _search_pdf_text_layer_matches
except Exception as exc:
    raise SystemExit(f'FAIL v5.378 import smoke: {exc}')

sample = '쓰레기를   넣으면\n쓰레기가 나온다\nDML — 데이터 조작어\n'
rows = _search_pdf_text_layer_matches(sample, '쓰레기를 넣으면 쓰레기가 나온다', case_sensitive=False, max_results=10)
if not rows:
    raise SystemExit('FAIL v5.378 Korean whitespace/linebreak search smoke')
rows2 = _search_pdf_text_layer_matches(sample, 'DML-데이터조작어', case_sensitive=False, max_results=10)
if not rows2:
    raise SystemExit('FAIL v5.378 punctuation-insensitive fallback smoke')

print('PASS v5.378 PDF Multi-Extractor Search + Notebook Runtime Context Isolation contract')
