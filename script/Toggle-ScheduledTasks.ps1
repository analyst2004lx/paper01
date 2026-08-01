#Requires -Version 5.1
<#
.SYNOPSIS
  Create or remove the two scheduled tasks (toggle).
  Usually launched elevated by Toggle-ScheduledTasks.bat.
#>
param(
    [ValidateSet('Auto', 'Create', 'Remove', 'Status')]
    [string]$Mode = 'Auto'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SyncPs1   = Join-Path $ScriptDir 'Sync-GitHubLocal.ps1'
$WgPs1     = Join-Path $ScriptDir 'Disconnect-WireGuard.ps1'
$LogDir    = Join-Path $ScriptDir 'logs'
$StateFile = Join-Path $LogDir 'scheduled-tasks.state'

$TaskSync = 'AIFolder-GitHubSync'
$TaskWg   = 'AIFolder-WireGuardDisconnect'

function Write-Info([string]$m) { Write-Host "[INFO] $m" }
function Write-Ok([string]$m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Write-Warn([string]$m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err([string]$m)  { Write-Host "[ERROR] $m" -ForegroundColor Red }

function Test-IsAdministrator {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-TaskExists([string]$Name) {
    try {
        $null = Get-ScheduledTask -TaskName $Name -ErrorAction Stop
        return $true
    } catch {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        schtasks /Query /TN $Name 2>&1 | Out-Null
        $code = $LASTEXITCODE
        $ErrorActionPreference = $prev
        return ($code -eq 0)
    }
}

function Remove-TaskSafe([string]$Name) {
    if (-not (Test-TaskExists $Name)) {
        Write-Info "Not found, skip delete: $Name"
        return $true
    }
    try {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction Stop
        Write-Ok "Deleted: $Name"
        return $true
    } catch {
        Write-Warn ("Unregister-ScheduledTask failed, try schtasks: {0}" -f $_.Exception.Message)
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        schtasks /Delete /TN $Name /F 2>&1 | Out-Null
        $code = $LASTEXITCODE
        $ErrorActionPreference = $prev
        if ($code -eq 0) {
            Write-Ok "Deleted via schtasks: $Name"
            return $true
        }
        Write-Err "Delete failed: $Name"
        return $false
    }
}

function New-SyncTrigger {
    try {
        $t = New-ScheduledTaskTrigger -Daily -At 10:00am
        $rep = (New-ScheduledTaskTrigger -Once -At 10:00am `
            -RepetitionInterval (New-TimeSpan -Hours 1) `
            -RepetitionDuration (New-TimeSpan -Hours 8)).Repetition
        $t.Repetition = $rep
        return $t
    } catch {
        Write-Warn ("Daily+Repetition failed, fallback daily 10:00 once: {0}" -f $_.Exception.Message)
        return (New-ScheduledTaskTrigger -Daily -At 10:00am)
    }
}

function Register-TasksModern {
    $psExe = (Get-Command powershell.exe).Source
    $syncArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$SyncPs1`""
    $wgArgs   = "-NoProfile -ExecutionPolicy Bypass -File `"$WgPs1`""

    $null = Remove-TaskSafe $TaskSync
    $null = Remove-TaskSafe $TaskWg

    $syncAction = New-ScheduledTaskAction -Execute $psExe -Argument $syncArgs -WorkingDirectory $ScriptDir
    $syncTrigger = New-SyncTrigger
    $syncPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    $syncSettings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew

    Register-ScheduledTask -TaskName $TaskSync -Action $syncAction -Trigger $syncTrigger `
        -Principal $syncPrincipal -Settings $syncSettings -Force | Out-Null
    Write-Ok "$TaskSync registered (hourly from ~10:00; script window 10:00-17:00)"

    $wgAction = New-ScheduledTaskAction -Execute $psExe -Argument $wgArgs -WorkingDirectory $ScriptDir
    $wgTrigger = New-ScheduledTaskTrigger -Daily -At 8:00pm
    try {
        $wgPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
    } catch {
        Write-Warn ("Interactive+Highest failed, use SYSTEM: {0}" -f $_.Exception.Message)
        $wgPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    }
    $wgSettings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew

    Register-ScheduledTask -TaskName $TaskWg -Action $wgAction -Trigger $wgTrigger `
        -Principal $wgPrincipal -Settings $wgSettings -Force | Out-Null
    Write-Ok "$TaskWg registered (daily 23:00, Highest)"
}

function Register-TasksSchtasks {
    Write-Warn 'Fallback path: schtasks.exe'
    $trSync = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$SyncPs1`""
    $trWg   = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$WgPs1`""

    schtasks /Delete /TN $TaskSync /F 2>$null | Out-Null
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    schtasks /Create /TN $TaskSync /TR $trSync /SC DAILY /ST 10:00 /RI 60 /DU 08:00 /RL LIMITED /F
    if ($LASTEXITCODE -ne 0) {
        Write-Warn 'Create with /RI failed; try daily once at 10:00'
        schtasks /Create /TN $TaskSync /TR $trSync /SC DAILY /ST 10:00 /RL LIMITED /F
        if ($LASTEXITCODE -ne 0) { throw "schtasks create $TaskSync failed" }
        Write-Ok "$TaskSync registered (daily 10:00 once)"
    } else {
        Write-Ok "$TaskSync registered (daily 10:00, every 60 min for 8h)"
    }

    schtasks /Delete /TN $TaskWg /F 2>$null | Out-Null
    schtasks /Create /TN $TaskWg /TR $trWg /SC DAILY /ST 23:00 /RL HIGHEST /F
    $ErrorActionPreference = $prev
    if ($LASTEXITCODE -ne 0) { throw "schtasks create $TaskWg failed" }
    Write-Ok "$TaskWg registered (daily 23:00 Highest)"
}

Write-Host ''
Write-Host '============================================================'
Write-Host '  AI_Folder scheduled tasks toggle'
Write-Host '============================================================'
Write-Info "ScriptDir: $ScriptDir"
Write-Info "Mode: $Mode"
Write-Info ("OS: {0}" -f [System.Environment]::OSVersion.VersionString)
Write-Info ("PowerShell: {0}" -f $PSVersionTable.PSVersion)
Write-Host ''

if (-not (Test-Path -LiteralPath $SyncPs1)) { throw "Missing: $SyncPs1" }
if (-not (Test-Path -LiteralPath $WgPs1))   { throw "Missing: $WgPs1" }

if (-not (Test-IsAdministrator)) {
    Write-Err 'Administrator required. Double-click Toggle-ScheduledTasks.bat (UAC).'
    exit 2
}

$hasSync = Test-TaskExists $TaskSync
$hasWg   = Test-TaskExists $TaskWg
Write-Info "Current: $TaskSync=$hasSync ; $TaskWg=$hasWg"

if ($Mode -eq 'Status') { exit 0 }

$doRemove = $false
$doCreate = $false
switch ($Mode) {
    'Remove' { $doRemove = $true }
    'Create' { $doCreate = $true }
    default {
        if ($hasSync -or $hasWg) { $doRemove = $true } else { $doCreate = $true }
    }
}

if ($doRemove) {
    Write-Info 'Removing tasks...'
    $ok1 = Remove-TaskSafe $TaskSync
    $ok2 = Remove-TaskSafe $TaskWg
    if (Test-Path -LiteralPath $StateFile) {
        Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
    }
    if ($ok1 -and $ok2) {
        Write-Ok 'Tasks removed (or already absent). Run again to register.'
        exit 0
    }
    Write-Err 'Remove incomplete.'
    exit 1
}

if ($doCreate) {
    Write-Info 'Creating tasks...'
    if (-not (Test-Path -LiteralPath $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }

    $hasRegisterCmdlet = $null -ne (Get-Command Register-ScheduledTask -ErrorAction SilentlyContinue)
    try {
        if ($hasRegisterCmdlet) { Register-TasksModern }
        else { Register-TasksSchtasks }
    } catch {
        Write-Warn ("Modern API failed: {0}" -f $_.Exception.Message)
        Register-TasksSchtasks
    }

    ('registered={0}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) |
        Set-Content -LiteralPath $StateFile -Encoding UTF8

    Write-Host ''
    Write-Ok 'Registration complete.'
    Write-Info 'Check Task Scheduler for AIFolder-* tasks.'
    Write-Info 'Manual test examples:'
    Write-Host "  powershell -ExecutionPolicy Bypass -File `"$SyncPs1`" -Force"
    Write-Host "  powershell -ExecutionPolicy Bypass -File `"$WgPs1`" -WhatIf"
    exit 0
}
