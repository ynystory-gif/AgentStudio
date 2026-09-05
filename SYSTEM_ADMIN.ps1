param(
    [switch]$ElevatedChild
)

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"

# v5.220: AgentStudio와 그 아래에서 생성되는 PowerShell 터미널은
# 항상 관리자 권한을 사용합니다. 이미 관리자이면 그대로 진행하고,
# 아니면 UAC를 통해 SYSTEM_ADMIN.ps1 자체를 한 번 승격합니다.
$CurrentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$CurrentPrincipal = New-Object Security.Principal.WindowsPrincipal($CurrentIdentity)
$IsAdministrator = $CurrentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $IsAdministrator) {
    Write-Host "[진행] AgentStudio 관리자 권한을 요청합니다..." -ForegroundColor Yellow
    try {
        $ElevatedArgs = @(
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ('"{0}"' -f $PSCommandPath),
            "-ElevatedChild"
        )
        $ElevatedProcess = Start-Process `
            -FilePath "powershell.exe" `
            -ArgumentList $ElevatedArgs `
            -Verb RunAs `
            -Wait `
            -PassThru

        $ElevatedExitCode = [int]$ElevatedProcess.ExitCode
        if ($ElevatedExitCode -ne 0) {
            $LauncherRoot = Split-Path -Parent $PSCommandPath
            $LauncherFailureLog = Join-Path $LauncherRoot "logs\system_manager_failure.log"
            Write-Host ""
            Write-Host "[실패] 관리자 권한으로 실행된 AgentStudio가 ExitCode=$ElevatedExitCode 로 종료되었습니다." -ForegroundColor Red
            if (Test-Path $LauncherFailureLog) {
                Write-Host "실패 상세 로그: $LauncherFailureLog" -ForegroundColor Yellow
                Write-Host "========== 실패 상세 ==========" -ForegroundColor DarkYellow
                Get-Content -LiteralPath $LauncherFailureLog -Tail 120 -ErrorAction SilentlyContinue |
                    ForEach-Object { Write-Host $_ }
                Write-Host "================================" -ForegroundColor DarkYellow
            }
            else {
                Write-Host "실패 상세 로그가 생성되지 않았습니다. SYSTEM_ADMIN.ps1 파싱/초기화 단계 오류일 수 있습니다." -ForegroundColor Yellow
            }
        }
        exit $ElevatedExitCode
    }
    catch {
        Write-Host "[실패] 관리자 권한 승격이 취소되었거나 실패했습니다." -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        exit 1
    }
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

# v5.363: SYSTEM_ADMIN must not carry a hand-maintained stale version literal.
# Resolve the expected version from this checkout's backend source so the launcher
# can still detect a genuinely old process on the selected port without failing
# simply because SYSTEM_ADMIN.ps1 itself was not bumped during packaging.
$FallbackAgentStudioVersion = "5.574"
function Resolve-LocalAgentStudioVersion {
    param(
        [string]$ProjectRoot,
        [string]$FallbackVersion
    )

    $MainPy = Join-Path $ProjectRoot "backend\app\main.py"
    try {
        if (Test-Path -LiteralPath $MainPy) {
            $Source = [System.IO.File]::ReadAllText($MainPy, [System.Text.Encoding]::UTF8)
            $Match = [System.Text.RegularExpressions.Regex]::Match(
                $Source,
                'FastAPI\s*\([\s\S]*?version\s*=\s*["''](?<version>\d+\.\d+)["'']',
                [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
            )
            if ($Match.Success) {
                return [string]$Match.Groups["version"].Value
            }
        }
    }
    catch {
        Write-Host "[경고] 로컬 Backend 버전 자동 확인 실패: $($_.Exception.Message)" -ForegroundColor Yellow
    }

    return $FallbackVersion
}

$ExpectedAgentStudioVersion = Resolve-LocalAgentStudioVersion `
    -ProjectRoot $Root `
    -FallbackVersion $FallbackAgentStudioVersion
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$LogDir = Join-Path $Root "logs"

$SystemLog = Join-Path $LogDir "system_manager.log"
$BackendLog = Join-Path $LogDir "backend_console.log"
$FrontendLog = Join-Path $LogDir "frontend_console.log"
$FailureLog = Join-Path $LogDir "system_manager_failure.log"
$DbHealthLog = Join-Path $LogDir "database_health.log"
$BackendStartupLog = Join-Path $LogDir "backend_startup.log"
$ProjectEnvPath = Join-Path $Root ".env"
$BackendEnvPath = Join-Path $BackendDir ".env"

# v5.493: apply saved Temp/Cache/Output roots before pip/npm/backend processes start.
function Get-AgentStudioEnvValue {
    param([string]$Key)
    if (-not (Test-Path $ProjectEnvPath)) { return "" }
    try {
        $escaped = [Regex]::Escape($Key)
        $Line = Get-Content -LiteralPath $ProjectEnvPath -Encoding UTF8 |
            Where-Object { $_ -match ("^\s*{0}\s*=" -f $escaped) } |
            Select-Object -Last 1
        if (-not $Line) { return "" }
        $parts = $Line -split "=", 2
        if ($parts.Count -ne 2) { return "" }
        return [string]$parts[1].Trim()
    } catch { return "" }
}
$ConfiguredTempRoot = Get-AgentStudioEnvValue "DEFAULT_TEMP_ROOT"
$ConfiguredCacheRoot = Get-AgentStudioEnvValue "DEFAULT_CACHE_ROOT"
$ConfiguredOutputRoot = Get-AgentStudioEnvValue "DEFAULT_OUTPUT_ROOT"
if ($ConfiguredTempRoot) { New-Item -ItemType Directory -Force -Path $ConfiguredTempRoot | Out-Null; $env:TEMP=$ConfiguredTempRoot; $env:TMP=$ConfiguredTempRoot; $env:TMPDIR=$ConfiguredTempRoot; $env:AGENTSTUDIO_TEMP_ROOT=$ConfiguredTempRoot }
if ($ConfiguredCacheRoot) {
    New-Item -ItemType Directory -Force -Path $ConfiguredCacheRoot | Out-Null
    $env:AGENTSTUDIO_CACHE_ROOT=$ConfiguredCacheRoot; $env:PIP_CACHE_DIR=Join-Path $ConfiguredCacheRoot "pip"; $env:NPM_CONFIG_CACHE=Join-Path $ConfiguredCacheRoot "npm"; $env:HF_HOME=Join-Path $ConfiguredCacheRoot "huggingface"; $env:TORCH_HOME=Join-Path $ConfiguredCacheRoot "torch"; $env:EASYOCR_MODULE_PATH=Join-Path $ConfiguredCacheRoot "easyocr"
    @($env:PIP_CACHE_DIR,$env:NPM_CONFIG_CACHE,$env:HF_HOME,$env:TORCH_HOME,$env:EASYOCR_MODULE_PATH) | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }
}
if ($ConfiguredOutputRoot) { New-Item -ItemType Directory -Force -Path $ConfiguredOutputRoot | Out-Null; $env:AGENTSTUDIO_OUTPUT_ROOT=$ConfiguredOutputRoot }

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"), $Message
    Add-Content -Path $SystemLog -Value $line -Encoding UTF8
}

function Write-Step {
    param([string]$Message)
    Write-Host "[진행] $Message"
    Write-Log "진행: $Message"
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[완료] $Message" -ForegroundColor Green
    Write-Log "완료: $Message"
}

function Write-Fail {
    param([string]$Message)
    Write-Host ""
    Write-Host "[실패] $Message" -ForegroundColor Red
    Write-Host "System 로그         : $SystemLog"
    Write-Host "Backend 콘솔 로그   : $BackendLog"
    Write-Host "Backend Startup 로그: $BackendStartupLog"
    Write-Host "DB Health 로그      : $DbHealthLog"
    Write-Host "Frontend 콘솔 로그  : $FrontendLog"
    Write-Log "실패: $Message"
}

function Test-PortAvailable {
    param([int]$Port)

    if ($Port -lt 1024 -or $Port -gt 65535) {
        return $false
    }

    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new(
            [System.Net.IPAddress]::Loopback,
            $Port
        )
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($listener) {
            try { $listener.Stop() } catch {}
        }
    }
}

function Get-FreePort {
    param(
        [int]$StartPort,
        [int]$ExcludedPort = 0
    )

    $safeStart = [Math]::Max(1024, [Math]::Min(65535, $StartPort))

    for ($port = $safeStart; $port -le 65535 -and $port -lt ($safeStart + 200); $port++) {
        if ($ExcludedPort -gt 0 -and $port -eq $ExcludedPort) {
            continue
        }
        if (Test-PortAvailable $port) {
            return $port
        }
    }

    throw "사용 가능한 포트를 찾을 수 없습니다. 시작 포트: $StartPort"
}

function Set-AgentStudioEnvDefaultIfMissing {
    param(
        [string]$Name,
        [string]$Value
    )

    if (-not $Name -or $null -eq $Value) {
        return
    }

    $existing = Get-AgentStudioEnvValue $Name
    if ($existing) {
        return
    }

    if (-not (Test-Path $ProjectEnvPath)) {
        $header = @(
            "# THEANOVA AgentStudio runtime settings",
            "# Auto-created by SYSTEM_ADMIN. Secrets are never generated here."
        ) -join [Environment]::NewLine
        Set-Content -LiteralPath $ProjectEnvPath -Value $header -Encoding UTF8
    }

    Add-Content -LiteralPath $ProjectEnvPath -Value ("{0}={1}" -f $Name,$Value) -Encoding UTF8
    Write-Host "[자동 설정] $Name=$Value" -ForegroundColor DarkCyan
    Write-Log "Bootstrap .env 기본값 추가: $Name=$Value"
}

function Get-BootstrapSetting {
    param(
        [string]$Name,
        [string]$DefaultValue = ""
    )

    $value = Get-AgentStudioEnvValue $Name
    if ($value) {
        return $value
    }

    if ($DefaultValue) {
        Set-AgentStudioEnvDefaultIfMissing -Name $Name -Value $DefaultValue
        return $DefaultValue
    }

    throw "프로젝트 루트 .env에 필수 설정 '$Name' 이 없습니다: $ProjectEnvPath"
}

function Resolve-AgentStudioPort {
    param(
        [string]$SettingName,
        [int]$ExcludedPort = 0,
        [string]$Label = "Service",
        [int]$DefaultPort = 0
    )

    $raw = Get-BootstrapSetting $SettingName $(if ($DefaultPort -gt 0) { [string]$DefaultPort } else { "" })
    $preferred = 0
    $parsed = 0

    if ([int]::TryParse([string]$raw, [ref]$parsed)) {
        if ($parsed -ge 1024 -and $parsed -le 65535) {
            $preferred = $parsed
        }
        else {
            throw "$Label 설정 포트가 범위를 벗어났습니다: $parsed ($SettingName)"
        }
    }
    else {
        throw "$Label 설정 포트가 숫자가 아닙니다: $raw ($SettingName)"
    }

    if ($ExcludedPort -gt 0 -and $preferred -eq $ExcludedPort) {
        throw "$Label 포트 $preferred 는 다른 AgentStudio 서비스와 중복됩니다. 프로젝트 루트 .env 값을 수정하세요."
    }

    if (-not (Test-PortAvailable $preferred)) {
        throw "$Label 포트 $preferred 는 이미 사용 중입니다. .env에 설정한 포트를 임의 변경하지 않습니다. 사용 중인 프로세스를 종료하거나 .env 값을 수정하세요."
    }
    return $preferred
}

function Stop-PortProcess {
    param([int]$Port)

    $connections = Get-NetTCPConnection `
        -State Listen `
        -LocalPort $Port `
        -ErrorAction SilentlyContinue

    foreach ($conn in $connections) {
        try {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
        catch {
        }
    }
}

function Stop-AgentStudioProcesses {
    Write-Step "기존 AgentStudio Backend/Frontend 종료"

    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and (
                $_.CommandLine -match "backend_console_runner\.py" -or
                $_.CommandLine -match "frontend_console_runner\.cjs" -or
                $_.CommandLine -match "run_server\.py"
            )
        } |
        ForEach-Object {
            $ProcessIdToStop = [int]$_.ProcessId
            try {
                # backend_console_runner.py -> run_server.py처럼 부모/자식으로 실행되는 경우까지
                # 한 번에 종료하여 이전 버전 Backend가 포트에 남지 않도록 합니다.
                & taskkill.exe /PID $ProcessIdToStop /T /F 2>$null | Out-Null
            }
            catch {
                try {
                    Stop-Process -Id $ProcessIdToStop -Force -ErrorAction SilentlyContinue
                }
                catch {
                }
            }
        }

    # v5.326: BrowserRuntime leak cleanup is bounded and bulk-based.
    # Every selected PID is already scoped by the AgentStudio BrowserRuntime command line,
    # so ordinary user Chrome/Edge windows remain untouched.
    $browserProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -in @("chrome.exe", "msedge.exe") -and
            $_.CommandLine -and
            $_.CommandLine -match "THEANOVA\\AgentStudio\\BrowserRuntime"
        })
    if ($browserProcesses.Count -gt 0) {
        $browserIds = @($browserProcesses | ForEach-Object { [int]$_.ProcessId })
        Stop-Process -Id $browserIds -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 350
        $remainingBrowser = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -in @("chrome.exe", "msedge.exe") -and
                $_.CommandLine -and
                $_.CommandLine -match "THEANOVA\\AgentStudio\\BrowserRuntime"
            })
        if ($remainingBrowser.Count -gt 0) {
            $remainingIds = @($remainingBrowser | ForEach-Object { [int]$_.ProcessId })
            Stop-Process -Id $remainingIds -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 250
        }
        $remainingBrowser = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -in @("chrome.exe", "msedge.exe") -and
                $_.CommandLine -and
                $_.CommandLine -match "THEANOVA\\AgentStudio\\BrowserRuntime"
            })
        Write-Log "AgentStudio BrowserRuntime bulk 정리: before=$($browserProcesses.Count) remaining=$($remainingBrowser.Count)"
    }

    Start-Sleep -Milliseconds 700
    Write-Ok "기존 AgentStudio 프로세스 트리 종료"
    Write-Log "외부 uvicorn/npm/vite 및 일반 Chrome/Edge 프로세스는 종료 대상에서 제외했습니다."
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$Retry = 30,
        [int]$DelaySec = 1
    )

    for ($i = 1; $i -le $Retry; $i++) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
        }

        Start-Sleep -Seconds $DelaySec
    }

    return $false
}

