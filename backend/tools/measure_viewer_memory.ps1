param([Parameter(Mandatory=$true)][string]$BindingsJson)
$ErrorActionPreference='Stop'
$bindings=$BindingsJson|ConvertFrom-Json
$rows=@()
foreach($binding in $bindings){
 $processId=[int]$binding.pid
 if($processId -le 0){throw 'Invalid process ID'}
 $p=Get-Process -Id $processId -ErrorAction SilentlyContinue
 if(!$p){$rows+=@{pid=$processId;role=$binding.role;state='exited_before_sample'};continue}
 if($binding.expected_started_utc -and $p.StartTime.ToUniversalTime().Ticks -ne ([DateTime]$binding.expected_started_utc).ToUniversalTime().Ticks){throw 'Registered process identity changed'}
 $p.Refresh()
 $rows+=@{pid=$processId;role=$binding.role;state='sampled';started_utc=$p.StartTime.ToUniversalTime().ToString('o');working_set_bytes=$p.WorkingSet64;private_commit_bytes=$p.PrivateMemorySize64;lifetime_peak_working_set_bytes=$p.PeakWorkingSet64;cpu_seconds=$p.TotalProcessorTime.TotalSeconds}
}
@{sampled_utc=[DateTime]::UtcNow.ToString('o');processes=$rows;method='Windows Get-Process: working set (resident), private commit, lifetime peak working set; sample boundaries only'}|ConvertTo-Json -Depth 5 -Compress
