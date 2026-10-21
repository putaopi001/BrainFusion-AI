# Dot-source before installs, tests, builds and inference on this workstation.
$runtimeRoot = 'E:/BrainFusion-Runtime'
New-Item -ItemType Directory -Force -Path "$runtimeRoot/tmp", "$runtimeRoot/cache", "$runtimeRoot/results" | Out-Null
$env:TEMP = "$runtimeRoot/tmp"
$env:TMP = "$runtimeRoot/tmp"
$env:TMPDIR = "$runtimeRoot/tmp"
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PIP_CACHE_DIR = "$runtimeRoot/cache/pip"
$env:HF_HOME = "$runtimeRoot/cache/huggingface"
$env:TORCH_HOME = "$runtimeRoot/cache/torch"
$env:XDG_CACHE_HOME = "$runtimeRoot/cache"
$env:npm_config_cache = "$runtimeRoot/cache/npm"
$env:PLAYWRIGHT_BROWSERS_PATH = "$runtimeRoot/cache/playwright"
$env:MPLCONFIGDIR = "$runtimeRoot/cache/matplotlib"
$env:CUDA_CACHE_PATH = "$runtimeRoot/cache/cuda"
$env:PYTHONUTF8 = '1'
