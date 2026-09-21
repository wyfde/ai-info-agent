param(
    [string]$Config = "D:\AI-INFO\config\config.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
Set-Location -LiteralPath $ProjectRoot

py -3.10 -m ai_job_intel --config $Config check-bitable
exit $LASTEXITCODE
