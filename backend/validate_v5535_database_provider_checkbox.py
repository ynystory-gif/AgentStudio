from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
db=(ROOT/'frontend/src/features/database/AgentDatabaseSetup.tsx').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
for token in [
    "if(Object.prototype.hasOwnProperty.call(row,'enabled')) return Boolean(row.enabled)",
    "nextPatch.use_in_agent=Boolean(nextPatch.enabled)",
    "enabled:postgresqlEnabled,use_in_agent:postgresqlEnabled",
    "enabled:firestoreEnabled,use_in_agent:firestoreEnabled",
    "enabled:redisEnabled,use_in_agent:redisEnabled",
    "enabled:false,use_in_agent:false,auto_provision:false",
]:
    assert token in db, token
assert "AGENTSTUDIO_FRONTEND_VERSION='5.535'" in app
assert 'version="5.535"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert '"version": "5.535"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
print('v5.535 database provider checkbox: PASS')
