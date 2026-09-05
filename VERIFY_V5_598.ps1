$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }

Write-Host '[1/6] v5.598 RAG integration/UX validation'
& $Python (Join-Path $Root 'backend\validate_v5598_rag_studio_integration_ux.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[2/6] Backend syntax'
& $Python -m py_compile `
  (Join-Path $Root 'backend\app\api\routes.py') `
  (Join-Path $Root 'backend\app\api\rag_routes.py') `
  (Join-Path $Root 'backend\app\services\rag_studio_service.py') `
  (Join-Path $Root 'backend\app\main.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[3/6] Existing Frontend contracts'
Push-Location (Join-Path $Root 'frontend')
try {
  node validate_frontend_contracts.cjs
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }

Write-Host '[4/6] RAG API double-prefix regression guard'
$RagApi = Get-Content -Raw -Encoding UTF8 (Join-Path $Root 'frontend\src\features\rag\ragApi.ts')
if ($RagApi -match '/api/rag/') { throw 'RAG API path에 /api/rag가 남아 있습니다. runtime-config의 /api와 중복됩니다.' }

Write-Host '[5/6] Full Frontend build when dependencies exist'
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

Write-Host '[6/6] Version files'
if (-not (Test-Path (Join-Path $Root 'README_V5_598_RagStudioIntegrationUxFix.md'))) { throw 'v5.598 README missing' }
Write-Host '[PASS] THEANOVA AgentStudio v5.598 verification complete.'
