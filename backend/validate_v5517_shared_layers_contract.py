from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'frontend'/'src'
APP=(SRC/'app'/'App.tsx').read_text(encoding='utf-8')
errors=[]

def require(cond,msg):
    if not cond: errors.append(msg)

require("AGENTSTUDIO_FRONTEND_VERSION='5.517'" in APP,'frontend version 5.517 missing')
require((SRC/'stores'/'workspacePreferences.ts').exists(),'workspace store missing')
require((SRC/'utils'/'storage.ts').exists(),'storage utility missing')
require((SRC/'utils'/'time.ts').exists(),'time utility missing')
require((SRC/'components'/'common'/'AgentBuildControls.tsx').exists(),'common AgentBuildControls missing')
require('type CssVarProperties =' not in APP,'CssVarProperties still declared in App')
require('function CodeDocumentationToggle(' not in APP,'CodeDocumentationToggle still declared in App')
require("readWorkspaceNumber('editorSplitRatio'" in APP,'editor split persistence not routed through store')
require("readWorkspaceBoolean('leftCollapsed'" in APP,'workspace persistence not routed through store')
require("writeWorkspacePreference('leftWidth'" in APP,'workspace writes not routed through store')
require("import { formatMediaElapsed } from '../utils/time'" in APP,'time utility import missing')
expected=[
 '내프로젝트 파일 GIT 올리기(1).pptx',
 '로컬 수정 무시하고 GitHub 최신본 내려받기(1).pptx',
 'GIT 내용을 전부 무시하고 올리기.ps1',
 '로컬 폴더의 변경 내용을 전부 무시하고 GIT 내려받기.ps1',
]
for name in expected: require((ROOT/name).exists(),f'Korean filename missing: {name}')
for p in ROOT.iterdir():
    require(not any(ch in p.name for ch in ('δ','∞','φ','Ω','�')),f'mojibake filename remains: {p.name}')
if errors:
    print('[v5.517] FAIL')
    for e in errors: print(' -',e)
    sys.exit(1)
print('[v5.517] shared layers + Korean filenames: PASS')
