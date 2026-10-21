<# Bounded, read-only exit observation. Never restarts/stops services or holds a development lock. #>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$PlanPath,[Parameter(Mandatory=$true)][string]$OutputRoot,[ValidateRange(1,21600)][int]$MaxSeconds=7200)
$ErrorActionPreference='Stop'
$planFile=(Resolve-Path -LiteralPath $PlanPath).Path
$root=[IO.Path]::GetFullPath($OutputRoot)
$base=[IO.Path]::GetFullPath('E:/BrainFusion-Runtime/results/nightly/')
if(!$root.StartsWith($base,[StringComparison]::OrdinalIgnoreCase) -or $root -eq $base.TrimEnd('\')){throw 'Exit observation output must be a new nightly child directory on E:'}
if(Test-Path -LiteralPath $root){throw 'Exit observation output already exists; never overwrite'}
$plan=Get-Content -LiteralPath $planFile -Raw|ConvertFrom-Json
if(!$plan.services -or @($plan.services).Count -gt 8){throw 'Require one to eight exact process identities'}
$names=@{};$observations=@()
# Open each process handle before creating output; reject reused identities.
foreach($entry in $plan.services){
    if($entry.name -notmatch '^[A-Za-z0-9_-]{1,40}$' -or $names.ContainsKey($entry.name)){throw 'Duplicate/invalid observation name'}
    $names[$entry.name]=$true
    $proc=[Diagnostics.Process]::GetProcessById([int]$entry.pid)
    if($proc.StartTime.ToUniversalTime().Ticks -ne ([DateTime]$entry.started_utc).ToUniversalTime().Ticks){throw 'Observed PID belongs to another launch'}
    $null=$proc.Handle
    $observations+=@{name=$entry.name;pid=$proc.Id;started_utc=$entry.started_utc;process=$proc;task=$proc.WaitForExitAsync();observed=$false}
}
New-Item -ItemType Directory -Path $root|Out-Null
$started=[DateTime]::UtcNow;$deadline=$started.AddSeconds($MaxSeconds)
$identity=@{pid=$PID;started_utc=(Get-Process -Id $PID).StartTime.ToUniversalTime().ToString('o');plan=$planFile;plan_sha256=(Get-FileHash -LiteralPath $planFile).Hash.ToLower();state='running';deadline_utc=$deadline.ToString('o');writes_project_or_business_data=$false;holds_development_lock=$false;restarts_services=$false}
$identity|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $root 'job.json') -Encoding utf8
$events=[Collections.Generic.List[object]]::new()
try{
    while([DateTime]::UtcNow -lt $deadline){
        foreach($entry in $observations){
            if(!$entry.observed -and $entry.task.IsCompleted){
                $null=$entry.task.GetAwaiter().GetResult();$entry.process.WaitForExit()
                $event=@{name=$entry.name;pid=$entry.pid;started_utc=$entry.started_utc;event='exited';exit_code=$entry.process.ExitCode;observed_utc=[DateTime]::UtcNow.ToString('o')}
                $events.Add($event);$event|ConvertTo-Json -Compress|Add-Content -LiteralPath (Join-Path $root 'events.jsonl') -Encoding utf8
                $entry.observed=$true
            }
        }
        $pending=@($observations|Where-Object {!$_.observed})
        if(!$pending.Count){break}
        [Threading.Tasks.Task[]]$tasks=@($pending|ForEach-Object {$_.task})+@([Threading.Tasks.Task]::Delay(1000))
        $null=[Threading.Tasks.Task]::WaitAny($tasks)
    }
    $identity.state=if(@($observations|Where-Object {!$_.observed}).Count){'deadline_reached'}else{'all_exits_observed'}
}catch{
    $identity.state='failed';$identity.error=$_.Exception.Message
    throw
}finally{
    $identity.ended_utc=[DateTime]::UtcNow.ToString('o')
    $identity|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $root 'job.json') -Encoding utf8
    @{state=$identity.state;events=@($events);still_unobserved=@($observations|Where-Object {!$_.observed}|ForEach-Object {@{name=$_.name;pid=$_.pid;started_utc=$_.started_utc}});scope='Exit codes/timestamps only; an exit code alone does not identify who terminated a process.'}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $root 'summary.json') -Encoding utf8
    foreach($entry in $observations){$entry.process.Dispose()}
}
