param(
    [string]$Python = 'E:\BrainFusion-Runtime\envs\runtime311-cpu-delivery-20261017T1516_s4\python.exe',
    [string]$Node = '',
    [string]$DemoRoot = 'E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo',
    [switch]$RunLiveAcceptance,
    [string]$EvidencePath = ''
)

$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BackendRoot = Join-Path $Repo 'backend'
$FrontendRoot = Join-Path $Repo 'frontend'
$PrepareCopy = Join-Path $BackendRoot 'tools\prepare_unified_demo.py'
$PrepareAccount = Join-Path $BackendRoot 'tools\prepare_unified_demo_account.py'
$DemoRoot = [System.IO.Path]::GetFullPath($DemoRoot)
$ExpectedArtifacts = @(
    @{ Id = 'upenn-clinical-cox-research'; Directory = 'E:\BrainFusion-Runtime\research-edition\results\survival-models\upenn-clinical-cox-research-v1.0.1'; Sha = '41c52f20371dd33a25c60bf981a6a811c6863bc01834062d33e6e4ae7f3ce8ff'; ManifestSha = '200a732297835ca7b3c2319b447191d8a8616b7a137a180f411e60533cee3df0' },
    @{ Id = 'upenn-clinical-captk-fusion-cox-research'; Directory = 'E:\BrainFusion-Runtime\research-edition\results\survival-models\upenn-clinical-captk-fusion-cox-research-v1.0.0'; Sha = '0988d6d145e103cea90c5c15daff94a17d1cf8741ea65c63d957f7915de3b034'; ManifestSha = '4c8051d5ae6c5d179fce32b18d1f3cae7160e662e21374de92e7dd215c323812' },
    @{ Id = 'ucsf-pdgm-clinical-cox-research'; Directory = 'E:\BrainFusion-Runtime\research-edition\results\survival-models\ucsf-pdgm-clinical-cox-research-v1.0.0'; Sha = '9ce60525516db23436e818d1e5f84dda71a6fc505889ffefb625bf77646d0016'; ManifestSha = '7f24e6a48987b3ad501439fe18e62b3134fba781430128f1637f0ce19b5a21ac' }
)

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-PortFree([int]$Port) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try { $listener.Start(); return $true } catch { return $false } finally { $listener.Stop() }
}

