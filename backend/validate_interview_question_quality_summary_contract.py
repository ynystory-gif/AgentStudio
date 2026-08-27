from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REQ=(ROOT/'backend/app/services/requirements_agent.py').read_text(encoding='utf-8')
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')

checks={
    'frontend version 5.342': "AGENTSTUDIO_FRONTEND_VERSION='5.369'" in APP,
    'question quality gate function': 'def apply_question_quality_gate' in REQ,
    'technical delegation blocked': 'technical_design_delegation' in REQ and 'TECHNICAL_DELEGATION_PATTERNS' in REQ,
    'multiple questions blocked': 'multiple_questions' in REQ and '_question_count' in REQ,
    'answered topic duplicate blocked': 'duplicate_answered_topic' in REQ and '_question_reasks_known_topic' in REQ,
    'single user-decision fallback': '_next_user_decision_question' in REQ and '사용자 화면은 어떤 형태' in REQ,
    'quality gate is applied': 'content, _quality_gate = apply_question_quality_gate' in REQ,
    'live builder summary helper': 'getBuilderConversationSummary' in APP,
    'purpose live content': "['01','목적',leftSummary.purpose]" in APP,
    'feature live content': "['02','기능',leftSummary.features]" in APP,
    'mcp live content': "['03','MCP / Tool',leftSummary.mcpTools]" in APP,
    'database live content': "['04','DB 설계',leftSummary.database]" in APP,
    'live requirement summary UI': '대화 요구사항 요약' in APP and 'builder-live-summary-list' in APP,
    'redis vector visible': "addIntegration('Redis','redis')" in APP and "addIntegration('pgvector'" in APP,
    'summary css': '.builder-live-summary{' in CSS,
}
failed=[]
for name,ok in checks.items():
    print(f"[v5.342-question-summary-contract] {name}: {'OK' if ok else 'FAIL'}")
    if not ok: failed.append(name)
if failed:
    raise SystemExit('FAIL: '+', '.join(failed))
print('[v5.342-question-summary-contract] PASS')
