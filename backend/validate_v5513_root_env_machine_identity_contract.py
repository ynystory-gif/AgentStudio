from pathlib import Path
root=Path(__file__).resolve().parents[1]
machine=(root/'backend/app/core/machine_identity.py').read_text(encoding='utf-8')
auth=(root/'backend/app/services/auth_service.py').read_text(encoding='utf-8')
main=(root/'backend/app/main.py').read_text(encoding='utf-8')
assert 'ENV_PATH = PROJECT_ROOT / ".env"' in machine
assert 'ENV_PATH = BACKEND_ROOT / ".env"' not in machine
assert 'def current_pc_name()' in machine
assert '_reconcile_current_pc_alias' in auth
assert 'physical not in normalized' in auth
assert 'version="5.513"' in main
print('[v5.513] root .env machine identity + safe PC alias migration: PASS')
