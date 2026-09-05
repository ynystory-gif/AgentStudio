from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
payload=json.loads((ROOT/'backend/app/data/coding_style/rules.json').read_text(encoding='utf-8'))
selector=(ROOT/'backend/app/services/coding_rule_selector.py').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
assert payload.get('version') in {'5.527','5.528'}
rules=payload.get('rules',[])
ids={r.get('id') for r in rules}
for rid in [f'CS-{n}' for n in range(275,297)]:
    assert rid in ids, rid
assert len(ids)==len(rules)
assert (ROOT/'backend/app/data/coding_style/sources/structured_chat_response_dynamic_renderer_guide.md').exists()
for token in ['structured_response','response_planner','renderer','registry','presentation','source','action','history','versioning']:
    assert token in selector, token
for literal in [
    "'structured response':'Agent 결과를 의미가 보존된 JSON 구조로 반환'",
    "'response planner':'질문과 Agent 목적에 맞는 응답 데이터 구조와 표시 방식을 결정'",
    "'renderer registry':'List·Table·Card·Chart 등 등록된 Renderer를 공통 관리'",
    "'schema validation':'Structured Response가 정의된 응답 계약을 만족하는지 검증'",
]:
    assert literal in app, literal
assert any(v in app for v in ("AGENTSTUDIO_FRONTEND_VERSION='5.527'", "AGENTSTUDIO_FRONTEND_VERSION='5.528'"))
assert any(f'version="{v}"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8') for v in ('5.527','5.528'))
assert any(f'"version": "{v}"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8') for v in ('5.527','5.528'))
print(f"v5.527 Structured Response contract: PASS ({len(rules)} rules)")
