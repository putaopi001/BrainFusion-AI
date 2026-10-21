param([switch]$FrontendOnly)
$ErrorActionPreference = 'Stop'
$stateFile = 'E:/BrainFusion-Runtime/local/processes.json'
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
$services = if ($FrontendOnly) { @('frontend') } else { @('frontend', 'backend') }
foreach ($service in $services) {
    $processId = $state."${service}_pid"
    $started = $state."${service}_start_utc"
    if (!$processId -or !$started) { throw 'Startup identity missing. Refusing to stop an unverified process.' }
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (!$process) { continue }
    # PowerShell 7 may deserialize ISO strings as DateTime; compare ticks.
    $expectedStart = ([DateTime]$started).ToUniversalTime()
    if ($process.StartTime.ToUniversalTime().Ticks -ne $expectedStart.Ticks) {
        throw "Process $processId belongs to another launch; no stop performed."
    }
    Stop-Process -Id $processId
    Write-Output "Stopped $service process $processId"
}
