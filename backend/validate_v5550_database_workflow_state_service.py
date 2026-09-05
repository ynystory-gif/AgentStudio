from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
db=(ROOT/'frontend/src/features/database/hooks/useDatabaseController.ts').read_text(encoding='utf-8')
wf=(ROOT/'frontend/src/features/workflow/hooks/useWorkflowController.ts').read_text(encoding='utf-8')
dbs=(ROOT/'frontend/src/features/database/services/databaseService.ts').read_text(encoding='utf-8')
wfs=(ROOT/'frontend/src/features/workflow/services/workflowService.ts').read_text(encoding='utf-8')
assert 'useDatabaseController()' in app
assert 'useWorkflowController()' in app
assert 'previewWorkflow({' in app
assert 'loadOwnedSqlObjects' in app and 'connectOwnedSql' in app and 'runOwnedSql' in app
for token in ['sqlProfile','sqlConnectionStatus','sqlQueryResult','loadSqlObjects','connectSql','disconnectSql','runSql','rebuildDatabasePreview']: assert token in db
for token in ['workflowDefinition','targetWorkflowPreview','workflowProgress','useEffect','loadWorkflowDefinition','inspectWorkflowProviderStatus']: assert token in wf
for token in ['/sql/objects','/sql/connect','/sql/disconnect','/sql/execute','/database-design/preview']: assert token in dbs
for token in ['/workflow/definition','/llm/runtime-status','/workflow/preview']: assert token in wfs
assert "AGENTSTUDIO_FRONTEND_VERSION='5.550'" in app
assert len(app.splitlines()) < 22052
print('v5.550 Database + Workflow State/Service extraction: PASS')
print('App.tsx:',len(app.splitlines()))
print('Database controller:',len(db.splitlines()))
print('Workflow controller:',len(wf.splitlines()))
