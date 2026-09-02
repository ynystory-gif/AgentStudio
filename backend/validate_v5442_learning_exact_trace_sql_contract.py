from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE = (ROOT / 'frontend/src/components/learning/LlmLearningCenter.tsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/components/learning/learning-case-list-cleanup.css').read_text(encoding='utf-8')
COLLECTION = (ROOT / 'backend/app/services/learning_collection_service.py').read_text(encoding='utf-8')
TEACHER = (ROOT / 'backend/app/services/learning_teacher_bridge.py').read_text(encoding='utf-8')
LEARNING = (ROOT / 'backend/app/services/llm_learning_service.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/learning_routes.py').read_text(encoding='utf-8')
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
API_ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')

checks = {
    'frontend version 5.442': "AGENTSTUDIO_FRONTEND_VERSION='5.442'" in APP,
    'backend version 5.442': 'version="5.442"' in MAIN,
    'health version 5.442': '"version": "5.442"' in API_ROUTES,
    'request has explicit source ids': 'source_case_ids: list[str] = Field(default_factory=list)' in ROUTES,
    'frontend sends exact visible source ids': 'source_case_ids:sourceCaseIds' in FE,
    'frontend avoids duplicate exact-source datasets but permits legacy family repair': "&&!row?.learning_exact_source_dataset_exists" in FE,
    'selector accepts explicit source ids': 'source_case_ids: list[str] | None = None' in COLLECTION and 'if explicit_ids:' in COLLECTION,
    'selector loads exact case ids': 'LlmMisjudgmentCase.id.in_(explicit_ids)' in COLLECTION,
    'automatic same-family selector only legacy path': 'existing_source_ids' in COLLECTION and 'if explicit_ids:' in COLLECTION,
    'job worker receives exact source ids': '_run_problem_collection_job(job_id, target, maximum, provider, source_case_ids)' in TEACHER,
    'job result verifies source mapping': 'source_mapping_verified' in COLLECTION,
    'mismatch fails collection': '오판 ID와 Dataset source_case_id 매핑 검증에 실패했습니다.' in COLLECTION,
    'visibility distinguishes exact source dataset': 'learning_exact_source_dataset_exists' in (ROOT / 'backend/app/services/learning_visibility_bridge.py').read_text(encoding='utf-8'),
    'normalized problem includes source case id': '"source_case_id": str(row.source_case_id or "")' in LEARNING,
    'problem viewer shows source case under problem id': 'Problem ID / 오판 ID' in FE and 'learning-source-case-id' in FE,
    'problem id trace css': '.learning-problem-id-block' in CSS,
    'cases SQL download': "downloadSql('cases')" in FE and 'LLM_오판_수집_리스트_조회.sql' in FE,
    'datasets SQL download': "downloadSql('datasets')" in FE and 'LLM_수집_문제_Dataset_리스트_조회.sql' in FE,
    'training SQL download': "downloadSql('training')" in FE and 'LLM_PC별_학습_적용_관리_리스트_조회.sql' in FE,
    'dataset SQL checks source mismatch': 'SOURCE_ID_MISMATCH' in FE and 'problem_source_case_id' in FE,
    'SQL export uses UTF8 BOM blob': "new Blob([`\\uFEFF${item.sql}`]" in FE,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL') + ' - ' + name)
print(f'{len(checks)-len(failed)}/{len(checks)} PASS')
raise SystemExit(1 if failed else 0)
