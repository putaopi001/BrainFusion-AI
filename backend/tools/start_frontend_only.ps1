param([int]$BackendPort, [int]$FrontendPort, [string]$RuntimeConfig, [string]$FrontendProject, [string]$NodePath, [string]$PreviewDist, [string]$LogRoot)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'background_process.ps1')
$bfProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$bfStatePath = 'E:/BrainFusion-Runtime/local/processes.json'
$bfState = Get-Content -LiteralPath $bfStatePath -Raw | ConvertFrom-Json
if ($bfState.backend_url -ne "http://127.0.0.1:$BackendPort" -or $bfState.url -ne "http://127.0.0.1:$FrontendPort") { throw 'Registered addresses differ; no service action.' }
$bfBackend = Get-Process -Id $bfState.backend_pid -ErrorAction Stop
if ($bfBackend.StartTime.ToUniversalTime().Ticks -ne ([DateTime]$bfState.backend_start_utc).ToUniversalTime().Ticks -or ![string]::Equals($bfBackend.Path,$bfState.backend_python,[StringComparison]::OrdinalIgnoreCase)) { throw 'Backend identity mismatch; no service action.' }
$bfBackendCommand = (Get-CimInstance Win32_Process -Filter "ProcessId=$($bfBackend.Id)").CommandLine
if (!$bfBackendCommand.Contains('uvicorn app.main:app')) { throw 'Unregistered backend command.' }
$bfApiListeners = @(Get-NetTCPConnection -State Listen -LocalPort $BackendPort -ErrorAction Stop)
if (!$bfApiListeners.Count -or @($bfApiListeners | Where-Object { $_.OwningProcess -ne $bfBackend.Id }).Count) { throw 'Backend listening ownership mismatch.' }
$bfHealth = Invoke-RestMethod -Uri "$($bfState.backend_url)/" -TimeoutSec 5
if ($bfHealth.code -ne 200 -or $bfHealth.data.name -ne 'BrainFusion-AI' -or $bfHealth.data.status -ne 'healthy') { throw 'Backend health identity failed.' }
if ($RuntimeConfig) {
    $bfRequestedPaths = (& $bfState.backend_python -B (Join-Path $PSScriptRoot 'read_runtime_config.py') $RuntimeConfig) | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Invalid existing runtime config.' }
    foreach ($bfProperty in $bfRequestedPaths.PSObject.Properties) {
        if ($bfState.runtime_paths.($bfProperty.Name) -ne $bfProperty.Value) { throw 'Requested runtime differs from live backend; no change.' }
    }
}
if (Get-NetTCPConnection -State Listen -LocalPort $FrontendPort -ErrorAction SilentlyContinue) { throw 'Frontend port already occupied; stop only verified registered frontend first.' }
if (!$FrontendProject) { $FrontendProject = Join-Path $bfProjectRoot 'frontend' }
$bfFrontend = (Resolve-Path -LiteralPath $FrontendProject).Path
if ([IO.Path]::GetPathRoot($bfFrontend) -ne 'E:\') { throw 'Frontend must stay on E.' }
if (!$NodePath) { $NodePath = (Get-Command node -ErrorAction Stop).Source }
$bfNode = (Resolve-Path -LiteralPath $NodePath).Path
if ([IO.Path]::GetPathRoot($bfNode) -ne 'E:\' -or [IO.Path]::GetFileName($bfNode) -ne 'node.exe') { throw 'Trusted existing E-drive node.exe required.' }
$bfVite = (Resolve-Path -LiteralPath (Join-Path $bfFrontend 'node_modules/vite/bin/vite.js')).Path
if (!$LogRoot) { throw 'Unique E-drive nightly log directory required.' }
$bfLogs = [IO.Path]::GetFullPath($LogRoot)
if (!$bfLogs.StartsWith('E:\BrainFusion-Runtime\results\nightly\',[StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $bfLogs)) { throw 'Fresh owned nightly log root required.' }
$bfMode = 'dev'; $bfResolvedPreview = $null
$bfFrontendArguments = @($bfVite,'--host','127.0.0.1','--port',"$FrontendPort",'--strictPort')
if ($PreviewDist) {
    $bfResolvedPreview = (Resolve-Path -LiteralPath (Join-Path $bfFrontend $PreviewDist)).Path
    if (!$bfResolvedPreview.StartsWith($bfFrontend + '\',[StringComparison]::OrdinalIgnoreCase) -or !(Test-Path -LiteralPath (Join-Path $bfResolvedPreview 'index.html'))) { throw 'Verified dist must stay within selected frontend.' }
    $bfMode = 'preview'
    $bfFrontendArguments = @($bfVite,'preview','--outDir',$bfResolvedPreview,'--host','127.0.0.1','--port',"$FrontendPort",'--strictPort')
}
New-Item -ItemType Directory -Path $bfLogs | Out-Null
$env:VITE_API_BASE = $bfState.backend_url
$bfWeb = Start-BrainFusionBackgroundProcess -FilePath $bfNode -ArgumentList $bfFrontendArguments -BootstrapPython $bfState.backend_python -WorkingDirectory $bfFrontend -StandardOutput (Join-Path $bfLogs 'frontend.out.log') -StandardError (Join-Path $bfLogs 'frontend.err.log')
$bfWebStarted = $bfWeb.StartTime.ToUniversalTime()
try {
    $bfReady = $false; $bfDeadline = [DateTime]::UtcNow.AddSeconds(20)
    while ([DateTime]::UtcNow -lt $bfDeadline) {
        $bfWeb.Refresh(); if ($bfWeb.HasExited) { throw 'Frontend exited; inspect retained logs.' }
        try {
            $bfReply = Invoke-WebRequest -Uri "$($bfState.url)/" -UseBasicParsing -TimeoutSec 2
            $bfMarker = if ($bfMode -eq 'preview') { '/assets/' } else { '/src/main.js' }
            if ($bfReply.StatusCode -eq 200 -and $bfReply.Content.Contains($bfMarker)) { $bfReady = $true; break }
        } catch { Start-Sleep -Milliseconds 250 }
    }
    if (!$bfReady) { throw 'Frontend readiness failed.' }
    $bfWebListeners = @(Get-NetTCPConnection -State Listen -LocalPort $FrontendPort -ErrorAction Stop)
    if (!$bfWebListeners.Count -or @($bfWebListeners | Where-Object { $_.OwningProcess -ne $bfWeb.Id }).Count) { throw 'New frontend port ownership mismatch.' }
    $bfBackend.Refresh(); if ($bfBackend.HasExited -or $bfBackend.StartTime.ToUniversalTime().Ticks -ne ([DateTime]$bfState.backend_start_utc).ToUniversalTime().Ticks) { throw 'Backend changed during frontend-only launch.' }
} catch {
    $bfWeb.Refresh()
    if (!$bfWeb.HasExited -and $bfWeb.StartTime.ToUniversalTime().Ticks -eq $bfWebStarted.Ticks) { Stop-Process -Id $bfWeb.Id }
    throw
}
$bfState.frontend_pid = $bfWeb.Id
$bfState.frontend_start_utc = $bfWebStarted.ToString('o')
foreach ($bfField in @{frontend_project=$bfFrontend;frontend_node=$bfNode;frontend_mode=$bfMode;frontend_logs=$bfLogs;frontend_preview_dist=$bfResolvedPreview}.GetEnumerator()) { $bfState | Add-Member -NotePropertyName $bfField.Key -NotePropertyValue $bfField.Value -Force }
$bfState | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $bfStatePath -Encoding UTF8
Write-Output "Frontend-only $bfMode ready: $($bfState.url); frontend=$($bfWeb.Id); backend=$($bfBackend.Id) unchanged. Logs: $bfLogs"
