#Requires -Version 5.1
<#
.SYNOPSIS
  Toggle the local wstunnel client that carries WireGuard.

  Not running -> add missing bypass routes, print OPEN, then keep this window
  attached to wstunnel so its log stays on screen.
  Already running -> stop wstunnel, disconnect WireGuard if it is still up,
  print CLOSED.

  Run from an Administrator PowerShell. If it is not elevated, it asks for UAC
  and continues in the new window.
#>

# ======================== USER CONFIG ========================
# Shared secret. Must match the VPS wstunnel --restrict-http-upgrade-path-prefix.
$PathPrefix = 'wg-mobile-2026-xK9mP2'

# Name sent as TLS SNI and as the HTTP Host header.
# Current working path (Cloudflare named tunnel):
$SniHost = 'wg.datilan.com'
# Direct-to-VPS path (hotspot often cuts it). To use it, also set $FixedRemote:
#   $SniHost    = 'analy-wg.duckdns.org'
#   $FixedRemote = '104.156.231.123'

# Empty = connect to the first A record of $SniHost, and bypass-route every A record.
# Set an IP to force the TCP target (routes for $SniHost are still added).
$FixedRemote = ''

$WstunnelExe = 'C:\wstunnel\wstunnel.exe'
$ListenSpec  = 'udp://39152:127.0.0.1:39152?timeout_sec=0'
$TunnelNames = @('windows', 'windows01', 'windows02')
$WireGuardDir = "$env:ProgramFiles\WireGuard"
# Used only when no 192.168.* default gateway can be seen.
$FallbackGateway = '192.168.8.1'
# =============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-IsAdministrator {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-WireGuardExe {
    foreach ($c in @(
        (Join-Path $WireGuardDir 'wireguard.exe'),
        "$env:ProgramFiles\WireGuard\wireguard.exe",
        "${env:ProgramFiles(x86)}\WireGuard\wireguard.exe"
    )) {
        if ($c -and (Test-Path -LiteralPath $c)) { return $c }
    }
    return $null
}

function Get-RunningWireGuardNames {
    $found = @()
    foreach ($name in $TunnelNames) {
        $svc = Get-Service -Name "WireGuardTunnel`$$name" -ErrorAction SilentlyContinue
        if ($svc -and $svc.Status -eq 'Running') { $found += $name }
    }
    return $found
}

function Get-WstunnelClientProcesses {
    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq 'wstunnel.exe'
    })
    $matched = @($all | Where-Object {
        $_.CommandLine -and ($_.CommandLine -like "*$PathPrefix*")
    })
    if ($matched.Count -gt 0) { return $matched }
    return $all
}

function Get-LanGateway {
    $routes = @(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue)
    $lan = $routes | Where-Object {
        $_.NextHop -like '192.168.*' -and $_.InterfaceAlias -notmatch 'WireGuard|^windows'
    } | Sort-Object RouteMetric | Select-Object -First 1
    if ($lan -and $lan.NextHop) { return [string]$lan.NextHop }
    return $FallbackGateway
}

function Get-TargetAddresses {
    $ips = @()
    if (-not [string]::IsNullOrWhiteSpace($FixedRemote)) {
        $ips += $FixedRemote.Trim()
    }
    try {
        $resolved = @(Resolve-DnsName -Name $SniHost -Type A -ErrorAction Stop |
            Where-Object { $_.Type -eq 'A' -and $_.IPAddress } |
            Select-Object -ExpandProperty IPAddress)
        foreach ($ip in $resolved) {
            if ($ips -notcontains $ip) { $ips += $ip }
        }
    } catch {
        if ($ips.Count -eq 0) {
            throw ("Cannot resolve {0}: {1}" -f $SniHost, $_.Exception.Message)
        }
        Write-Host ("DNS lookup for {0} failed; using {1}" -f $SniHost, ($ips -join ', ')) -ForegroundColor Yellow
    }
    return $ips
}

