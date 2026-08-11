#Requires -Version 5.1
<#
.SYNOPSIS
  Daytime sync between a GitHub repo and a local folder.

.DESCRIPTION
  Compare content hashes first. If equal, skip.
  If different, three-way vs merge-base:
    - only local changed  -> push
    - only remote changed -> pull/overwrite local
    - both changed        -> conflict (skip; log path)
  Falls back to hash+mtime when merge-base is unavailable.

.NOTES
  Requires Git for Windows and push permission to the repo.
#>
param(
    [switch]$Force,
    [switch]$WhatIf
)

# ======================== USER CONFIG ========================
# WARNING: LocalFolder is synced with the ENTIRE GitHub repo.
# If the repo is only for paper files, prefer a dedicated subfolder, e.g.
#   LocalFolder = Join-Path $env:USERPROFILE 'Desktop\AI_Folder\paper01'
#
# Default: parent of this script folder (…\AI_Folder\script -> …\AI_Folder).
# Works on any PC / any Windows username without hardcoding paths.
$Config = @{
    LocalFolder   = (Split-Path -Parent $PSScriptRoot)
    RepoUrl       = 'https://github.com/analyst2004lx/paper01'
    # Use 'master' if your default branch is master; empty = auto-detect
    Branch        = 'main'
    WindowStart   = '10:00'
    WindowEnd     = '17:00'
    LogDir        = (Join-Path $PSScriptRoot 'logs')
    CommitPrefix  = 'auto-sync'
    NewerSkewSec  = 5
    # When merge-base missing and hashes differ: 'Mtime' = who-newer wins; 'Conflict' = skip
    DivergedFallback = 'Mtime'
    # On content-identical: align local LastWriteTime to remote commit time.
    # Default off — three-way sync no longer needs mtime; enabling costs 1x git-log per file.
    AlignMtimeWhenEqual = $false
    SyncDeletions = $false
    # Used only for commits made by this script (does not change your global git config)
    GitUserName   = 'analyst2004lx'
    GitUserEmail  = 'analyst2004lx@users.noreply.github.com'
    # Relative folders under LocalFolder to ignore entirely (folder + all contents).
    # Add more as needed, e.g. 'script\temp', 'script\cache'
    # LogDir is also auto-ignored when it lies under LocalFolder.
    IgnoreFolders = @(
        'script\logs'
        #'script\logs'
    )
    # Match by exact relative path, path prefix, or any path segment (file/folder name)
    IgnoreNames   = @(
        '.git'
        '.cursor'
        'node_modules'
        '.venv'
        '__pycache__'
        'Thumbs.db'
        '.DS_Store'
    )
    # Optional list file: <Ignore>...</Ignore> skip sync; <Delete>...</Delete> remove from GitHub.
    # If a path is in both, Ignore wins. Missing paths are skipped.
    IgnoreDeleteListFile = (Join-Path $PSScriptRoot 'Sync-GitHub-Ignore_and_Delete.txt')
    GitPath       = ''
    # GitHub fetch often stalls on flaky links: retry + hard timeout (seconds)
    FetchRetries     = 5
    FetchRetrySec    = 6
    FetchTimeoutSec  = 90
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
        if (-not (Test-Path -LiteralPath $script:LogDir)) {
            New-Item -ItemType Directory -Path $script:LogDir -Force | Out-Null
        }
        Add-Content -LiteralPath $script:LogFile -Value $line -Encoding UTF8
    } catch {}
}

function Get-GitExe {
    if ($Config.GitPath -and (Test-Path -LiteralPath $Config.GitPath)) {
        return $Config.GitPath
    }
    $cmd = Get-Command git -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($c in @(
        'C:\Program Files\Git\cmd\git.exe',
        'C:\Program Files (x86)\Git\cmd\git.exe'
    )) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    throw 'git.exe not found. Install Git for Windows or set Config.GitPath.'
}

