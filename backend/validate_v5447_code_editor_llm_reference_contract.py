from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')

checks = []
def require(name: str, cond: bool):
    checks.append((name, bool(cond)))
    if not cond:
        raise AssertionError(name)

app = read('frontend/src/App.jsx')
styles = read('frontend/src/styles.css')
notebook = read('frontend/src/components/notebook/NotebookEditor.tsx')
routes = read('backend/app/api/routes.py')
main = read('backend/app/main.py')
codex = read('backend/app/services/codex_app_server_service.py')

require('frontend reference state', 'const [codeEditReferences,setCodeEditReferences]=useState([])' in app)
require('prompt ref focus', 'const codeEditPromptRef=useRef(null)' in app and 'ref={codeEditPromptRef}' in app)
require('monaco context action', "label:'LLM 참조 문구'" in app)
require('action requires selection', "precondition:'editorHasSelection'" in app)
require('action registered primary', 'registerCodeEditReferenceAction(editor,()=>selectedEditorFileRef.current' in app)
require('action registered split', 'registerCodeEditReferenceAction(editor,()=>relativePath)' in app)
require('notebook context action', "label: 'LLM 참조 문구'" in notebook and "precondition: 'editorHasSelection'" in notebook)
require('notebook reference callback', 'onAddLlmReference?.({' in notebook and 'cell_index: index' in notebook)
require('selection text captured', 'model.getValueInRange?.(selection)' in app)
require('line range captured', 'start_line:selection.startLineNumber' in app and 'end_line:selection.endLineNumber' in app)
require('notebook cell propagated', 'cell_index:Number.isInteger(reference.cell_index)' in app)
require('reference panel', 'className="code-edit-reference-panel"' in app and '전체 해제' in app)
require('project switch clears refs', 'setCodeEditReferences([])' in app and '},[root])' in app)
require('file request sends refs', app.count('reference_texts:requestReferences') >= 2)
require('chat traces refs', '🔖 LLM 참조 문구' in app)
require('frontend per-ref bound', 'const maxReferenceChars=24000' in app)
require('backend file request model', 'class CodeEditRequest(BaseModel):' in routes and 'reference_texts: list[dict] = Field(default_factory=list)' in routes)
require('backend project request model', 'class ProjectCodeEditRequest(BaseModel):' in routes and routes.count('reference_texts: list[dict] = Field(default_factory=list)') >= 2)
require('backend normalization helper', 'def _build_llm_code_reference_prompt' in routes)
require('backend total bound', 'total_limit = 60000' in routes and 'per_item_limit = 24000' in routes)
require('file prompt explicit refs', routes.count('[사용자 선택 LLM 참조 문구]') >= 3)
require('reference usage rules', '참조 문구는 사용자가 편집기에서 직접 선택해 지정한 핵심 근거' in routes)
require('backend returns reference trace', routes.count('"reference_count": len(normalized_references)') >= 3)
require('reference css', '.code-edit-reference-panel{' in styles and '.code-edit-reference-item pre{' in styles)
require('frontend version', "AGENTSTUDIO_FRONTEND_VERSION='5.447'" in app)
require('backend version', 'version="5.447"' in main and '"version": "5.447"' in routes)
require('codex version', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.447"' in codex)
require('build trace', 'CodeEditorSelectionLlmReference' in routes)

print(f'v5.447 contracts: {len(checks)}/{len(checks)} PASS')
