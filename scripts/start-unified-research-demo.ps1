param(
    [string]$Python = 'E:\BrainFusion-Runtime\envs\runtime311-cpu-delivery-20261017T1516_s4\python.exe',
    [string]$Node = '',
    [string]$DemoRoot = 'E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo'
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
    @{ Id = 'upenn-clinical-captk-fusion-cox-research'; Directory = 'E:\BrainFusion-Runtime\research-edition\results\survival-models\upenn-clinical-captk-fusion-cox-research-v1.0.0'; Sha = '0988d6d145e103cea90c5c15daff94a17d1cf8741ea65c63d957f7915de3b034'; ManifestSha = '4c8051d5ae6c5d179fce32b18d1f3cae7160e662e21374de92e7dd215c323812' }
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
$savedEnvironment = @{}
$keys = @(
    'DATABASE_URL','UPLOAD_DIR','LOCAL_AUTH_FILE','RESEARCH_DIR','DATASET_DIR','FEATURE_JOBS_DIR',
    'RADIOMICS_COMPATIBILITY','RADIOMICS_PYTHON','MODEL_DIR','PACS_ALLOW_DOCKER_HOST','PACS_CONFIG_FILE',
    'PACS_IMPORT_REGISTRY_FILE','PACS_IMPORT_JOBS_DIR','PACS_DERIVED_DIR','DICOM_QUARANTINE_DIR',
    'DICOM_CONVERSION_INDEX_FILE','SURVIVAL_MODEL_DIR','SURVIVAL_FUSION_MODEL_DIR',
    'SURVIVAL_RESEARCH_PREDICTION_ENABLED','CORS_ORIGINS','PROJECT_NAME','VITE_API_BASE','VITE_UNIFIED_RESEARCH_DEMO'
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
        PACS_CONFIG_FILE = Join-Path $configRoot 'no-pacs-config.json'
        PACS_IMPORT_REGISTRY_FILE = Join-Path $configRoot 'no-pacs-registry.json'
        PACS_IMPORT_JOBS_DIR = Join-Path $runtimeRoot 'pacs-import-jobs'
        PACS_DERIVED_DIR = Join-Path $runtimeRoot 'pacs-derived'
        DICOM_QUARANTINE_DIR = Join-Path $runtimeRoot 'dicom-quarantine'
        DICOM_CONVERSION_INDEX_FILE = Join-Path $configRoot 'no-dicom-conversions.json'
        SURVIVAL_MODEL_DIR = $ExpectedArtifacts[0].Directory
        SURVIVAL_FUSION_MODEL_DIR = $ExpectedArtifacts[1].Directory
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
            if ($health.data.status -eq 'healthy' -and $availableIds -contains $ExpectedArtifacts[0].Id -and $availableIds -contains $ExpectedArtifacts[1].Id -and $front.StatusCode -eq 200) {
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
    Write-Host 'Synthetic survival demo login (local-only, disposable role; not a medical credential):'
    Write-Host "Username: $($account.username)"
    Write-Host "Password: $($account.password)" -ForegroundColor Yellow
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
    foreach ($key in $keys) { [Environment]::SetEnvironmentVariable($key, $savedEnvironment[$key], 'Process') }
    if ($null -ne $lock) { $lock.Dispose() }
}
