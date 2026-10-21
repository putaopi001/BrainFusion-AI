function Start-BrainFusionBackgroundProcess {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [string[]]$ArgumentList=@(),
        [Parameter(Mandatory=$true)][string]$WorkingDirectory,
        [Parameter(Mandatory=$true)][string]$StandardOutput,
        [Parameter(Mandatory=$true)][string]$StandardError,
        [string]$BootstrapPython=(Join-Path $PSScriptRoot '../../.conda/brainfusion/python.exe')
    )
    $bfBootstrap=(Resolve-Path -LiteralPath $BootstrapPython -ErrorAction Stop).Path
    $bfProgram=(Resolve-Path -LiteralPath $FilePath -ErrorAction Stop).Path
    $bfDirectory=(Resolve-Path -LiteralPath $WorkingDirectory -ErrorAction Stop).Path
    $bfRequests='E:/BrainFusion-Runtime/local/process-starts'
    New-Item -ItemType Directory -Path $bfRequests -Force | Out-Null
    $bfRequest=Join-Path $bfRequests (([guid]::NewGuid().ToString('N'))+'.json')
    $bfReceipt=[IO.Path]::ChangeExtension($bfRequest,'.result.json')
    @{command=@($bfProgram)+@($ArgumentList);cwd=$bfDirectory;stdout=$StandardOutput;stderr=$StandardError} |
        ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $bfRequest -Encoding utf8
    $bfHelper=Join-Path $PSScriptRoot 'start_background_process.py'
    # Invoke the bootstrap synchronously in this user session. The bootstrap
    # requests CREATE_BREAKAWAY_FROM_JOB when applicable and verifies the
    # service is no longer in any job before accepting its identity. The child
    # receives the current process environment naturally; secrets are not serialized.
    $bfPreference=Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue
    $bfHadPreference=$null -ne $bfPreference
    if($bfHadPreference){$bfOldPreference=$bfPreference.Value}
    $PSNativeCommandUseErrorActionPreference=$false
    try {
        & $bfBootstrap -B $bfHelper '--request' $bfRequest
        $bfBootstrapExit=$LASTEXITCODE
    } finally {
        if($bfHadPreference){$PSNativeCommandUseErrorActionPreference=$bfOldPreference}
        else {Remove-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue}
    }
    if($bfBootstrapExit -ne 0 -and -not(Test-Path -LiteralPath $bfReceipt)){
        throw "Local background bootstrap failed with exit code $bfBootstrapExit; no service identity was accepted."
    }
    $bfDeadline=[datetime]::UtcNow.AddSeconds(20)
    while(-not(Test-Path -LiteralPath $bfReceipt)) {
        if([datetime]::UtcNow -gt $bfDeadline){throw "Background launch receipt timed out; inspect $bfRequest before retrying."}
        Start-Sleep -Milliseconds 100
    }
    $bfResult=Get-Content -LiteralPath $bfReceipt -Raw | ConvertFrom-Json
    if($bfResult.status -ne 'started'){throw "Background launch failed: $($bfResult.error)"}
    $bfProcess=Get-Process -Id $bfResult.pid -ErrorAction Stop
    if($bfProcess.StartTime.ToUniversalTime().ToFileTimeUtc() -ne [long]$bfResult.started_filetime){throw 'Background process identity changed; no unknown process stopped.'}
    return $bfProcess
}
