param([switch]$V2)
$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$backend = Join-Path $repo 'backend'
$frontend = Join-Path $repo 'frontend'
$python = 'E:\BrainFusion-AI\.conda\brainfusion\python.exe'
$runtime = 'E:\BrainFusion-Runtime\research-edition'
$clinicalModel = Join-Path $runtime 'results\survival-models\upenn-clinical-cox-research-v1.0.1'
$fusionModel = Join-Path $runtime 'results\survival-models\upenn-clinical-captk-fusion-cox-research-v1.0.0'
$ucsfV2Model = Join-Path $runtime 'results\ucsf-pdgm-survival-v2-20261027\model-artifact'
$expected = @{
  clinical = '41c52f20371dd33a25c60bf981a6a811c6863bc01834062d33e6e4ae7f3ce8ff'
  fusion = '0988d6d145e103cea90c5c15daff94a17d1cf8741ea65c63d957f7915de3b034'
  ucsfV2 = '820ee0c05d50b49ee7343a2bed51b5ff60c70fad7d83551d5fa7f9fb60c5144c'
}
$formalPorts = @(18100, 18180)
$processes = @()
$sandbox = $null
$evidenceRoot = if ($V2) { Join-Path $runtime 'results\survival-v2-live-e2e-20261027' } else { Join-Path $runtime 'results\survival-live-artifact-e2e-20261026' }
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
$evidenceRun = Join-Path $evidenceRoot ('run-' + (Get-Date -Format 'yyyyMMddTHHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $evidenceRun | Out-Null
$artifactSummary = @()
$backendPort = $null
$frontendPort = $null
$listeners = @{}
$testExit = 1
$backendHealthy = $false
$frontendHealthy = $false
$predictionCount = $null
$errorText = $null
$began = (Get-Date).ToString('o')

function Get-Sha256([string]$Path) {
  (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-FreePort([int]$Port) {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
  try { $listener.Start(); return $true } catch { return $false } finally { $listener.Stop() }
}

function Find-FreePort([int]$First, [int]$Last) {
  for ($port = $First; $port -le $Last; $port++) {
    if (Test-FreePort $port) { return $port }
  }
  throw "No free loopback port in $First-$Last."
}

function Wait-Http([string]$Url, [System.Diagnostics.Process]$Process) {
  for ($attempt = 0; $attempt -lt 40; $attempt++) {
    if ($Process.HasExited) { throw "Test process exited before becoming healthy: $Url" }
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -eq 200) { return $true }
    } catch { Start-Sleep -Milliseconds 500 }
  }
  throw "Timed out waiting for isolated service: $Url"
}

try {
  if (!(Test-Path -LiteralPath $python)) { throw "Expected BrainFusion interpreter missing: $python" }
  $modelEntries = if ($V2) {
    @([pscustomobject]@{ Name = 'ucsfV2'; Directory = $ucsfV2Model })
  } else {
    @([pscustomobject]@{ Name = 'clinical'; Directory = $clinicalModel },
      [pscustomobject]@{ Name = 'fusion'; Directory = $fusionModel })
  }
  foreach ($entry in $modelEntries) {
    $name = $entry.Name; $directory = $entry.Directory
    $artifact = Join-Path $directory 'cox-model.json'
    $manifestPath = Join-Path $directory 'model-manifest.json'
    if (!(Test-Path -LiteralPath $artifact) -or !(Test-Path -LiteralPath $manifestPath)) {
      throw "Model artifact or manifest missing: $directory"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $actual = Get-Sha256 $artifact
    if ($actual -ne $expected[$name] -or $manifest.artifact_sha256 -ne $actual) {
      throw "Model artifact SHA/manifest mismatch: $name"
    }
    $model = Get-Content -LiteralPath $artifact -Raw | ConvertFrom-Json
    if ($model.model_version -ne $manifest.model_version -or $model.model_id -ne $manifest.model_id) {
      throw "Model identity mismatch: $name"
    }
    $artifactSummary += [ordered]@{
      model_id = $manifest.model_id
      model_version = $manifest.model_version
      artifact_sha256 = $actual
      manifest_sha256 = Get-Sha256 $manifestPath
      feature_order = @($model.features.names)
    }
  }

  $listeners = @{}
  foreach ($port in $formalPorts) {
    $listeners[[string]$port] = [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
  }
  $backendPort = Find-FreePort 18231 18290
  $frontendPort = Find-FreePort 5190 5250
  $sandbox = Join-Path $runtime ('.survival-live-e2e-' + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path $sandbox | Out-Null
  $authFile = Join-Path $sandbox 'local-users.json'
  $databaseFile = Join-Path $sandbox 'isolated-test.sqlite'
  $password = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N') + 'Aa1!'
  $username = 'bf_synthetic_' + [guid]::NewGuid().ToString('N').Substring(0, 8)
  $env:BRAINFUSION_TEST_USERNAME = $username
  $env:BRAINFUSION_TEST_PASSWORD = $password
  $env:TEST_AUTH_FILE = $authFile
  $env:TEST_BACKEND = $backend
  $accountScript = @'
import json, os, secrets, sys
sys.path.insert(0, os.environ['TEST_BACKEND'])
from app.services.local_auth import hash_password
record = {'format_version': 1, 'users': [{'id': secrets.token_hex(16), 'username': os.environ['BRAINFUSION_TEST_USERNAME'], 'display_name': 'Synthetic research test doctor', 'role': 'doctor', 'disabled': False, 'password_hash': hash_password(os.environ['BRAINFUSION_TEST_PASSWORD'])}]}
with open(os.environ['TEST_AUTH_FILE'], 'w', encoding='utf-8') as f: json.dump(record, f)
'@
  $accountScript | & $python -
  if ($LASTEXITCODE -ne 0) { throw 'Could not create isolated synthetic test account.' }

  $env:DATABASE_URL = 'sqlite:///' + $databaseFile.Replace('\', '/')
  $env:LOCAL_AUTH_FILE = $authFile
  $env:UPLOAD_DIR = Join-Path $sandbox 'uploads'
  $env:RESEARCH_DIR = Join-Path $sandbox 'research-empty'
  $env:DATASET_DIR = Join-Path $sandbox 'dataset-empty'
  $env:FEATURE_JOBS_DIR = Join-Path $sandbox 'feature-jobs-empty'
  $env:MODEL_DIR = Join-Path $sandbox 'models-empty'
  $env:SURVIVAL_MODEL_DIR = if ($V2) { '' } else { $clinicalModel }
  $env:SURVIVAL_FUSION_MODEL_DIR = if ($V2) { '' } else { $fusionModel }
  $env:SURVIVAL_UCSF_MODEL_DIR = if ($V2) { $ucsfV2Model } else { '' }
  $env:SURVIVAL_RESEARCH_PREDICTION_ENABLED = 'true'
  $env:SURVIVAL_RESEARCH_CASE_ENABLED = if ($V2) { 'true' } else { 'false' }
  $env:CORS_ORIGINS = "http://127.0.0.1:$frontendPort,http://localhost:$frontendPort"
  $env:LOG_LEVEL = 'WARNING'
  $env:PYTHONUTF8 = '1'
  $apiUrl = "http://127.0.0.1:$backendPort"
  $webUrl = "http://127.0.0.1:$frontendPort"

  $backendLog = Join-Path $sandbox 'backend.log'
  $backendErrorLog = Join-Path $sandbox 'backend-error.log'
  $pythonArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', [string]$backendPort, '--log-level', 'warning')
  $backendProcess = Start-Process -FilePath $python -ArgumentList $pythonArgs -WorkingDirectory $backend -PassThru -WindowStyle Hidden -RedirectStandardOutput $backendLog -RedirectStandardError $backendErrorLog
  $processes += $backendProcess
  $backendHealthy = Wait-Http "$apiUrl/" $backendProcess

  $env:VITE_API_BASE = $apiUrl
  $env:BRAINFUSION_API_URL = $apiUrl
  $env:BRAINFUSION_WEB_URL = $webUrl
  $env:BRAINFUSION_BROWSER_CHANNEL = 'msedge'
  $env:BRAINFUSION_SURVIVAL_LIVE_E2E = if ($V2) { '0' } else { '1' }
  $env:BRAINFUSION_SURVIVAL_V2_LIVE_E2E = if ($V2) { '1' } else { '0' }
  $env:BRAINFUSION_LIVE_RESULT_PATH = Join-Path $evidenceRun 'live-api-results.json'
  $viteLog = Join-Path $sandbox 'vite.log'
  $viteErrorLog = Join-Path $sandbox 'vite-error.log'
  $node = (Get-Command node.exe).Source
  $viteCli = Join-Path $frontend 'node_modules\vite\bin\vite.js'
  if (!(Test-Path -LiteralPath $viteCli)) { throw 'Vite dependency is not present; refusing to install packages during the live test.' }
  $viteProcess = Start-Process -FilePath $node -ArgumentList @($viteCli, '--host', '127.0.0.1', '--port', [string]$frontendPort, '--strictPort') -WorkingDirectory $frontend -PassThru -WindowStyle Hidden -RedirectStandardOutput $viteLog -RedirectStandardError $viteErrorLog
  $processes += $viteProcess
  $frontendHealthy = Wait-Http $webUrl $viteProcess

  Push-Location $frontend
  try {
    $testSpec = if ($V2) { 'e2e/survival-v2-research-case.spec.js' } else { 'e2e/survival-live-artifact.spec.js' }
    $testOutput = & $env:ComSpec /d /c "npm run test:e2e -- $testSpec 2>&1"
    $testExit = $LASTEXITCODE
    $testOutput | Out-File -LiteralPath (Join-Path $evidenceRun 'playwright.log') -Encoding utf8
  } finally { Pop-Location }

  if (Test-Path -LiteralPath (Join-Path $sandbox 'isolated-test.sqlite')) {
    $env:TEST_DB_FILE = $databaseFile
    $countScript = @'
import json, os, sqlite3
connection = sqlite3.connect(os.environ['TEST_DB_FILE'])
tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
if 'predictions' not in tables: raise RuntimeError('isolated prediction table missing')
count = connection.execute('SELECT COUNT(*) FROM predictions').fetchone()[0]
print(json.dumps({'prediction_rows': count, 'tables': len(tables)}))
'@
    $countText = $countScript | & $python -
    if ($LASTEXITCODE -eq 0) { $predictionCount = ($countText | ConvertFrom-Json).prediction_rows }
  }
  foreach ($logName in @('backend.log', 'backend-error.log', 'vite.log', 'vite-error.log')) {
    $logPath = Join-Path $sandbox $logName
    if (Test-Path -LiteralPath $logPath) { Copy-Item $logPath (Join-Path $evidenceRun $logName) }
  }
  if ($testExit -ne 0) { $errorText = 'Playwright real-artifact test failed; inspect saved logs and API result.' }
  if ($predictionCount -ne 0) { $errorText = 'Expected zero persisted prediction rows in the isolated database.' }
} catch {
  $errorText = $_.Exception.Message
} finally {
  if ($sandbox -and $evidenceRun) {
    foreach ($logName in @('backend.log', 'backend-error.log', 'vite.log', 'vite-error.log', 'playwright.log')) {
      $logPath = Join-Path $sandbox $logName
      if (Test-Path -LiteralPath $logPath) { Copy-Item -LiteralPath $logPath -Destination (Join-Path $evidenceRun $logName) -Force }
    }
  }
  foreach ($process in $processes) {
    try { if (!$process.HasExited) { Stop-Process -Id $process.Id -ErrorAction Stop; $process.WaitForExit(5000) | Out-Null } } catch { }
  }
  if ($sandbox -and (Test-Path -LiteralPath $sandbox)) {
    $resolvedSandbox = (Resolve-Path -LiteralPath $sandbox).Path
    $runtimeFull = (Resolve-Path -LiteralPath $runtime).Path
    if (!$resolvedSandbox.StartsWith($runtimeFull, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Refusing to remove non-runtime temporary path: $resolvedSandbox"
    }
    Remove-Item -LiteralPath $resolvedSandbox -Recurse
  }
  if ($evidenceRun) {
    $summary = [ordered]@{
      recorded_at = (Get-Date).ToString('o')
      status = if (!$errorText -and $testExit -eq 0 -and $backendHealthy -and $frontendHealthy -and $predictionCount -eq 0) { 'PASS' } else { 'FAIL_OR_BLOCKED' }
      error = $errorText
      input_scope = if ($V2) { @('SYNTHETIC_TEST', 'RESEARCH_CASE') } else { @('SYNTHETIC_TEST') }
      v2_isolated_opt_in = [bool]$V2
      backend_isolated = $true
      temporary_sqlite_used = $true
      temporary_account_used = $true
      model_artifacts = $artifactSummary
      formal_ports_listening_at_preflight = $listeners
      isolated_backend_port = $backendPort
      isolated_frontend_port = $frontendPort
      backend_healthy = $backendHealthy
      frontend_healthy = $frontendHealthy
      targeted_playwright_exit_code = $testExit
      isolated_prediction_rows_after_test = $predictionCount
      formal_environment_modified = $false
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidenceRun 'run-summary.json') -Encoding utf8
  }
  Remove-Item Env:\BRAINFUSION_TEST_USERNAME,Env:\BRAINFUSION_TEST_PASSWORD,Env:\TEST_AUTH_FILE,Env:\TEST_BACKEND,Env:\TEST_DB_FILE,Env:\DATABASE_URL,Env:\LOCAL_AUTH_FILE,Env:\UPLOAD_DIR,Env:\RESEARCH_DIR,Env:\DATASET_DIR,Env:\FEATURE_JOBS_DIR,Env:\MODEL_DIR,Env:\SURVIVAL_MODEL_DIR,Env:\SURVIVAL_FUSION_MODEL_DIR,Env:\SURVIVAL_UCSF_MODEL_DIR,Env:\SURVIVAL_RESEARCH_PREDICTION_ENABLED,Env:\SURVIVAL_RESEARCH_CASE_ENABLED,Env:\CORS_ORIGINS,Env:\LOG_LEVEL,Env:\PYTHONUTF8,Env:\VITE_API_BASE,Env:\BRAINFUSION_API_URL,Env:\BRAINFUSION_WEB_URL,Env:\BRAINFUSION_BROWSER_CHANNEL,Env:\BRAINFUSION_SURVIVAL_LIVE_E2E,Env:\BRAINFUSION_SURVIVAL_V2_LIVE_E2E,Env:\BRAINFUSION_LIVE_RESULT_PATH -ErrorAction SilentlyContinue
}

if ($errorText -or $testExit -ne 0 -or $predictionCount -ne 0) {
  Write-Error "Survival live-artifact E2E did not pass: $errorText. Evidence: $evidenceRun"
}
Write-Output "PASS: isolated real-artifact survival E2E; evidence: $evidenceRun"
