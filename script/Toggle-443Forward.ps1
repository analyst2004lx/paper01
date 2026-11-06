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

# Cloudflare entrance. Both A records are probed; only one whose TLS
# handshake actually finishes is used. TCP being open is not enough.
$SniHost = 'wg.datilan.com'
# Used only when its own TLS handshake succeeds. Right now nothing listens
# on this port, so a failed probe skips it instead of camping there.
$DirectIp  = '104.156.231.123'
$DirectSni = 'analy-wg.duckdns.org'
# Optional address to try first. Empty keeps the normal order.
$FixedRemote = ''
# How long a TLS probe may take before the address is skipped.
$ProbeTimeoutMs = 5000
# After "Doing TLS handshake", this many quiet seconds means TLS finished.
$HoldAfterTlsSec = 12
# After the first TCP attempt, give up if TLS is still not up.
$GiveUpSec = 16
# Once TLS has been up, wstunnel may reconnect by itself. If the TCP path
# is still failing after this many seconds, probe the other addresses.
$ReconnectGraceSec = 20
# If wstunnel dies after TLS came up (WireGuard toggle, one remote reset),
# restart that same address this many times before probing again.
$SamePathRetries = 3

$WstunnelExe = 'C:\wstunnel\wstunnel.exe'
$ListenSpec  = 'udp://39152:127.0.0.1:39152?timeout_sec=0'
$TunnelNames = @('windows', 'windows01', 'windows02')
$WireGuardDir = "$env:ProgramFiles\WireGuard"
# Used only when no 192.168.* default gateway can be seen.
$FallbackGateway = '192.168.8.1'
# =============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:TlsCallback = $null

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

function Get-TunnelTargets {
    # Fixed order: optional pin, Cloudflare A records sorted, then the VPS itself.
    # Sorting avoids DNS flipping the "next" address back to the one that just failed.
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($FixedRemote)) {
        $candidates += [pscustomobject]@{ Ip = $FixedRemote.Trim(); Sni = $SniHost }
    }
    try {
        $resolved = @(Resolve-DnsName -Name $SniHost -Type A -ErrorAction Stop |
            Where-Object { $_.Type -eq 'A' -and $_.IPAddress } |
            Select-Object -ExpandProperty IPAddress | Sort-Object)
        foreach ($ip in $resolved) {
            $candidates += [pscustomobject]@{ Ip = [string]$ip; Sni = $SniHost }
        }
    } catch {
        Write-Host ("DNS lookup for {0} failed: {1}" -f $SniHost, $_.Exception.Message) -ForegroundColor Yellow
    }
    $candidates += [pscustomobject]@{ Ip = $DirectIp; Sni = $DirectSni }
    $rows = @()
    $seen = @{}
    foreach ($c in $candidates) {
        if ([string]::IsNullOrWhiteSpace($c.Ip)) { continue }
        $ip = $c.Ip.Trim()
        if ($seen.ContainsKey($ip)) { continue }
        $seen[$ip] = $true
        $rows += [pscustomobject]@{ Ip = $ip; Sni = $c.Sni }
    }
    return @($rows)
}

function Initialize-TlsCallback {
    if ($script:TlsCallback) { return }
    if (-not ('ScriptTlsAccept' -as [type])) {
        Add-Type -TypeDefinition @'
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
public static class ScriptTlsAccept {
    public static bool Any(object sender, X509Certificate certificate, X509Chain chain, SslPolicyErrors sslPolicyErrors) {
        return true;
    }
}
'@
    }
    $script:TlsCallback = [System.Delegate]::CreateDelegate(
        [System.Net.Security.RemoteCertificateValidationCallback],
        [ScriptTlsAccept].GetMethod('Any'))
}

function Test-TlsEndpoint {
    # ok | tcp-timeout | refused | tcp-fail | tls-timeout | tls-fail
    param(
        [Parameter(Mandatory = $true)][string]$Ip,
        [Parameter(Mandatory = $true)][string]$Sni,
        [int]$TimeoutMs = $ProbeTimeoutMs
    )
    Initialize-TlsCallback
    $callback = $script:TlsCallback
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($Ip, 443, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) { return 'tcp-timeout' }
        try {
            $client.EndConnect($iar)
        } catch {
            $inner = $_.Exception
            while ($inner.InnerException) { $inner = $inner.InnerException }
            $msg = [string]$inner.Message
            if ($msg -match '10061|Connection refused|积极拒绝') { return 'refused' }
            return 'tcp-fail'
        }
        $stream = $client.GetStream()
        $stream.ReadTimeout = $TimeoutMs
        $stream.WriteTimeout = $TimeoutMs
        $ssl = New-Object System.Net.Security.SslStream($stream, $false, $callback)
        $task = $ssl.AuthenticateAsClientAsync($Sni)
        $done = $false
        try {
            $done = $task.Wait($TimeoutMs)
        } catch {
            $inner = $_.Exception
            while ($inner.InnerException) { $inner = $inner.InnerException }
            $msg = [string]$inner.Message
            if ($msg -match 'timed out|timeout|超时') { return 'tls-timeout' }
            return 'tls-fail'
        }
        if (-not $done) { return 'tls-timeout' }
        if ($task.IsFaulted) { return 'tls-fail' }
        return 'ok'
    } catch {
        return 'tls-fail'
    } finally {
        try { $client.Close() } catch { }
    }
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

