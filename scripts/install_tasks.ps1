param(
    [string]$Config = "D:\AI-INFO\config\config.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PowerShell = (Get-Command powershell.exe).Source

$eveningAction = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ProjectRoot\scripts\run_evening.ps1`" -Config `"$Config`""
$morningAction = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ProjectRoot\scripts\run_morning.ps1`" -Config `"$Config`""

$eveningTrigger = New-ScheduledTaskTrigger -Daily -At "22:00"
$morningTrigger = New-ScheduledTaskTrigger -Daily -At "08:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName "AI-INFO-Evening" -Action $eveningAction -Trigger $eveningTrigger -Settings $settings -Force
Register-ScheduledTask -TaskName "AI-INFO-Morning" -Action $morningAction -Trigger $morningTrigger -Settings $settings -Force
