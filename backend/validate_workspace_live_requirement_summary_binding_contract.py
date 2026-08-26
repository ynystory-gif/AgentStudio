from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

checks = {
    "frontend version 5.343": "AGENTSTUDIO_FRONTEND_VERSION='5.356'" in APP,
    "workspace computes live summary": "const leftSummary=getBuilderConversationSummary()" in APP,
    "workspace live step source": "const designBuilderSteps=[" in APP and "['01','목적',leftSummary.purpose]" in APP,
    "feature live step": "['02','기능',leftSummary.features]" in APP,
    "mcp live step": "['03','MCP / Tool',leftSummary.mcpTools]" in APP,
    "database live step": "['04','DB 설계',leftSummary.database]" in APP,
    "runtime live step": "['05','실행 환경',leftSummary.runtime]" in APP,
    "confirmation live step": "['06','확인',leftSummary.confirmation]" in APP,
    "workspace no old static purpose": "['01','목적','어떤 Agent를 만들지']" not in APP,
    "workspace detailed summary": 'className="builder-live-summary"' in APP and '대화 요구사항 요약' in APP,
    "db cache vector split": "database:databaseValues" in APP and "mcpTools:mcpToolValues" in APP,
}

failed = []
for name, ok in checks.items():
    print(f"[v5.343-live-left-summary] {name}: {'OK' if ok else 'FAIL'}")
    if not ok:
        failed.append(name)
if failed:
    raise SystemExit("FAILED: " + ", ".join(failed))
print("[v5.343-live-left-summary] PASS")