function Get-SupervisorProcesses {
    $me = $PID
    return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ProcessId -ne $me -and
        $_.CommandLine -and
        ($_.CommandLine -like '*Toggle-443Forward.ps1*')
    })
}

function Format-ProcessArg {
    param([string]$Value)
    if ($Value -notmatch '[\s"]') { return $Value }
    return '"' + ($Value.Replace('"', '\"')) + '"'
}

function Get-WgPeerStat {
    # Bytes and last handshake for the WireGuard peer aimed at this wstunnel.
    $wg = Join-Path $WireGuardDir 'wg.exe'
    if (-not (Test-Path -LiteralPath $wg)) { return $null }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $raw = @(& $wg show all dump 2>&1 | Where-Object { $_ -is [string] })
    $ErrorActionPreference = $prev
    $fallback = $null
    foreach ($line in $raw) {
        $p = [string]$line -split "`t"
        if ($p.Count -lt 8) { continue }
        if ($p[4] -notmatch '^\d+$') { continue }
        $stat = [pscustomobject]@{
            Handshake = [int64]$p[4]
            Rx        = [int64]$p[5]
            Tx        = [int64]$p[6]
        }
        if ($p[2] -like '127.0.0.1:*') { return $stat }
        if (-not $fallback) { $fallback = $stat }
    }
    return $fallback
}

