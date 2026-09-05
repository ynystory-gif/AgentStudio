from pathlib import Path
root=Path(__file__).resolve().parents[1]
provider=(root/'backend/app/services/ai_trends/huggingface_provider.py').read_text(encoding='utf-8')
component=(root/'frontend/src/features/ai-trends/components/AITrendsDashboard.tsx').read_text(encoding='utf-8')
cache=(root/'backend/app/services/ai_trends/daily_cache.py').read_text(encoding='utf-8')
assert '"sort": "trendingScore"' in provider
assert '_trending_repos(client, "models", 5)' in provider
assert '_trending_repos(client, "spaces", 8)' in provider
assert '_model_datasets(client, dataset_query, 3)' in provider
assert 'qwen3.5' in provider
assert 'ai-trends-model-hover' in component
assert 'limit={5}' in component
assert 'SpacesCategory' in component
assert '사용중인 모델 데이터셋' in component
assert 'CACHE_VERSION = 4' in cache
print('v5.576 AI trends exact ranking validation: PASS')