function Get-FreePort([int]$Start, [int]$End) {
    foreach ($candidate in $Start..$End) { if (Test-PortFree $candidate) { return $candidate } }
    throw "No free loopback port in $Start-$End"
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Configured Python interpreter is missing: $Python" }
if (-not $Node) { $Node = (Get-Command node.exe -ErrorAction Stop).Source }
if (-not (Test-Path -LiteralPath $Node -PathType Leaf)) { throw "Node executable is missing: $Node" }
if (-not (Test-Path (Join-Path $FrontendRoot 'node_modules\.bin\vite.cmd'))) { throw 'Frontend dependencies are missing. Use the existing frontend node_modules; this launcher does not install packages.' }

foreach ($artifact in $ExpectedArtifacts) {
    $artifactFile = Join-Path $artifact.Directory 'cox-model.json'
    $manifestFile = Join-Path $artifact.Directory 'model-manifest.json'
    if (-not (Test-Path $artifactFile -PathType Leaf) -or -not (Test-Path $manifestFile -PathType Leaf)) { throw "Research model artifact is missing: $($artifact.Id)" }
    if ((Get-Sha256 $artifactFile) -ne $artifact.Sha) { throw "Research model hash does not match the reviewed version: $($artifact.Id)" }
    if ((Get-Sha256 $manifestFile) -ne $artifact.ManifestSha) { throw "Research model manifest hash does not match the reviewed version: $($artifact.Id)" }
    $manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
    if ($manifest.model_id -ne $artifact.Id -or $manifest.artifact_sha256 -ne $artifact.Sha -or -not $manifest.research_only) { throw "Research model manifest content is inconsistent: $($artifact.Id)" }
}

New-Item -ItemType Directory -Force -Path $DemoRoot | Out-Null
$lockPath = Join-Path $DemoRoot 'demo.lock'
$lock = $null
$backendProcess = $null
$frontendProcess = $null
$authPath = $null
$savedEnvironment = @{}
$keys = @(
    'DATABASE_URL','UPLOAD_DIR','LOCAL_AUTH_FILE','RESEARCH_DIR','DATASET_DIR','FEATURE_JOBS_DIR',
    'RADIOMICS_COMPATIBILITY','RADIOMICS_PYTHON','MODEL_DIR','PACS_ALLOW_DOCKER_HOST','PACS_CONFIG_FILE',
    'PACS_RESEARCH_DEMO_PIXEL_READ','PACS_IMPORT_REGISTRY_FILE','PACS_IMPORT_JOBS_DIR','PACS_DERIVED_DIR','DICOM_QUARANTINE_DIR',
    'DICOM_CONVERSION_INDEX_FILE','SURVIVAL_MODEL_DIR','SURVIVAL_FUSION_MODEL_DIR',
    'SURVIVAL_RESEARCH_PREDICTION_ENABLED','SURVIVAL_UCSF_MODEL_DIR','CORS_ORIGINS','PROJECT_NAME','VITE_API_BASE','VITE_UNIFIED_RESEARCH_DEMO',
    'UPENN_SUB002_INPUT_DIR','UPENN_SUB002_RESULT_DIR','UPENN_SUB002_EVIDENCE_DIR',
    'BRAINFUSION_API_URL','BRAINFUSION_WEB_URL','BRAINFUSION_TEST_USERNAME','BRAINFUSION_TEST_PASSWORD',
    'BRAINFUSION_UNIFIED_RESULT_PATH','BRAINFUSION_UNIFIED_LIVE_E2E','BRAINFUSION_BROWSER_CHANNEL'
)
foreach ($key in $keys) { $savedEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }

try {
    $lock = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)

    $copyResultText = (& $Python $PrepareCopy --target $DemoRoot | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Isolated demo data preparation failed: $copyResultText" }
    $copyResult = $copyResultText | ConvertFrom-Json
    Write-Host "Demo data: $($copyResult.status); cases=$($copyResult.cases); copied_upload_files=$($copyResult.upload_files)"

    $runtimeRoot = Join-Path $DemoRoot 'runtime'
    $uploadRoot = Join-Path $runtimeRoot 'uploads'
    $dbPath = Join-Path $runtimeRoot 'brainfusion.db'
    $authPath = Join-Path $runtimeRoot 'local-users.json'
    $configRoot = Join-Path $runtimeRoot 'pacs-disabled'
    $logs = Join-Path $DemoRoot 'logs'
    $featureJobs = Join-Path $runtimeRoot 'feature_jobs'
    foreach ($path in @($logs, $featureJobs, $configRoot, (Join-Path $runtimeRoot 'pacs-import-jobs'), (Join-Path $runtimeRoot 'pacs-derived'), (Join-Path $runtimeRoot 'dicom-quarantine'))) {
        New-Item -ItemType Directory -Force -Path $path | Out-Null
    }

    $accountText = (& $Python $PrepareAccount $authPath | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the disposable local demo login.' }
    $account = $accountText | ConvertFrom-Json

    $stage7ConfigPath = 'E:\BrainFusion-Runtime\stage7_orthanc_20261021\pacs-config.json'
    if (-not (Test-Path -LiteralPath $stage7ConfigPath -PathType Leaf)) { throw 'The existing Stage7 isolated Orthanc configuration is unavailable.' }
    $stage7Config = Get-Content -LiteralPath $stage7ConfigPath -Raw | ConvertFrom-Json
    if ($stage7Config.archive_id -ne 'stage7-orthanc' -or $stage7Config.base_url -ne 'http://127.0.0.1:18142' -or -not $stage7Config.expected_database_server_identifier) {
        throw 'Stage7 archive identity or loopback endpoint does not match the reviewed research archive.'
    }
    $dockerInspect = (& docker inspect brainfusion-stage7-orthanc | Out-String) | ConvertFrom-Json
    $configMountMatches = @($dockerInspect[0].Mounts | Where-Object {
        (($_.Source -replace '\\','/') -match '/BrainFusion-Runtime/stage7_orthanc_20261021/orthanc\.json$') -and
        $_.Destination -eq '/etc/orthanc/orthanc.json'
    })
    $archiveContainerMatches = ($LASTEXITCODE -eq 0 -and $dockerInspect[0].State.Status -eq 'running' -and
        $dockerInspect[0].Config.Image -eq 'orthancteam/orthanc:26.9.1' -and
        $dockerInspect[0].NetworkSettings.Ports.'8042/tcp'[0].HostIp -eq '127.0.0.1' -and
        $dockerInspect[0].NetworkSettings.Ports.'8042/tcp'[0].HostPort -eq '18142' -and
        $configMountMatches.Count -eq 1)
    if (-not $archiveContainerMatches) {
        throw 'Stage7 Orthanc container, image, loopback port or config mount failed the isolated-archive check.'
    }
    $stage7Secure = ConvertTo-SecureString $stage7Config.password -AsPlainText -Force
    $stage7Credential = [pscredential]::new($stage7Config.username, $stage7Secure)
    $basicBytes = [System.Text.Encoding]::UTF8.GetBytes($stage7Credential.UserName + ':' + $stage7Credential.GetNetworkCredential().Password)
    $basicToken = [Convert]::ToBase64String($basicBytes)
    Add-Type -AssemblyName System.Net.Http
    $httpClient = [System.Net.Http.HttpClient]::new()
    try {
        $httpClient.Timeout = [TimeSpan]::FromSeconds(8)
        $httpClient.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new('Basic', $basicToken)
        $stage7System = ($httpClient.GetStringAsync($stage7Config.base_url + '/system').GetAwaiter().GetResult() | ConvertFrom-Json)
        $stage7Stats = ($httpClient.GetStringAsync($stage7Config.base_url + '/statistics').GetAwaiter().GetResult() | ConvertFrom-Json)
    } finally {
        $httpClient.Dispose()
        [Array]::Clear($basicBytes, 0, $basicBytes.Length)
        $basicToken = $null
    }
    if (-not $stage7System.DatabaseServerIdentifier -or $stage7Stats.CountStudies -lt 1 -or $stage7Stats.CountInstances -lt 2) {
        throw 'Stage7 Orthanc did not expose a pinned database identity and a viewable archive.'
    }
    $pacsReadonlyRoot = Join-Path $runtimeRoot 'pacs-readonly'
    New-Item -ItemType Directory -Force -Path $pacsReadonlyRoot | Out-Null
    $pacsReadonlyConfigPath = Join-Path $pacsReadonlyRoot 'stage7-research.json'
    $stage7Config.expected_database_server_identifier = $stage7System.DatabaseServerIdentifier
    $stage7Config.allow_pixel_read = $false
    $stage7Config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $pacsReadonlyConfigPath -Encoding utf8
    Write-Host "Isolated Stage7 archive verified: studies=$($stage7Stats.CountStudies); series=$($stage7Stats.CountSeries); instances=$($stage7Stats.CountInstances); source PIN refreshed only in disposable demo config."

    $apiPort = Get-FreePort 18231 18279
    $frontPort = Get-FreePort 5190 5249
    $apiUrl = "http://127.0.0.1:$apiPort"
    $frontUrl = "http://127.0.0.1:$frontPort"

    $envValues = @{
        DATABASE_URL = 'sqlite:///' + ($dbPath -replace '\\','/')
        UPLOAD_DIR = $uploadRoot
        LOCAL_AUTH_FILE = $authPath
        RESEARCH_DIR = 'E:\BrainFusion-Runtime\results\research'
        DATASET_DIR = 'E:\BrainFusion-Data\WAW-GliomAI-v3'
        FEATURE_JOBS_DIR = $featureJobs
        RADIOMICS_COMPATIBILITY = 'E:\BrainFusion-Runtime\results\stage6\compatibility.json'
        RADIOMICS_PYTHON = 'E:\BrainFusion-Runtime\envs\radiomics39\python.exe'
        MODEL_DIR = Join-Path $runtimeRoot 'segresnet-disabled'
        PACS_ALLOW_DOCKER_HOST = 'false'
        PACS_CONFIG_FILE = $pacsReadonlyConfigPath
        PACS_RESEARCH_DEMO_PIXEL_READ = 'true'
        PACS_IMPORT_REGISTRY_FILE = 'E:\BrainFusion-Runtime\local\pacs-import-candidates.json'
        PACS_IMPORT_JOBS_DIR = Join-Path $runtimeRoot 'pacs-import-jobs'
        PACS_DERIVED_DIR = 'E:\BrainFusion-Data\PACS-derived'
        DICOM_QUARANTINE_DIR = Join-Path $runtimeRoot 'dicom-quarantine'
        DICOM_CONVERSION_INDEX_FILE = Join-Path $configRoot 'no-dicom-conversions.json'
        SURVIVAL_MODEL_DIR = $ExpectedArtifacts[0].Directory
        SURVIVAL_FUSION_MODEL_DIR = $ExpectedArtifacts[1].Directory
        SURVIVAL_UCSF_MODEL_DIR = 'E:\BrainFusion-Runtime\research-edition\results\survival-models\ucsf-pdgm-clinical-cox-research-v1.0.0'
        UPENN_SUB002_INPUT_DIR = 'E:\BrainFusion-Data\UPENN-GBM\official-nifti\sub-002'
        UPENN_SUB002_RESULT_DIR = 'E:\BrainFusion-Runtime\research-edition\results\upenn-sub002-segresnet-20261025\run-20261025T222645'
        UPENN_SUB002_EVIDENCE_DIR = 'E:\BrainFusion-Runtime\research-edition\results\p0-p2-final-science-20261026-v2'
        SURVIVAL_RESEARCH_PREDICTION_ENABLED = 'true'
        CORS_ORIGINS = $frontUrl
        PROJECT_NAME = 'BrainFusion-AI Isolated Research Demo'
        VITE_API_BASE = $apiUrl
        VITE_UNIFIED_RESEARCH_DEMO = 'true'
    }
    foreach ($key in $envValues.Keys) { [Environment]::SetEnvironmentVariable($key, [string]$envValues[$key], 'Process') }

    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backendOut = Join-Path $logs "backend-$timestamp.out.log"
    $backendErr = Join-Path $logs "backend-$timestamp.err.log"
    $frontendOut = Join-Path $logs "frontend-$timestamp.out.log"
    $frontendErr = Join-Path $logs "frontend-$timestamp.err.log"
    $backendArgs = @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',[string]$apiPort,'--no-access-log')
    $backendProcess = Start-Process -FilePath $Python -ArgumentList $backendArgs -WorkingDirectory $BackendRoot -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru
    $viteCli = Join-Path $FrontendRoot 'node_modules\vite\bin\vite.js'
    $frontendArgs = @($viteCli,'--host','127.0.0.1','--port',[string]$frontPort,'--strictPort')
    $frontendProcess = Start-Process -FilePath $Node -ArgumentList $frontendArgs -WorkingDirectory $FrontendRoot -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru

    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) { break }
        try {
            $health = Invoke-RestMethod -Uri "$apiUrl/" -TimeoutSec 2
            $models = Invoke-RestMethod -Uri "$apiUrl/api/survival/models" -TimeoutSec 5
            $front = Invoke-WebRequest -Uri "$frontUrl/" -TimeoutSec 2 -UseBasicParsing
            $availableIds = @($models.data.models | ForEach-Object { $_.model_id })
            if ($health.data.status -eq 'healthy' -and @($ExpectedArtifacts | Where-Object { $availableIds -contains $_.Id }).Count -eq $ExpectedArtifacts.Count -and $front.StatusCode -eq 200) {
                $ready = $true; break
            }
        } catch { Start-Sleep -Seconds 1 }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) {
        $tail = @()
        foreach ($file in @($backendOut,$backendErr,$frontendOut,$frontendErr)) { if (Test-Path $file) { $tail += Get-Content $file -Tail 12 } }
        throw "Isolated demo did not become healthy. Latest startup output:`n$($tail -join "`n")"
    }

    Write-Host ''
    Write-Host 'Isolated BrainFusion-AI research demo is running.' -ForegroundColor Green
    Write-Host "Frontend: $frontUrl"
    Write-Host "Backend:  $apiUrl"
    if (-not $RunLiveAcceptance) {
        Write-Host 'Synthetic survival demo login (local-only, disposable role; not a medical credential):'
        Write-Host "Username: $($account.username)"
        Write-Host "Password: $($account.password)" -ForegroundColor Yellow
    } else {
        Write-Host 'Running opt-in live Edge acceptance with in-process synthetic demo credentials.'
        if (-not $EvidencePath) {
            $EvidencePath = Join-Path $DemoRoot ('evidence\unified-live-e2e-' + (Get-Date -Format 'yyyyMMddTHHmmss') + '.json')
        }
        $env:BRAINFUSION_API_URL = $apiUrl
        $env:BRAINFUSION_WEB_URL = $frontUrl
        $env:BRAINFUSION_TEST_USERNAME = $account.username
        $env:BRAINFUSION_TEST_PASSWORD = $account.password
        $env:BRAINFUSION_UNIFIED_RESULT_PATH = $EvidencePath
        $env:BRAINFUSION_UNIFIED_LIVE_E2E = '1'
        $env:BRAINFUSION_BROWSER_CHANNEL = 'msedge'
        Push-Location $FrontendRoot
        try {
            & npm.cmd run test:e2e -- --grep 'isolated archive pixels and UCSF research model are live end to end'
            if ($LASTEXITCODE -ne 0) { throw "Live isolated browser acceptance failed with exit code $LASTEXITCODE." }
        } finally { Pop-Location }
        Write-Host "Aggregated live acceptance evidence: $EvidencePath"
    }
    Write-Host 'Demo DB/uploads/logs are isolated under:'
    Write-Host $DemoRoot
    Write-Host 'Close with Ctrl+C. The launcher stops only the two child processes it started; copied data and logs remain for review.'
    while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) { Start-Sleep -Seconds 2 }
    if ($backendProcess.HasExited) { throw 'The isolated backend stopped unexpectedly; inspect the isolated backend logs.' }
    if ($frontendProcess.HasExited) { throw 'The isolated frontend stopped unexpectedly; inspect the isolated frontend logs.' }
}
finally {
    foreach ($proc in @($frontendProcess,$backendProcess)) {
        if ($null -ne $proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue }
    }
    # Retain the isolated config and local account file outside the repository for local demo reuse.
    foreach ($key in $keys) { [Environment]::SetEnvironmentVariable($key, $savedEnvironment[$key], 'Process') }
    if ($null -ne $lock) { $lock.Dispose() }
}