function Start-WstunnelClient {
    param(
        [Parameter(Mandatory = $true)][string]$Ip,
        [Parameter(Mandatory = $true)][string]$Sni
    )
    $parts = @(
        'client',
        '--no-color',
        '--http-upgrade-path-prefix', $PathPrefix,
        '--tls-sni-override', $Sni,
        '-H', "Host:$Sni",
        '--websocket-ping-frequency', '15s',
        '--connection-retry-max-backoff', '2s',
        '-L', $ListenSpec,
        "wss://${Ip}:443"
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $WstunnelExe
    $psi.Arguments = (($parts | ForEach-Object { Format-ProcessArg $_ }) -join ' ')
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $proc.EnableRaisingEvents = $true
    [void]$proc.Start()
    return $proc
}

function Invoke-OneWstunnel {
    # Returns stop | retry | next
    param(
        [Parameter(Mandatory = $true)]$Target,
        [Parameter(Mandatory = $true)][string]$StopFile
    )
    # Lines are queued by the event thread and judged on this thread.
    # A shared hashtable was not visible to the event thread in time, so the
    # reset at 15:56 was ignored for about two minutes.
    $queue = New-Object 'System.Collections.Concurrent.ConcurrentQueue[string]'
    $proc = Start-WstunnelClient -Ip $Target.Ip -Sni $Target.Sni
    $sid = [guid]::NewGuid().ToString('n')
    $onLine = {
        $line = $EventArgs.Data
        if ([string]::IsNullOrEmpty($line)) { return }
        $q = [System.Collections.Concurrent.ConcurrentQueue[string]]$Event.MessageData
        $q.Enqueue($line)
    }
    $null = Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -MessageData $queue -SourceIdentifier "wstunnel-out-$sid" -Action $onLine
    $null = Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -MessageData $queue -SourceIdentifier "wstunnel-err-$sid" -Action $onLine
    $openings = 0
    $tlsFails = 0
    $established = $false
    $failover = $false
    $attemptAt = $null
    $tlsAt = $null
    $downSince = $null
    $lastFailAt = $null
    $wgNext = $null
    $wgMark = $null
    try {
        $proc.BeginOutputReadLine()
        $proc.BeginErrorReadLine()
        while (-not $proc.HasExited -and -not $failover) {
            if (Test-Path -LiteralPath $StopFile) { break }
            $line = ''
            while ($queue.TryDequeue([ref]$line)) {
                Write-Host $line
                $isFail = $line -match 'os error 10054|Timed out after \d+s doing the TLS handshake|Cannot connect to tcp endpoint|failed to get a connection to the server from the pool: TimedOut|10061|Connection refused|积极拒绝'
                if ($line -match 'Opening TCP connection') {
                    $openings++
                    if (-not $attemptAt) { $attemptAt = Get-Date }
                    if (-not $established -and $openings -ge 2) { $failover = $true }
                } elseif ($line -match 'Doing TLS handshake') {
                    if (-not $tlsAt) { $tlsAt = Get-Date }
                } elseif ($isFail) {
                    $lastFailAt = Get-Date
                    if ($line -match 'Timed out after \d+s doing the TLS handshake') { $tlsFails++ }
                    if (-not $established) {
                        if ($line -notmatch 'failed to get a connection to the server from the pool') { $failover = $true }
                    } elseif (-not $downSince) {
                        $downSince = Get-Date
                        Write-Host ("{0} dropped the TCP session. Leaving wstunnel to reconnect for {1}s." -f $Target.Ip, $ReconnectGraceSec) -ForegroundColor Yellow
                    }
                }
            }
            if ($tlsAt -and -not $established -and $tlsFails -eq 0 -and $openings -le 1) {
                if (((Get-Date) - $tlsAt).TotalSeconds -ge $HoldAfterTlsSec) {
                    $established = $true
                    Write-Host ("TLS is up on {0}. Holding this path." -f $Target.Ip) -ForegroundColor Green
                }
            }
            if ($attemptAt -and -not $established) {
                if (((Get-Date) - $attemptAt).TotalSeconds -ge $GiveUpSec) { $failover = $true }
            }
            if ($established -and $downSince) {
                $quiet = $lastFailAt -and ((Get-Date) - $lastFailAt).TotalSeconds -ge $HoldAfterTlsSec
                if ($quiet) {
                    $downSince = $null
                    $lastFailAt = $null
                    Write-Host ("{0} reconnected." -f $Target.Ip) -ForegroundColor Green
                } elseif (((Get-Date) - $downSince).TotalSeconds -ge $ReconnectGraceSec) {
                    $failover = $true
                }
            }
            # wstunnel stays quiet when the WebSocket is half-open. WireGuard
            # then retries every 5s and almost nothing comes back.
            if ($established -and -not $downSince -and -not $failover) {
                if (-not $wgNext -or (Get-Date) -ge $wgNext) {
                    $wgNext = (Get-Date).AddSeconds(5)
                    $stat = Get-WgPeerStat
                    if ($stat) {
                        $unixNow = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
                        if ($stat.Handshake -eq 0) {
                            if ($tlsAt -and ((Get-Date) - $tlsAt).TotalSeconds -ge 40) {
                                Write-Host 'WireGuard has no handshake. Probing again.' -ForegroundColor Yellow
                                $failover = $true
                            }
                        } elseif (($unixNow - $stat.Handshake) -gt 150) {
                            Write-Host ("WireGuard handshake is {0}s old. Probing again." -f ($unixNow - $stat.Handshake)) -ForegroundColor Yellow
                            $failover = $true
                        }
                        if (-not $failover -and $wgMark -and ((Get-Date) - $wgMark.At).TotalSeconds -ge 20) {
                            $txd = $stat.Tx - $wgMark.Tx
                            $rxd = $stat.Rx - $wgMark.Rx
                            if ($txd -gt 500 -and $rxd -lt 250) {
                                Write-Host 'WireGuard is retrying handshakes and receiving nothing. Probing again.' -ForegroundColor Yellow
                                $failover = $true
                            }
                            $wgMark = [pscustomobject]@{ At = Get-Date; Tx = $stat.Tx; Rx = $stat.Rx }
                        } elseif (-not $wgMark) {
                            $wgMark = [pscustomobject]@{ At = Get-Date; Tx = $stat.Tx; Rx = $stat.Rx }
                        }
                    }
                }
            }
            Start-Sleep -Milliseconds 300
        }
    } finally {
        if (-not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            $null = $proc.WaitForExit(4000)
        }
        Unregister-Event -SourceIdentifier "wstunnel-out-$sid" -ErrorAction SilentlyContinue
        Unregister-Event -SourceIdentifier "wstunnel-err-$sid" -ErrorAction SilentlyContinue
        Get-Job -Name "wstunnel-out-$sid","wstunnel-err-$sid" -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $StopFile) { return 'stop' }
    if ($failover) {
        Write-Host ("{0} still down after the reconnect wait (openings={1}, tls-timeout={2}). Probing again." -f $Target.Ip, $openings, $tlsFails) -ForegroundColor Yellow
        return 'next'
    }
    # Process exited without a connect failure. A WireGuard toggle resets the
    # local UDP socket and makes wstunnel quit; that path itself may still be good.
    if ($established) {
        Write-Host ("{0} dropped after TLS. Restarting this path." -f $Target.Ip) -ForegroundColor Yellow
        return 'retry'
    }
    Write-Host ("{0} exited before TLS. Probing again." -f $Target.Ip) -ForegroundColor Yellow
    return 'next'
}

function Invoke-WstunnelSupervisor {
    param(
        [Parameter(Mandatory = $true)][string]$Gateway,
        [Parameter(Mandatory = $true)][string]$StopFile
    )
    while ($true) {
        if (Test-Path -LiteralPath $StopFile) { return }
        $targets = @(Get-TunnelTargets)
        if ($targets.Count -eq 0) {
            Write-Host 'No path to try. Retrying in 5s.' -ForegroundColor Yellow
            Start-Sleep -Seconds 5
            continue
        }
        foreach ($t in $targets) { Ensure-BypassRoute -Ip $t.Ip -Gateway $Gateway }
        $chosen = $null
        foreach ($t in $targets) {
            if (Test-Path -LiteralPath $StopFile) { return }
            $probe = Test-TlsEndpoint -Ip $t.Ip -Sni $t.Sni
            Write-Host ("probe {0} [{1}] {2}" -f $t.Ip, $t.Sni, $probe)
            if ($probe -eq 'ok' -and -not $chosen) { $chosen = $t }
        }
        if (-not $chosen) {
            Write-Host 'No path completed TLS. Retrying in 5s.' -ForegroundColor Yellow
            Start-Sleep -Seconds 5
            continue
        }
        $retries = 0
        while ($true) {
            if (Test-Path -LiteralPath $StopFile) { return }
            Write-Host ("wstunnel -> {0}  SNI {1}" -f $chosen.Ip, $chosen.Sni)
            $result = Invoke-OneWstunnel -Target $chosen -StopFile $StopFile
            if ($result -eq 'stop') { return }
            if ($result -eq 'retry' -and $retries -lt $SamePathRetries) {
                $retries++
                Start-Sleep -Seconds 1
                continue
            }
            break
        }
        Start-Sleep -Seconds 1
    }
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

$StopFile = Join-Path $env:TEMP 'Toggle-443Forward.stop'
$clients = @(Get-WstunnelClientProcesses)
$supervisors = @(Get-SupervisorProcesses)
$wgRunning = @(Get-RunningWireGuardNames)

if ($clients.Count -gt 0 -or $supervisors.Count -gt 0) {
    New-Item -ItemType File -Path $StopFile -Force | Out-Null
    foreach ($sup in $supervisors) {
        Write-Host ("stopping supervisor pid {0}" -f $sup.ProcessId)
        Stop-Process -Id $sup.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Stop-WstunnelClients | Out-Null
    if ($wgRunning.Count -gt 0) {
        $wgExe = Get-WireGuardExe
        Disconnect-WireGuardTunnels -Names $wgRunning -WireGuardExe $wgExe | Out-Null
    }
    Remove-Item -LiteralPath $StopFile -Force -ErrorAction SilentlyContinue
    Write-Host 'Now the 443 port forward is Closed -_-' -ForegroundColor Red
    exit 0
}

Remove-Item -LiteralPath $StopFile -Force -ErrorAction SilentlyContinue
$gateway = Get-LanGateway
$targets = @(Get-TunnelTargets)

Write-Host ("gateway: {0}" -f $gateway)
foreach ($t in $targets) {
    Ensure-BypassRoute -Ip $t.Ip -Gateway $gateway
}

Write-Host 'Now the 443 port forward is OPEN ^_^' -ForegroundColor Red
$pathText = ($targets | ForEach-Object { '{0} [{1}]' -f $_.Ip, $_.Sni }) -join ', '
Write-Host ("Paths: {0}" -f $pathText)
$wgRunning = @(Get-RunningWireGuardNames)
if ($wgRunning.Count -eq 0) {
    Write-Host 'Please connect WireGuard' -ForegroundColor Yellow
}

try {
    Invoke-WstunnelSupervisor -Gateway $gateway -StopFile $StopFile
} finally {
    if (Test-Path -LiteralPath $StopFile) {
        Remove-Item -LiteralPath $StopFile -Force -ErrorAction SilentlyContinue
    }
}
exit 0
