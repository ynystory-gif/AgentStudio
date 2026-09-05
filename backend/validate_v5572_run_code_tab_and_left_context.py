from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
tabs=(ROOT/'frontend/src/features/workspace/workspace.types.ts').read_text(encoding='utf-8')

run=tabs.index("{id:'RUN',label:'실행 결과'")
code=tabs.index("{id:'CODE',label:'코드 편집'")
assert run < code
assert "['DESIGN','WORKFLOW','RUN'].includes(workspaceTab)?<>" in app
assert "workspaceTab==='RUN'&&<div className=\"design-left-context-note\">현재 실행 결과는 이 Agent 설계 요구사항과 개발 계획을 기준으로 확인합니다.</div>" in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.572'" in app
print('v5.572 RUN/CODE tab order + RUN design left context: PASS')