function Find-OllamaExe {
    $cmd = Get-Command "ollama.exe" -ErrorAction SilentlyContinue
    if (-not $cmd) {
        $cmd = Get-Command "ollama" -ErrorAction SilentlyContinue
    }
    if ($cmd -and $cmd.Source -and (Test-Path $cmd.Source)) {
        return $cmd.Source
    }

    if ($env:LOCALAPPDATA) {
        $candidate = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Ensure-OllamaServer {
    $autoStartRaw = Get-BootstrapSetting "OLLAMA_AUTO_START" "true"
    $autoStart = ([string]$autoStartRaw).Trim().ToLowerInvariant() -notin @("0", "false", "no", "off")

    if (-not $autoStart) {
        Write-Host "[확인] Ollama 자동 시작: 사용 안 함" -ForegroundColor DarkGray
        Write-Log "Ollama 자동 시작 비활성"
        return
    }

    $healthUrl = "http://127.0.0.1:11434/api/version"
    if (Wait-HttpOk $healthUrl 1 1) {
        Write-Ok "Ollama Server 이미 실행 중 (127.0.0.1:11434)"
        return
    }

    $ollamaExe = Find-OllamaExe
    if (-not $ollamaExe) {
        Write-Host "[경고] Ollama 자동 시작 요청됨 - 실행 파일을 찾지 못했습니다." -ForegroundColor Yellow
        Write-Host "       시스템 관리 화면에서 Ollama 설치 상태를 확인하십시오." -ForegroundColor Yellow
        Write-Log "Ollama 자동 시작 실패: ollama.exe 찾지 못함"
        return
    }

    $OllamaRuntimeDir = Join-Path $BackendDir "logs\ollama_server"
    New-Item -ItemType Directory -Force -Path $OllamaRuntimeDir | Out-Null
    $OllamaOutLog = Join-Path $OllamaRuntimeDir "ollama_server.log"
    $OllamaErrLog = Join-Path $OllamaRuntimeDir "ollama_server.err.log"
    $OllamaPidFile = Join-Path $OllamaRuntimeDir "managed_ollama.pid"

    Write-Step "Ollama Server 자동 시작 (127.0.0.1:11434)"
    $previousOllamaHost = $env:OLLAMA_HOST
    try {
        $env:OLLAMA_HOST = "127.0.0.1:11434"
        $ollamaProcess = Start-Process `
            -FilePath $ollamaExe `
            -ArgumentList @("serve") `
            -WorkingDirectory (Split-Path -Parent $ollamaExe) `
            -WindowStyle Hidden `
            -RedirectStandardOutput $OllamaOutLog `
            -RedirectStandardError $OllamaErrLog `
            -PassThru

        $pidInfo = @{
            pid = [int]$ollamaProcess.Id
            exe = [string]$ollamaExe
            base_url = "http://127.0.0.1:11434"
            started_at = (Get-Date).ToString("o")
            owner = "THEANOVA AgentStudio SYSTEM_ADMIN"
        } | ConvertTo-Json -Depth 3
        [System.IO.File]::WriteAllText($OllamaPidFile, $pidInfo, $Utf8NoBom)
    }
    catch {
        Write-Host "[경고] Ollama Server 시작 실패: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "       Ollama 로그: $OllamaErrLog" -ForegroundColor Yellow
        Write-Log "Ollama Server 시작 실패: $($_.Exception.Message)"
        return
    }
    finally {
        $env:OLLAMA_HOST = $previousOllamaHost
    }

    if (Wait-HttpOk $healthUrl 20 1) {
        Write-Ok "Ollama Server 자동 시작 완료"
        Write-Log "Ollama Server 자동 시작 성공: $ollamaExe"
    }
    else {
        Write-Host "[경고] Ollama 프로세스를 실행했지만 API가 응답하지 않습니다." -ForegroundColor Yellow
        Write-Host "       Ollama stdout: $OllamaOutLog" -ForegroundColor Yellow
        Write-Host "       Ollama stderr: $OllamaErrLog" -ForegroundColor Yellow
        Write-Log "Ollama 자동 시작 후 Health Check 실패"
    }
}

function Invoke-LocalJsonNoProxy {
    param(
        [string]$Url,
        [int]$TimeoutMs = 2500
    )

    # v5.555: Windows PowerShell/WinHTTP proxy settings can unexpectedly
    # intercept even 127.0.0.1 requests. Backend startup verification must
    # always talk directly to the local listener.
    $request = [System.Net.HttpWebRequest]::Create($Url)
    $request.Proxy = $null
    $request.Timeout = $TimeoutMs
    $request.ReadWriteTimeout = $TimeoutMs
    $request.Method = "GET"
    $request.KeepAlive = $false

    $response = $null
    $reader = $null
    try {
        $response = $request.GetResponse()
        $statusCode = [int]$response.StatusCode
        $reader = New-Object System.IO.StreamReader($response.GetResponseStream(), [System.Text.Encoding]::UTF8)
        $body = $reader.ReadToEnd()
        if ($statusCode -lt 200 -or $statusCode -ge 300) {
            throw ("Local HTTP {0}: {1}" -f $statusCode, $body)
        }
        if ([string]::IsNullOrWhiteSpace($body)) {
            return $null
        }
        return ($body | ConvertFrom-Json)
    }
    finally {
        if ($reader) { $reader.Dispose() }
        if ($response) { $response.Dispose() }
    }
}

function Wait-ApiHealth {
    param(
        [string]$Url,
        [int]$Retry = 90,
        [int]$DelaySec = 1
    )

    $lastErrorMessage = ""
    for ($i = 1; $i -le $Retry; $i++) {
        try {
            $r = Invoke-LocalJsonNoProxy -Url $Url -TimeoutMs 2000
            $healthName = [string]$r.name
            $healthVersion = [string]$r.version
            if ($r.ok -eq $true -and $healthName -eq "THEANOVA AgentStudio") {
                if ($i -gt 1) {
                    Write-Log ("FastAPI Health 직접 연결 확인: attempt={0}/{1}; version={2}" -f $i, $Retry, $healthVersion)
                }
                return $true
            }

            $lastErrorMessage = (
                "직접 Health 응답 불일치: ok={0}; name={1}; version={2}" -f `
                [string]$r.ok, $healthName, $healthVersion
            )
        }
        catch {
            $lastErrorMessage = $_.Exception.Message
        }

        if (($i % 15) -eq 0 -and $i -lt $Retry) {
            Write-Host ("[대기] Backend 초기화 진행 중... {0}/{1}초" -f $i, $Retry) -ForegroundColor DarkGray
            Write-Log ("FastAPI Health 직접 연결 대기: attempt={0}/{1}; last={2}" -f $i, $Retry, $lastErrorMessage)
        }

        Start-Sleep -Seconds $DelaySec
    }

    if ($lastErrorMessage) {
        Write-Log ("FastAPI Health 직접 연결 최종 실패: {0}" -f $lastErrorMessage)
    }
    return $false
}

