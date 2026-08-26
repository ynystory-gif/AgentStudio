from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
APP = ROOT / 'frontend' / 'src' / 'App.jsx'
ROUTES = ROOT / 'backend' / 'app' / 'api' / 'routes.py'
REQ_AGENT = ROOT / 'backend' / 'app' / 'services' / 'requirements_agent.py'
ATTACH = ROOT / 'backend' / 'app' / 'services' / 'ai_attachment_service.py'
MINER = ROOT / 'backend' / 'app' / 'services' / 'attachment_requirement_mining.py'
PATCH = ROOT / 'backend' / 'app' / 'services' / 'patch_service.py'
WORKFLOW = ROOT / 'backend' / 'app' / 'services' / 'agent_workflow.py'
MAIN = ROOT / 'backend' / 'app' / 'main.py'


def must(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


app_text = APP.read_text(encoding='utf-8')
routes_text = ROUTES.read_text(encoding='utf-8')
req_text = REQ_AGENT.read_text(encoding='utf-8')
attach_text = ATTACH.read_text(encoding='utf-8')
miner_text = MINER.read_text(encoding='utf-8')
patch_text = PATCH.read_text(encoding='utf-8')
workflow_text = WORKFLOW.read_text(encoding='utf-8')
main_text = MAIN.read_text(encoding='utf-8')

must("AGENTSTUDIO_FRONTEND_VERSION='5.368'" in app_text, 'Frontend version must be 5.368')
must('version="5.368"' in main_text, 'Backend FastAPI version must be 5.368')
must('"version": "5.368"' in routes_text, 'Health/export version must be 5.368')

# Deep attachment requirement mining contracts.
must('_requirement_candidate_lines' in attach_text, 'Requirement candidate extractor missing')
must('[명시적 요구사항 후보]' in attach_text, 'Explicit requirement block missing')
must('fair_share' in attach_text, 'Attachment fair-share context budget missing')
must('_REQUIREMENTS_TOTAL_CONTEXT_CHARS = 28_000' in attach_text, 'Expanded requirements budget missing')
must('extract_attachment_requirement_registry' in miner_text, 'Requirement Registry miner missing')
must('REQ-{len(requirements) + 1:03d}' in miner_text, 'Stable REQ ids missing')
must('attachment_requirements' in routes_text and 'attachment_requirement_coverage' in routes_text, 'Routes do not return requirement registry')
must('interviewAttachmentRequirements' in app_text, 'Frontend requirement registry state missing')
must('추출 요구사항' in app_text, 'Frontend requirement registry UI missing')
must('Deep Requirement Registry - 명시적 문서 요구사항 우선' in app_text, 'Generated project request does not include attachment registry')

# Interview slot completion/dedup contracts.
must('_is_explicit_none_answer' in req_text, 'Explicit NONE slot completion missing')
must('_answered_question_slots' in req_text, 'Answered slot tracker missing')
must("return ''" in req_text[req_text.find('def _next_user_decision_question'):req_text.find('def _quality_gate_next_question')], 'Asked-slot repeat guard missing')
must('next_question = _next_user_decision_question(user_text, history, requirement_context)' in req_text, 'Quality gate must use current slot state')
must('요구사항 분석이 완료되었습니다. Workflow 설계 단계로 진행할 수 있습니다.' in req_text, 'Interview completion message missing')

# Root-source repair contracts for the uploaded TEST_FAILED case.
must('_strip_outer_markdown_fence_for_source' in patch_text, 'Source fence sanitizer missing')
must('outer_markdown_fence_removed' in patch_text, 'Patch result fence repair marker missing')
must('explicitly_relative = raw_slash.startswith("./")' in workflow_text, 'Explicit project-root relative path priority missing')
must('exact_root_candidate = (root / normalized).is_file()' in workflow_text, 'Exact project-root candidate detection missing')
must('_repair_wrapped_generated_source_files' in workflow_text, 'Pre-test source fence recovery missing')
must('pretest_source_repair' in workflow_text, 'Pre-test repair state missing')

# Runtime requirement-mining check without LangChain/model dependencies.
sys.path.insert(0, str(BACKEND))
from app.services.ai_attachment_service import _requirements_outline  # noqa: E402
from app.services.attachment_requirement_mining import extract_attachment_requirement_registry  # noqa: E402

notebook_problem = '''
## Cell 1 (markdown)
# 미니프로젝트 문제지: 온라인 리테일 주문·매출 콘솔
online_retail_2011.csv, ERD, 목표 화면을 기준으로 Streamlit 앱을 구현합니다. PostgreSQL은 매출·주문 관계형 데이터를 관리해야 합니다. pgvector는 문장 기반 의미 검색을 담당합니다. Redis는 검색 결과 캐시와 최근 처리 기록, 운영 카운터를 담당합니다. LangChain은 자연어 요청을 구조화합니다.

## Cell 2 (markdown)
## 제공 자료
- online_retail_2011.csv를 사용한다.
- 상품 검색은 자연어 문장을 입력하면 벡터 유사성 검사로 조회되어야 한다.
- 검색 결과는 최대 100건만 조회한다.

## Cell 3 (markdown)
## 산출물
- apps/retail_project.py를 생성한다.
- 검색 결과 리포트를 저장한다.

## Cell 4 (markdown)
## 제약
- 비밀번호와 API 키를 코드에 적지 않는다.
- Redis의 모든 키는 retail: 접두사를 사용한다.
- 문서 임베딩과 질문 임베딩은 같은 모델과 차원을 사용한다.
'''
digest = _requirements_outline(notebook_problem, 'notebook', 12000)
registry = extract_attachment_requirement_registry(
    '### 참고 파일 분석본: 7. 미니프로젝트_온라인_리테일_주문_대시보드_문제.ipynb\n'
    '- 경로: example.ipynb\n- 형식: notebook\n- 원문 문자 수: 2000\n- 용도: test\n- 주의: test\n\n'
    + digest
)
rows = registry.get('requirements') or []
combined = '\n'.join(str(row.get('text') or '') for row in rows).casefold()
must(len(rows) >= 9, f'Expected rich requirement mining, got only {len(rows)} rows')
for needle in ('streamlit', 'postgresql', 'pgvector', 'redis', '100건', '리포트', '비밀번호', 'retail:', '같은 모델'):
    must(needle.casefold() in combined, f'Missing mined requirement evidence: {needle}')
coverage = registry.get('coverage') or {}
must(coverage.get('coverage_gate') == 'PASS', 'Requirement coverage gate must pass')
must(int(coverage.get('source_files') or 0) == 1, 'Source file tracking must be preserved')

# Extract the pure source-fence sanitizer from patch_service.py and test the exact
# root main.py failure shape without importing LangChain dependencies.
tree = ast.parse(patch_text)
selected = []
for node in tree.body:
    if isinstance(node, ast.Assign):
        names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if '_SOURCE_FENCE_LANGS' in names:
            selected.append(node)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == '_strip_outer_markdown_fence_for_source':
        selected.append(node)
module = ast.Module(body=selected, type_ignores=[])
ns = {'Path': Path, 're': re}
exec(compile(module, str(PATCH), 'exec'), ns, ns)
strip_fence = ns['_strip_outer_markdown_fence_for_source']
repaired, changed = strip_fence(Path('main.py'), "```python\nprint('ok')\n```\n")
must(changed, 'Python whole-file fence should be repaired')
must(repaired.strip() == "print('ok')", 'Fence repair must preserve raw Python source')
unchanged, changed_md = strip_fence(Path('README.md'), '```python\nprint(1)\n```\n')
must(not changed_md and unchanged.startswith('```python'), 'Markdown documents must not be source-fence repaired')

print('PASS v5.368 Deep Attachment Requirement Mining + Root Source Fence Repair contract')
