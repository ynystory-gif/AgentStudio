from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise AssertionError(message)

require("AGENTSTUDIO_FRONTEND_VERSION='5.368'" in APP,'frontend version must be 5.368')
require("const expanded=!!fileTreeExpanded[node.path]" in APP,'tree expansion must obey user state during search')
require("const expanded=!!projectFileSearchNeedle ||" not in APP,'search must not force every folder open')
require('검색 결과는 처음에는 일치 파일의 상위 폴더를 자동으로 펼칩니다.' in APP,'search ancestor initial expansion contract missing')
require('className="powershell-run-button editor-find-toolbar-button"' in APP,'unified find toolbar button missing')
require("onClick={()=>openEditorTextSearch('CURRENT')}" in APP,'unified find must default to current file')
require('⌕ 현재 파일 찾기' not in APP,'legacy current-file command button must be removed')
require('⌕ 프로젝트 텍스트 찾기' not in APP,'legacy project command button must be removed')
require("editorTextSearchScope==='CURRENT'" in APP and "editorTextSearchScope==='PROJECT'" in APP,'search panel scope switch must remain')
require('.editor-find-toolbar-button' in CSS,'unified find button style missing')
print('PASS v5.368 Search Tree Toggle & Unified Find contract')