try {
    if (Test-Path $FailureLog) {
        Remove-Item -LiteralPath $FailureLog -Force -ErrorAction SilentlyContinue
    }
    Write-Log "SYSTEM_ADMIN 시작"

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "THEANOVA AgentStudio 시작"
    Write-Host "============================================================"
    Write-Host "프로젝트 경로: $Root"
    Write-Host ""

    if (-not (Test-Path $BackendDir)) {
        throw "Backend 폴더가 없습니다: $BackendDir"
    }

    if (-not (Test-Path $FrontendDir)) {
        throw "Frontend 폴더가 없습니다: $FrontendDir"
    }

    Stop-AgentStudioProcesses

    # v5.538: runtime-only, non-secret settings are self-healed on first run.
    # Existing root .env values remain authoritative and are never overwritten.
    if (-not (Test-Path $ProjectEnvPath)) {
        Write-Host "[안내] 프로젝트 루트 .env가 없어 안전한 Runtime 기본값만 자동 생성합니다." -ForegroundColor Yellow
        Write-Log "root .env 없음 - non-secret bootstrap settings만 자동 생성"
    }

    $BackendPort = Resolve-AgentStudioPort `
        -SettingName "AGENTSTUDIO_BACKEND_PORT" `
        -Label "Backend" `
        -DefaultPort 8000

    $FrontendPort = Resolve-AgentStudioPort `
        -SettingName "AGENTSTUDIO_FRONTEND_PORT" `
        -ExcludedPort $BackendPort `
        -Label "Frontend" `
        -DefaultPort 5173

    Write-Host "[확인] Backend 포트 : $BackendPort"
    Write-Host "[확인] Frontend 포트: $FrontendPort"
    Write-Log "Backend=$BackendPort, Frontend=$FrontendPort"

    Ensure-OllamaServer

    # runtime-config.js
    $PublicDir = Join-Path $FrontendDir "public"
    New-Item -ItemType Directory -Force -Path $PublicDir | Out-Null

    $RootJson = $Root | ConvertTo-Json -Compress
    $RuntimeConfigLines = @(
        "window.__AGENTSTUDIO_CONFIG__ = {",
        '  BACKEND_HOST: window.location.hostname,',
        ("  BACKEND_PORT: {0}," -f $BackendPort),
        ("  FRONTEND_PORT: {0}," -f $FrontendPort),
        ("  API_BASE_URL: window.location.protocol + '//'+ window.location.hostname + ':{0}/api'," -f $BackendPort),
        ("  WS_BASE_URL: (window.location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + window.location.hostname + ':{0}/api/ws'," -f $BackendPort),
        ("  AGENTSTUDIO_ROOT: {0}" -f $RootJson),
        "};"
    )
    $RuntimeConfig = $RuntimeConfigLines -join [Environment]::NewLine

    Set-Content `
        -Path (Join-Path $PublicDir "runtime-config.js") `
        -Value $RuntimeConfig `
        -Encoding UTF8

    Write-Ok "Runtime 포트 설정 생성"

    # Python / venv
    $VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

    if (-not (Test-Path $VenvPython)) {
        Write-Step "Backend 가상환경 생성"

        $Python = Get-Command py -ErrorAction SilentlyContinue
        if ($Python) {
            & py -3.12 -m venv (Join-Path $BackendDir ".venv")
        }
        else {
            $Python = Get-Command python -ErrorAction Stop
            & python -m venv (Join-Path $BackendDir ".venv")
        }

        if ($LASTEXITCODE -ne 0) {
            throw "Backend 가상환경 생성 실패"
        }
    }

    Write-Step "Backend 패키지 확인"
    & $VenvPython -m pip install -r (Join-Path $BackendDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Backend 패키지 확인/설치 실패"
    }
    Write-Ok "Backend 패키지 확인"

    # npm
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "Node.js/npm을 찾을 수 없습니다."
    }
    Write-Host "[확인] Node.js/npm 사용 가능"

    # v5.510: project-root/.env is the only source of database credentials.
    # Legacy backend/.env may contain stale database accounts from old releases, so
    # never migrate or use DB connection keys from that file. Non-DB settings may be
    # migrated when root .env already exists, then backend/.env is removed.
    $LegacyBackendEnvPath = Join-Path $Root "backend\.env"
    $SensitiveLegacyDbKeys = @(
        "DATABASE_URL", "LANGGRAPH_DATABASE_URL",
        "AGENTSTUDIO_LOCAL_DATABASE_URL", "AGENTSTUDIO_LOCAL_LANGGRAPH_DATABASE_URL",
        "SUPABASE_DATABASE_URL", "SUPABASE_LANGGRAPH_DATABASE_URL"
    )
    if (Test-Path $LegacyBackendEnvPath) {
        try {
            if (Test-Path $ProjectEnvPath) {
                $projectKeys = @{}
                foreach ($line in (Get-Content -LiteralPath $ProjectEnvPath -Encoding UTF8)) {
                    if ($line -match '^\s*([^#=\s]+)\s*=') { $projectKeys[$matches[1]] = $true }
                }
                $missingLines = New-Object System.Collections.Generic.List[string]
                foreach ($line in (Get-Content -LiteralPath $LegacyBackendEnvPath -Encoding UTF8)) {
                    if ($line -match '^\s*([^#=\s]+)\s*=') {
                        $key = $matches[1]
                        if (($SensitiveLegacyDbKeys -notcontains $key) -and (-not $projectKeys.ContainsKey($key))) {
                            $missingLines.Add($line)
                        }
                    }
                }
                if ($missingLines.Count -gt 0) {
                    Add-Content -LiteralPath $ProjectEnvPath -Value "`r`n# Migrated non-DB settings from legacy backend/.env by AgentStudio v5.517" -Encoding UTF8
                    Add-Content -LiteralPath $ProjectEnvPath -Value $missingLines -Encoding UTF8
                }
            }
            Remove-Item -LiteralPath $LegacyBackendEnvPath -Force
            Write-Host "[정리] legacy backend/.env 삭제 (DB 연결정보는 root .env만 사용)"
        } catch { Write-Warning "legacy backend/.env 정리 실패: $($_.Exception.Message)" }
    }

    # v5.517: v5.515/v5.516 archives were created from a workspace whose Korean
    # root filenames had already been mojibake-corrupted. When v5.517 is overlaid in
    # place, those invalid duplicate guide/script names remain unless explicitly removed.
    # Remove only root PS1/PPTX names containing known mojibake marker characters.
    $removedMojibakeRootFiles = @()
    Get-ChildItem -LiteralPath $Root -File -ErrorAction SilentlyContinue | Where-Object {
        ($_.Extension -in @('.ps1', '.pptx')) -and ($_.Name -match '[δ∞φΩ]')
    } | ForEach-Object {
        $removedMojibakeRootFiles += $_.Name
        Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop
    }
    if ($removedMojibakeRootFiles.Count -gt 0) {
        Write-Host "[정리] 손상된 한글 파일명 잔여 파일 제거: $($removedMojibakeRootFiles.Count)개"
    }

    # v5.510: in-place upgrades do not delete files removed from a newer ZIP.
    # src/App.tsx is obsolete after v5.507 moved the application root to src/app/App.tsx.
    # Delete the stale legacy file before contract validation so old installations can
    # upgrade in place without a false regression failure.
    $LegacyFrontendAppPath = Join-Path $FrontendDir "src\App.tsx"
    if (Test-Path $LegacyFrontendAppPath) {
        Remove-Item -LiteralPath $LegacyFrontendAppPath -Force
        Write-Host "[정리] 이전 Frontend src/App.tsx 제거 (src/app/App.tsx 사용)"
    }

    # v5.517: in-place ZIP overlays can leave directories/files that were intentionally
    # retired by the feature split. The frontend contract validator treats those paths
    # as regressions, so remove only the exact legacy paths before validation.
    $RetiredFrontendFeaturePaths = @(
        (Join-Path $FrontendDir "src\components\notebook"),
        (Join-Path $FrontendDir "src\components\memo\ProjectMemoPanel.tsx"),
        (Join-Path $FrontendDir "src\components\viewers\DocumentViewers.tsx"),
        (Join-Path $FrontendDir "src\utils\notebook.ts"),
        (Join-Path $FrontendDir "src\components\database"),
        (Join-Path $FrontendDir "src\components\codex"),
        (Join-Path $FrontendDir "src\components\media\MediaWorkflowEditor.tsx"),
        (Join-Path $FrontendDir "src\components\media\MediaWorkflowEditor.css")
    )
    $removedRetiredFrontendPaths = @()
    foreach ($retiredFeaturePath in $RetiredFrontendFeaturePaths) {
        if (Test-Path -LiteralPath $retiredFeaturePath) {
            Remove-Item -LiteralPath $retiredFeaturePath -Recurse -Force -ErrorAction Stop
            $removedRetiredFrontendPaths += $retiredFeaturePath
        }
    }
    if ($removedRetiredFrontendPaths.Count -gt 0) {
        Write-Host "[정리] 분리 전 Frontend 잔여 경로 제거: $($removedRetiredFrontendPaths.Count)개"
    }


    # v5.506: remove obsolete offline TypeScript migration shims left behind by an
    # in-place upgrade from v5.503. ZIP extraction does not delete files that no
    # longer exist in the newer archive, so the stale declaration can otherwise
    # shadow the real React 19 / xterm package types and break every TSX build.
    $obsoleteTypeShimPatterns = @(
        "__temp_typecheck_shim__.d.ts",
        "__temp_typecheck_*.d.ts"
    )
    $removedObsoleteTypeShims = @()
    foreach ($pattern in $obsoleteTypeShimPatterns) {
        Get-ChildItem -Path (Join-Path $FrontendDir "src") -Filter $pattern -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
            $removedObsoleteTypeShims += $_.FullName
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop
        }
    }
    if ($removedObsoleteTypeShims.Count -gt 0) {
        Write-Host "[정리] 이전 TypeScript 임시 타입 선언 제거: $($removedObsoleteTypeShims.Count)개"
    }

    # Also clear incremental TypeScript build metadata after removing stale input
    # files. This prevents an old program graph from being reused on an upgrade.
    $tsBuildInfoPath = Join-Path $FrontendDir "node_modules\.tmp\tsconfig.app.tsbuildinfo"
    if (Test-Path $tsBuildInfoPath) {
        Remove-Item -LiteralPath $tsBuildInfoPath -Force -ErrorAction SilentlyContinue
        Write-Host "[정리] 이전 TypeScript 빌드 캐시 제거"
    }

    Push-Location $FrontendDir
    try {
        if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
            Write-Step "Frontend npm install"
            & npm install
            if ($LASTEXITCODE -ne 0) {
                throw "Frontend npm install 실패"
            }
        }
        else {
            Write-Host "[확인] node_modules가 이미 존재합니다."
        }

        Write-Step "Frontend 빌드 검증"

