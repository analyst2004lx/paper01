#Requires -Version 5.1
<#
.SYNOPSIS
  Daytime sync between a GitHub repo and a local folder (newer wins).

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
#   LocalFolder = 'C:\Users\analy\Desktop\AI_Folder\paper01'
$Config = @{
    LocalFolder   = 'C:\Users\Administrator\Desktop\AI_Folder'
    RepoUrl       = 'https://github.com/analyst2004lx/paper01'
    # Use 'master' if your default branch is master; empty = auto-detect
    Branch        = 'main'
    WindowStart   = '10:00'
    WindowEnd     = '17:00'
    LogDir        = 'C:\Users\Administrator\Desktop\AI_Folder\script\logs'
    CommitPrefix  = 'auto-sync'
    NewerSkewSec  = 5
    SyncDeletions = $false
    # Used only for commits made by this script (does not change your global git config)
    GitUserName   = 'analyst2004lx'
    GitUserEmail  = 'analyst2004lx@users.noreply.github.com'
    IgnoreNames   = @(
        '.git'
        'script\logs'
        '.cursor'
        'node_modules'
        '.venv'
        '__pycache__'
        'Thumbs.db'
        '.DS_Store'
    )
    GitPath       = ''
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
        [switch]$WithCommitIdentity
    )
    $git = $script:GitExe

    # Always disable quotepath so Chinese paths are not shown as \345\273\272...
    $prefix = @('-c', 'core.quotepath=false')
    if ($WithCommitIdentity) {
        if ($Config.GitUserName)  { $prefix += @('-c', ('user.name={0}' -f $Config.GitUserName)) }
        if ($Config.GitUserEmail) { $prefix += @('-c', ('user.email={0}' -f $Config.GitUserEmail)) }
    }
    $allArgs = $prefix + $GitArgs
    Write-Log ('git {0}  (cwd={1})' -f ($GitArgs -join ' '), $WorkDir) -Level DEBUG

    # Native git stderr becomes ErrorRecord in PowerShell; keep it from terminating
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        $output = & $git -C $WorkDir @allArgs 2>&1
        $code = $LASTEXITCODE
    } catch {
        $code = 1
        $output = $_.Exception.Message
    } finally {
        $ErrorActionPreference = $prevEap
    }

    # Flatten ErrorRecord / strings
    $parts = @()
    foreach ($o in @($output)) {
        if ($null -eq $o) { continue }
        if ($o -is [System.Management.Automation.ErrorRecord]) {
            $parts += $o.ToString()
        } else {
            $parts += [string]$o
        }
    }
    $text = ($parts -join [Environment]::NewLine).Trim()

    if ($code -ne 0) {
        if ($AllowFail) {
            return [pscustomobject]@{ ExitCode = $code; Output = $text }
        }
        throw ('git failed (exit={0}): git {1}{2}{3}' -f $code, ($GitArgs -join ' '), [Environment]::NewLine, $text)
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

function Test-IgnoredPath {
    param([string]$RelativePath)
    $norm = $RelativePath -replace '/', '\'
    # NTFS alternate data streams e.g. file.pdf:Zone.Identifier
    if ($norm -match ':') { return $true }
    if ($norm -match 'Zone\.Identifier$') { return $true }
    foreach ($ig in $Config.IgnoreNames) {
        $igNorm = $ig -replace '/', '\'
        if ($norm -eq $igNorm) { return $true }
        if ($norm.StartsWith(($igNorm + '\'), [StringComparison]::OrdinalIgnoreCase)) { return $true }
        $parts = $norm.Split('\')
        if ($parts -contains $igNorm) { return $true }
    }
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

try {
    Write-Log '========== sync start =========='
    Write-Log ('LocalFolder: {0}' -f $Config.LocalFolder)
    Write-Log ('RepoUrl: {0}' -f $Config.RepoUrl)
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

    if (-not (Test-Path -LiteralPath $Config.LocalFolder)) {
        Write-Log ('Local folder missing, create: {0}' -f $Config.LocalFolder) -Level WARN
        if (-not $WhatIf) {
            New-Item -ItemType Directory -Path $Config.LocalFolder -Force | Out-Null
        }
    }

    $gitDir = Join-Path $Config.LocalFolder '.git'
    $isRepo = Test-Path -LiteralPath $gitDir

    if (-not $isRepo) {
        Write-Log 'Not a git repo yet; clone or init...'
        $items = @(Get-ChildItem -LiteralPath $Config.LocalFolder -Force -ErrorAction SilentlyContinue)
        if ($items.Count -eq 0) {
            if ($WhatIf) {
                Write-Log ('[WhatIf] would clone {0}' -f $Config.RepoUrl)
            } else {
                Invoke-Git -GitArgs @('clone', $Config.RepoUrl, '.') -WorkDir $Config.LocalFolder | Out-Null
                Write-Log 'clone done'
            }
        } else {
            Write-Log 'Folder not empty and has no .git: git init + remote add (files kept)' -Level WARN
            if (-not $WhatIf) {
                Invoke-Git -GitArgs @('init') | Out-Null
                Invoke-Git -GitArgs @('remote', 'remove', 'origin') -AllowFail | Out-Null
                Invoke-Git -GitArgs @('remote', 'add', 'origin', $Config.RepoUrl) | Out-Null
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
    $fetch = Invoke-Git -GitArgs @('fetch', 'origin', '--prune') -AllowFail
    if ($fetch.ExitCode -ne 0) {
        Write-Log ('fetch failed. Check network/credentials.{0}{1}' -f [Environment]::NewLine, $fetch.Output) -Level ERROR
        Write-Log 'Hints: 1) Open WireGuard/VPN then retry  2) Browser open github.com  3) Test: git ls-remote origin  4) Configure git http.proxy if needed' -Level ERROR
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

    $cur = Invoke-Git -GitArgs @('rev-parse', '--abbrev-ref', 'HEAD') -AllowFail
    if ($cur.ExitCode -ne 0 -or $cur.Output -eq 'HEAD' -or [string]::IsNullOrWhiteSpace($cur.Output)) {
        Write-Log ('Checkout local branch {0}' -f $branch)
        $co = Invoke-Git -GitArgs @('checkout', '-B', $branch, $remoteRef) -AllowFail
        if ($co.ExitCode -ne 0) {
            Invoke-Git -GitArgs @('checkout', '-B', $branch) -AllowFail | Out-Null
        }
    } elseif ($cur.Output.Trim() -ne $branch) {
        Write-Log ('Switch {0} -> {1}' -f $cur.Output.Trim(), $branch) -Level WARN
        Invoke-Git -GitArgs @('checkout', '-B', $branch) | Out-Null
    }

    # If repo was created via "git init" on a non-empty folder, local history may be
    # unrelated to GitHub. Soft-reset onto remote keeps all local file contents.
    $headCheck = Invoke-Git -GitArgs @('rev-parse', '--verify', 'HEAD') -AllowFail
    if ($headCheck.ExitCode -eq 0) {
        $mergeBase = Invoke-Git -GitArgs @('merge-base', 'HEAD', $remoteRef) -AllowFail
        if ($mergeBase.ExitCode -ne 0) {
            Write-Log 'Local history is unrelated to remote (common after git init on existing files). Reattaching onto remote; local files kept.' -Level WARN
            Invoke-Git -GitArgs @('reset', '--soft', $remoteRef) | Out-Null
            Write-Log ('Soft-reset onto {0} complete' -f $remoteRef)
        }
    }

    function Get-RemoteCommitTime([string]$RelPath) {
        $r = Invoke-Git -GitArgs @('log', '-1', '--format=%ct', $remoteRef, '--', $RelPath) -AllowFail
        if ($r.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($r.Output)) { return $null }
        $line = ($r.Output -split "`n" | Select-Object -First 1).Trim()
        if ($line -match '^\d+$') { return [int64]$line }
        return $null
    }

    $ls = Invoke-Git -GitArgs @('ls-tree', '-r', '--name-only', $remoteRef)
    $remoteFiles = @()
    if (-not [string]::IsNullOrWhiteSpace($ls.Output)) {
        $remoteFiles = @(
            $ls.Output -split "`r?`n" |
            ForEach-Object { ConvertFrom-GitQuotedPath $_ } |
            Where-Object { $_ -and -not (Test-IgnoredPath $_) }
        )
    }
    Write-Log ('Remote file count: {0}' -f $remoteFiles.Count)

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
    $pullCount = 0
    $pushCandidates = New-Object 'System.Collections.Generic.List[string]'
    $skipCount = 0
    $errorCount = 0

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
            $remoteTime = Get-RemoteCommitTime $rel
            $remoteExists = $null -ne $remoteTime
            $localTime = if ($localExists) { Get-FileUnixTime $localPath } else { $null }

            if ($remoteExists -and -not $localExists) {
                Write-Log ('Remote only -> pull: {0}' -f $rel)
                Invoke-Git -GitArgs @('checkout', $remoteRef, '--', $rel) | Out-Null
                try {
                    if (Test-Path -LiteralPath $localPath -PathType Leaf) {
                        $dto = [DateTimeOffset]::FromUnixTimeSeconds($remoteTime).LocalDateTime
                        (Get-Item -LiteralPath $localPath).LastWriteTime = $dto
                    }
                } catch {}
                $pullCount++
                continue
            }

            if ($localExists -and -not $remoteExists) {
                Write-Log ('Local only -> push candidate: {0}' -f $rel)
                [void]$pushCandidates.Add($rel)
                continue
            }

            if ($localExists -and $remoteExists) {
                $skew = [int64]$Config.NewerSkewSec
                if ($localTime -gt ($remoteTime + $skew)) {
                    Write-Log ('Local newer -> push: {0} (local={1}, remote={2})' -f $rel, $localTime, $remoteTime)
                    [void]$pushCandidates.Add($rel)
                } elseif ($remoteTime -gt ($localTime + $skew)) {
                    Write-Log ('Remote newer -> overwrite local: {0} (local={1}, remote={2})' -f $rel, $localTime, $remoteTime)
                    Invoke-Git -GitArgs @('checkout', $remoteRef, '--', $rel) | Out-Null
                    try {
                        $dto = [DateTimeOffset]::FromUnixTimeSeconds($remoteTime).LocalDateTime
                        (Get-Item -LiteralPath $localPath).LastWriteTime = $dto
                    } catch {}
                    $pullCount++
                } else {
                    $skipCount++
                    Write-Log ('Close timestamps, skip: {0}' -f $rel) -Level DEBUG
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

    Write-Log ('Stats: pull/overwrite={0}, pushCandidates={1}, skipped~={2}, pathErrors={3}' -f `
        $pullCount, $pushCandidates.Count, $skipCount, $errorCount)

    $pushOk = $true
    if ($pushCandidates.Count -gt 0) {
        Write-Log ('Staging {0} local-newer/local-only files...' -f $pushCandidates.Count)
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
