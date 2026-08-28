from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
checks={
    'version': "AGENTSTUDIO_FRONTEND_VERSION='5.405'" in APP and 'version="5.405"' in MAIN and '"version": "5.405"' in ROUTES,
    'csv detection': "CSV_SPREADSHEET_EXTENSIONS=new Set(['csv','tsv'])" in APP and 'isCsvSpreadsheetFile' in APP,
    'delimiter detection': 'detectSpreadsheetDelimiter' in APP and 'countDelimiterOutsideQuotes' in APP,
    'quoted csv parser': 'parseSpreadsheetPreview' in APP and "if(inQuotes&&text[index+1]==='\"')" in APP,
    'excel grid headers': 'spreadsheetColumnLabel' in APP and 'csv-grid-column-head' in APP and 'csv-grid-row-head' in APP,
    'sticky spreadsheet ux': 'position:sticky' in CSS and '.csv-grid-corner' in CSS,
    'grid raw modes': "mode==='GRID'" in APP and "mode==='RAW'" in APP and '원문 편집' in APP,
    'cell select copy': 'selectedCell' in APP and 'copySelected' in APP and 'navigator.clipboard' in APP,
    'large file guard': 'maxRows=5000' in APP and 'maxColumns=200' in APP,
    'render integration': ': isCsvSpreadsheetFile(selected)' in APP and '<CsvSpreadsheetViewer' in APP,
    'bookmark exclusion': '&&!isCsvSpreadsheetFile(path)' in APP,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.405 contract FAIL: '+', '.join(failed))
print(f'v5.405 CSV spreadsheet grid viewer contract PASS {len(checks)}/{len(checks)}')
