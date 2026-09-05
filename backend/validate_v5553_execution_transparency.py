from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
panel=(ROOT/'frontend/src/features/agent-development/components/AgentExecutionTransparencyPanel.tsx').read_text(encoding='utf-8')
css=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
assert 'AgentExecutionTransparencyPanel' in app
assert 'mode="DESIGN"' in app
assert 'mode="DEVELOPMENT"' in app
for token in ['지금 처리 중','현재까지 정리된 내용','요구사항 분석 내용 보기','실제 Backend 진행 이벤트']:
    assert token in panel, token
assert 'AI 내부 사고 과정을 임의로 만들어 표시하지 않습니다.' in panel
assert '.agent-execution-transparency' in css
assert '@keyframes agentExecutionPulse' in css
assert "AGENTSTUDIO_FRONTEND_VERSION='5.553'" in app
print('v5.553 execution transparency: PASS')
print('App.tsx:',len(app.splitlines()))
