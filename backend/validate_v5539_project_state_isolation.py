from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
routes=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')

for token in [
    'normalizeProjectIdentityPath',
    'sameProjectIdentity',
    '프로젝트 Checkpoint 경로 불일치 차단',
    'Local Draft 경로 불일치 차단',
    '다른 프로젝트의 설계 Snapshot 복원 차단',
    'setDesignProjectId(null)',
    'authoritativeSaveRoot',
    'project_root:authoritativeSaveRoot',
    'setSelectedProjectId(null)',
]:
    assert token in app, token

for token in [
    '다른 프로젝트의 Agent 설계 기록을 덮어쓰는 저장을 차단했습니다.',
    'status_code=409',
    '_project_identity',
]:
    assert token in routes, token

assert "AGENTSTUDIO_FRONTEND_VERSION='5.539'" in app
assert 'version="5.539"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert '"version": "5.539"' in routes
print('v5.539 project state isolation: PASS')
