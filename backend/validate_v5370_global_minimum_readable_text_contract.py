from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / 'frontend' / 'src' / 'styles.css').read_text(encoding='utf-8')
ERD = (ROOT / 'frontend' / 'src' / 'components' / 'database' / 'DatabaseDiagramViewer.tsx').read_text(encoding='utf-8')
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend' / 'app' / 'main.py').read_text(encoding='utf-8')
PS1 = (ROOT / 'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8')

violations = []
for match in re.finditer(r'font-size\s*:\s*([0-9]+(?:\.[0-9]+)?)px', CSS):
    value = float(match.group(1))
    if value < 13:
        violations.append(f'CSS font-size {value}px at {match.start()}')
for match in re.finditer(r'font\s*:\s*([0-9]+(?:\.[0-9]+)?)px', CSS):
    value = float(match.group(1))
    if value < 13:
        violations.append(f'CSS font shorthand {value}px at {match.start()}')
for match in re.finditer(r'fontSize="([0-9]+(?:\.[0-9]+)?)"', ERD):
    value = float(match.group(1))
    if value < 13:
        violations.append(f'ERD SVG fontSize {value}px')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.371'" in APP,
    'backend version': 'version="5.371"' in MAIN,
    'launcher version': '$FallbackAgentStudioVersion = "5.371"' in PS1,
    'readability variable': '--agentstudio-min-readable-font-size:13px' in CSS,
    'small baseline': 'small{font-size:var(--agentstudio-min-readable-font-size);}' in CSS,
    'reference text baseline': '.live-db-preview-head small{font-size:var(--agentstudio-min-readable-font-size);}' in CSS,
    'no sub-13 explicit fonts': not violations,
}
failed = [name for name, ok in checks.items() if not ok]
if failed or violations:
    detail = ', '.join(failed + violations[:20])
    raise SystemExit('FAIL v5.371: ' + detail)
print('PASS v5.371 Global Minimum Readable Text Size contract')
