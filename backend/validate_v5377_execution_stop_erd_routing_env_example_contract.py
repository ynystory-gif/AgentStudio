from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
ERD = (ROOT / 'frontend' / 'src' / 'components' / 'database' / 'DatabaseDiagramViewer.tsx').read_text(encoding='utf-8')
WORKFLOW = (ROOT / 'backend' / 'app' / 'services' / 'agent_workflow.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.377'" in APP,
    'backend health version': '"version": "5.377"' in ROUTES,
    'active workflow id cleared in development finally': "setActiveWorkflowJobId('')\n      setAgentBuildBusy(false)" in APP,
    'erd relation route margin': 'RELATION_ROUTE_MARGIN = 118' in ERD,
    'erd distant relation top bottom corridor': 'columnDistance === 1' in ERD and 'const useTop = relationshipIndex % 2 === 0' in ERD,
    'erd lane index passed': 'relationshipPath(relationship, tableMap, index, diagram.relationships.length, layout.height)' in ERD,
    'erd white halo': 'stroke="#ffffff" strokeWidth="5"' in ERD,
    'env example requirements helper': 'function Ensure-EnvExampleRequirements' in WORKFLOW,
    'system admin no env create-copy': 'Copy-Item $EnvExample $EnvFile -Force' not in WORKFLOW and 'New-Item -ItemType File -Path $EnvFile' not in WORKFLOW,
    'system admin opens env example': 'Start-Process notepad.exe -ArgumentList @($EnvExample)' in WORKFLOW,
    'system admin never opens env': 'Start-Process notepad.exe -ArgumentList @($EnvFile)' not in WORKFLOW,
    'database url example': 'postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/YOUR_DATABASE' in WORKFLOW,
    'redis url example': 'redis://127.0.0.1:6379/0' in WORKFLOW,
    'cmd setup message references env example': 'Review the opened .env.example guide. AgentStudio does not create or modify .env.' in WORKFLOW,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.377 contract: ' + ', '.join(failed))
print('PASS v5.377 Execution Stop Lifecycle + ERD Obstacle Routing + Env Example Only Setup contract')