function Ensure-BypassRoute {
    param(
        [Parameter(Mandatory = $true)][string]$Ip,
        [Parameter(Mandatory = $true)][string]$Gateway
    )
    $existing = @(Get-NetRoute -DestinationPrefix "$Ip/32" -ErrorAction SilentlyContinue)
    foreach ($r in $existing) {
        if ([string]$r.NextHop -eq $Gateway) {
            Write-Host ("route exists: {0} via {1}" -f $Ip, $Gateway)
            return
        }
    }
    if ($existing.Count -gt 0) {
        Write-Host ("replacing route for {0}" -f $Ip) -ForegroundColor Yellow
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & route.exe delete $Ip | Out-Null
        $ErrorActionPreference = $prev
    }
    Write-Host ("route add {0} mask 255.255.255.255 {1}" -f $Ip, $Gateway)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & route.exe add $Ip mask 255.255.255.255 $Gateway
    $ErrorActionPreference = $prev
}

function Stop-WstunnelClients {
    $procs = @(Get-WstunnelClientProcesses)
    foreach ($p in $procs) {
        Write-Host ("stopping wstunnel pid {0}" -f $p.ProcessId)
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    $deadline = (Get-Date).AddSeconds(8)
    do {
        if (@(Get-WstunnelClientProcesses).Count -eq 0) { return $true }
        Start-Sleep -Milliseconds 300
    } while ((Get-Date) -lt $deadline)
    return (@(Get-WstunnelClientProcesses).Count -eq 0)
}

function Disconnect-WireGuardTunnels {
    param([string[]]$Names, [string]$WireGuardExe)
    $ok = $true
    foreach ($name in $Names) {
        Write-Host ("disconnect WireGuard: {0}" -f $name)
        if (-not $WireGuardExe) {
            Write-Host 'wireguard.exe not found' -ForegroundColor Yellow
            $ok = $false
            continue
        }
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & $WireGuardExe /uninstalltunnelservice $name 2>&1 | Out-Host
        $ErrorActionPreference = $prev
        $deadline = (Get-Date).AddSeconds(8)
        $gone = $false
        do {
            $svc = Get-Service -Name "WireGuardTunnel`$$name" -ErrorAction SilentlyContinue
            if (-not $svc -or $svc.Status -ne 'Running') { $gone = $true; break }
            Start-Sleep -Milliseconds 300
        } while ((Get-Date) -lt $deadline)
        if (-not $gone) { $ok = $false }
    }
    return $ok
}

if (-not (Test-IsAdministrator)) {
    Write-Host 'Requesting Administrator (route and WireGuard need it)...' -ForegroundColor Yellow
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @(
        '-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath
    )
    exit 0
}

if (-not (Test-Path -LiteralPath $WstunnelExe)) {
    Write-Host ("wstunnel not found: {0}" -f $WstunnelExe) -ForegroundColor Red
    exit 1
}

$clients = @(Get-WstunnelClientProcesses)
$wgRunning = @(Get-RunningWireGuardNames)

if ($clients.Count -gt 0) {
    Stop-WstunnelClients | Out-Null
    if ($wgRunning.Count -gt 0) {
        $wgExe = Get-WireGuardExe
        Disconnect-WireGuardTunnels -Names $wgRunning -WireGuardExe $wgExe | Out-Null
    }
    Write-Host 'Now the 443 port forward is Closed -_-' -ForegroundColor Red
    exit 0
}

$gateway = Get-LanGateway
$addresses = @(Get-TargetAddresses)
$connectTo = if (-not [string]::IsNullOrWhiteSpace($FixedRemote)) { $FixedRemote.Trim() } else { $addresses[0] }

Write-Host ("gateway: {0}" -f $gateway)
foreach ($ip in $addresses) {
    Ensure-BypassRoute -Ip $ip -Gateway $gateway
}

Write-Host 'Now the 443 port forward is OPEN ^_^' -ForegroundColor Red
$wgRunning = @(Get-RunningWireGuardNames)
if ($wgRunning.Count -eq 0) {
    Write-Host 'Please connect WireGuard' -ForegroundColor Yellow
}

Write-Host ("wstunnel -> {0}  SNI {1}" -f $connectTo, $SniHost)
$wstunnelArgs = @(
    'client',
    '--http-upgrade-path-prefix', $PathPrefix,
    '--tls-sni-override', $SniHost,
    '-H', "Host:$SniHost",
    '--websocket-ping-frequency', '0s',
    '-L', $ListenSpec,
    "wss://${connectTo}:443"
)
& $WstunnelExe @wstunnelArgs
exit $LASTEXITCODE
