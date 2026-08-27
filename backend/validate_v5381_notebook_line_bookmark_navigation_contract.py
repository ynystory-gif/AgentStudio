from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
NOTEBOOK = (ROOT / 'frontend' / 'src' / 'components' / 'notebook' / 'NotebookEditor.tsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend' / 'src' / 'styles.css').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend' / 'app' / 'main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')
SERVICE = (ROOT / 'backend' / 'app' / 'services' / 'codex_app_server_service.py').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.381'" in APP,
    'backend main version': 'version="5.381"' in MAIN,
    'backend health version': '"version": "5.381"' in ROUTES,
    'codex client version': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.381"' in SERVICE,
    'build marker': 'NotebookLineBookmarkNavigation' in ROUTES,
    'glyph margin enabled': 'glyphMargin: true' in NOTEBOOK,
    'glyph margin click toggles bookmark': 'GUTTER_GLYPH_MARGIN === 2' in NOTEBOOK and 'toggleLineBookmark(index, lineNumber)' in NOTEBOOK,
    'bookmark decoration': "glyphMarginClassName: 'notebook-line-bookmark-glyph'" in NOTEBOOK,
    'bookmark persisted by notebook path': 'NOTEBOOK_BOOKMARK_STORAGE_PREFIX' in NOTEBOOK and 'window.localStorage.setItem' in NOTEBOOK,
    'previous/next navigation': 'moveToBookmark(-1)' in NOTEBOOK and 'moveToBookmark(1)' in NOTEBOOK,
    'bookmark count': '북마크 {bookmarks.length}' in NOTEBOOK,
    'clear all bookmarks': 'clearBookmarks' in NOTEBOOK and '모두 해제' in NOTEBOOK,
    'cell insert bookmark shift': 'shiftBookmarksForInsertedCell(insertAt)' in NOTEBOOK,
    'cell delete bookmark shift': 'shiftBookmarksForDeletedCell(index)' in NOTEBOOK,
    'bookmark visual css': '.notebook-line-bookmark-glyph::before' in CSS and '.notebook-bookmark-navigation' in CSS,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.381 contract: ' + ', '.join(failed))
print('PASS v5.381 Notebook Line Bookmark Navigation contract')
