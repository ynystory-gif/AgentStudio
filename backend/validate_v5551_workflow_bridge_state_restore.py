from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
db=(ROOT/'frontend/src/features/database/hooks/useDatabaseController.ts').read_text(encoding='utf-8')

required=[
    "const [developmentProgress,setDevelopmentProgress]=useState<LegacyRecord>",
    "const [developmentFinalStatus,setDevelopmentFinalStatus]=useState<LegacyValue|null>",
    "const builderMessagesEndRef=useRef<LegacyValue|null>",
]
for token in required:
    assert token in app, token

assert "setSqlConnectionStatus((prev:LegacyValue)=>" in db
assert "AGENTSTUDIO_FRONTEND_VERSION='5.551'" in app
print("v5.551 workflow bridge state restore: PASS")