function ConvertFrom-GitQuotedPath {
    param([string]$Path)
    # Decode git quotepath style: "\345\273\272...." -> real UTF-8 path
    if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }
    $p = $Path.Trim()
    if (-not ($p.StartsWith('"') -and $p.EndsWith('"') -and $p.Length -ge 2)) {
        return $p
    }
    $inner = $p.Substring(1, $p.Length - 2)
    $byteList = New-Object System.Collections.Generic.List[byte]
    $i = 0
    while ($i -lt $inner.Length) {
        if ($inner[$i] -eq [char]'\' -and ($i + 3) -lt $inner.Length -and
            $inner.Substring($i + 1, 3) -match '^[0-7]{3}$') {
            $byteList.Add([byte][Convert]::ToInt32($inner.Substring($i + 1, 3), 8))
            $i += 4
            continue
        }
        if ($inner[$i] -eq [char]'\' -and ($i + 1) -lt $inner.Length) {
            $n = $inner[$i + 1]
            switch ($n) {
                'n' { [void]$byteList.Add(10) }
                't' { [void]$byteList.Add(9) }
                'r' { [void]$byteList.Add(13) }
                '"' { [void]$byteList.Add([byte][char]'"') }
                '\' { [void]$byteList.Add([byte][char]'\') }
                default {
                    foreach ($b in [System.Text.Encoding]::UTF8.GetBytes([string]$n)) {
                        [void]$byteList.Add($b)
                    }
                }
            }
            $i += 2
            continue
        }
        foreach ($b in [System.Text.Encoding]::UTF8.GetBytes([string]$inner[$i])) {
            [void]$byteList.Add($b)
        }
        $i++
    }
    return [System.Text.Encoding]::UTF8.GetString($byteList.ToArray())
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string[]]$GitArgs,
        [string]$WorkDir = $Config.LocalFolder,
        [switch]$AllowFail,
        [switch]$WithCommitIdentity,
        # Print "still running" every N seconds (0 = silent wait)
        [int]$HeartbeatSec = 15,
        # Kill git if it exceeds this many seconds (0 = wait forever)
        [int]$TimeoutSec = 0
    )
    $git = $script:GitExe

    # Always disable quotepath so Chinese paths are not shown as \345\273\272...
    $prefix = @('-c', 'core.quotepath=false', '-c', 'i18n.logoutputencoding=utf-8')
    if ($WithCommitIdentity) {
        if ($Config.GitUserName)  { $prefix += @('-c', ('user.name={0}' -f $Config.GitUserName)) }
        if ($Config.GitUserEmail) { $prefix += @('-c', ('user.email={0}' -f $Config.GitUserEmail)) }
    }
    $allArgs = $prefix + $GitArgs
    $cmdLabel = ($GitArgs -join ' ')
    Write-Log ('git {0}  (cwd={1})' -f $cmdLabel, $WorkDir) -Level DEBUG

    $argList = @()
    foreach ($a in $allArgs) { $argList += [string]$a }

    $code = 1
    $stdout = ''
    $stderr = ''
    $timedOut = $false
    $proc = $null
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $git
        $psi.Arguments = (($argList | ForEach-Object {
            $a = $_
            if ($a -match '[\s"]') { '"' + ($a -replace '"', '\"') + '"' } else { $a }
        }) -join ' ')
        $psi.WorkingDirectory = $WorkDir
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $psi.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
        $psi.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)

        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi
        [void]$proc.Start()

        # Read both streams asynchronously to prevent buffer deadlock
        $outTask = $proc.StandardOutput.ReadToEndAsync()
        $errTask = $proc.StandardError.ReadToEndAsync()

        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $lastBeat = 0
        while (-not $proc.HasExited) {
            Start-Sleep -Milliseconds 500
            if ($TimeoutSec -gt 0 -and $sw.Elapsed.TotalSeconds -ge $TimeoutSec) {
                $timedOut = $true
                Write-Log ('TIMEOUT after {0}s — killing git: {1}' -f $TimeoutSec, $cmdLabel) -Level WARN
                try { $proc.Kill() } catch {}
                # Also kill helper (git-remote-https) that may keep the pack download hung
                Get-Process -Name 'git-remote-https','git' -ErrorAction SilentlyContinue |
                    Where-Object { $_.Id -ne $PID } |
                    ForEach-Object {
                        try {
                            # Only kill children started around this command window
                            if ($_.StartTime -ge $sw.StartTime.AddSeconds(-2)) {
                                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
                            }
                        } catch {}
                    }
                break
            }
            if ($HeartbeatSec -gt 0 -and $sw.Elapsed.TotalSeconds -ge ($lastBeat + $HeartbeatSec)) {
                $lastBeat = [int]$sw.Elapsed.TotalSeconds
                Write-Log ('... git still running ({0}s): {1}' -f $lastBeat, $cmdLabel) -Level INFO
            }
        }
        try { $stdout = $outTask.Result } catch { $stdout = '' }
        try { $stderr = $errTask.Result } catch { $stderr = '' }
        if ($timedOut) {
            $code = 124
            if ([string]::IsNullOrWhiteSpace($stderr)) {
                $stderr = ("Timed out after {0}s (likely stalled GitHub download)." -f $TimeoutSec)
            }
        } else {
            $code = $proc.ExitCode
        }
        if ($sw.Elapsed.TotalSeconds -ge 3) {
            Write-Log ('git finished in {0:N1}s (exit={1}): {2}' -f $sw.Elapsed.TotalSeconds, $code, $cmdLabel) -Level DEBUG
        }
    } catch {
        $code = 1
        $stderr = $_.Exception.Message
    } finally {
        if ($null -ne $proc) { $proc.Dispose() }
    }

    $parts = @()
    if (-not [string]::IsNullOrWhiteSpace($stdout)) { $parts += $stdout.TrimEnd() }
    if (-not [string]::IsNullOrWhiteSpace($stderr)) { $parts += $stderr.TrimEnd() }
    $text = ($parts -join [Environment]::NewLine).Trim()

    if ($code -ne 0) {
        if ($AllowFail) {
            return [pscustomobject]@{ ExitCode = $code; Output = $text }
        }
        throw ('git failed (exit={0}): git {1}{2}{3}' -f $code, $cmdLabel, [Environment]::NewLine, $text)
    }
    return [pscustomobject]@{ ExitCode = 0; Output = $text }
}

function Get-TimeOfDayMinutes {
    param([Parameter(Mandatory = $true)][string]$HhMm)
    # Accept "10:00", "10:00:00", allow spaces; culture-invariant
    $s = $HhMm.Trim()
    if ($s -notmatch '^(\d{1,2}):(\d{2})(?::\d{2})?$') {
        throw ("Invalid time '{0}'. Use HH:mm like 10:00." -f $HhMm)
    }
    $h = [int]$Matches[1]
    $m = [int]$Matches[2]
    if ($h -lt 0 -or $h -gt 23 -or $m -lt 0 -or $m -gt 59) {
        throw ("Invalid time '{0}'. Hour 0-23, minute 0-59." -f $HhMm)
    }
    return ($h * 60 + $m)
}

function Test-InTimeWindow {
    param([datetime]$Now = (Get-Date))
    # Compare by minutes-from-midnight to avoid culture-specific ParseExact issues
    $nowMin   = $Now.Hour * 60 + $Now.Minute
    $startMin = Get-TimeOfDayMinutes -HhMm $Config.WindowStart
    $endMin   = Get-TimeOfDayMinutes -HhMm $Config.WindowEnd
    if ($startMin -le $endMin) {
        return ($nowMin -ge $startMin -and $nowMin -le $endMin)
    }
    # Overnight window e.g. 22:00-06:00
    return ($nowMin -ge $startMin -or $nowMin -le $endMin)
}

