param([Parameter(Mandatory=$true)][string]$EvidenceDirectory)
$ErrorActionPreference = 'Stop'
$target = [IO.Path]::GetFullPath($EvidenceDirectory)
if (!$target.Replace('\','/').StartsWith('E:/BrainFusion-Runtime/results/nightly/')) { throw 'Use a unique E: nightly evidence directory.' }
New-Item -ItemType Directory -Path $target -ErrorAction Stop | Out-Null
$statePath = 'E:/BrainFusion-Runtime/local/processes.json'
$before = Get-Content -LiteralPath $statePath -Raw
$registered = $before | ConvertFrom-Json
$backendPort = ([Uri]$registered.backend_url).Port
$frontendPort = ([Uri]$registered.url).Port
$dbPath = $registered.database.Substring('sqlite:///'.Length)
$checks = @()
$script = Join-Path $PSScriptRoot 'start_local.ps1'
& $script -ReuseExisting -BackendPort $backendPort -FrontendPort $frontendPort -DatabasePath $dbPath
$checks += 'Healthy registered services reused'
foreach ($scenario in @('wrong-port','wrong-database','duplicate-launch')) {
    $failure = $null
    try {
        if ($scenario -eq 'wrong-port') { & $script -ReuseExisting -BackendPort ($backendPort + 1) -FrontendPort $frontendPort }
        elseif ($scenario -eq 'wrong-database') { & $script -ReuseExisting -BackendPort $backendPort -FrontendPort $frontendPort -Demo }
        else { & $script -BackendPort $backendPort -FrontendPort $frontendPort -DatabasePath $dbPath }
    } catch { $failure = $_.Exception.Message }
    if (!$failure) { throw "Scenario $scenario did not reject the request." }
    $expected = switch ($scenario) { 'wrong-port' { 'Requested ports differ' }; 'wrong-database' { 'Requested database differs' }; 'duplicate-launch' { 'already in use' } }
    if (!$failure.Contains($expected)) { throw "Unexpected rejection for ${scenario}: $failure" }
    $checks += @{ scenario=$scenario; rejected=$true; reason=$failure }
}
if ((Get-Content -LiteralPath $statePath -Raw) -ne $before) { throw 'Process registration changed during reuse verification.' }
foreach ($service in @('backend','frontend')) {
    $running = Get-Process -Id $registered."${service}_pid" -ErrorAction Stop
    if ($running.StartTime.ToUniversalTime().Ticks -ne ([DateTime]$registered."${service}_start_utc").ToUniversalTime().Ticks) { throw 'Service identity changed.' }
}
$result = @{ status='passed'; checks=$checks; process_identity_unchanged=$true; no_stop_or_new_launch=$true; services=$registered; scope='Registered service reuse, ownership and health; complete environment/path relocation and artifact recovery remain separate E3 work.' }
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $target 'validation.json') -Encoding UTF8
$result | ConvertTo-Json -Depth 8