# Frontend dependency verification (v5.81)
$frontendNodeModules = Join-Path $FrontendDir "node_modules"
$requiredFrontendPackages = @(
    "@xterm/xterm",
    "@xterm/addon-fit",
    "typescript",
    "vite",
    "@types/node",
    "@types/react",
    "@types/react-dom"
)
$requiredFrontendPackageFiles = @(
    "typescript\bin\tsc",
    "vite\client.d.ts",
    "@types\node\index.d.ts",
    "@types\react\index.d.ts",
    "@types\react-dom\index.d.ts"
)

$needNpmInstall = -not (Test-Path $frontendNodeModules)

if (-not $needNpmInstall) {
    foreach ($packageName in $requiredFrontendPackages) {
        $packagePath = Join-Path $frontendNodeModules $packageName
        if (-not (Test-Path $packagePath)) {
            Write-Host "[확인] Frontend 필수 패키지 누락: $packageName" -ForegroundColor Yellow
            $needNpmInstall = $true
            break
        }
    }
}

if (-not $needNpmInstall) {
    foreach ($relativePackageFile in $requiredFrontendPackageFiles) {
        $packageFilePath = Join-Path $frontendNodeModules $relativePackageFile
        if (-not (Test-Path $packageFilePath)) {
            Write-Host "[확인] Frontend 패키지 파일 누락/불완전: $relativePackageFile" -ForegroundColor Yellow
            $needNpmInstall = $true
            break
        }
    }
}