function Normalize-RelPathEntry {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    $s = $Path.Trim().Trim('"').Replace('/', '\').TrimStart('\').TrimEnd('\')
    if ([string]::IsNullOrWhiteSpace($s)) { return $null }
    if ($s.StartsWith('#')) { return $null }
    return $s
}

function Test-PathCoveredByEntry {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Entry
    )
    $norm = ($RelativePath -replace '/', '\').TrimStart('\').TrimEnd('\')
    $ent  = Normalize-RelPathEntry $Entry
    if ([string]::IsNullOrWhiteSpace($ent)) { return $false }
    if ($norm -eq $ent) { return $true }
    if ($norm.StartsWith(($ent + '\'), [StringComparison]::OrdinalIgnoreCase)) { return $true }
    return $false
}

function Read-IgnoreDeleteList {
    param([string]$ListFile)
    $ignore = New-Object 'System.Collections.Generic.List[string]'
    $delete = New-Object 'System.Collections.Generic.List[string]'
    if ([string]::IsNullOrWhiteSpace($ListFile) -or -not (Test-Path -LiteralPath $ListFile -PathType Leaf)) {
        return [pscustomobject]@{ Ignore = @(); Delete = @(); Loaded = $false }
    }

    # UTF-8 (with or without BOM)
    $raw = [System.IO.File]::ReadAllText($ListFile, [System.Text.UTF8Encoding]::new($false))
    if ($raw.Length -gt 0 -and [int][char]$raw[0] -eq 0xFEFF) { $raw = $raw.Substring(1) }

    function Read-TaggedBlock([string]$Text, [string]$Tag) {
        $out = New-Object 'System.Collections.Generic.List[string]'
        # Tags must start a line (avoids matching mentions inside # comments).
        $pattern = '(?ims)^\s*<{0}\s*>\s*$(.*?)^\s*</{0}\s*>\s*$' -f [regex]::Escape($Tag)
        foreach ($m in [regex]::Matches($Text, $pattern)) {
            $body = $m.Groups[1].Value
            foreach ($line in ($body -split "`r?`n")) {
                $n = Normalize-RelPathEntry $line
                if ($null -ne $n) { [void]$out.Add($n) }
            }
        }
        return @($out)
    }

    foreach ($p in @(Read-TaggedBlock $raw 'Ignore')) { [void]$ignore.Add($p) }
    foreach ($p in @(Read-TaggedBlock $raw 'Delete')) { [void]$delete.Add($p) }

    return [pscustomobject]@{
        Ignore = @($ignore | Select-Object -Unique)
        Delete = @($delete | Select-Object -Unique)
        Loaded = $true
    }
}

function Get-EffectiveIgnoreFolders {
    # Relative folder paths (Windows '\') that should be fully ignored
    $set = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)

    foreach ($f in @($Config.IgnoreFolders)) {
        if ($null -eq $f) { continue }
        $s = Normalize-RelPathEntry ([string]$f)
        if (-not [string]::IsNullOrWhiteSpace($s)) { [void]$set.Add($s) }
    }

    # Always ignore LogDir when it is inside LocalFolder (multi-PC safe)
    if ($Config.LogDir -and $Config.LocalFolder) {
        try {
            $logFull  = [System.IO.Path]::GetFullPath($Config.LogDir)
            $rootFull = [System.IO.Path]::GetFullPath($Config.LocalFolder).TrimEnd('\')
            $prefix = $rootFull + '\'
            if ($logFull.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
                $logFull.Equals($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
                $rel = if ($logFull.Length -le $rootFull.Length) { '' }
                       else { $logFull.Substring($rootFull.Length).TrimStart('\') }
                if (-not [string]::IsNullOrWhiteSpace($rel)) { [void]$set.Add($rel) }
            }
        } catch {}
    }

    return @($set)
}

function Test-ListIgnoredPath {
    param([string]$RelativePath)
    foreach ($ent in @($script:ListIgnorePaths)) {
        if (Test-PathCoveredByEntry -RelativePath $RelativePath -Entry $ent) { return $true }
    }
    return $false
}

function Test-ListDeletePath {
    param([string]$RelativePath)
    # Ignore wins over Delete
    if (Test-ListIgnoredPath -RelativePath $RelativePath) { return $false }
    foreach ($ent in @($script:ListDeletePaths)) {
        if (Test-PathCoveredByEntry -RelativePath $RelativePath -Entry $ent) { return $true }
    }
    return $false
}

function Test-IgnoredPath {
    param([string]$RelativePath)
    $norm = ($RelativePath -replace '/', '\').TrimStart('\')
    # NTFS alternate data streams e.g. file.pdf:Zone.Identifier
    if ($norm -match ':') { return $true }
    if ($norm -match 'Zone\.Identifier$') { return $true }

    foreach ($folder in @(Get-EffectiveIgnoreFolders)) {
        if ($norm -eq $folder) { return $true }
        if ($norm.StartsWith(($folder + '\'), [StringComparison]::OrdinalIgnoreCase)) { return $true }
    }

    foreach ($ig in @($Config.IgnoreNames)) {
        if ($null -eq $ig) { continue }
        $igNorm = Normalize-RelPathEntry ([string]$ig)
        if ([string]::IsNullOrWhiteSpace($igNorm)) { continue }
        if ($norm -eq $igNorm) { return $true }
        if ($norm.StartsWith(($igNorm + '\'), [StringComparison]::OrdinalIgnoreCase)) { return $true }
        $parts = $norm.Split('\')
        if ($parts -contains $igNorm) { return $true }
    }

    # From Sync-GitHub-Ignore_and_Delete.txt: Ignore entries, and Delete entries
    # (Delete paths are excluded from pull/push so they are not re-synced after remote removal).
    if (Test-ListIgnoredPath -RelativePath $norm) { return $true }
    if (Test-ListDeletePath -RelativePath $norm) { return $true }

    return $false
}

function Test-SafeRelativePath {
    param([string]$RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath)) { return $false }
    # Windows invalid filename chars (also breaks Join-Path). Allow Unicode letters.
    if ($RelativePath -match '[<>:"|?*\x00-\x1F]') { return $false }
    if ($RelativePath -match '(^|[\\/])\.\.([\\/]|$)') { return $false }
    return $true
}

function Get-LocalPathFromRel {
    param([Parameter(Mandatory = $true)][string]$RelGit)
    $relWin = ($RelGit -replace '/', '\').TrimStart('\')
    if (-not (Test-SafeRelativePath -RelativePath $relWin)) {
        throw ("Unsafe relative path: {0}" -f $RelGit)
    }
    return [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($Config.LocalFolder, $relWin))
}

function Get-FileUnixTime {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return [int64]([DateTimeOffset](Get-Item -LiteralPath $Path).LastWriteTimeUtc).ToUnixTimeSeconds()
}

$script:LogDir  = $Config.LogDir
$script:LogFile = Join-Path $Config.LogDir ('sync-{0}.log' -f (Get-Date -Format 'yyyyMMdd'))
$script:GitExe  = $null
$script:ListIgnorePaths = @()
$script:ListDeletePaths = @()

try {
    Write-Log '========== sync start =========='
    Write-Log ('LocalFolder: {0}' -f $Config.LocalFolder)
    Write-Log ('RepoUrl: {0}' -f $Config.RepoUrl)

    $listInfo = Read-IgnoreDeleteList -ListFile $Config.IgnoreDeleteListFile
    $script:ListIgnorePaths = @($listInfo.Ignore)
    $script:ListDeletePaths = @($listInfo.Delete)
    if ($listInfo.Loaded) {
        Write-Log ('IgnoreDeleteList: {0}' -f $Config.IgnoreDeleteListFile)
        Write-Log ('  <Ignore> entries: {0}' -f $script:ListIgnorePaths.Count)
        if ($script:ListIgnorePaths.Count -gt 0) {
            Write-Log (('    ' + ($script:ListIgnorePaths -join '; '))) -Level DEBUG
        }
        Write-Log ('  <Delete> entries: {0}' -f $script:ListDeletePaths.Count)
        if ($script:ListDeletePaths.Count -gt 0) {
            Write-Log (('    ' + ($script:ListDeletePaths -join '; '))) -Level DEBUG
        }
    } else {
        Write-Log ('IgnoreDeleteList not found (optional): {0}' -f $Config.IgnoreDeleteListFile) -Level DEBUG
    }

    Write-Log ('IgnoreFolders: {0}' -f ((@(Get-EffectiveIgnoreFolders) -join ', ')))
    Write-Log ('Force={0} WhatIf={1}' -f $Force, $WhatIf)

    if (-not $Force) {
        if (-not (Test-InTimeWindow)) {
            Write-Log ('Now {0} outside window {1}-{2}, skip. Use -Force to override.' -f `
                (Get-Date -Format 'HH:mm:ss'), $Config.WindowStart, $Config.WindowEnd) -Level WARN
            exit 0
        }
        Write-Log ('Inside window {0}-{1}' -f $Config.WindowStart, $Config.WindowEnd)
    } else {
        Write-Log 'Force specified, skip time window check' -Level WARN
    }

    $script:GitExe = Get-GitExe
    Write-Log ('Git: {0}' -f $script:GitExe)
    Write-Log (Invoke-Git -GitArgs @('--version') -WorkDir $env:TEMP).Output

    # Remove stale .git/*.lock left by crashed/interrupted git (common after Ctrl+C / network fail)
    function Clear-StaleGitLocks {
        param([string]$RepoRoot, [int]$MinAgeSec = 60)
        $gitMeta = Join-Path $RepoRoot '.git'
        if (-not (Test-Path -LiteralPath $gitMeta)) { return }
        $gitRunning = @(Get-Process -Name 'git','git-remote-https','git-remote-http' -ErrorAction SilentlyContinue)
        if ($gitRunning.Count -gt 0) {
            Write-Log ('Other git process running (PIDs: {0}); leave lock files alone.' -f `
                (($gitRunning | ForEach-Object { $_.Id }) -join ',')) -Level WARN
            return
        }
        $locks = @(Get-ChildItem -LiteralPath $gitMeta -Filter '*.lock' -Force -ErrorAction SilentlyContinue)
        # also index.lock at .git root
        $indexLock = Join-Path $gitMeta 'index.lock'
        if ((Test-Path -LiteralPath $indexLock) -and ($locks.FullName -notcontains $indexLock)) {
            $locks += Get-Item -LiteralPath $indexLock -Force
        }
        foreach ($lk in $locks) {
            $age = ((Get-Date) - $lk.LastWriteTime).TotalSeconds
            if ($age -lt $MinAgeSec) {
                Write-Log ('Lock is recent ({0:N0}s): {1} — skip auto-remove' -f $age, $lk.Name) -Level WARN
                continue
            }
            try {
                Remove-Item -LiteralPath $lk.FullName -Force -ErrorAction Stop
                Write-Log ('Removed stale lock: {0} (age {1:N0}s)' -f $lk.Name, $age) -Level WARN
            } catch {
                Write-Log ('Cannot remove lock {0}: {1}' -f $lk.Name, $_.Exception.Message) -Level WARN
            }
        }
    }
    Clear-StaleGitLocks -RepoRoot $Config.LocalFolder

    if (-not (Test-Path -LiteralPath $Config.LocalFolder)) {
        Write-Log ('Local folder missing, create: {0}' -f $Config.LocalFolder) -Level WARN
        if (-not $WhatIf) {
            New-Item -ItemType Directory -Path $Config.LocalFolder -Force | Out-Null
        }
    }

    $gitDir = Join-Path $Config.LocalFolder '.git'
    $gitDirExists = Test-Path -LiteralPath $gitDir
    # Do not trust a mere .git folder — empty/corrupt leftover is common after failed sync
    $probe = Invoke-Git -GitArgs @('rev-parse', '--is-inside-work-tree') -AllowFail
    $isRepo = ($probe.ExitCode -eq 0 -and $probe.Output.Trim() -eq 'true')

    if ($gitDirExists -and -not $isRepo) {
        Write-Log 'Found broken/empty .git (not a valid repo). Removing it so we can re-init...' -Level WARN
        if (-not $WhatIf) {
            try {
                # Clear ReadOnly/Hidden so Remove-Item can delete
                Get-ChildItem -LiteralPath $gitDir -Force -Recurse -ErrorAction SilentlyContinue |
                    ForEach-Object { $_.Attributes = 'Normal' }
                $item = Get-Item -LiteralPath $gitDir -Force
                $item.Attributes = 'Normal'
                Remove-Item -LiteralPath $gitDir -Recurse -Force -ErrorAction Stop
                Write-Log 'Removed broken .git'
            } catch {
                throw ("Cannot remove broken .git: {0}. Delete it manually then re-run." -f $_.Exception.Message)
            }
        }
        $gitDirExists = $false
    }

    if (-not $isRepo) {
        Write-Log 'Not a git repo yet; clone or init...'
        $items = @(Get-ChildItem -LiteralPath $Config.LocalFolder -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne '.git' })
        if ($items.Count -eq 0) {
            if ($WhatIf) {
                Write-Log ('[WhatIf] would clone {0}' -f $Config.RepoUrl)
            } else {
                Invoke-Git -GitArgs @('clone', $Config.RepoUrl, '.') -WorkDir $Config.LocalFolder | Out-Null
                Write-Log 'clone done'
            }
        } else {
            Write-Log 'Folder not empty and has no valid .git: git init + remote add (files kept)' -Level WARN
            if (-not $WhatIf) {
                Invoke-Git -GitArgs @('init') | Out-Null
                Invoke-Git -GitArgs @('remote', 'remove', 'origin') -AllowFail | Out-Null
                Invoke-Git -GitArgs @('remote', 'add', 'origin', $Config.RepoUrl) | Out-Null
                Write-Log ('origin set to {0}' -f $Config.RepoUrl)
            }
        }
    } else {
        Write-Log 'Existing git repo detected'
        $remote = Invoke-Git -GitArgs @('remote', 'get-url', 'origin') -AllowFail
        if ($remote.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($remote.Output)) {
            Write-Log 'origin missing, adding...' -Level WARN
            if (-not $WhatIf) {
                Invoke-Git -GitArgs @('remote', 'add', 'origin', $Config.RepoUrl) | Out-Null
            }
        } else {
            $url = $remote.Output.Trim()
            Write-Log ('origin: {0}' -f $url)
            $a = $url.TrimEnd('.git')
            $b = $Config.RepoUrl.TrimEnd('.git')
            if ($a -ne $b) {
                Write-Log 'origin URL differs from config; updating' -Level WARN
                if (-not $WhatIf) {
                    Invoke-Git -GitArgs @('remote', 'set-url', 'origin', $Config.RepoUrl) | Out-Null
                }
            }
        }
    }

    if ($WhatIf) {
        Write-Log '[WhatIf] stop before fetch/merge/push'
        Write-Log '========== sync end (WhatIf) =========='
        exit 0
    }

    Write-Log 'fetch origin...'
    # HTTP/1.1 + larger buffer helps when HTTPS pack download stalls mid-way
    $httpHardening = @(
        '-c', 'http.version=HTTP/1.1'
        '-c', 'http.postBuffer=524288000'
        '-c', 'http.lowSpeedLimit=1000'
        '-c', 'http.lowSpeedTime=60'
    )
    $fetchOk = $false
    $fetch = $null
    $maxTry = [Math]::Max(1, [int]$Config.FetchRetries)
    $fetchTimeout = [Math]::Max(30, [int]$Config.FetchTimeoutSec)
    for ($i = 1; $i -le $maxTry; $i++) {
        Write-Log ('fetch attempt {0}/{1} (timeout={2}s)...' -f $i, $maxTry, $fetchTimeout)
        if ($i -le 2) {
            $fetchArgs = $httpHardening + @('fetch', 'origin', '--prune')
        } else {
            Write-Log 'Using shallow fetch fallback (depth=1; smaller download)...' -Level WARN
            $fetchArgs = $httpHardening + @('fetch', 'origin', '--prune', '--depth', '1')
        }
        $fetch = Invoke-Git -GitArgs $fetchArgs -AllowFail -HeartbeatSec 15 -TimeoutSec $fetchTimeout
        if ($fetch.ExitCode -eq 0) {
            $fetchOk = $true
            Write-Log ('fetch ok on attempt {0}' -f $i)
            break
        }
        Write-Log ('fetch attempt {0} failed (exit={1}): {2}' -f $i, $fetch.ExitCode, $fetch.Output) -Level WARN
        # Clear locks left by killed/stalled fetch
        Clear-StaleGitLocks -RepoRoot $Config.LocalFolder -MinAgeSec 0
        if ($i -lt $maxTry) {
            $wait = [int]$Config.FetchRetrySec * $i
            Write-Log ('Wait {0}s then retry (WireGuard/VPN recommended)...' -f $wait) -Level WARN
            Start-Sleep -Seconds $wait
        }
    }
    if (-not $fetchOk) {
        Write-Log ('fetch failed after {0} attempts.{1}{2}' -f $maxTry, [Environment]::NewLine, $fetch.Output) -Level ERROR
        Write-Log 'This usually means GitHub pack download stalled (not a script logic bug).' -Level ERROR
        Write-Log 'Hints: 1) Connect WireGuard/VPN  2) Open https://github.com  3) git -c http.version=HTTP/1.1 ls-remote origin  4) Retry later' -Level ERROR
        exit 2
    }

    $branch = $Config.Branch
    if ([string]::IsNullOrWhiteSpace($branch)) {
        $sym = Invoke-Git -GitArgs @('symbolic-ref', 'refs/remotes/origin/HEAD') -AllowFail
        if ($sym.ExitCode -eq 0 -and $sym.Output -match 'origin/(\S+)$') {
            $branch = $Matches[1]
        } else {
            foreach ($try in @('main', 'master')) {
                $chk = Invoke-Git -GitArgs @('rev-parse', '--verify', ('origin/{0}' -f $try)) -AllowFail
                if ($chk.ExitCode -eq 0) { $branch = $try; break }
            }
        }
        if ([string]::IsNullOrWhiteSpace($branch)) {
            throw 'Cannot detect remote default branch. Set Config.Branch.'
        }
        Write-Log ('Auto branch: {0}' -f $branch)
    } else {
        $chk = Invoke-Git -GitArgs @('rev-parse', '--verify', ('origin/{0}' -f $branch)) -AllowFail
        if ($chk.ExitCode -ne 0) {
            Write-Log ('Configured branch origin/{0} missing; try main/master...' -f $branch) -Level WARN
            $found = $null
            foreach ($try in @('main', 'master')) {
                $c2 = Invoke-Git -GitArgs @('rev-parse', '--verify', ('origin/{0}' -f $try)) -AllowFail
                if ($c2.ExitCode -eq 0) { $found = $try; break }
            }
            if (-not $found) {
                throw ("Remote branch '{0}' not found, and no main/master." -f $branch)
            }
            Write-Log ('Fallback branch: {0}' -f $found) -Level WARN
            $branch = $found
        }
    }
    $remoteRef = 'origin/{0}' -f $branch
    Write-Log ('Remote ref: {0}' -f $remoteRef)

    # After "git init" on a non-empty folder there is often no commit yet, or an
    # orphan commit unrelated to GitHub. Prefer lightweight attach (NO full checkout)
    # so we don't rewrite the whole working tree and appear hung.
    $headCheck = Invoke-Git -GitArgs @('rev-parse', '--verify', 'HEAD') -AllowFail
    $needReattach = $false
    if ($headCheck.ExitCode -ne 0) {
        $needReattach = $true
        Write-Log 'No local HEAD commit yet (fresh init). Will attach onto remote without full checkout...' -Level WARN
    } else {
        $mergeBase = Invoke-Git -GitArgs @('merge-base', 'HEAD', $remoteRef) -AllowFail
        if ($mergeBase.ExitCode -ne 0) {
            $needReattach = $true
            Write-Log 'Local history is unrelated to remote. Will reattach onto remote; local files kept.' -Level WARN
        }
    }

    if ($needReattach) {
        Write-Log ('Attaching branch "{0}" -> {1} (reset --mixed; worktree files kept)...' -f $branch, $remoteRef)
        # Point HEAD at branch name even if unborn, then move branch/index to remote tip
        Invoke-Git -GitArgs @('symbolic-ref', 'HEAD', ('refs/heads/{0}' -f $branch)) -AllowFail | Out-Null
        $reset = Invoke-Git -GitArgs @('reset', '--mixed', $remoteRef) -AllowFail -HeartbeatSec 10
        if ($reset.ExitCode -ne 0 -and $reset.Output -match 'index\.lock') {
            Write-Log 'reset hit index.lock; clearing stale locks and retrying...' -Level WARN
            Clear-StaleGitLocks -RepoRoot $Config.LocalFolder -MinAgeSec 0
            $reset = Invoke-Git -GitArgs @('reset', '--mixed', $remoteRef) -AllowFail -HeartbeatSec 10
        }
        if ($reset.ExitCode -ne 0) {
            throw ('git reset --mixed failed: {0}' -f $reset.Output)
        }
        Write-Log ('Attach complete: HEAD is {0} (index synced to remote; local edits kept)' -f $branch)
    } else {
        $cur = Invoke-Git -GitArgs @('rev-parse', '--abbrev-ref', 'HEAD') -AllowFail
        if ($cur.ExitCode -eq 0 -and $cur.Output.Trim() -ne $branch -and $cur.Output.Trim() -ne 'HEAD') {
            Write-Log ('Switch branch {0} -> {1} (no remote tree checkout)...' -f $cur.Output.Trim(), $branch) -Level WARN
            # -B without start-point only moves branch tip / switches; much faster than checkout origin/*
            $sw = Invoke-Git -GitArgs @('checkout', '-B', $branch) -AllowFail -HeartbeatSec 10
            if ($sw.ExitCode -ne 0) {
                Write-Log ('checkout -B failed: {0}; continuing on current branch' -f $sw.Output) -Level WARN
            }
        } else {
            Write-Log ('Already on usable branch (HEAD={0})' -f $(if ($cur.Output) { $cur.Output.Trim() } else { '?' }))
        }
    }

    function Get-RemoteCommitTime([string]$RelPath) {
        # IMPORTANT: only call this for paths that exist in the *current* remote tree.
        # `git log -- path` also matches deleted history and must not be used for existence.
        $r = Invoke-Git -GitArgs @('log', '-1', '--format=%ct', $remoteRef, '--', $RelPath) -AllowFail
        if ($r.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($r.Output)) { return $null }
        $line = ($r.Output -split "`n" | Select-Object -First 1).Trim()
        if ($line -match '^\d+$') { return [int64]$line }
        return $null
    }

    # Match `git hash-object` under core.autocrlf (text: CRLF->LF before hashing).
    $autoCrlfRes = Invoke-Git -GitArgs @('config', '--get', 'core.autocrlf') -AllowFail
    $script:HashNormalizeCrlf = $false
    if ($autoCrlfRes.ExitCode -eq 0) {
        $v = (($autoCrlfRes.Output -split "`n" | Select-Object -First 1).Trim().ToLowerInvariant())
        if ($v -eq 'true' -or $v -eq 'input') { $script:HashNormalizeCrlf = $true }
    }
    Write-Log ('Local blob hash: in-process SHA1 (normalizeCrlf={0})' -f $script:HashNormalizeCrlf)

    function ConvertTo-GitHashBytes([byte[]]$Bytes) {
        if (-not $script:HashNormalizeCrlf -or $null -eq $Bytes -or $Bytes.Length -eq 0) { return $Bytes }
        # Skip binary-ish buffers (NUL in first 8KiB) — same idea as git's text heuristic.
        $probe = [Math]::Min($Bytes.Length, 8192)
        for ($i = 0; $i -lt $probe; $i++) {
            if ($Bytes[$i] -eq 0) { return $Bytes }
        }
        $out = New-Object System.Collections.Generic.List[byte] ($Bytes.Length)
        for ($i = 0; $i -lt $Bytes.Length; $i++) {
            if ($Bytes[$i] -eq 13 -and ($i + 1) -lt $Bytes.Length -and $Bytes[$i + 1] -eq 10) {
                [void]$out.Add(10)
                $i++
            } else {
                [void]$out.Add($Bytes[$i])
            }
        }
        return $out.ToArray()
    }

    function Get-LocalFileHash([string]$AbsPath) {
        # Git blob SHA-1 in-process (same as `git hash-object` with autocrlf).
        if (-not (Test-Path -LiteralPath $AbsPath -PathType Leaf)) { return $null }
        $sha = $null
        try {
            $raw = [System.IO.File]::ReadAllBytes($AbsPath)
            $bytes = ConvertTo-GitHashBytes -Bytes $raw
            $sha = [System.Security.Cryptography.SHA1]::Create()
            $header = [System.Text.Encoding]::ASCII.GetBytes(('blob {0}' -f $bytes.Length))
            $payload = New-Object byte[] ($header.Length + 1 + $bytes.Length)
            [Array]::Copy($header, 0, $payload, 0, $header.Length)
            $payload[$header.Length] = 0
            if ($bytes.Length -gt 0) {
                [Array]::Copy($bytes, 0, $payload, $header.Length + 1, $bytes.Length)
            }
            $hash = $sha.ComputeHash($payload)
            return ([BitConverter]::ToString($hash) -replace '-', '').ToLowerInvariant()
        } catch {
            return $null
        } finally {
            if ($sha) { $sha.Dispose() }
        }
    }

    function Read-LsTreeHashMap([string]$TreeIsh) {
        # path -> blob sha1 from `git ls-tree -r <tree>`
        $map = @{}
        $r = Invoke-Git -GitArgs @('ls-tree', '-r', $TreeIsh) -AllowFail
        if ($r.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($r.Output)) { return $map }
        foreach ($line in ($r.Output -split "`r?`n")) {
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            # e.g. "100644 blob abcdef...\tpath/with spaces"
            if ($line -match '^\S+\s+blob\s+([0-9a-f]{40})\t(.+)$') {
                $p = ConvertFrom-GitQuotedPath $Matches[2]
                if ($p) { $map[$p] = $Matches[1].ToLowerInvariant() }
            }
        }
        return $map
    }

    function Set-LocalMtimeFromRemote([string]$AbsPath, [string]$RelPath) {
        if (-not $Config.AlignMtimeWhenEqual) { return }
        if (-not (Test-Path -LiteralPath $AbsPath -PathType Leaf)) { return }
        $ct = Get-RemoteCommitTime $RelPath
        if ($null -eq $ct) { return }
        try {
            $dto = [DateTimeOffset]::FromUnixTimeSeconds($ct).LocalDateTime
            (Get-Item -LiteralPath $AbsPath).LastWriteTime = $dto
        } catch {}
    }

    # merge-base for three-way decisions
    $mbRes = Invoke-Git -GitArgs @('merge-base', 'HEAD', $remoteRef) -AllowFail
    $mergeBase = $null
    if ($mbRes.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($mbRes.Output)) {
        $mergeBase = ($mbRes.Output -split "`n" | Select-Object -First 1).Trim()
        Write-Log ('Three-way merge-base: {0}' -f $mergeBase)
    } else {
        Write-Log ('No merge-base with {0}; will use hash+mtime fallback when content differs.' -f $remoteRef) -Level WARN
    }

    Write-Log 'Loading remote tree hashes...'
    $remoteHashMap = Read-LsTreeHashMap -TreeIsh $remoteRef
    $baseHashMap = @{}
    if ($mergeBase) {
        Write-Log 'Loading merge-base tree hashes...'
        $baseHashMap = Read-LsTreeHashMap -TreeIsh $mergeBase
    }

    $remoteFilesAll = @($remoteHashMap.Keys)
    Write-Log ('Remote file count (raw): {0}' -f $remoteFilesAll.Count)

    # Apply <Delete> list: remove matching paths from GitHub index (Ignore wins).
    # Missing remote paths are skipped. Use --cached so a still-present local copy is kept.
    $deleteRmCount = 0
    $deleteSkipMissing = 0
    if ($script:ListDeletePaths.Count -gt 0) {
        $toRemove = New-Object 'System.Collections.Generic.List[string]'
        foreach ($ent in @($script:ListDeletePaths)) {
            if (Test-ListIgnoredPath -RelativePath $ent) {
                Write-Log ('Delete skipped (also in Ignore): {0}' -f $ent) -Level DEBUG
                continue
            }
            $matched = @(
                $remoteFilesAll | Where-Object { Test-PathCoveredByEntry -RelativePath $_ -Entry $ent }
            )
            if ($matched.Count -eq 0) {
                $deleteSkipMissing++
                Write-Log ('Delete skip (not on GitHub): {0}' -f $ent) -Level DEBUG
                continue
            }
            foreach ($m in $matched) {
                if (Test-ListIgnoredPath -RelativePath $m) { continue }
                if (-not ($toRemove -contains $m)) { [void]$toRemove.Add($m) }
            }
        }
        if ($toRemove.Count -gt 0) {
            Write-Log ('Staging GitHub deletes from list: {0} file(s)...' -f $toRemove.Count)
            if ($WhatIf) {
                Write-Log ('[WhatIf] would git rm --cached: {0}' -f (($toRemove | Select-Object -First 20) -join '; '))
            } else {
                foreach ($relDel in $toRemove) {
                    $rm = Invoke-Git -GitArgs @('rm', '--cached', '-f', '--', $relDel) -AllowFail
                    if ($rm.ExitCode -eq 0) {
                        $deleteRmCount++
                        Write-Log ('git rm --cached: {0}' -f $relDel)
                        if ($remoteHashMap.ContainsKey($relDel)) { $remoteHashMap.Remove($relDel) }
                    } else {
                        Write-Log ('git rm failed: {0} :: {1}' -f $relDel, $rm.Output) -Level WARN
                    }
                }
                $remoteFilesAll = @($remoteHashMap.Keys)
            }
        } else {
            Write-Log 'No <Delete> targets present on GitHub (nothing to remove).'
        }
        Write-Log ('Delete list stats: removed={0}, missingEntries={1}' -f $deleteRmCount, $deleteSkipMissing)
    }

    $remoteFiles = @(
        $remoteFilesAll | Where-Object { $_ -and -not (Test-IgnoredPath $_) }
    )
    Write-Log ('Remote file count (sync): {0}' -f $remoteFiles.Count)

    $localFiles = New-Object 'System.Collections.Generic.List[string]'
    Get-ChildItem -LiteralPath $Config.LocalFolder -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            # Skip NTFS alternate data streams (Name may contain ':')
            if ($_.Name -match ':') { return }
            $full = $_.FullName
            if ($full.Length -le $Config.LocalFolder.Length) { return }
            $rel = $full.Substring($Config.LocalFolder.Length).TrimStart('\')
            $relGit = $rel -replace '\\', '/'
            if (-not (Test-SafeRelativePath -RelativePath $rel)) {
                Write-Log ('Skip unsafe local path: {0}' -f $relGit) -Level WARN
                return
            }
            if (-not (Test-IgnoredPath $relGit)) {
                [void]$localFiles.Add($relGit)
            }
        } catch {
            Write-Log ('Skip local item due to error: {0}' -f $_.Exception.Message) -Level WARN
        }
    }
    Write-Log ('Local file count (filtered): {0}' -f $localFiles.Count)

    $all = @($remoteFiles + $localFiles.ToArray() | Select-Object -Unique)
    # O(1) membership for "does this path exist on current origin/main tip?"
    $remoteTreeSet = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
    foreach ($rf in $remoteFiles) { [void]$remoteTreeSet.Add($rf) }

    $pullCount = 0
    $pushCandidates = New-Object 'System.Collections.Generic.List[string]'
    $skipCount = 0
    $equalCount = 0
    $conflictCount = 0
    $errorCount = 0
    $conflictPaths = New-Object 'System.Collections.Generic.List[string]'

    foreach ($relRaw in $all) {
        try {
            $rel = ConvertFrom-GitQuotedPath $relRaw
            if (Test-IgnoredPath $rel) { continue }
            if (-not (Test-SafeRelativePath -RelativePath ($rel -replace '/', '\'))) {
                Write-Log ('Skip unsafe path: {0}' -f $rel) -Level WARN
                $errorCount++
                continue
            }

            $localPath = Get-LocalPathFromRel -RelGit $rel
            $localExists = Test-Path -LiteralPath $localPath -PathType Leaf
            # Existence = in current remote tree (ls-tree), NOT "ever appeared in git log"
            $remoteExists = $remoteTreeSet.Contains($rel)

            if ($remoteExists -and -not $localExists) {
                Write-Log ('Remote only -> pull: {0}' -f $rel)
                Invoke-Git -GitArgs @('checkout', $remoteRef, '--', $rel) | Out-Null
                Set-LocalMtimeFromRemote -AbsPath $localPath -RelPath $rel
                $pullCount++
                continue
            }

            if ($localExists -and -not $remoteExists) {
                Write-Log ('Local only -> push candidate: {0}' -f $rel)
                [void]$pushCandidates.Add($rel)
                continue
            }

            if (-not ($localExists -and $remoteExists)) { continue }

            # --- both sides have the file: content hash first, then three-way ---
            $localHash = Get-LocalFileHash -AbsPath $localPath
            $remoteHash = $remoteHashMap[$rel]
            if ([string]::IsNullOrWhiteSpace($localHash) -or [string]::IsNullOrWhiteSpace($remoteHash)) {
                Write-Log ('Hash unavailable, skip: {0}' -f $rel) -Level WARN
                $errorCount++
                continue
            }

            if ($localHash -eq $remoteHash) {
                $equalCount++
                Set-LocalMtimeFromRemote -AbsPath $localPath -RelPath $rel
                Write-Log ('Content equal, skip: {0}' -f $rel) -Level DEBUG
                continue
            }

            # Content differs
            $baseHash = $null
            if ($mergeBase -and $baseHashMap.ContainsKey($rel)) {
                $baseHash = $baseHashMap[$rel]
            }

            $decision = $null  # 'push' | 'pull' | 'conflict' | 'mtime-local' | 'mtime-remote'

            if ($mergeBase) {
                $localChanged = $true
                $remoteChanged = $true
                if ($null -ne $baseHash) {
                    $localChanged = ($localHash -ne $baseHash)
                    $remoteChanged = ($remoteHash -ne $baseHash)
                } else {
                    # Not in merge-base: both sides "added" (or re-added) after base
                    $localChanged = $true
                    $remoteChanged = $true
                }

                if ($localChanged -and -not $remoteChanged) {
                    $decision = 'push'
                } elseif ($remoteChanged -and -not $localChanged) {
                    $decision = 'pull'
                } elseif ($localChanged -and $remoteChanged) {
                    $decision = 'conflict'
                } else {
                    # neither changed vs base but tips differ — should be rare; treat as conflict
                    $decision = 'conflict'
                }
            } else {
                # No merge-base: hash differs -> mtime or conflict per config
                if ($Config.DivergedFallback -eq 'Conflict') {
                    $decision = 'conflict'
                } else {
                    $localTime = Get-FileUnixTime $localPath
                    $remoteTime = Get-RemoteCommitTime $rel
                    $skew = [int64]$Config.NewerSkewSec
                    if ($null -ne $localTime -and $null -ne $remoteTime) {
                        if ($localTime -gt ($remoteTime + $skew)) { $decision = 'mtime-local' }
                        elseif ($remoteTime -gt ($localTime + $skew)) { $decision = 'mtime-remote' }
                        else { $decision = 'conflict' }
                    } else {
                        $decision = 'conflict'
                    }
                }
            }

            switch ($decision) {
                'push' {
                    Write-Log ('Only local changed -> push: {0}' -f $rel)
                    [void]$pushCandidates.Add($rel)
                }
                'pull' {
                    Write-Log ('Only remote changed -> pull: {0}' -f $rel)
                    Invoke-Git -GitArgs @('checkout', $remoteRef, '--', $rel) | Out-Null
                    Set-LocalMtimeFromRemote -AbsPath $localPath -RelPath $rel
                    $pullCount++
                }
                'mtime-local' {
                    Write-Log ('Hash differs (no merge-base), local mtime newer -> push: {0}' -f $rel) -Level WARN
                    [void]$pushCandidates.Add($rel)
                }
                'mtime-remote' {
                    Write-Log ('Hash differs (no merge-base), remote newer -> pull: {0}' -f $rel) -Level WARN
                    Invoke-Git -GitArgs @('checkout', $remoteRef, '--', $rel) | Out-Null
                    Set-LocalMtimeFromRemote -AbsPath $localPath -RelPath $rel
                    $pullCount++
                }
                default {
                    $conflictCount++
                    [void]$conflictPaths.Add($rel)
                    Write-Log ('CONFLICT (both changed) -> skip: {0}' -f $rel) -Level WARN
                    $skipCount++
                }
            }
        } catch {
            $errorCount++
            Write-Log ('Skip file due to error [{0}]: {1}' -f $rel, $_.Exception.Message) -Level WARN
            continue
        }
    }

    if ($Config.SyncDeletions) {
        Write-Log 'SyncDeletions=true: full bidirectional delete is limited in this version; overwrite sync only.' -Level WARN
    }

    if ($conflictPaths.Count -gt 0) {
        $conflictFile = Join-Path $script:LogDir ('conflicts-{0}.txt' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
        try {
            $conflictPaths | Set-Content -LiteralPath $conflictFile -Encoding UTF8
            Write-Log ('Conflict list written: {0}' -f $conflictFile) -Level WARN
        } catch {
            Write-Log ('Could not write conflict list: {0}' -f $_.Exception.Message) -Level WARN
        }
    }

    Write-Log ('Stats: pull={0}, pushCandidates={1}, contentEqual={2}, conflicts={3}, skipped={4}, pathErrors={5}, listDeletes={6}' -f `
        $pullCount, $pushCandidates.Count, $equalCount, $conflictCount, $skipCount, $errorCount, $deleteRmCount)

    $pushOk = $true
    if ($pushCandidates.Count -gt 0) {
        Write-Log ('Staging {0} local-changed/local-only files...' -f $pushCandidates.Count)
        $added = 0
        $addFail = 0
        foreach ($rel in $pushCandidates) {
            $add = Invoke-Git -GitArgs @('add', '-f', '--', $rel) -AllowFail
            if ($add.ExitCode -eq 0) { $added++ } else {
                $addFail++
                Write-Log ('git add failed: {0} :: {1}' -f $rel, $add.Output) -Level WARN
            }
        }
        Write-Log ('git add done: ok={0}, fail={1}' -f $added, $addFail)
    } else {
        Write-Log 'No local-newer/local-only files to stage'
    }

    # Commit only when the index actually differs from HEAD (ignore untracked noise like logs/)
    $cachedQuiet = Invoke-Git -GitArgs @('diff', '--cached', '--quiet') -AllowFail
    $hasStaged = ($cachedQuiet.ExitCode -ne 0)
    if ($hasStaged) {
        $stagedList = Invoke-Git -GitArgs @('diff', '--cached', '--name-only') -AllowFail
        $stagedNames = @()
        if (-not [string]::IsNullOrWhiteSpace($stagedList.Output)) {
            $stagedNames = @($stagedList.Output -split "`r?`n" | Where-Object { $_ })
        }
        Write-Log ('Staged files for commit: {0}' -f $stagedNames.Count)
        if ($stagedNames.Count -gt 0) {
            Write-Log (($stagedNames | Select-Object -First 15) -join [Environment]::NewLine) -Level DEBUG
        }

        $msg = '{0} {1:yyyy-MM-dd HH:mm:ss} ({2} files)' -f $Config.CommitPrefix, (Get-Date), $stagedNames.Count
        $commit = Invoke-Git -GitArgs @('commit', '-m', $msg) -AllowFail -WithCommitIdentity
        if ($commit.ExitCode -ne 0) {
            Write-Log ('commit failed (exit={0}): {1}' -f $commit.ExitCode, $commit.Output) -Level ERROR
            Write-Log 'If identity error: set Config.GitUserName / GitUserEmail in this script.' -Level ERROR
            $pushOk = $false
        } else {
            Write-Log ('committed: {0}' -f $msg)
        }
    } else {
        Write-Log 'Nothing new to commit (working tree matches HEAD, or only timestamp differed).'
    }

    # Push whenever local is ahead of remote (including commits from a previous run)
    if ($pushOk) {
        $mbPush = Invoke-Git -GitArgs @('merge-base', 'HEAD', $remoteRef) -AllowFail
        if ($mbPush.ExitCode -ne 0) {
            Write-Log 'Skip push: local history still unrelated to remote.' -Level ERROR
            $pushOk = $false
        } else {
            $ahead = Invoke-Git -GitArgs @('rev-list', '--count', ('{0}..HEAD' -f $remoteRef)) -AllowFail
            $behind = Invoke-Git -GitArgs @('rev-list', '--count', ('HEAD..{0}' -f $remoteRef)) -AllowFail
            $aheadN = 0
            $behindN = 0
            if ($ahead.ExitCode -eq 0 -and $ahead.Output -match '^\d+') { $aheadN = [int]$ahead.Output.Trim() }
            if ($behind.ExitCode -eq 0 -and $behind.Output -match '^\d+') { $behindN = [int]$behind.Output.Trim() }

            if ($behindN -gt 0) {
                Write-Log ('Remote ahead by {0} commit(s); merging {1} before push...' -f $behindN, $remoteRef) -Level WARN
                $merge = Invoke-Git -GitArgs @('merge', '--no-edit', $remoteRef) -AllowFail -WithCommitIdentity
                if ($merge.ExitCode -ne 0) {
                    Write-Log ('merge failed: {0}' -f $merge.Output) -Level ERROR
                    Write-Log 'Resolve conflicts manually, then re-run the script.' -Level ERROR
                    $pushOk = $false
                } else {
                    Write-Log 'merge ok'
                    $aheadN = 1
                }
            }

            if ($pushOk -and $aheadN -gt 0) {
                Write-Log ('push origin/{0} (ahead={1}) ...' -f $branch, $aheadN)
                $push = Invoke-Git -GitArgs @('push', '-u', 'origin', $branch) -AllowFail
                if ($push.ExitCode -ne 0) {
                    Write-Log ('push failed. Login Git Credential Manager / SSH first.{0}{1}' -f [Environment]::NewLine, $push.Output) -Level ERROR
                    exit 3
                }
                Write-Log 'push ok'
            } elseif ($pushOk) {
                Write-Log 'Remote already up to date (nothing to push)'
            }
        }
    }

    if ($pushOk) {
        Write-Log '========== sync success =========='
        exit 0
    } else {
        Write-Log '========== sync finished with push/commit issues ==========' -Level WARN
        exit 4
    }
}
catch {
    Write-Log ('Unhandled error: {0}' -f $_.Exception.Message) -Level ERROR
    if ($_.ScriptStackTrace) { Write-Log $_.ScriptStackTrace -Level ERROR }
    Write-Log '========== sync failed ==========' -Level ERROR
    exit 1
}
