#Requires -Version 5.1
<#
.SYNOPSIS
  If WireGuard tunnel to Vultr is connected, disconnect it (same as GUI Deactivate).

.NOTES
  Stopping/uninstalling a WireGuard tunnel service REQUIRES Administrator.
  This script will auto-elevate via UAC when needed (manual run).
  Scheduled task should use "Run with highest privileges".
#>
param(
    [switch]$WhatIf,
    # Internal: set by elevated child to avoid infinite UAC loop
    [switch]$ElevatedRelaunch
)

# ======================== USER CONFIG ========================
$Config = @{
    # Tunnel name shown in WireGuard UI (conf name without .conf)
    TunnelName           = 'windows02'
    # true = disconnect every running WireGuardTunnel$* service
    DisconnectAllRunning = $false
    WireGuardDir         = "$env:ProgramFiles\WireGuard"
    # Only disconnect when endpoint contains this string; empty = no filter
    EndpointFilter       = '104.156.231.123'
    LogDir               = 'C:\Users\analy\Desktop\AI_Folder\script\logs'
    # Manual run: if not admin, popup UAC and relaunch as admin
    AutoElevate          = $true
}
# =============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Log {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [ValidateSet('INFO', 'WARN', 'ERROR', 'DEBUG')][string]$Level = 'INFO'
    )
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = '[{0}] [{1}] {2}' -f $ts, $Level, $Message
    switch ($Level) {
        'WARN'  { Write-Host $line -ForegroundColor Yellow }
        'ERROR' { Write-Host $line -ForegroundColor Red }
        'DEBUG' { Write-Host $line -ForegroundColor DarkGray }
        default { Write-Host $line }
    }
    try {
        if (-not (Test-Path -LiteralPath $Config.LogDir)) {
            New-Item -ItemType Directory -Path $Config.LogDir -Force | Out-Null
        }
        $logFile = Join-Path $Config.LogDir ('wireguard-{0}.log' -f (Get-Date -Format 'yyyyMMdd'))
        Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
    } catch {}
}

function Test-IsAdministrator {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Request-SelfElevation {
    param([Parameter(Mandatory = $true)][string]$ScriptPath)
    # Relaunch this script elevated; returns child exit code, or -1 on failure
    if ([string]::IsNullOrWhiteSpace($ScriptPath) -or -not (Test-Path -LiteralPath $ScriptPath)) {
        Write-Log 'Cannot resolve script path for elevation.' -Level ERROR
        return -1
    }

    $argList = @(
        '-NoProfile'
        '-ExecutionPolicy', 'Bypass'
        '-File', $ScriptPath
        '-ElevatedRelaunch'
    )
    if ($WhatIf) { $argList += '-WhatIf' }

    Write-Log 'Requesting UAC elevation (Administrator)...' -Level WARN
    try {
        $p = Start-Process -FilePath 'powershell.exe' `
            -ArgumentList $argList `
            -Verb RunAs `
            -PassThru `
            -Wait
        $code = 0
        if ($null -ne $p.ExitCode) { $code = [int]$p.ExitCode }
        Write-Log ('Elevated process exit code: {0}' -f $code)
        return $code
    } catch {
        Write-Log ('UAC elevation cancelled or failed: {0}' -f $_.Exception.Message) -Level ERROR
        return -1
    }
}

function Get-WireGuardExe {
    foreach ($c in @(
        (Join-Path $Config.WireGuardDir 'wireguard.exe'),
        "$env:ProgramFiles\WireGuard\wireguard.exe",
        "${env:ProgramFiles(x86)}\WireGuard\wireguard.exe"
    )) {
        if ($c -and (Test-Path -LiteralPath $c)) { return $c }
    }
    return $null
}

function Get-TunnelService {
    param([Parameter(Mandatory = $true)][string]$TunnelName)
    $svcName = "WireGuardTunnel`$$TunnelName"
    return Get-Service -Name $svcName -ErrorAction SilentlyContinue
}

function Get-RunningTunnelServices {
    Get-Service -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -like 'WireGuardTunnel$*' -and $_.Status -eq 'Running'
    }
}

function Get-TunnelNameFromServiceName {
    param([string]$ServiceName)
    if ($ServiceName -match '^WireGuardTunnel\$(.+)$') { return $Matches[1] }
    return $null
}

