from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
css=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
assert "['DESIGN','WORKFLOW'].includes(workspaceTab)?<>" in app
assert '현재 Workflow는 이 Agent 설계 요구사항을 기준으로 생성됩니다.' in app
assert '.design-left-context-note' in css
assert "AGENTSTUDIO_FRONTEND_VERSION='5.558'" in app
print('v5.558 Workflow design-left panel reuse: PASS')
