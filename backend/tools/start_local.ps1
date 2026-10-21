param([switch]$Demo, [int]$BackendPort = 8000, [int]$FrontendPort = 5173, [string]$DatabasePath, [switch]$ReuseExisting, [string]$RuntimeConfig, [string]$PythonPath, [string]$PacsRuntimeLayer, [switch]$FrontendOnly, [string]$FrontendProject, [string]$NodePath, [string]$PreviewDist, [string]$FrontendLogRoot)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'background_process.ps1')
$hadPythonPath = Test-Path Env:PYTHONPATH
$originalPythonPath = $env:PYTHONPATH
try {
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if ([IO.Path]::GetPathRoot($projectRoot) -ne 'E:\') { throw 'This workstation configuration requires the project on E:.' }
. (Join-Path $PSScriptRoot 'use_e_drive.ps1')
if ($FrontendOnly) {
    if ($Demo -or $DatabasePath -or $ReuseExisting -or $PythonPath -or $PacsRuntimeLayer) { throw 'FrontendOnly cannot change backend/database or use ReuseExisting.' }
    & (Join-Path $PSScriptRoot 'start_frontend_only.ps1') -BackendPort $BackendPort -FrontendPort $FrontendPort -RuntimeConfig $RuntimeConfig -FrontendProject $FrontendProject -NodePath $NodePath -PreviewDist $PreviewDist -LogRoot $FrontendLogRoot
    return
}
if ($FrontendProject -or $NodePath -or $PreviewDist -or $FrontendLogRoot) { throw 'Custom frontend options require explicit FrontendOnly; no service action performed.' }
$stateRoot = 'E:/BrainFusion-Runtime/local'
$python = Join-Path $projectRoot '.conda/brainfusion/python.exe'
if ($PythonPath) {
    $python = (Resolve-Path -LiteralPath $PythonPath -ErrorAction Stop).Path
    if ([IO.Path]::GetPathRoot($python) -ne 'E:\' -or [IO.Path]::GetFileName($python) -ne 'python.exe' -or !(Test-Path -LiteralPath $python -PathType Leaf)) {
        throw 'PythonPath must name an existing python.exe on E:. No launch or stop performed.'
    }
    # Windows venv python.exe is a redirector: its PID is not the server PID.
    # Existing ownership/stop checks support direct interpreters only.
    $venvConfig = Join-Path (Split-Path (Split-Path $python -Parent) -Parent) 'pyvenv.cfg'
    if (Test-Path -LiteralPath $venvConfig -PathType Leaf) {
        throw 'Windows venv redirectors are not supported by this direct-PID launcher. No service was started or stopped; use this environment for CLI validation only until child-process ownership is supported.'
    }
}
$layerIdentity = $null
if ($PacsRuntimeLayer) {
    $layerIdentity = (& $python -B (Join-Path $PSScriptRoot 'validate_pacs_runtime_layer.py') --base-python $python --layer $PacsRuntimeLayer) | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or !$layerIdentity -or $layerIdentity.status -ne 'passed') { throw 'Pinned PACS import layer validation failed; no service action performed.' }
    $env:PYTHONPATH = $layerIdentity.site_path
}
$runtimePaths = $null
if ($RuntimeConfig) {
    if ($Demo -or $DatabasePath) { throw '-RuntimeConfig cannot be combined with -Demo/-DatabasePath.' }
    $runtimePaths = (& $python -B (Join-Path $PSScriptRoot 'read_runtime_config.py') $RuntimeConfig) | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or !$runtimePaths) { throw 'Invalid runtime configuration; no launch performed.' }
}
if ($ReuseExisting) {
    # Reuse requires the registered identities, listening owners and healthy app.
    # Do not treat a random process at the desired ports as our service.
    if (!(Test-Path -LiteralPath "$stateRoot/processes.json")) { throw 'No registered services to reuse. Start without -ReuseExisting.' }
    $registered = Get-Content -LiteralPath "$stateRoot/processes.json" -Raw | ConvertFrom-Json
    $oldLayer = $registered.pacs_runtime_layer
    if (($null -eq $oldLayer) -ne ($null -eq $layerIdentity) -or
        ($layerIdentity -and ($oldLayer.identity_sha256 -ne $layerIdentity.identity_sha256 -or $oldLayer.site_path -ne $layerIdentity.site_path))) {
        throw 'Requested PACS import layer differs from the registered backend; no service action performed.'
    }
    if ($registered.backend_url -ne "http://127.0.0.1:$BackendPort" -or $registered.url -ne "http://127.0.0.1:$FrontendPort") {
        throw 'Requested ports differ from the registered services; no launch or stop performed.'
    }
    if ($Demo -and $DatabasePath) { throw 'Choose either -Demo or -DatabasePath, not both.' }
    $expectedDatabase = $null
    if ($Demo) { $expectedDatabase = 'E:/BrainFusion-Runtime/results/stage2/workflow.db' }
    if ($DatabasePath) { $expectedDatabase = (Resolve-Path -LiteralPath $DatabasePath -ErrorAction Stop).Path.Replace('\', '/') }
    if ($expectedDatabase -and $registered.database.Replace('\', '/') -ne ('sqlite:///' + $expectedDatabase)) {
        throw 'Requested database differs from the registered services; no launch or stop performed.'
    }
    if ($runtimePaths) {
        foreach ($property in $runtimePaths.PSObject.Properties) {
            if (!$registered.runtime_paths -or $registered.runtime_paths.($property.Name) -ne $property.Value) {
                throw "Requested runtime path $($property.Name) differs from registered services; no action performed."
            }
        }
    }
    foreach ($service in @('backend', 'frontend')) {
        $processId = $registered."${service}_pid"; $started = $registered."${service}_start_utc"
        if (!$processId -or !$started) { throw 'Registered process identity is incomplete.' }
        $running = Get-Process -Id $processId -ErrorAction Stop
        if ($running.StartTime.ToUniversalTime().Ticks -ne ([DateTime]$started).ToUniversalTime().Ticks) {
            throw "Registered $service PID belongs to a different launch; no action performed."
        }
        if ($service -eq 'backend' -and ![string]::Equals($running.Path, $python, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Requested Python interpreter differs from the running backend; reuse cannot switch environments. No launch or stop performed.'
        }
        $command = (Get-CimInstance Win32_Process -Filter "ProcessId=$processId").CommandLine
        $expectedCommand = if ($service -eq 'backend') { 'uvicorn app.main:app' } else { (Join-Path $projectRoot 'frontend/node_modules/vite/bin/vite.js').Replace('\', '/') }
        if (!$command -or !$command.Replace('\', '/').Contains($expectedCommand)) { throw "Registered $service command is not this application." }
        $port = if ($service -eq 'backend') { $BackendPort } else { $FrontendPort }
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction Stop)
        if (!$listeners.Count -or @($listeners | Where-Object { $_.OwningProcess -ne $processId }).Count) {
            throw "Port $port does not belong exclusively to the registered $service."
        }
    }
    $health = Invoke-RestMethod -Uri "$($registered.backend_url)/" -TimeoutSec 5
    if ($health.code -ne 200 -or $health.data.name -ne 'BrainFusion-AI' -or $health.data.status -ne 'healthy') { throw 'Backend health identity failed.' }
    $webHealth = Invoke-WebRequest -Uri "$($registered.url)/" -UseBasicParsing -TimeoutSec 5
    if ($webHealth.StatusCode -ne 200 -or $webHealth.Content -notmatch '/src/main.js') { throw 'Frontend health identity failed.' }
    Write-Output "Reused verified services: $($registered.url) ; API $($registered.backend_url)/docs"
    Write-Output "Existing process IDs unchanged: backend=$($registered.backend_pid), frontend=$($registered.frontend_pid)"
    return
}
foreach ($port in @($BackendPort, $FrontendPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) { throw "Port $port is already in use." }
}
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
if (Test-Path -LiteralPath "$stateRoot/processes.json") {
    $existing = Get-Content -LiteralPath "$stateRoot/processes.json" -Raw | ConvertFrom-Json
    if ($existing.backend_pid -and $existing.backend_start_utc) {
        $running = Get-Process -Id $existing.backend_pid -ErrorAction SilentlyContinue
        if ($running -and $running.StartTime.ToUniversalTime().Ticks -eq ([DateTime]$existing.backend_start_utc).ToUniversalTime().Ticks) {
            throw "A registered backend is already active at $($existing.url). Stop it before another launch."
        }
    }
}
$env:DATABASE_URL = 'sqlite:///E:/BrainFusion-Runtime/local/brainfusion.db'
if ($Demo) {
    $demoDb = 'E:/BrainFusion-Runtime/results/stage2/workflow.db'
    if (!(Test-Path -LiteralPath $demoDb)) { throw 'Run verify_core_workflow.py to prepare the demonstration database.' }
    $env:DATABASE_URL = 'sqlite:///E:/BrainFusion-Runtime/results/stage2/workflow.db'
}
if ($DatabasePath) {
    if ($Demo) { throw 'Choose either -Demo or -DatabasePath, not both.' }
    $resolvedDatabase = (Resolve-Path -LiteralPath $DatabasePath -ErrorAction Stop).Path
    if ([IO.Path]::GetPathRoot($resolvedDatabase) -ne 'E:\') { throw 'Database must stay on E: on this workstation.' }
    $env:DATABASE_URL = 'sqlite:///' + $resolvedDatabase.Replace('\', '/')
}
if (!$env:MODEL_DIR) { $env:MODEL_DIR = 'E:/BrainFusion-Runtime/models/monai-brats' }
$env:GPU_BUDGET_MB = '6000'
if (!$env:RESEARCH_DIR) { $env:RESEARCH_DIR = 'E:/BrainFusion-Runtime/results/research' }
if (!$env:DATASET_DIR) { $env:DATASET_DIR = 'E:/BrainFusion-Data/WAW-GliomAI-v3' }
if ($runtimePaths) {
    foreach ($property in $runtimePaths.PSObject.Properties) {
        if ($property.Name -eq 'DATABASE_PATH') { $env:DATABASE_URL = 'sqlite:///' + $property.Value.Replace('\','/') }
        else { [Environment]::SetEnvironmentVariable($property.Name, $property.Value, 'Process') }
    }
}
$env:CORS_ORIGINS = "http://127.0.0.1:$FrontendPort,http://localhost:$FrontendPort"
$env:VITE_API_BASE = "http://127.0.0.1:$BackendPort"
& $python -B (Join-Path $PSScriptRoot 'preflight_runtime.py') --strict
if ($LASTEXITCODE -ne 0) { throw 'Startup preflight failed; no service was started. Fix the listed artifacts/dependencies.' }
$node = (Get-Command node -ErrorAction Stop).Source
$api = Start-BrainFusionBackgroundProcess -FilePath $python -ArgumentList @('-B', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort") -BootstrapPython $python -WorkingDirectory (Join-Path $projectRoot 'backend') -StandardOutput "$stateRoot/backend.out.log" -StandardError "$stateRoot/backend.err.log"
try {
    $viteScript = Join-Path $projectRoot 'frontend/node_modules/vite/bin/vite.js'
    $web = Start-BrainFusionBackgroundProcess -FilePath $node -ArgumentList @($viteScript, '--host', '127.0.0.1', '--port', "$FrontendPort", '--strictPort') -BootstrapPython $python -WorkingDirectory (Join-Path $projectRoot 'frontend') -StandardOutput "$stateRoot/frontend.out.log" -StandardError "$stateRoot/frontend.err.log"
    foreach ($address in @("http://127.0.0.1:$BackendPort/", "http://127.0.0.1:$FrontendPort/")) {
        $ready = $false
        $deadline = [DateTime]::UtcNow.AddSeconds(20)
        while ([DateTime]::UtcNow -lt $deadline) {
            $api.Refresh(); $web.Refresh()
            if ($api.HasExited -or $web.HasExited) { throw "Service exited during startup. See logs in $stateRoot." }
            try {
                $response = Invoke-WebRequest -Uri $address -UseBasicParsing -TimeoutSec 2
                if ($response.StatusCode -eq 200) { $ready = $true; break }
            } catch { Start-Sleep -Milliseconds 250 }
        }
        if (!$ready) { throw "Service readiness timed out: $address. See logs in $stateRoot." }
        $servicePort = ([Uri]$address).Port
        $expectedOwner = if ($servicePort -eq $BackendPort) { $api.Id } else { $web.Id }
        $owners = @(Get-NetTCPConnection -State Listen -LocalPort $servicePort -ErrorAction Stop)
        if (!$owners.Count -or @($owners | Where-Object { $_.OwningProcess -ne $expectedOwner }).Count) { throw 'New service listener does not belong to its registered direct process.' }

    }
} catch {
    Stop-Process -Id $api.Id -ErrorAction SilentlyContinue
    if ($web) { Stop-Process -Id $web.Id -ErrorAction SilentlyContinue }
    throw
}
@{ backend_pid = $api.Id; frontend_pid = $web.Id; backend_start_utc = $api.StartTime.ToUniversalTime().ToString('o'); frontend_start_utc = $web.StartTime.ToUniversalTime().ToString('o'); backend_python = $python; pacs_runtime_layer = $layerIdentity; url = "http://127.0.0.1:$FrontendPort"; backend_url = "http://127.0.0.1:$BackendPort"; database = $env:DATABASE_URL; runtime_paths = $runtimePaths } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$stateRoot/processes.json" -Encoding UTF8
Write-Output "Frontend: http://127.0.0.1:$FrontendPort ; API: http://127.0.0.1:$BackendPort/docs"
Write-Output "Process IDs: backend=$($api.Id), frontend=$($web.Id). Logs: $stateRoot"

} finally {
    if ($PacsRuntimeLayer) {
        if ($hadPythonPath) { $env:PYTHONPATH = $originalPythonPath }
        else { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue }
    }
}