function Test-TunnelMatchesEndpointFilter {
    param([string]$TunnelName, [string]$Filter)
    if ([string]::IsNullOrWhiteSpace($Filter)) { return $true }

    $wg = Join-Path $Config.WireGuardDir 'wg.exe'
    if (Test-Path -LiteralPath $wg) {
        try {
            $out = & $wg show 2>&1 | Out-String
            if ($out -match [regex]::Escape($Filter)) { return $true }
            if ($out -match 'interface:' -or $out -match 'peer:') {
                Write-Log ('wg show did not match EndpointFilter={0}' -f $Filter) -Level WARN
                return $false
            }
        } catch {
            Write-Log ('wg.exe error: {0}' -f $_.Exception.Message) -Level DEBUG
        }
    }

    $confCandidates = @(
        (Join-Path (Join-Path $Config.WireGuardDir 'Data\Configurations') ($TunnelName + '.conf')),
        (Join-Path (Join-Path $env:LOCALAPPDATA 'WireGuard') ($TunnelName + '.conf')),
        (Join-Path $Config.WireGuardDir ($TunnelName + '.conf'))
    )
    foreach ($conf in $confCandidates) {
        if (-not (Test-Path -LiteralPath $conf)) { continue }
        try {
            $text = Get-Content -LiteralPath $conf -Raw -ErrorAction Stop
            if ($text -match [regex]::Escape($Filter)) { return $true }
        } catch {
            Write-Log ('read conf failed: {0}' -f $conf) -Level DEBUG
        }
    }

    Write-Log ('Cannot verify EndpointFilter; proceed by tunnel name: {0}' -f $TunnelName) -Level WARN
    return $true
}

