from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/components/learning/LlmLearningCenter.tsx').read_text(encoding='utf-8')
MAIN_TSX = (ROOT / 'frontend/src/main.tsx').read_text(encoding='utf-8')
SERVICE = (ROOT / 'backend/app/services/llm_learning_service.py').read_text(encoding='utf-8')
COLLECT = (ROOT / 'backend/app/services/learning_collection_service.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')
FRONT_APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')

checks = {
    'frontend version 5.439': "AGENTSTUDIO_FRONTEND_VERSION='5.439'" in FRONT_APP,
    'backend version 5.439': 'version="5.439"' in MAIN,
    'health version 5.439': '"version": "5.439"' in ROUTES,
    'codex version 5.439': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.439"' in CODEX,
    'normalized problem model read': 'LlmLearningProblem' in SERVICE,
    'dataset storage reconciliation': 'async def ensure_dataset_problem_storage' in SERVICE,
    'relational authoritative read': 'relational_authoritative_with_legacy_mirror' in SERVICE,
    'legacy mirror repair': 'dataset.problems_json = hydrated' in SERVICE,
    'problem count repair': 'dataset.problem_count = len(hydrated)' in SERVICE,
    'collection verifies persisted dataset': 'persisted = await ensure_dataset_problem_storage' in COLLECT,
    'zero problem collection rejected': 'Dataset 저장 후 학습 문제를 확인하지 못했습니다.' in COLLECT,
    'completion reports persisted problem count': '문제 {generated_problem_count}개 DB 저장 확인' in COLLECT,
    'job persistence flag': '"persistence_verified"' in COLLECT,
    'startup relational schema repair': 'await ensure_learning_relational_schema()' in MAIN,
    'dataset tab native trace column': '<th>오판 / Dataset ID</th>' in APP,
    'problem id native column': '<th>Problem ID</th>' in APP,
    'empty problem warning': '이 Dataset의 문제 본문이 비어 있습니다.' in APP,
    'learning apply blocked for empty problems': "!(selectedDataset.problems||[]).length" in APP,
    'completed collection switches dataset tab': "sessionStorage.setItem(TAB_KEY,'datasets')" in APP,
    'dataset tab refreshes backend': "refresh().catch(e=>setMessage(String(e)))" in APP,
    'DOM trace enhancer removed from root': 'LearningDatasetTraceEnhancer' not in MAIN_TSX,
    'DOM tab restore enhancer removed from root': 'LearningPageStateRestoreEnhancer' not in MAIN_TSX,
    'validation syncs normalized rows': 'row.validated = str(row.problem_key or row.id) in approved_set' in SERVICE,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
if failed:
    raise SystemExit('v5.439 learning problem persistence repair contract failed: ' + ', '.join(failed))
print(f'v5.439 learning problem persistence repair contract PASS {len(checks)}/{len(checks)}')
