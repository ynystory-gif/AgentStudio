from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
routes=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
memo=(ROOT/'frontend/src/features/project/components/ProjectMemoPanel.tsx').read_text(encoding='utf-8')
assert 'media_stt_summary.log' in routes
assert 'local_safe_summary' in routes
assert '"fallback": True' in routes
assert '"log_path": str(log_path)' in routes
assert 'provider_errors' in routes
assert memo.index('✦ 요약정리') < memo.index('💾 요약 파일 저장')
assert 'liveSummaryErrorLogPath' in memo
assert 'parseSummaryErrorDetail' in memo
print('v5.560 transcript summary fallback + log path: PASS')