function Wait-TunnelGone {
    param([string]$TunnelName, [int]$TimeoutSec = 8)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    do {
        $svc = Get-TunnelService -TunnelName $TunnelName
        if (-not $svc) { return $true }
        if ($svc.Status -ne 'Running') { return $true }
        Start-Sleep -Milliseconds 400
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Disconnect-Tunnel {
    param(
        [Parameter(Mandatory = $true)][string]$TunnelName,
        [string]$WireGuardExe
    )
    $svcName = "WireGuardTunnel`$$TunnelName"
    Write-Log ('Disconnect tunnel: {0} (service {1})' -f $TunnelName, $svcName)

    if ($WhatIf) {
        Write-Log ('[WhatIf] would run: wireguard.exe /uninstalltunnelservice {0}' -f $TunnelName)
        return $true
    }

    if (-not (Test-IsAdministrator)) {
        Write-Log 'Not Administrator: cannot stop WireGuard tunnel service (Access Denied).' -Level ERROR
        Write-Log 'Right-click PowerShell -> Run as administrator, or allow UAC elevation.' -Level ERROR
        return $false
    }

    # Method 1: official WireGuard CLI (same as GUI Disconnect)
    if ($WireGuardExe) {
        Write-Log ('Method1: {0} /uninstalltunnelservice {1}' -f $WireGuardExe, $TunnelName)
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $output = & $WireGuardExe /uninstalltunnelservice $TunnelName 2>&1
        $code = $LASTEXITCODE
        $ErrorActionPreference = $prev
        $text = if ($null -eq $output) { '' } else { ($output | Out-String).Trim() }
        Write-Log ('wireguard.exe exit={0} output={1}' -f $code, $text)

        if (Wait-TunnelGone -TunnelName $TunnelName -TimeoutSec 8) {
            Write-Log ('Disconnected via uninstalltunnelservice: {0}' -f $TunnelName)
            return $true
        }
        Write-Log 'Service still present after uninstalltunnelservice; try sc.exe stop' -Level WARN
    } else {
        Write-Log 'wireguard.exe not found; skip Method1' -Level WARN
    }

    # Method 2: sc.exe stop (needs admin)
    Write-Log ('Method2: sc.exe stop "{0}"' -f $svcName)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $scOut = & sc.exe stop $svcName 2>&1
    $scCode = $LASTEXITCODE
    $ErrorActionPreference = $prev
    Write-Log ('sc stop exit={0} output={1}' -f $scCode, (($scOut | Out-String).Trim()))

    if (Wait-TunnelGone -TunnelName $TunnelName -TimeoutSec 8) {
        Write-Log ('Disconnected via sc stop: {0}' -f $TunnelName)
        # Best-effort remove leftover service definition
        if ($WireGuardExe) {
            $ErrorActionPreference = 'Continue'
            & $WireGuardExe /uninstalltunnelservice $TunnelName 2>&1 | Out-Null
            $ErrorActionPreference = $prev
        }
        return $true
    }

    # Method 3: Stop-Service
    Write-Log ('Method3: Stop-Service -Force {0}' -f $svcName)
    try {
        Stop-Service -Name $svcName -Force -ErrorAction Stop
        if (Wait-TunnelGone -TunnelName $TunnelName -TimeoutSec 8) {
            Write-Log ('Disconnected via Stop-Service: {0}' -f $TunnelName)
            return $true
        }
    } catch {
        Write-Log ('Stop-Service failed: {0}' -f $_.Exception.Message) -Level ERROR
    }

    Write-Log ('All disconnect methods failed for {0}. Is the process elevated?' -f $TunnelName) -Level ERROR
    return $false
}

try {
    Write-Log '========== WireGuard check start =========='
    Write-Log ('TunnelName={0}; DisconnectAllRunning={1}; EndpointFilter={2}; WhatIf={3}' -f `
        $Config.TunnelName, $Config.DisconnectAllRunning, $Config.EndpointFilter, $WhatIf)

    $isAdmin = Test-IsAdministrator
    Write-Log ('IsAdministrator={0}; ElevatedRelaunch={1}' -f $isAdmin, $ElevatedRelaunch)

    $wgExe = Get-WireGuardExe
    if ($wgExe) { Write-Log ('WireGuard exe: {0}' -f $wgExe) }
    else { Write-Log 'wireguard.exe not found; will try sc/Stop-Service only' -Level WARN }

    $running = @(Get-RunningTunnelServices)
    if ($running.Count -eq 0) {
        Write-Log 'No running WireGuard tunnel service. Nothing to do.'
        Write-Log '========== WireGuard check end (idle) =========='
        exit 0
    }

    Write-Log ('Running tunnels: {0}' -f $running.Count)
    foreach ($s in $running) {
        Write-Log ('  - {0} Status={1}' -f $s.Name, $s.Status)
    }

    # Resolve targets first (may exit early with nothing to do)
    $targets = @()
    if ($Config.DisconnectAllRunning) {
        $targets = @(
            $running | ForEach-Object { Get-TunnelNameFromServiceName $_.Name } | Where-Object { $_ }
        )
    } else {
        if ([string]::IsNullOrWhiteSpace($Config.TunnelName)) {
            Write-Log 'TunnelName empty and DisconnectAllRunning=false.' -Level ERROR
            exit 2
        }
        $exact = Get-TunnelService -TunnelName $Config.TunnelName
        if (-not $exact) {
            Write-Log ('Specified tunnel service not found: WireGuardTunnel${0}. Nothing to do.' -f $Config.TunnelName)
            Write-Log '========== WireGuard check end (not connected) =========='
            exit 0
        }
        if ($exact.Status -ne 'Running') {
            Write-Log ('Specified tunnel not running: {0} Status={1}. Nothing to do.' -f $exact.Name, $exact.Status)
            Write-Log '========== WireGuard check end (not connected) =========='
            exit 0
        }
        $targets = @($Config.TunnelName)
    }

    # Filter by endpoint before elevating (avoid unnecessary UAC)
    $needDisconnect = @()
    foreach ($name in $targets) {
        if (Test-TunnelMatchesEndpointFilter -TunnelName $name -Filter $Config.EndpointFilter) {
            $needDisconnect += $name
        } else {
            Write-Log ('Skip {0}: EndpointFilter not matched' -f $name) -Level WARN
        }
    }

    if ($needDisconnect.Count -eq 0) {
        Write-Log 'No matching tunnel to disconnect. Nothing to do.'
        Write-Log '========== WireGuard check end (filtered out) =========='
        exit 0
    }

    # Elevate when needed (tunnel service cannot be stopped without admin)
    if (-not $WhatIf -and -not $isAdmin) {
        if ($Config.AutoElevate -and -not $ElevatedRelaunch) {
            $childCode = Request-SelfElevation -ScriptPath $PSCommandPath
            if ($childCode -ge 0) { exit $childCode }
            Write-Log 'Auto-elevate failed. Please run as Administrator.' -Level ERROR
            exit 5
        }
        Write-Log 'Not Administrator and AutoElevate=false. Cannot disconnect.' -Level ERROR
        exit 5
    }

    $disconnected = 0
    $failed = 0
    foreach ($name in $needDisconnect) {
        if (Disconnect-Tunnel -TunnelName $name -WireGuardExe $wgExe) { $disconnected++ }
        else { $failed++ }
    }

    Write-Log ('Result: disconnected={0}, failed={1}' -f $disconnected, $failed)
    Write-Log '========== WireGuard check end =========='
    if ($failed -gt 0) { exit 1 }
    exit 0
}
catch {
    Write-Log ('Unhandled error: {0}' -f $_.Exception.Message) -Level ERROR
    if ($_.ScriptStackTrace) { Write-Log $_.ScriptStackTrace -Level ERROR }
    exit 1
}
