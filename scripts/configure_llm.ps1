param(
    [string]$Config = "D:\AI-INFO\config\config.json"
)

$ErrorActionPreference = "Stop"

$secureKey = Read-Host "请输入 LLM API Key（输入内容不会显示）" -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
}

if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "API Key 不能为空。"
}

$configPath = (Resolve-Path -LiteralPath $Config).Path
$configObject = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $configObject.llm) {
    throw "配置文件中缺少 llm 配置段。"
}

$configObject.llm | Add-Member -NotePropertyName "api_key" -NotePropertyValue $apiKey -Force
$json = $configObject | ConvertTo-Json -Depth 10
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($configPath, $json, $utf8)

$env:AI_JOB_INTEL_LLM_API_KEY = $apiKey

Write-Host "API Key 已写入项目配置：$configPath" -ForegroundColor Green
Write-Host "现在可以运行 scripts\check_llm.ps1 测试连接。"
