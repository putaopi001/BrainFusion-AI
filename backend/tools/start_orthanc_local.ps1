param([string]$Root = 'E:/BrainFusion-Runtime/orthanc-local')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'background_process.ps1')
$binary = 'E:/BrainFusion-Runtime/toolchains/orthanc-1.13.0-dicomweb-1.24/Orthanc.exe'
$plugin = 'E:/BrainFusion-Runtime/toolchains/orthanc-1.13.0-dicomweb-1.24/OrthancDicomWeb-1.24.dll'
$root = (Resolve-Path -LiteralPath $Root).Path
if ([IO.Path]::GetPathRoot($root) -ne 'E:\') { throw 'Orthanc root must stay on E:.' }
$config = Join-Path $root 'orthanc.json'
foreach ($path in @($binary, $plugin, $config)) {
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing: $path" }
}
$configuration = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
if ($configuration.HttpPort -ne 8042 -or $configuration.RemoteAccessAllowed -ne $false -or $configuration.AuthenticationEnabled -ne $true -or $configuration.DicomServerEnabled -ne $false) {
    throw 'Only the authenticated loopback HTTP 8042 archive profile is supported.'
}
if (Get-NetTCPConnection -LocalPort 8042 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 8042 is already occupied; no process started or stopped.'
}
$recordPath = Join-Path $root 'process.json'
if (Test-Path -LiteralPath $recordPath) {
    $prior = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    $priorProcess = Get-Process -Id $prior.pid -ErrorAction SilentlyContinue
    if ($priorProcess -and $priorProcess.StartTime.ToUniversalTime().Ticks -eq ([DateTime]$prior.started_utc).ToUniversalTime().Ticks) {
        throw 'Registered Orthanc is still running; no duplicate started.'
    }
}
$logs = Join-Path $root ('logs/' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
New-Item -ItemType Directory -Path $logs | Out-Null
$proc = Start-BrainFusionBackgroundProcess -FilePath $binary -ArgumentList @($config) -WorkingDirectory $root -StandardOutput (Join-Path $logs 'stdout.log') -StandardError (Join-Path $logs 'stderr.log')
Start-Sleep -Seconds 2
$proc.Refresh()
if ($proc.HasExited) { throw "Orthanc exited. See $logs" }
@{pid=$proc.Id;started_utc=$proc.StartTime.ToUniversalTime().ToString('o');logs=$logs;config=$config} | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding UTF8
Write-Output 'Orthanc process started. Run prepare_local_orthanc.py --connect to verify authenticated readiness.'
