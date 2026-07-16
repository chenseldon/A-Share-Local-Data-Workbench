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

function Assert-BackendDependencies {
    python -c "import duckdb, fastapi, uvicorn" | Out-Null
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
    Assert-BackendDependencies
}
catch {
    throw "Missing Python backend dependencies. Install them first, for example: python -m pip install duckdb fastapi httpx pydantic `"uvicorn[standard]`""
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
    exit 0
}

$backendCommand = @"
`$env:ASHARE_DEMO_DATA = '$DemoDataEnabled'
Set-Location '$ProjectRoot'
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port $BackendPort
"@

$frontendCommand = @"
Set-Location '$FrontendRoot'
npm.cmd run dev -- --host 127.0.0.1 --port $FrontendPort
"@

if (Test-TcpPortOpen $BackendPort) {
    Write-Host "Backend port $BackendPort is already in use; not starting another backend process." -ForegroundColor Yellow
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
    Write-Host "Frontend port $FrontendPort is already in use; not starting another frontend process." -ForegroundColor Yellow
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

$url = "http://127.0.0.1:$FrontendPort"
Write-Host "Open: $url" -ForegroundColor Green
Write-Host "Demo data enabled: $DemoDataEnabled"

if (-not $NoOpen) {
    Start-Process $url
}
