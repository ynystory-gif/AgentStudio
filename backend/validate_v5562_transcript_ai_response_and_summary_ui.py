from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
router=(ROOT/'backend/app/services/model_router.py').read_text(encoding='utf-8')
memo=(ROOT/'frontend/src/features/project/components/ProjectMemoPanel.tsx').read_text(encoding='utf-8')
assert 'def _response_text(result: Any) -> str:' in router
assert 'LLM이 2회 연속 빈 응답을 반환했습니다.' in router
assert router.count('content = _response_text(result)') >= 4
assert 'project-live-summary-provider-notice' in memo
assert 'project-live-summary-bottom' in memo
assert '로컬 요약 생성 완료' in memo
assert memo.index('project-live-summary-provider-notice') < memo.index('project-live-summary-bottom')
print('v5.562 transcript AI response normalization + summary UI separation: PASS')
