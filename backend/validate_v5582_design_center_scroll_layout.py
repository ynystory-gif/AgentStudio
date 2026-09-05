from pathlib import Path
root=Path(__file__).resolve().parents[1]
app=(root/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
css=(root/'frontend/src/styles.css').read_text(encoding='utf-8')
main=(root/'backend/app/main.py').read_text(encoding='utf-8')
assert "AGENTSTUDIO_FRONTEND_VERSION='5.582'" in app
assert "studio-open':'interview-open" in app
assert '.unified-agent-design.interview-open' in css
assert 'grid-template-rows:auto minmax(0,1fr)!important' in css
assert '.unified-agent-design.studio-open' in css
assert 'overflow-y:auto!important' in css
assert '.unified-agent-design.studio-open .pts-input-view' in css
assert 'overflow:visible!important' in css
assert 'version="5.582"' in main
print('v5.582 design center scroll/tab layout validation: PASS')
