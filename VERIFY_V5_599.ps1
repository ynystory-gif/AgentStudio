$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }

Write-Host '[1/7] v5.599 Account/Project settings + history validation'
& $Python (Join-Path $Root 'backend\validate_v5599_account_project_settings.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[2/7] Backend syntax'
& $Python -m py_compile `
  (Join-Path $Root 'backend\app\models\account_setting_entities.py') `
  (Join-Path $Root 'backend\app\services\account_setting_service.py') `
  (Join-Path $Root 'backend\app\services\sql_workspace_service.py') `
  (Join-Path $Root 'backend\app\api\account_settings_routes.py') `
  (Join-Path $Root 'backend\app\api\rag_routes.py') `
  (Join-Path $Root 'backend\app\api\routes.py') `
  (Join-Path $Root 'backend\app\rag\operation_service.py') `
  (Join-Path $Root 'backend\app\rag\security_service.py') `
  (Join-Path $Root 'backend\app\services\rag_studio_service.py') `
  (Join-Path $Root 'backend\app\core\database.py') `
  (Join-Path $Root 'backend\app\main.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[3/7] Existing Frontend contracts'
Push-Location (Join-Path $Root 'frontend')
try {
  node validate_frontend_contracts.cjs
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }

Write-Host '[4/7] New table-specific PK guard'
$Models = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'backend\app\models\account_setting_entities.py')
if ($Models -match '(?m)^\s*id\s*:') { throw 'v5.599 신규 Account/Project 설정 테이블에 bare id 컬럼이 있습니다.' }
foreach ($Pk in @('account_database_profiles_id','account_setting_profiles_id','account_project_settings_id','project_setting_histories_id')) {
  if ($Models -notmatch [regex]::Escape($Pk)) { throw "필수 PK 누락: $Pk" }
}

Write-Host '[5/7] Secret + History UI regression guard'
$Service = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'backend\app\services\account_setting_service.py')
if ($Service -notmatch "'_password_dpapi'") { throw 'DPAPI secret scrubbing guard missing' }
$HistoryUi = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'frontend\src\features\history\ProjectHistoryPanel.tsx')
if ($HistoryUi -notmatch '변경 전' -or $HistoryUi -notmatch '변경 후') { throw 'History detail Diff UI missing' }

Write-Host '[6/7] Full Frontend build when dependencies exist'
$Frontend = Join-Path $Root 'frontend'
if (Test-Path (Join-Path $Frontend 'node_modules')) {
  Push-Location $Frontend
  try {
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  } finally { Pop-Location }
} else {
  Write-Host '[SKIP] frontend/node_modules 없음 - SYSTEM_ADMIN 실행 환경에서 npm run build가 수행됩니다.' -ForegroundColor Yellow
}

Write-Host '[7/7] Version files'
if (-not (Test-Path (Join-Path $Root 'README_V5_599_AccountProjectSettingsHistory.md'))) { throw 'v5.599 README missing' }
Write-Host '[PASS] THEANOVA AgentStudio v5.599 verification complete.'
