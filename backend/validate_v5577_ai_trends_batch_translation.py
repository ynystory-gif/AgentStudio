from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
translation = (ROOT / 'backend/app/services/ai_trends/korean_translation.py').read_text(encoding='utf-8')
cache = (ROOT / 'backend/app/services/ai_trends/daily_cache.py').read_text(encoding='utf-8')
ui = (ROOT / 'frontend/src/features/ai-trends/components/AITrendsDashboard.tsx').read_text(encoding='utf-8')
types = (ROOT / 'frontend/src/features/ai-trends/types/aiTrends.ts').read_text(encoding='utf-8')

checks = {
    'primary models/papers/news batch': 'PRIMARY_CATEGORIES = ("models", "papers", "news")' in translation,
    'secondary spaces/datasets batch': 'SECONDARY_CATEGORIES = ("spaces", "datasets")' in translation,
    'batch all-at-once prompt': '이 배치 전체를 한 번에 처리하세요' in translation,
    'OpenAI/Codex preferred': 'OpenAI/Codex are preferred' in translation and '"openai"' in translation and '"codex"' in translation,
    'Codex app-server completion': 'codex_app_server_manager.run_text_completion' in translation,
    'OpenAI chat path': 'get_chat_model(provider)' in translation,
    'model hover translation instruction': '마우스 오버 설명용' in translation,
    'paper title/body translation instruction': 'papers의 title_ko와 summary_ko' in translation,
    'news title/body translation instruction': 'news의 title_ko와 summary_ko' in translation,
    'two-call batch metadata': 'batch_requests' in translation and 'providers' in translation,
    'cache invalidated': 'CACHE_VERSION = 4' in cache,
    'frontend translation metadata': 'batch_requests?:number' in types and 'providers?:string[]' in types,
    'frontend batch footer': '한국어 배치 번역' in ui,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
if failed:
    raise SystemExit('v5.577 validation failed: ' + ', '.join(failed))
print('validate_v5577_ai_trends_batch_translation: PASS')
