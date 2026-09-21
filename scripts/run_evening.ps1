param(
    [string]$Config = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Config)) {
    $Config = Join-Path $ProjectRoot "config\config.json"
}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
Set-Location -LiteralPath $ProjectRoot

py -3.10 -m ai_job_intel --config $Config run-evening
exit $LASTEXITCODE
