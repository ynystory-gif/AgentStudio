from pathlib import Path
import json, os, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))

from app.services.ai_trends import daily_cache

with tempfile.TemporaryDirectory() as td:
    old=os.environ.get("THEANOVA_AGENTSTUDIO_DATA_DIR")
    os.environ["THEANOVA_AGENTSTUDIO_DATA_DIR"]=td
    try:
        assert daily_cache.read_daily() is None
        sample={"collection_date":daily_cache.today_key(),"models":{"status":"OK","items":[]},"cache":{"hit":False}}
        daily_cache.write_daily(sample)
        loaded=daily_cache.read_daily()
        assert loaded and loaded["collection_date"]==daily_cache.today_key()
        path=daily_cache.cache_path()
        raw=json.loads(path.read_text(encoding="utf-8"))
        raw["collection_date"]="2000-01-01"
        path.write_text(json.dumps(raw),encoding="utf-8")
        assert daily_cache.read_daily() is None
    finally:
        if old is None: os.environ.pop("THEANOVA_AGENTSTUDIO_DATA_DIR",None)
        else: os.environ["THEANOVA_AGENTSTUDIO_DATA_DIR"]=old

routes=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
service=(ROOT/'backend/app/services/ai_trends/service.py').read_text(encoding='utf-8')
assert '@router.get("/ai-trends")' in routes
assert 'cached = read_daily()' in service
assert 'write_daily(result)' in service
assert "useAITrends(screen==='HOME')" in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.573'" in app
print('v5.573 AI Trends daily collection cache: PASS')
