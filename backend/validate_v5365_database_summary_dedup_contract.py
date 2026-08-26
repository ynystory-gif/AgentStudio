from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')

required = {
    'version': "const AGENTSTUDIO_FRONTEND_VERSION='5.368'",
    'normalizer': 'const normalizeDatabaseValues=(values=[])=>{',
    'split composite database summary': ".split(/\\s*[·,+/]\\s*/g)",
    'postgres canonical': "if(lower.includes('postgresql')) label='PostgreSQL'",
    'redis canonical': "else if(lower==='redis'||lower.includes('redis ')) label='Redis'",
    'pgvector canonical': "else if(lower.includes('pgvector')||lower==='vector db'||lower==='vector search') label='pgvector'",
    'database summary uses normalizer': 'const databaseValues=normalizeDatabaseValues([',
}

missing = [name for name, needle in required.items() if needle not in APP]
if missing:
    raise SystemExit('FAIL v5.368 database summary dedup contract: ' + ', '.join(missing))

# Regression guard: the old exact-array dedup implementation treats the composite
# string as a different value from each technology and therefore duplicates it.
old = "const databaseValues=uniqueValues([\n      byId.database?.value,"
if old in APP:
    raise SystemExit('FAIL v5.368: legacy composite DB summary dedup still active')

print('PASS v5.368 Database Summary Dedup contract')
