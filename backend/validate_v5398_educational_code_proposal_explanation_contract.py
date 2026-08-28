from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')

checks={
    'version': "AGENTSTUDIO_FRONTEND_VERSION='5.398'" in APP and 'version="5.398"' in MAIN,
    'backend explanation helper': '_build_edit_explanation' in ROUTES and 'code_edit_explanation' in ROUTES,
    'structured fields': 'value_reasons' in ROUTES and 'code_walkthrough' in ROUTES and 'proposal_explanation' in ROUTES,
    'non blocking fallback': '_fallback_edit_explanation' in ROUTES and 'source": "fallback"' in ROUTES,
    'frontend mapping': 'proposalExplanation=result?.proposal_explanation||null' in APP,
    'why values section': '왜 이 값/표현을 사용하나요?' in APP,
    'walkthrough section': '>코드 설명<' in APP,
    'notes section': '>확인할 점<' in APP,
    'proposal code label': '>제안 코드<' in APP,
    'learning styles': '.code-proposal-learning' in CSS and '.code-proposal-reason-item' in CSS,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL: '+', '.join(failed))
print(f'v5.398 educational code proposal explanation contract PASS {len(checks)}/{len(checks)}')
