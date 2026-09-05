from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
assert "const isAgentDesignInteraction=(event: LegacyValue)=>" in app
assert "agentDesignAutoSaveTabRef.current!=='DESIGN'" in app
assert "'.unified-agent-design'" in app
assert "'.design-left-panel'" in app
assert "'.design-info-panel'" in app
assert "const onPointer=()=>schedule()" not in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.561'" in app
print('v5.561 Agent Design autosave scope: PASS')
