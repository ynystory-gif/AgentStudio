from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / "backend/app/services/agent_workflow.py").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8")

checks = [
    ("frontend version", "AGENTSTUDIO_FRONTEND_VERSION='5.461'" in APP),
    ("backend version", 'version="5.461"' in MAIN and '"version": "5.461"' in ROUTES),
    ("codex version", 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.461"' in CODEX),
    ("checkbox label", "변수·메소드 설명 추가" in APP),
    ("checkbox state", "const [codeDocumentationEnabled,setCodeDocumentationEnabled]=useState(false)" in APP),
    ("checkbox beside development control", 'className="development-start-control"' in APP and 'className={`code-documentation-option ${codeDocumentationEnabled?' in APP),
    ("checkbox locked while building", "disabled={busy||stage==='BUILDING'}" in APP),
    ("new project resets option", "setCodeDocumentationEnabled(false)" in APP),
    ("draft persists option", "code_documentation:{" in APP and "enabled:Boolean(codeDocumentationEnabled)" in APP),
    ("draft restores option", "setCodeDocumentationEnabled(Boolean(snapshot?.code_documentation?.enabled))" in APP),
    ("autosave tracks option", "codeDocumentationEnabled,\n    uiLayoutConfig" in APP),
    ("normal build sends policy", "code_documentation:codeDocumentation" in APP and "design_bundle:{" in APP),
    ("redevelopment sends policy", "code_documentation:codeDocumentation" in APP and "/workflow/redevelop-start-job" in APP),
    ("redevelopment request accepts policy", "code_documentation: dict = {}" in ROUTES),
    ("redevelopment restores prior policy", 'previous_bundle.get("code_documentation")' in ROUTES),
    ("prompt policy helper", "def _code_documentation_instruction" in WORKFLOW and "사용자 선택: 변수·메소드 설명 주석 추가" in WORKFLOW),
    ("language-specific standards", "TypeScript/JavaScript는 JSDoc" in WORKFLOW and "C#은 XML documentation" in WORKFLOW and "Java는 Javadoc" in WORKFLOW),
    ("no comment spam policy", "단순 반복문의 index" in WORKFLOW and "주석을 남발하지 마십시오" in WORKFLOW),
    ("preserve existing comments", "기존 파일을 수정할 때 이미 존재하는 유효한 주석/docstring은 삭제" in WORKFLOW),
    ("all codegen paths receive policy", WORKFLOW.count("+ code_documentation_instruction") >= 4 and "+ _code_documentation_instruction(state)" in WORKFLOW),
    ("documentation validation", "def _code_documentation_findings" in WORKFLOW and "code_documentation_errors" in WORKFLOW),
    ("missing public docs gate build", "and not code_documentation_errors" in WORKFLOW),
    ("major variable docs audited", "code_documentation_warnings" in WORKFLOW and "missing_variables" in WORKFLOW),
    ("repair includes doc omissions", '"code_documentation_errors",' in WORKFLOW and "문서화만 보완하십시오" in WORKFLOW),
    ("right panel responsive layout", ".right-agent-build-card .development-start-control{grid-column:1 / -1;}" in CSS),
]

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
print(f"\n{len(checks)-len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit("contract failed: " + ", ".join(failed))
