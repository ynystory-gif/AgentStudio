$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }

Write-Host '[1/5] v5.602 History SQL / DB binding / Qwen dynamic contracts'
& $Python (Join-Path $Root 'backend\validate_v5602_history_sql_qwen_dynamic.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[2/5] Backend syntax'
& $Python -m py_compile `
  (Join-Path $Root 'backend\app\core\database.py') `
  (Join-Path $Root 'backend\app\services\account_setting_service.py') `
  (Join-Path $Root 'backend\app\api\account_settings_routes.py') `
  (Join-Path $Root 'backend\app\services\learning_sql_export_service.py') `
  (Join-Path $Root 'backend\app\services\ollama_model_manager_service.py') `
  (Join-Path $Root 'backend\app\services\active_ollama_model_service.py') `
  (Join-Path $Root 'backend\app\services\ai_trends\huggingface_provider.py') `
  (Join-Path $Root 'backend\app\services\ai_trends\daily_cache.py') `
  (Join-Path $Root 'backend\app\services\ai_trends\service.py') `
  (Join-Path $Root 'backend\app\api\learning_routes.py') `
  (Join-Path $Root 'backend\app\api\routes.py') `
  (Join-Path $Root 'backend\app\main.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[3/5] Existing Frontend contracts'
Push-Location (Join-Path $Root 'frontend')
try {
  node validate_frontend_contracts.cjs
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }

Write-Host '[4/5] AI Trends exact-ranking regression guard'
& $Python (Join-Path $Root 'backend\validate_v5576_ai_trends_exact_ranking.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[5/5] Version files'
if (-not (Test-Path (Join-Path $Root 'README_V5_602_HistoryListSqlSchemaQwenDynamic.md'))) { throw 'v5.602 README missing' }
if (Test-Path (Join-Path $Root 'README_V5_601_HistorySqlWorkflowPromptToolSync.md')) { throw 'old v5.601 release README must not remain in v5.602 package root' }
Write-Host '[PASS] THEANOVA AgentStudio v5.602 verification complete.'
