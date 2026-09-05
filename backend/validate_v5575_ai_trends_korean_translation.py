from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    'translation_service': ROOT/'backend/app/services/ai_trends/korean_translation.py',
    'trend_service': ROOT/'backend/app/services/ai_trends/service.py',
    'cache': ROOT/'backend/app/services/ai_trends/daily_cache.py',
    'provider': ROOT/'backend/app/services/ai_trends/huggingface_provider.py',
    'dashboard': ROOT/'frontend/src/features/ai-trends/components/AITrendsDashboard.tsx',
    'types': ROOT/'frontend/src/features/ai-trends/types/aiTrends.ts',
}
for name, path in checks.items():
    assert path.exists(), f'missing {name}: {path}'

translation = checks['translation_service'].read_text(encoding='utf-8')
service = checks['trend_service'].read_text(encoding='utf-8')
cache = checks['cache'].read_text(encoding='utf-8')
provider = checks['provider'].read_text(encoding='utf-8')
dashboard = checks['dashboard'].read_text(encoding='utf-8')

assert 'translate_categories_to_korean' in translation
assert 'get_chat_model()' in translation
assert 'paper/news' in translation
assert 'owner/repository' in translation
assert 'result["translation"] = await translate_categories_to_korean' in service
assert 'write_daily(result)' in service
assert 'CACHE_VERSION = 2' in cache
assert 'summary_original' in provider
assert 'THEANOVA-AgentStudio/5.575' in provider
assert '한국어 자동 번역' in dashboard
assert '인기 모델' in dashboard and '최신 논문' in dashboard and 'AI 뉴스' in dashboard
print('v5.575 AI trends Korean translation validation: PASS')
