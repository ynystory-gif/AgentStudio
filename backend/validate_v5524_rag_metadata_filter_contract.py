from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
payload=json.loads((ROOT/'backend/app/data/coding_style/rules.json').read_text(encoding='utf-8'))
selector=(ROOT/'backend/app/services/coding_rule_selector.py').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')

assert payload.get('version') in {'5.524','5.525'}
rules=payload.get('rules', [])
ids={r.get('id') for r in rules}
for rid in [f'CS-{n}' for n in range(229,243)]:
    assert rid in ids, rid
assert len(ids) == len(rules)
assert (ROOT/'backend/app/data/coding_style/sources/rag_metadata_filter_guide.md').exists()

for token in [
    'metadata','retrieval','security','permission_filter','vectorstore',
    'fallback','recommendation','validation'
]:
    assert token in selector, token

assert any(v in app for v in ("AGENTSTUDIO_FRONTEND_VERSION='5.524'", "AGENTSTUDIO_FRONTEND_VERSION='5.525'"))
assert any(f'version="{v}"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8') for v in ('5.524','5.525'))
assert any(f'"version": "{v}"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8') for v in ('5.524','5.525'))
print(f"v5.524 RAG Metadata Filter contract: PASS ({len(rules)} rules)")
