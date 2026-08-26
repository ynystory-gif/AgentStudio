from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
LOCAL = (ROOT / 'backend/app/services/local_control.py').read_text(encoding='utf-8')
NOTEBOOK = (ROOT / 'frontend/src/components/notebook/NotebookEditor.tsx').read_text(encoding='utf-8')
NOTEBOOK_TYPES = (ROOT / 'frontend/src/types/notebook.ts').read_text(encoding='utf-8')


def require(ok, message):
    if not ok:
        raise AssertionError(message)


require("AGENTSTUDIO_FRONTEND_VERSION='5.368'" in APP, 'frontend version must be 5.368')
require('projectFileSearch' in APP and '파일명 또는 경로 찾기' in APP, 'project file name/path search UI missing')
require('projectTreeForDisplay' in APP and 'projectFileSearchMatches' in APP, 'project tree filtering missing')
require("openEditorTextSearch('CURRENT')" in APP, 'current file text search button missing')
require("editorTextSearchScope==='PROJECT'" in APP and '프로젝트 전체' in APP, 'project text search scope missing')
require("api('/files/search-text'" in APP, 'frontend project text search API missing')
require('buildCurrentFileTextSearchResults' in APP and 'live_buffer:true' in APP, 'live editor buffer search missing')
require('revealEditorTextSearchResult' in APP, 'search result navigation missing')
require('@router.post("/files/search-text")' in ROUTES, 'backend search route missing')
require('search_project_text' in ROUTES, 'backend search service not wired')
require('_IGNORED_PROJECT_DIR_NAMES' in LOCAL and '_iter_project_tree(base)' in LOCAL, 'project ignore pruning must be reused')
require('_PROJECT_TEXT_SEARCH_MAX_FILE_BYTES' in LOCAL, 'large file safety limit missing')
require('_search_notebook_source' in LOCAL and 'cell_index' in LOCAL, 'Notebook cell source search missing')
require('revealSearchMatch' in NOTEBOOK and 'data-notebook-cell-index' in NOTEBOOK, 'Notebook search navigation missing')
require('revealSearchMatch' in NOTEBOOK_TYPES, 'Notebook controller contract missing')
print('PASS v5.368 Project Search & Text Find contract')
