from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
service=(ROOT/'backend/app/services/generated_database_provision_service.py').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')

assert 'document("__probe__")' not in service
assert 'probe_document = "connection_probe"' in service
assert 'snapshot = client.collection(probe_collection).document(probe_document).get()' in service
assert "read-only probe=" in service
assert "AGENTSTUDIO_FRONTEND_VERSION='5.540'" in app
assert 'version="5.540"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert '"version": "5.540"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
print('v5.540 Firestore reserved probe ID fix: PASS')
