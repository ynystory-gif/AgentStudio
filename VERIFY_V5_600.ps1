$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }

Write-Host '[1/7] v5.600 Account/Project settings + Project History strict TypeScript validation'
& $Python (Join-Path $Root 'backend\validate_v5600_project_history_strict_type_safety.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[2/7] Backend syntax'
& $Python -m py_compile `
  (Join-Path $Root 'backend\app\models\account_setting_entities.py') `
  (Join-Path $Root 'backend\app\services\account_setting_service.py') `
  (Join-Path $Root 'backend\app\services\sql_workspace_service.py') `
  (Join-Path $Root 'backend\app\api\account_settings_routes.py') `
  (Join-Path $Root 'backend\app\api\rag_routes.py') `
  (Join-Path $Root 'backend\app\api\routes.py') `
  (Join-Path $Root 'backend\app\core\database.py') `
  (Join-Path $Root 'backend\app\main.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[3/7] Existing Frontend contracts'
Push-Location (Join-Path $Root 'frontend')
try {
  node validate_frontend_contracts.cjs
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }

Write-Host '[4/7] Project History strict-array regression guard'
$HistoryUi = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'frontend\src\features\history\ProjectHistoryPanel.tsx')
if ($HistoryUi -match 'next\[0\]\.id') { throw 'ProjectHistoryPanel에 unsafe next[0].id 접근이 다시 들어왔습니다.' }
if ($HistoryUi -notmatch 'const firstItem=next\[0\]') { throw 'ProjectHistoryPanel strict-safe firstItem guard missing' }
if ($HistoryUi -notmatch 'if\(firstItem&&!selectedId\)setSelectedId\(firstItem\.id\)') { throw 'ProjectHistoryPanel firstItem existence check missing' }

Write-Host '[5/7] New table-specific PK guard'
$Models = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'backend\app\models\account_setting_entities.py')
if ($Models -match '(?m)^\s*id\s*:') { throw 'v5.600 신규 Account/Project 설정 테이블에 bare id 컬럼이 있습니다.' }
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

Write-Host '[7/7] Version files'
if (-not (Test-Path (Join-Path $Root 'README_V5_600_ProjectHistoryStrictTypeSafetyBuildFix.md'))) { throw 'v5.600 README missing' }
Write-Host '[PASS] THEANOVA AgentStudio v5.600 verification complete.'
