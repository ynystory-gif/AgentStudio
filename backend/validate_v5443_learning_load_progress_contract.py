from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
CENTER = (ROOT / 'frontend/src/components/learning/LlmLearningCenter.tsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/components/learning/learning-case-list-cleanup.css').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks = {
    'frontend version 5.443': "AGENTSTUDIO_FRONTEND_VERSION='5.443'" in APP,
    'backend version 5.443': 'version="5.443"' in MAIN,
    'health version 5.443': '"version": "5.443"' in ROUTES,
    'codex version 5.443': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.443"' in CODEX,
    'load state exists': 'LearningLoadState' in CENTER and 'setLoadState' in CENTER,
    'parallel summary request': "api<any>('/learning/summary')" in CENTER,
    'parallel case request': '/learning/misjudgments?limit=1000' in CENTER,
    'parallel dataset request': "api<any>('/learning/datasets')" in CENTER,
    'actual completion progress': 'Backend 응답 ${completed}/${total}' in CENTER,
    'elapsed heartbeat timer': 'elapsedSeconds' in CENTER and 'window.setInterval' in CENTER,
    'long wait alive message': '응답 대기 중 (화면은 동작 중입니다.)' in CENTER,
    'part status badges': "loadPartLabel" in CENTER and "className={loadState.parts[part]}" in CENTER,
    'load failure visible': '학습 데이터 로드 실패' in CENTER and 'llm-data-load-error' in CENTER,
    'tab refresh progress': '오판 수집 탭 로드' in CENTER and '수집 문제 / Dataset 탭 로드' in CENTER and 'PC별 학습 적용 관리 탭 로드' in CENTER,
    'provider refresh progress': '모델 제공자 필터 적용' in CENTER,
    'false empty state guarded': 'datasets.length===0&&!loadState.active' in CENTER,
    'progress css': '.llm-data-load-progress' in CSS and '.llm-data-load-progress-track' in CSS,
    'running animation': '@keyframes llm-learning-load-pulse' in CSS,
    'reduced motion': '@media (prefers-reduced-motion: reduce)' in CSS,
    'build marker': 'LearningCenterLoadProgressHeartbeat' in ROUTES,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL') + ' - ' + name)
print(f'RESULT {len(checks)-len(failed)}/{len(checks)} PASS')
if failed:
    raise SystemExit(1)
