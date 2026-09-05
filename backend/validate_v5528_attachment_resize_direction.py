from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
assert "state.startHeight-(event.clientY-state.startY)" in app
assert "(event.key==='ArrowUp'?step:-step)" in app
assert "위로 드래그하면 높이가 커지고, 아래로 드래그하면 높이가 작아집니다." in app
assert "위로 드래그하면 높이 증가 · 아래로 드래그하면 감소" in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.529'" in app
assert 'version="5.529"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert '"version": "5.529"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
print("v5.529 attachment resize direction: PASS")
