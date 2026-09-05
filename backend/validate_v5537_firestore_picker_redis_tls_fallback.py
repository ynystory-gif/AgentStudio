from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
db=(ROOT/'frontend/src/features/database/AgentDatabaseSetup.tsx').read_text(encoding='utf-8')
backend=(ROOT/'backend/app/services/generated_database_provision_service.py').read_text(encoding='utf-8')
css=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
for token in ['onPickFirestoreCredential','파일 찾기','pickAgentFirestoreCredential',"db_type:'firestore'",'service_account_json','agentFirestoreCredentialBusy']:
    assert token in app+db, token
for token in ['tls_override','loopback','fallback_applied','"suggested_config": {"tls": False}','비TLS로 자동 재시도']:
    assert token in backend, token
assert "redisRow?.fallback_applied" in app
assert '.agent-db-path-picker' in css
assert '.agent-db-inline-warning' in css
assert "AGENTSTUDIO_FRONTEND_VERSION='5.537'" in app
print('v5.537 Firestore picker / Redis TLS fallback: PASS')
