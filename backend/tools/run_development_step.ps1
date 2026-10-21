<#
Run one finite, synchronous development step under the shared exclusive lock.
The step must wait for its mutating children; do not launch detached writers.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$RunId,
    [Parameter(Mandatory=$true)][string]$ScriptPath,
    [string[]]$StepArguments = @(),
    [string]$AutomationRoot = 'E:/BrainFusion-Runtime/automation'
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$step = (Resolve-Path -LiteralPath $ScriptPath -ErrorAction Stop).Path
New-Item -ItemType Directory -Path $AutomationRoot -Force | Out-Null
$stream = $null
try {
    $stream = [IO.File]::Open((Join-Path $AutomationRoot 'development.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
} catch [IO.IOException] {
    # Never replace the current holder's metadata or run the supplied step.
    Write-Error "Development lock unavailable: $($_.Exception.Message)" -ErrorAction Continue
    exit 73
}
$result = 1
$metadata = $null
try {
    $process = Get-Process -Id $PID
    $metadata = [ordered]@{
        run_id = $RunId
        holder_pid = $PID
        holder_started_utc = $process.StartTime.ToUniversalTime().ToString('o')
        started_utc = [DateTime]::UtcNow.ToString('o')
        mechanism = 'FileStream FileShare.None; synchronous step'
        script_path = $step
        state = 'held'
    }
    $metadata | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $AutomationRoot 'development-lock.json') -Encoding utf8
    # Execute real work in this process, rather than waiting on a lock helper.
    $global:LASTEXITCODE = 0
    & $step @StepArguments
    if (-not $?) { throw 'Development step failed' }
    if ($LASTEXITCODE -ne 0) { throw "Native command failed with exit code $LASTEXITCODE" }
    $result = 0
} catch {
    Write-Error "Development step failed: $($_.Exception.Message)" -ErrorAction Continue
} finally {
    try {
        if ($null -ne $metadata) {
            $metadata.state = 'released'
            $metadata['released_utc'] = [DateTime]::UtcNow.ToString('o')
            $metadata['exit_code'] = $result
            $metadata | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $AutomationRoot 'development-lock.json') -Encoding utf8
        }
    } finally {
        $stream.Dispose()
    }
}
exit $result
