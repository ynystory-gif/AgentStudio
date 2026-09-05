from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
routes=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')

assert 'class PresentationOpenRequest(BaseModel):' in routes
assert '@router.post("/presentation/open")' in routes
assert 'target.suffix.casefold() not in {".ppt", ".pptx"}' in routes
assert 'os.startfile(str(target))' in routes
assert '["open", str(target)]' in routes
assert '["xdg-open", str(target)]' in routes

assert "api('/presentation/open'" in app
assert "body:JSON.stringify({path:saved.path})" in app
assert 'PPT 저장은 완료되었습니다.' in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.571'" in app
print('v5.571 PPT save + auto-open: PASS')
