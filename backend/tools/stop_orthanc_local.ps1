param([string]$Root = 'E:/BrainFusion-Runtime/orthanc-local')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $Root).Path
if ([IO.Path]::GetPathRoot($root) -ne 'E:\') { throw 'Orthanc root must stay on E:.' }
$record = Get-Content -LiteralPath (Join-Path $root 'process.json') -Raw | ConvertFrom-Json
$process = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
if (!$process) { Write-Output 'Registered Orthanc is already stopped.'; return }
if (!$record.started_utc -or $process.StartTime.ToUniversalTime().Ticks -ne ([DateTime]$record.started_utc).ToUniversalTime().Ticks) {
    throw 'Orthanc PID has been reused; no shutdown sent.'
}
$binary = 'E:/BrainFusion-Runtime/toolchains/orthanc-1.13.0-dicomweb-1.24/Orthanc.exe'
$config = Join-Path $root 'orthanc.json'
$command = (Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id)").CommandLine
if (![string]::Equals($process.Path, $binary.Replace('/', '\'), [StringComparison]::OrdinalIgnoreCase) -or
    !$command.Replace('\', '/').Contains($config.Replace('\', '/')) -or
    ![string]::Equals($record.config, $config, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Orthanc executable/configuration identity mismatch; no shutdown sent.'
}
$listeners = @(Get-NetTCPConnection -LocalPort 8042 -State Listen -ErrorAction Stop)
if (!$listeners.Count -or @($listeners | Where-Object { $_.OwningProcess -ne $process.Id }).Count) {
    throw 'Archive port identity mismatch; no shutdown sent.'
}
$configuration = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
if ($configuration.AuthenticationEnabled -ne $true -or $configuration.RemoteAccessAllowed -ne $false -or $configuration.HttpPort -ne 8042) { throw 'Unexpected archive profile.' }
$users = @($configuration.RegisteredUsers.PSObject.Properties)
if ($users.Count -ne 1) { throw 'Expected one local archive service account.' }
$token = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($users[0].Name + ':' + $users[0].Value))
$null = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8042/tools/shutdown' -Headers @{Authorization="Basic $token"} -Body '' -TimeoutSec 5
if (!$process.WaitForExit(20000)) { throw 'Graceful shutdown timed out; no forced termination performed.' }
Write-Output 'Verified Orthanc gracefully stopped; no other process terminated.'