if ($needNpmInstall) {
    Write-Host "[진행] Frontend 패키지 설치/갱신" -ForegroundColor Cyan
    Push-Location $FrontendDir
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend npm install 실패"
        }
        Write-Host "[완료] Frontend 패키지 설치/갱신" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "[확인] Frontend 필수 패키지가 모두 설치되어 있습니다." -ForegroundColor DarkGray
}

        $FrontendBuildLog = Join-Path $LogDir "frontend_build.log"
        # v5.467: Windows PowerShell 5.1 converts native stderr from npm.ps1 into
        # ErrorRecord/RemoteException when ErrorActionPreference=Stop. Build tools often
        # write warnings to stderr even when they intend normal output, so capture the
        # complete stream without letting PowerShell terminate before npm's exit code
        # can be evaluated.
        $PreviousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $FrontendBuildOutput = & npm run build 2>&1 | Tee-Object -FilePath $FrontendBuildLog
            $FrontendBuildExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $PreviousErrorActionPreference
        }
        $FrontendBuildOutput | ForEach-Object { Write-Host $_ }
        if ($FrontendBuildExitCode -ne 0) {
            $FrontendBuildTail = ($FrontendBuildOutput | Select-Object -Last 50) -join [Environment]::NewLine
            throw "Frontend 빌드 검증 실패`n$FrontendBuildTail`n전체 빌드 로그: $FrontendBuildLog"
        }
        Write-Ok "Frontend 빌드 검증"
    }
    finally {
        Pop-Location
    }

    # Backend start
    Write-Step "Backend 시작"

    # Native stderr(Uvicorn INFO 포함)를 PowerShell 오류 레코드로 변환하지 않도록
    # cmd.exe에서 stdout/stderr를 하나로 합쳐 로그 파일에 저장합니다.
    # 별도 PowerShell 창에는 로그 파일을 실시간으로 tail 하므로 INFO가 빨간 오류로 보이지 않습니다.
    # Backend console is streamed by a dedicated Python UTF-8 tee runner.
    # Do not tail the UTF-8 log with PowerShell Get-Content because Windows
    # PowerShell may reinterpret byte encoding and display mojibake.
    $BackendRunnerPy = Join-Path $BackendDir "backend_console_runner.py"

    if (-not (Test-Path $BackendRunnerPy)) {
        throw "Backend console runner가 없습니다: $BackendRunnerPy"
    }

    # v5.169: 중첩 PowerShell -Command 문자열을 제거합니다.
    # Windows PowerShell 5.1에서 긴 -Command 문자열 내부의 &, backtick, 괄호가
    # 외부 SYSTEM_ADMIN.ps1 파서와 충돌하여 SYSTEM_ADMIN 자체가 시작 전에
    # ParserError(AmpersandNotAllowed)를 내던 문제를 방지합니다.
    $BackendPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $BackendPython)) {
        throw "Backend Python이 없습니다: $BackendPython"
    }

    $PreviousPythonUtf8 = $env:PYTHONUTF8
    $PreviousPythonIoEncoding = $env:PYTHONIOENCODING
    $PreviousBackendPort = $env:AGENTSTUDIO_BACKEND_PORT
    $PreviousBackendFrontendPort = $env:AGENTSTUDIO_FRONTEND_PORT
    try {
        # Start-Process 자식 프로세스가 UTF-8/실제 Runtime 포트 환경을 상속하도록 잠시 설정합니다.
        $env:PYTHONUTF8 = "1"
        $env:PYTHONIOENCODING = "utf-8"
        $env:AGENTSTUDIO_BACKEND_PORT = [string]$BackendPort
        $env:AGENTSTUDIO_FRONTEND_PORT = [string]$FrontendPort

        # v5.510: stale machine/user/process DB variables must not override root .env.
        # Pydantic receives explicit values from root .env, but clearing inherited DB
        # variables here also protects libraries/services that read os.environ directly.
        $InheritedDatabaseEnvKeys = @(
            "DATABASE_URL", "LANGGRAPH_DATABASE_URL",
            "AGENTSTUDIO_LOCAL_DATABASE_URL", "AGENTSTUDIO_LOCAL_LANGGRAPH_DATABASE_URL",
            "SUPABASE_DATABASE_URL", "SUPABASE_LANGGRAPH_DATABASE_URL"
        )
        foreach ($dbEnvKey in $InheritedDatabaseEnvKeys) {
            Remove-Item -Path ("Env:" + $dbEnvKey) -ErrorAction SilentlyContinue
        }

        Start-Process `
            -FilePath $BackendPython `
            -ArgumentList @(
                ".\backend_console_runner.py",
                "--host", "127.0.0.1",
                "--port", ([string]$BackendPort),
                "--log", "..\logs\backend_console.log"
            ) `
            -WorkingDirectory $BackendDir `
            -WindowStyle Normal
    }
    finally {
        $env:PYTHONUTF8 = $PreviousPythonUtf8
        $env:PYTHONIOENCODING = $PreviousPythonIoEncoding
        $env:AGENTSTUDIO_BACKEND_PORT = $PreviousBackendPort
        $env:AGENTSTUDIO_FRONTEND_PORT = $PreviousBackendFrontendPort
    }

    $BackendHealthUrl = "http://127.0.0.1:$BackendPort/api/health"

    # Record which PID actually owns the configured backend port. This makes
    # stale/foreign listener problems visible instead of reporting only a timeout.
    try {
        Start-Sleep -Milliseconds 350
        $BackendPortOwner = Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($BackendPortOwner) {
            $OwnerPid = [int]$BackendPortOwner.OwningProcess
            $OwnerProcess = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $OwnerPid) -ErrorAction SilentlyContinue
            $OwnerCommand = if ($OwnerProcess) { [string]$OwnerProcess.CommandLine } else { "" }
            Write-Log ("Backend listen 확인: port={0}; pid={1}; command={2}" -f $BackendPort, $OwnerPid, $OwnerCommand)
        }
        else {
            Write-Log ("Backend listen 대기 시작: port={0}; listener 아직 없음" -f $BackendPort)
        }
    }
    catch {
        Write-Log ("Backend listen 진단 실패: {0}" -f $_.Exception.Message)
    }

    Write-Step "FastAPI Health Check: $BackendHealthUrl"
    # v5.554: DB/provider 초기화와 Python import가 느린 PC에서도 Backend가
    # 실제로 기동 중인 상태를 조기 실패로 오판하지 않도록 최대 90초 기다립니다.
    if (-not (Wait-ApiHealth $BackendHealthUrl 90 1)) {
        Write-Host ""
        Write-Host "[실패] FastAPI Backend가 정상 시작되지 않았습니다." -ForegroundColor Red
        Write-Host "Backend 로그 전체 경로: $BackendLog" -ForegroundColor Yellow
        Write-Host "Backend Startup 로그 : $BackendStartupLog" -ForegroundColor Yellow
        Write-Host ""

        if (Test-Path $BackendLog) {
            Write-Host "========== Backend 로그 마지막 60줄 ==========" -ForegroundColor DarkYellow
            try {
                Get-Content -Path $BackendLog -Tail 60 -ErrorAction Stop |
                    ForEach-Object { Write-Host $_ }
            }
            catch {
                Write-Host "[경고] Backend 로그 읽기 실패: $($_.Exception.Message)"
            }
            Write-Host "=============================================" -ForegroundColor DarkYellow
        }

        throw "FastAPI Health Check 90초 초과 - Backend 로그를 확인하십시오: $BackendLog"
    }
    $BackendHealthInfo = Invoke-LocalJsonNoProxy -Url $BackendHealthUrl -TimeoutMs 5000
    $RunningVersion = [string]$BackendHealthInfo.version
    if ($RunningVersion -ne $ExpectedAgentStudioVersion) {
        throw (
            "Backend 버전 불일치 - 기대 버전: {0}, 현재 실행 버전: {1}. " -f `
            $ExpectedAgentStudioVersion, $RunningVersion
        ) + "이전 AgentStudio Backend 프로세스가 남아 있거나 다른 폴더를 실행 중인지 확인하십시오."
    }
    Write-Ok "FastAPI Health Check 성공 / Backend v$RunningVersion"

    # DB health
    # PostgreSQL 오류는 AgentStudio 전체 실행 중단 사유가 아닙니다.
    # Backend/Frontend를 먼저 기동하고 시스템 관리 화면에서 DB를 복구할 수 있어야 합니다.
    $DbHealthUrl = "http://127.0.0.1:$BackendPort/api/health/database"
    Write-Step "PostgreSQL Health Check via FastAPI"

    $DatabaseHealthy = $false

    try {
        $dbHealth = Invoke-LocalJsonNoProxy -Url $DbHealthUrl -TimeoutMs 5000

        if ($dbHealth.ok -eq $true -and $dbHealth.database_connected -eq $true) {
            $DatabaseHealthy = $true
            Write-Ok "PostgreSQL Health Check 성공"
            Write-Host "[확인] DB 프로젝트 수: $($dbHealth.project_count)"
        }
        else {
            $message = if ($dbHealth.message) {
                $dbHealth.message
            } else {
                "PostgreSQL Health Check 응답이 비정상입니다."
            }

            $detailLines = @(
                ("[{0}] PostgreSQL Health Check 실패" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff")),
                ("URL: {0}" -f $DbHealthUrl),
                ("Message: {0}" -f $message),
                ("LogPath: {0}" -f $dbHealth.log_path)
            )
            $detail = $detailLines -join [Environment]::NewLine

            Set-Content -Path $DbHealthLog -Value $detail -Encoding UTF8

            Write-Host "[경고] PostgreSQL Health Check 실패" -ForegroundColor Yellow
            Write-Host "       AgentStudio는 계속 실행합니다."
            Write-Host "       DB Health 로그: $DbHealthLog"
            Write-Log "경고: PostgreSQL Health Check 실패 - $message"
        }
    }
    catch {
        $detailLines = @(
            ("[{0}] PostgreSQL Health Check 호출 실패" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff")),
            ("URL: {0}" -f $DbHealthUrl),
            "",
            $_.Exception.ToString()
        )
        $detail = $detailLines -join [Environment]::NewLine

        Set-Content -Path $DbHealthLog -Value $detail -Encoding UTF8

        Write-Host "[경고] PostgreSQL Health Check 호출 실패" -ForegroundColor Yellow
        Write-Host "       AgentStudio는 계속 실행합니다."
        Write-Host "       DB Health 로그: $DbHealthLog"
        Write-Log "경고: PostgreSQL Health Check 호출 실패 - $($_.Exception.Message)"
    }

    # Frontend start
    Write-Step "Frontend 시작"

    $FrontendRunner = Join-Path $FrontendDir "frontend_console_runner.cjs"

    if (-not (Test-Path $FrontendRunner)) {
        throw "Frontend console runner가 없습니다: $FrontendRunner"
    }

    # Vite config와 Browser HMR client가 동일한 host/port를 사용하도록
    # 환경변수와 CLI 인자를 같은 값으로 전달합니다.
    # v5.169: Backend와 동일하게 중첩 PowerShell -Command 문자열을 사용하지 않습니다.
    $NodeCommand = Get-Command "node.exe" -ErrorAction SilentlyContinue
    if (-not $NodeCommand) {
        $NodeCommand = Get-Command "node" -ErrorAction SilentlyContinue
    }
    if (-not $NodeCommand) {
        throw "Node.js 실행 파일을 찾을 수 없습니다. node가 PATH에 등록되어 있는지 확인하십시오."
    }

    $PreviousFrontendHost = $env:AGENTSTUDIO_FRONTEND_HOST
    $PreviousFrontendPort = $env:AGENTSTUDIO_FRONTEND_PORT
    try {
        $env:AGENTSTUDIO_FRONTEND_HOST = "127.0.0.1"
        $env:AGENTSTUDIO_FRONTEND_PORT = [string]$FrontendPort

        Start-Process `
            -FilePath $NodeCommand.Source `
            -ArgumentList @(
                ".\frontend_console_runner.cjs",
                "--host", "127.0.0.1",
                "--port", ([string]$FrontendPort),
                "--log", "..\logs\frontend_console.log"
            ) `
            -WorkingDirectory $FrontendDir `
            -WindowStyle Normal
    }
    finally {
        $env:AGENTSTUDIO_FRONTEND_HOST = $PreviousFrontendHost
        $env:AGENTSTUDIO_FRONTEND_PORT = $PreviousFrontendPort
    }

    $FrontendUrl = "http://127.0.0.1:$FrontendPort"

    Write-Step "Frontend Health Check: $FrontendUrl"
    if (-not (Wait-HttpOk $FrontendUrl 30 1)) {
        Write-Host ""
        Write-Host "[실패] Vite Frontend가 정상 응답하지 않습니다." -ForegroundColor Red
        Write-Host "Frontend 로그 전체 경로: $FrontendLog" -ForegroundColor Yellow

        if (Test-Path $FrontendLog) {
            Write-Host "========== Frontend 로그 마지막 80줄 ==========" -ForegroundColor DarkYellow
            try {
                Get-Content -Path $FrontendLog -Tail 80 -ErrorAction Stop |
                    ForEach-Object { Write-Host $_ }
            }
            catch {
                Write-Host "[경고] Frontend 로그 읽기 실패: $($_.Exception.Message)"
            }
            Write-Host "===============================================" -ForegroundColor DarkYellow
        }

        throw "Frontend Health Check 실패 - Vite/HMR 로그를 확인하십시오: $FrontendLog"
    }

    Write-Ok "Frontend HTTP/HMR Server Health Check 성공"

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "[완료되었습니다] THEANOVA AgentStudio 시작 완료" -ForegroundColor Green
    Write-Host "============================================================"
    Write-Host "Backend : http://127.0.0.1:$BackendPort"
    Write-Host "API     : http://127.0.0.1:$BackendPort/api"
    Write-Host "Frontend: $FrontendUrl"
    Write-Host ""
    Write-Host "System 로그  : $SystemLog"
    Write-Host "Backend 로그 : $BackendLog"
    Write-Host "Frontend 로그: $FrontendLog"
    Write-Host "DB Health 로그: $DbHealthLog"
    Write-Host ""

    if ($DatabaseHealthy) {
        Write-Host "PostgreSQL 상태: 정상" -ForegroundColor Green
    }
    else {
        Write-Host "PostgreSQL 상태: 연결 필요" -ForegroundColor Yellow
        Write-Host "AgentStudio는 실행되었으며 시스템 관리 화면에서 DB 설정을 확인하십시오."
    }

    Write-Host ""

    Write-Log "AgentStudio 시작 완료"

    Start-Process $FrontendUrl

    exit 0
}
catch {
    $FailureLines = @(
        ("[{0}] SYSTEM_ADMIN 실패" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff")),
        ("Version: {0}" -f $ExpectedAgentStudioVersion),
        ("Root: {0}" -f $Root),
        ("Message: {0}" -f $_.Exception.Message),
        ("Type: {0}" -f $_.Exception.GetType().FullName),
        ("NativeExitCode: {0}" -f $LASTEXITCODE),
        "",
        "Exception:",
        $_.Exception.ToString(),
        "",
        "ScriptStackTrace:",
        ([string]$_.ScriptStackTrace)
    )
    try {
        Set-Content -LiteralPath $FailureLog -Value ($FailureLines -join [Environment]::NewLine) -Encoding UTF8
    }
    catch {
        # Failure reporting must never hide the original startup exception.
    }

    Write-Fail $_.Exception.Message
    Write-Host ""
    Write-Host "실패 상세 로그: $FailureLog" -ForegroundColor Yellow
    Write-Host "상세 오류:"
    Write-Host $_.Exception.ToString()

    # v5.467: when SYSTEM_ADMIN was relaunched through UAC, this is the elevated
    # console that previously disappeared immediately after a startup failure.
    # Keep it open so the actual npm/backend/frontend error remains readable.
    if ($ElevatedChild) {
        Write-Host ""
        Write-Host "============================================================" -ForegroundColor DarkYellow
        Write-Host "[실패] 오류 확인을 위해 이 관리자 창을 자동으로 닫지 않습니다." -ForegroundColor Yellow
        Write-Host "로그를 확인한 뒤 Enter 키를 누르면 창을 닫습니다." -ForegroundColor Yellow
        Write-Host "============================================================" -ForegroundColor DarkYellow
        try {
            [void](Read-Host)
        }
        catch {
            # Non-interactive hosts may not provide stdin; failure logging already completed.
        }
    }
    exit 1
}
