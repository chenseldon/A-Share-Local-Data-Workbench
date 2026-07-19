param(
    [switch]$DemoData,
    [switch]$NoOpen,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$BackendPort = 8000
$FrontendPort = 5173
$DemoDataEnabled = if ($DemoData) { "1" } else { "0" }
$DefaultFreeStockdbSdkPath = "D:\Edge\free-stockdb-main\pybao"
if (-not $env:ASHARE_FREE_STOCKDB_SDK_PATH) {
    $env:ASHARE_FREE_STOCKDB_SDK_PATH = $DefaultFreeStockdbSdkPath
}

function Test-CommandAvailable {
    param([string]$CommandName)
    return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Test-TcpPortOpen {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $asyncResult = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne(300)) {
            return $false
        }
        $client.EndConnect($asyncResult)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Test-HttpHealth {
    param(
        [string]$Url,
        [int]$TimeoutSec = 2
    )

    try {
        $response = Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec
        return $null -ne $response -and $response.status -eq "ok"
    }
    catch {
        return $false
    }
}

function Assert-BackendDependencies {
    python -c "import os, sys; p=os.environ.get('ASHARE_FREE_STOCKDB_SDK_PATH'); sys.path.insert(0, p) if p and p not in sys.path else None; import duckdb, fastapi, uvicorn, stock_sdk, zhibiao" | Out-Null
}

function Assert-FreeStockdbSdkPath {
    $sdkPath = $env:ASHARE_FREE_STOCKDB_SDK_PATH
    if (-not (Test-Path (Join-Path $sdkPath "stock_sdk.py")) -or -not (Test-Path (Join-Path $sdkPath "zhibiao.py"))) {
        throw "free-stockdb Python SDK is not available. Set ASHARE_FREE_STOCKDB_SDK_PATH to the pybao directory containing stock_sdk.py and zhibiao.py. Current value: $sdkPath"
    }
}

Write-Host "A-Share Local Data Workbench" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"

if (-not (Test-CommandAvailable "python")) {
    throw "Python is not available on PATH."
}

if (-not (Test-CommandAvailable "npm.cmd")) {
    throw "npm.cmd is not available on PATH. Install Node.js first."
}

try {
    Assert-FreeStockdbSdkPath
    Assert-BackendDependencies
}
catch {
    throw "Missing Python backend dependencies or free-stockdb SDK path. $($_.Exception.Message)"
}

if (-not (Test-Path (Join-Path $FrontendRoot "node_modules"))) {
    if ($CheckOnly) {
        Write-Host "frontend/node_modules is missing; npm install would run before startup." -ForegroundColor Yellow
    }
    else {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
        Push-Location $FrontendRoot
        try {
            npm.cmd install
        }
        finally {
            Pop-Location
        }
    }
}

if ($CheckOnly) {
    Write-Host "Check complete. Backend port: $BackendPort; frontend port: $FrontendPort; demo data: $DemoDataEnabled"
    Write-Host "free-stockdb SDK path: $env:ASHARE_FREE_STOCKDB_SDK_PATH"
    exit 0
}

$backendCommand = @"
`$env:ASHARE_DEMO_DATA = '$DemoDataEnabled'
`$env:ASHARE_FREE_STOCKDB_SDK_PATH = '$env:ASHARE_FREE_STOCKDB_SDK_PATH'
Set-Location '$ProjectRoot'
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port $BackendPort
"@

$frontendCommand = @"
Set-Location '$FrontendRoot'
npm.cmd run dev -- --host 127.0.0.1 --port $FrontendPort
"@

$backendHealthUrl = "http://127.0.0.1:$BackendPort/api/health"
$frontendUrl = "http://127.0.0.1:$FrontendPort"

if (Test-TcpPortOpen $BackendPort) {
    if (Test-HttpHealth $backendHealthUrl) {
        Write-Host "Backend port $BackendPort is already serving /api/health; reusing it." -ForegroundColor Yellow
    }
    else {
        Write-Host "Backend port $BackendPort is occupied, but /api/health is not reachable. Close the stale process or change the port." -ForegroundColor Red
    }
}
else {
    Start-Process powershell.exe -WorkingDirectory $ProjectRoot -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $backendCommand
    )
}

if (Test-TcpPortOpen $FrontendPort) {
    Write-Host "Frontend port $FrontendPort is already in use; not starting another frontend process. Use $frontendUrl." -ForegroundColor Yellow
}
else {
    Start-Process powershell.exe -WorkingDirectory $FrontendRoot -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $frontendCommand
    )
}

Start-Sleep -Seconds 3

Write-Host "API health: $backendHealthUrl" -ForegroundColor DarkCyan
Write-Host "Open: $frontendUrl" -ForegroundColor Green
Write-Host "Demo data enabled: $DemoDataEnabled"
Write-Host "free-stockdb SDK path: $env:ASHARE_FREE_STOCKDB_SDK_PATH"

if (-not $NoOpen) {
    Start-Process $frontendUrl
}
