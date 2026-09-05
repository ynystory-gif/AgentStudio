$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }

Write-Host '[1/7] v5.601 feature contracts'
& $Python (Join-Path $Root 'backend\validate_v5601_history_sql_workflow_prompt_tool_sync.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[2/7] Backend syntax'
& $Python -m py_compile `
  (Join-Path $Root 'backend\app\services\account_setting_service.py') `
  (Join-Path $Root 'backend\app\api\account_settings_routes.py') `
  (Join-Path $Root 'backend\app\services\project_adaptive_report.py') `
  (Join-Path $Root 'backend\app\api\routes.py') `
  (Join-Path $Root 'backend\app\main.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[3/7] Existing Frontend contracts'
Push-Location (Join-Path $Root 'frontend')
try {
  node validate_frontend_contracts.cjs
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }

Write-Host '[4/7] v5.601 Frontend regression guards'
$App = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'frontend\src\app\App.tsx')
$History = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'frontend\src\features\history\ProjectHistoryPanel.tsx')
$Studio = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'frontend\src\features\prompt-tool-studio\components\PromptToolStudio.tsx')
if ($History -match 'next\[0\]\.id') { throw 'ProjectHistoryPanel unsafe next[0].id regression' }
if ($History -notmatch 'SQL 임시 파일') { throw 'History SQL detail button missing' }
if ($App -notmatch 'workspace-workflow-save-button') { throw 'Workflow save button missing' }
if ($App -notmatch "setting_group:'WORKFLOW'") { throw 'Workflow DB save missing' }
if ($Studio -notmatch 'pts-sync-badge') { throw 'Prompt/Tool sync badge missing' }

Write-Host '[5/7] Existing Account/Project table-specific PK guard'
$Models = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'backend\app\models\account_setting_entities.py')
if ($Models -match '(?m)^\s*id\s*:') { throw 'Account/Project setting tables contain bare id column.' }
foreach ($Pk in @('account_database_profiles_id','account_setting_profiles_id','account_project_settings_id','project_setting_histories_id')) {
  if ($Models -notmatch [regex]::Escape($Pk)) { throw "필수 PK 누락: $Pk" }
}

Write-Host '[6/7] Full Frontend build when complete dependencies exist'
$Frontend = Join-Path $Root 'frontend'
$NodeModules = Join-Path $Frontend 'node_modules'
$ViteTypes = Join-Path $NodeModules 'vite\client.d.ts'
$NodeTypes = Join-Path $NodeModules '@types\node\index.d.ts'
if ((Test-Path $NodeModules) -and (Test-Path $ViteTypes) -and (Test-Path $NodeTypes)) {
  Push-Location $Frontend
  try {
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  } finally { Pop-Location }
} else {
  Write-Host '[SKIP] 완전한 Frontend node_modules 없음 - SYSTEM_ADMIN 실행 환경에서 npm run build가 수행됩니다.' -ForegroundColor Yellow
}

Write-Host '[7/7] Distribution version files'
if (-not (Test-Path (Join-Path $Root 'README_V5_601_HistorySqlWorkflowPromptToolSync.md'))) { throw 'v5.601 README missing' }
if (Get-ChildItem -Path $Root -Filter 'README_V5_*.md' | Where-Object { $_.Name -ne 'README_V5_601_HistorySqlWorkflowPromptToolSync.md' }) { throw '배포 루트에 이전 버전 README가 포함되어 있습니다.' }
if (Get-ChildItem -Path $Root -Filter 'VERIFY_V5_*.ps1' | Where-Object { $_.Name -ne 'VERIFY_V5_601.ps1' }) { throw '배포 루트에 이전 버전 VERIFY가 포함되어 있습니다.' }
Write-Host '[PASS] THEANOVA AgentStudio v5.601 verification complete.'
