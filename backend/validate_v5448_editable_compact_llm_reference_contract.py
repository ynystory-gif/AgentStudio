from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


checks = []


def require(name: str, cond: bool):
    checks.append((name, bool(cond)))
    if not cond:
        raise AssertionError(name)


app = read("frontend/src/App.jsx")
styles = read("frontend/src/styles.css")
routes = read("backend/app/api/routes.py")
main = read("backend/app/main.py")
codex = read("backend/app/services/codex_app_server_service.py")

# Requested clutter removal.
require("removed selected-file chat title", "선택된 파일과 대화하며 코드 수정" not in app)
require("removed current target file helper", "현재 대상 파일:" not in app)
require(
    "removed initial edit instruction",
    "수정할 파일을 선택한 뒤 원하는 변경 내용을 입력하세요. 현재 파일 코드를 기준으로 수정안을 만들고 적용할 수 있습니다."
    not in app,
)
require("initial chat is empty", "const [codeEditChat,setCodeEditChat]=useState([])" in app)
require(
    "chat hidden until meaningful content",
    "(codeEditChat.length>0||codeEditBusy||codeEditProposal)&&<div className=\"code-llm-chat\"" in app,
)
require(
    "empty reference panel hidden",
    "codeEditReferences.length>0&&<div className=\"code-edit-reference-panel\"" in app,
)
require("verbose reference empty helper removed", "참조 문구 없음" not in app)

# Reference text is editable and the edited value is sent to the backend.
require("editable reference update handler", "const updateCodeEditReferenceText=(referenceId,nextText)=>" in app)
require("reference textarea", 'className="code-edit-reference-text"' in app)
require("reference textarea controlled", "value={reference.text}" in app)
require("reference textarea onChange", "updateCodeEditReferenceText(reference.id,event.target.value)" in app)
require("reference textarea limit", "maxLength={24000}" in app)
require("empty edited references excluded", ".filter(reference=>String(reference.text||'').trim())" in app)
require("edited flag transported", "edited:Boolean(reference.edited)" in app)
require("editable reference styling", ".code-edit-reference-text{" in styles and ".code-edit-reference-text:focus{" in styles)

# Backend must treat user-edited reference text as the authoritative reference context.
require("backend edited flag normalized", '"edited": bool(raw.get("edited"))' in routes)
require("backend edited marker", '사용자 편집' in routes)
require("backend edited reference precedence", "수정된 텍스트를 원본 선택 내용보다 우선" in routes)
require("file reference request model", "reference_texts: list[dict] = Field(default_factory=list)" in routes)

# Version synchronization.
require("frontend version", "AGENTSTUDIO_FRONTEND_VERSION='5.448'" in app)
require("backend version", 'version="5.448"' in main and '"version": "5.448"' in routes)
require("codex version", 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.448"' in codex)
require("build trace", "EditableLlmReferenceCompactChat" in routes)

print(f"v5.448 contracts: {len(checks)}/{len(checks)} PASS")
