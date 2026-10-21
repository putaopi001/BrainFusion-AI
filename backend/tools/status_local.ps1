<# Read-only identity, listener and HTTP checks. Does not start/stop services. #>
param()
$ErrorActionPreference='Stop'
$application=Get-Content -LiteralPath 'E:/BrainFusion-Runtime/local/processes.json' -Raw | ConvertFrom-Json
$archive=Get-Content -LiteralPath 'E:/BrainFusion-Runtime/orthanc-local/process.json' -Raw | ConvertFrom-Json
$rows=@()
foreach($item in @(
    @{name='backend';pid=$application.backend_pid;started=$application.backend_start_utc;port=([uri]$application.backend_url).Port},
    @{name='frontend';pid=$application.frontend_pid;started=$application.frontend_start_utc;port=([uri]$application.url).Port},
    @{name='orthanc';pid=$archive.pid;started=$archive.started_utc;port=8042}
)) {
    $process=Get-Process -Id $item.pid -ErrorAction SilentlyContinue
    $matches=($process -and $process.StartTime.ToUniversalTime().Ticks -eq ([DateTimeOffset]$item.started).UtcTicks)
    $listeners=@(Get-NetTCPConnection -LocalPort $item.port -State Listen -ErrorAction SilentlyContinue)
    $owns=($matches -and $listeners.Count -gt 0 -and @($listeners | Where-Object {$_.OwningProcess -ne $item.pid}).Count -eq 0)
    $rows+=@{name=$item.name;pid=$item.pid;identity_matches=[bool]$matches;owns_listener=[bool]$owns;port=$item.port}
}
$health=[ordered]@{backend='unavailable';frontend='unavailable';pacs='unavailable';accounts_configured=$false}
if(($rows | Where-Object name -eq 'backend').owns_listener) {
    try {
        $reply=Invoke-RestMethod -Uri ($application.backend_url+'/') -TimeoutSec 5
        if($reply.code -eq 200 -and $reply.data.name -eq 'BrainFusion-AI'){$health.backend=$reply.data.status}
        $reply=Invoke-RestMethod -Uri ($application.backend_url+'/pacs/status') -TimeoutSec 5
        $health.pacs=$reply.data.state
        $reply=Invoke-RestMethod -Uri ($application.backend_url+'/local-auth/session') -TimeoutSec 5
        $health.accounts_configured=[bool]$reply.data.configured
    } catch {$health['backend_error']=$_.Exception.Message}
}
if(($rows | Where-Object name -eq 'frontend').owns_listener) {
    try {
        $reply=Invoke-WebRequest -Uri $application.url -TimeoutSec 5
        if($reply.StatusCode -eq 200 -and ($reply.Content.Contains('/src/main.js') -or $reply.Content.Contains('/assets/'))){$health.frontend='ready'}
    } catch {$health['frontend_error']=$_.Exception.Message}
}
$healthy=(@($rows | Where-Object {!$_.owns_listener}).Count -eq 0 -and $health.backend -eq 'healthy' -and $health.frontend -eq 'ready' -and $health.pacs -eq 'ready' -and $health.accounts_configured)
@{checked_utc=[datetime]::UtcNow.ToString('o');healthy=$healthy;services=$rows;health=$health;frontend_url=$application.url;backend_url=$application.backend_url;read_only=$true}|ConvertTo-Json -Depth 5
if(-not $healthy){exit 2}
