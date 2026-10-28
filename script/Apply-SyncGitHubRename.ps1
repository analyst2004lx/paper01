#Requires -Version 5.1
<#
.SYNOPSIS
  Apply <Rename> pairs from Sync-GitHub-Ignore_and_Delete.txt.

.DESCRIPTION
  Called by Sync-GitHubLocal.ps1 after the remote tree is loaded and before
  the per-file pull/push loop. Do not run this file by itself: a standalone
  rename would still be undone when the sync compares against origin.

  File: compare blob hashes. Equal = rename only. Different = rename and
  keep the bytes that already live at the new path.
  Folder: no single hash. Pair each file by its path relative to the folder.
#>

function Invoke-SyncGitHubRename {
    param(
        [Parameter(Mandatory = $true)][string]$LocalFolder,
        [Parameter(Mandatory = $true)][string]$ListFile,
        [Parameter(Mandatory = $true)][string]$RemoteRef,
        [Parameter(Mandatory = $true)][hashtable]$RemoteHashMap,
        [string]$GitExe = '',
        # Empty: ask. Used so the conflict path can be checked without a person at the keyboard.
        [string]$ConflictAnswer = ''
    )

    function Write-RnLog {
        param([string]$Message, [string]$Level = 'INFO')
        if (Get-Command -Name Write-Log -ErrorAction SilentlyContinue) {
            Write-Log -Message $Message -Level $Level
        } else {
            Write-Host ('[{0}] {1}' -f $Level, $Message)
        }
    }

    function Invoke-RnGit {
        param([Parameter(Mandatory = $true)][string[]]$GitArgs, [switch]$AllowFail)
        $git = $script:RnGit
        $prefix = @('-c', 'core.quotepath=false', '-c', 'i18n.logoutputencoding=utf-8')
        $all = @($prefix + $GitArgs)
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $git
        $psi.Arguments = (($all | ForEach-Object {
            $a = [string]$_
            if ($a -match '[\s"]') { '"' + ($a -replace '"', '\"') + '"' } else { $a }
        }) -join ' ')
        $psi.WorkingDirectory = $script:RnRoot
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $psi.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
        $psi.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi
        [void]$proc.Start()
        $outTask = $proc.StandardOutput.ReadToEndAsync()
        $errTask = $proc.StandardError.ReadToEndAsync()
        [void]$proc.WaitForExit()
        $stdout = ''
        $stderr = ''
        try { $stdout = $outTask.Result } catch { $stdout = '' }
        try { $stderr = $errTask.Result } catch { $stderr = '' }
        $text = (($stdout, $stderr) | Where-Object { $_ }) -join [Environment]::NewLine
        return [pscustomobject]@{ ExitCode = $proc.ExitCode; Output = $text }
    }

    function ConvertTo-RnGit {
        param([string]$PathText)
        if ([string]::IsNullOrWhiteSpace($PathText)) { return $null }
        $s = $PathText.Trim().Trim('"').Trim("'")
        $s = ($s -replace '\\', '/').Trim('/')
        if ([string]::IsNullOrWhiteSpace($s)) { return $null }
        if ($s -match '(^|/)\.\.(/|$)') { return $null }
        if ($s -match '[:\uFF1A"<>|*?\x00-\x1F]') { return $null }
        return $s
    }

    function Get-RnAbs {
        param([string]$GitRel)
        $rel = ($GitRel -replace '/', '\').TrimStart('\')
        $root = [System.IO.Path]::GetFullPath($script:RnRoot).TrimEnd('\')
        $full = [System.IO.Path]::GetFullPath((Join-Path $root $rel))
        if (-not ($full.Equals($root, [StringComparison]::OrdinalIgnoreCase) -or
            $full.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase))) {
            throw ("Rename path escapes the repo: {0}" -f $GitRel)
        }
        return $full
    }

    function Find-RnKey {
        param([string]$GitRel)
        if ($script:RnMap.ContainsKey($GitRel)) { return $GitRel }
        foreach ($k in @($script:RnMap.Keys)) {
            if ([string]::Equals([string]$k, $GitRel, [StringComparison]::OrdinalIgnoreCase)) { return [string]$k }
        }
        return $null
    }

    function Get-RnChildKeys {
        param([string]$GitRel)
        $prefix = $GitRel.TrimEnd('/') + '/'
        $out = New-Object 'System.Collections.Generic.List[string]'
        foreach ($k in @($script:RnMap.Keys)) {
            if (([string]$k).StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                [void]$out.Add([string]$k)
            }
        }
        return @($out)
    }

    function Get-RnBlobHash {
        param([string]$AbsPath)
        if (-not (Test-Path -LiteralPath $AbsPath -PathType Leaf)) { return $null }
        $sha = $null
        try {
            $raw = [System.IO.File]::ReadAllBytes($AbsPath)
            $bytes = $raw
            if ($script:RnCrlf -and $raw.Length -gt 0) {
                $probe = [Math]::Min($raw.Length, 8192)
                $binary = $false
                for ($i = 0; $i -lt $probe; $i++) {
                    if ($raw[$i] -eq 0) { $binary = $true; break }
                }
                if (-not $binary) {
                    $list = New-Object 'System.Collections.Generic.List[byte]' ($raw.Length)
                    for ($i = 0; $i -lt $raw.Length; $i++) {
                        if ($raw[$i] -eq 13 -and ($i + 1) -lt $raw.Length -and $raw[$i + 1] -eq 10) {
                            [void]$list.Add([byte]10)
                            $i++
                        } else {
                            [void]$list.Add($raw[$i])
                        }
                    }
                    $bytes = $list.ToArray()
                }
            }
            if ($null -eq $bytes) { $bytes = [byte[]]@() }
            $sha = [System.Security.Cryptography.SHA1]::Create()
            $header = [System.Text.Encoding]::ASCII.GetBytes(('blob {0}' -f $bytes.Length))
            $payload = New-Object byte[] ($header.Length + 1 + $bytes.Length)
            [Array]::Copy($header, 0, $payload, 0, $header.Length)
            $payload[$header.Length] = 0
            if ($bytes.Length -gt 0) { [Array]::Copy($bytes, 0, $payload, $header.Length + 1, $bytes.Length) }
            $hash = $sha.ComputeHash($payload)
            return ([BitConverter]::ToString($hash) -replace '-', '').ToLowerInvariant()
        } catch {
            return $null
        } finally {
            if ($sha) { $sha.Dispose() }
        }
    }

    function Get-RnKind {
        param([string]$GitRel)
        $abs = Get-RnAbs $GitRel
        $isFile = Test-Path -LiteralPath $abs -PathType Leaf
        $isDir = Test-Path -LiteralPath $abs -PathType Container
        $exact = Find-RnKey $GitRel
        $kids = @(Get-RnChildKeys $GitRel)
        if ($isDir -or $kids.Count -gt 0) {
            if ($isFile) { return 'mixed' }
            return 'dir'
        }
        if ($isFile -or $exact) { return 'file' }
        return 'missing'
    }

    function Get-LocalSubPaths {
        param([string]$GitRel)
        $abs = Get-RnAbs $GitRel
        if (-not (Test-Path -LiteralPath $abs -PathType Container)) { return @() }
        $rootLen = $abs.TrimEnd('\').Length
        $list = New-Object 'System.Collections.Generic.List[string]'
        Get-ChildItem -LiteralPath $abs -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.Name -match ':') { return }
            $rel = $_.FullName.Substring($rootLen).TrimStart('\') -replace '\\', '/'
            if (-not [string]::IsNullOrWhiteSpace($rel)) { [void]$list.Add($rel) }
        }
        return @($list)
    }

    function Ensure-ParentDir {
        param([string]$AbsPath)
        $parent = Split-Path -Parent $AbsPath
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
    }

    function Remove-EmptyRnDir {
        param([string]$AbsPath)
        if (-not (Test-Path -LiteralPath $AbsPath -PathType Container)) { return }
        $dirs = @(Get-ChildItem -LiteralPath $AbsPath -Recurse -Directory -Force -ErrorAction SilentlyContinue |
            Sort-Object { $_.FullName.Length } -Descending)
        foreach ($d in $dirs) {
            $left = @(Get-ChildItem -LiteralPath $d.FullName -Force -ErrorAction SilentlyContinue)
            if ($left.Count -eq 0) { Remove-Item -LiteralPath $d.FullName -Force -ErrorAction SilentlyContinue }
        }
        $top = @(Get-ChildItem -LiteralPath $AbsPath -Force -ErrorAction SilentlyContinue)
        if ($top.Count -eq 0) { Remove-Item -LiteralPath $AbsPath -Force -ErrorAction SilentlyContinue }
    }

    function Move-RnMapKey {
        param([string]$OldKey, [string]$NewGit, [string]$Hash)
        if ($OldKey) { [void]$script:RnMap.Remove($OldKey) }
        $existing = Find-RnKey $NewGit
        if ($existing -and -not [string]::Equals($existing, $NewGit, [StringComparison]::Ordinal)) {
            [void]$script:RnMap.Remove($existing)
        }
        if ($Hash) { $script:RnMap[$NewGit] = $Hash }
    }

    # Place the winning bytes at the new path and stage a rename (old path leaves the index).
    # Returns renamed | renamed-overwrite | already | missing | failed
    function Move-OneFile {
        param([string]$OldGit, [string]$NewGit)
        $oldAbs = Get-RnAbs $OldGit
        $newAbs = Get-RnAbs $NewGit
        $oldKey = Find-RnKey $OldGit
        $newKey = Find-RnKey $NewGit
        $oldLocal = Test-Path -LiteralPath $oldAbs -PathType Leaf
        $newLocal = Test-Path -LiteralPath $newAbs -PathType Leaf

        $hashOld = $null
        $hashNew = $null
        if ($oldLocal) { $hashOld = Get-RnBlobHash $oldAbs }
        elseif ($oldKey) { $hashOld = [string]$script:RnMap[$oldKey] }
        if ($newLocal) { $hashNew = Get-RnBlobHash $newAbs }
        elseif ($newKey) { $hashNew = [string]$script:RnMap[$newKey] }

        if (-not $hashOld -and -not $hashNew) { return 'missing' }
        # New name is already the only copy. Leave content to the normal sync.
        if ($hashNew -and -not $hashOld -and -not $oldKey) { return 'already' }

        $same = $true
        if ($hashOld -and $hashNew -and ($hashOld -ne $hashNew)) { $same = $false }

        if ($newLocal) {
            if ($oldLocal) { Remove-Item -LiteralPath $oldAbs -Force }
        }
        elseif ($newKey -and -not $same) {
            Ensure-ParentDir $newAbs
            $checkoutPath = $newKey
            $c = Invoke-RnGit -GitArgs @('checkout', $script:RnRef, '--', $checkoutPath)
            if ($c.ExitCode -ne 0) {
                Write-RnLog ("Rename checkout failed: {0} :: {1}" -f $checkoutPath, $c.Output) 'WARN'
                return 'failed'
            }
            if ($oldLocal) { Remove-Item -LiteralPath $oldAbs -Force }
        }
        elseif ($oldLocal) {
            Ensure-ParentDir $newAbs
            Move-Item -LiteralPath $oldAbs -Destination $newAbs
        }
        elseif ($oldKey) {
            $c = Invoke-RnGit -GitArgs @('checkout', $script:RnRef, '--', $oldKey)
            if ($c.ExitCode -ne 0) {
                Write-RnLog ("Rename checkout failed: {0} :: {1}" -f $oldKey, $c.Output) 'WARN'
                return 'failed'
            }
            Ensure-ParentDir $newAbs
            if (Test-Path -LiteralPath $oldAbs -PathType Leaf) {
                Move-Item -LiteralPath $oldAbs -Destination $newAbs
            }
        }
        else {
            return 'missing'
        }

        if (Test-Path -LiteralPath $newAbs -PathType Leaf) {
            $add = Invoke-RnGit -GitArgs @('add', '-f', '--', $NewGit)
            if ($add.ExitCode -ne 0) {
                Write-RnLog ("Rename git add failed: {0} :: {1}" -f $NewGit, $add.Output) 'WARN'
                return 'failed'
            }
        }
        $rmTarget = if ($oldKey) { $oldKey } else { $OldGit }
        [void](Invoke-RnGit -GitArgs @('rm', '--cached', '-f', '--', $rmTarget) -AllowFail)

        $winHash = $null
        if (Test-Path -LiteralPath $newAbs -PathType Leaf) { $winHash = Get-RnBlobHash $newAbs }
        if (-not $winHash) { $winHash = $hashNew }
        if (-not $winHash) { $winHash = $hashOld }
        Move-RnMapKey -OldKey $oldKey -NewGit $NewGit -Hash $winHash
        if ($same) { return 'renamed' }
        return 'renamed-overwrite'
    }

    function Invoke-WholeTreeRename {
        param([string]$OldGit, [string]$NewGit)
        $oldAbs = Get-RnAbs $OldGit
        $newAbs = Get-RnAbs $NewGit
        if (Test-Path -LiteralPath $newAbs) { return $false }
        $kids = @(Get-RnChildKeys $OldGit)
        $did = $false
        if ((Test-Path -LiteralPath $oldAbs -PathType Container) -and $kids.Count -gt 0) {
            $r = Invoke-RnGit -GitArgs @('mv', '--', $OldGit, $NewGit)
            if ($r.ExitCode -eq 0) {
                $did = $true
            } else {
                Write-RnLog ("git mv failed, will rename file by file: {0} -> {1} :: {2}" -f $OldGit, $NewGit, $r.Output) 'WARN'
                return $false
            }
        }
        elseif (Test-Path -LiteralPath $oldAbs -PathType Container) {
            Ensure-ParentDir $newAbs
            Move-Item -LiteralPath $oldAbs -Destination $newAbs
            $did = $true
        }
        elseif ($kids.Count -gt 0) {
            $c = Invoke-RnGit -GitArgs @('checkout', $script:RnRef, '--', $OldGit)
            if ($c.ExitCode -ne 0) { return $false }
            $r = Invoke-RnGit -GitArgs @('mv', '--', $OldGit, $NewGit)
            if ($r.ExitCode -ne 0) { return $false }
            $did = $true
        }
        if (-not $did) { return $false }
        foreach ($k in $kids) {
            $rest = $k.Substring($OldGit.Length)
            $nk = $NewGit + $rest
            $hash = [string]$script:RnMap[$k]
            [void]$script:RnMap.Remove($k)
            $script:RnMap[$nk] = $hash
        }
        return $true
    }

    function Read-RnListText {
        param([string]$Path)
        $bytes = [System.IO.File]::ReadAllBytes($Path)
        $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
        $enc = New-Object System.Text.UTF8Encoding $bom
        $text = $enc.GetString($bytes)
        if ($text.Length -gt 0 -and [int][char]$text[0] -eq 0xFEFF) { $text = $text.Substring(1) }
        return [pscustomobject]@{ Text = $text; Bom = $bom }
    }

    function Write-RnListText {
        param([string]$Path, [string]$Text, [bool]$Bom)
        $enc = New-Object System.Text.UTF8Encoding $Bom
        [System.IO.File]::WriteAllText($Path, $Text, $enc)
    }

    function Get-RnIgnorePaths {
        param([string[]]$Lines)
        $paths = New-Object 'System.Collections.Generic.List[string]'
        $in = $false
        foreach ($line in $Lines) {
            if ($line -match '^\s*<Ignore>\s*$') { $in = $true; continue }
            if ($line -match '^\s*</Ignore>\s*$') { $in = $false; continue }
            if (-not $in) { continue }
            $t = $line.Trim()
            if ([string]::IsNullOrWhiteSpace($t) -or $t.StartsWith('#')) { continue }
            $g = ConvertTo-RnGit $t
            if ($g) { [void]$paths.Add($g) }
        }
        return @($paths)
    }

    function Test-RnRelated {
        param([string]$A, [string]$B)
        if ([string]::Equals($A, $B, [StringComparison]::OrdinalIgnoreCase)) { return $true }
        if ($A.StartsWith($B + '/', [StringComparison]::OrdinalIgnoreCase)) { return $true }
        if ($B.StartsWith($A + '/', [StringComparison]::OrdinalIgnoreCase)) { return $true }
        return $false
    }

    function Parse-RnPair {
        param([string]$Line)
        $t = $Line.Trim()
        if ([string]::IsNullOrWhiteSpace($t) -or $t.StartsWith('#')) { return $null }
        $m = [regex]::Match($t, '^(.+?)\s*[:\uFF1A]\s*(.+)$')
        if (-not $m.Success) { return $null }
        $old = ConvertTo-RnGit $m.Groups[1].Value
        $new = ConvertTo-RnGit $m.Groups[2].Value
        if (-not $old -or -not $new) { return $null }
        if ([string]::Equals($old, $new, [StringComparison]::OrdinalIgnoreCase)) { return $null }
        return [pscustomobject]@{ Old = $old; New = $new }
    }

    function Get-RnAnswerYes {
        if (-not [string]::IsNullOrWhiteSpace($ConflictAnswer)) {
            $preset = $ConflictAnswer.Trim()
            return ($preset -eq 'Y' -or $preset -eq 'y')
        }
        Write-Host 'Conflict in Rename and Ignore, Rename first?'
        $ans = Read-Host
        if ($null -eq $ans) { return $false }
        $t = $ans.Trim()
        return ($t -eq 'Y' -or $t -eq 'y')
    }

    if ([string]::IsNullOrWhiteSpace($ListFile) -or -not (Test-Path -LiteralPath $ListFile -PathType Leaf)) {
        Write-RnLog 'Rename list file not found; skip.' 'DEBUG'
        return
    }
    if ([string]::IsNullOrWhiteSpace($GitExe) -or -not (Test-Path -LiteralPath $GitExe -PathType Leaf)) {
        $cmd = Get-Command git -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) { $GitExe = $cmd.Source }
    }
    if ([string]::IsNullOrWhiteSpace($GitExe) -or -not (Test-Path -LiteralPath $GitExe -PathType Leaf)) {
        Write-RnLog 'Rename skipped: git.exe not found.' 'WARN'
        return
    }

    $script:RnRoot = $LocalFolder
    $script:RnGit = $GitExe
    $script:RnRef = $RemoteRef
    $script:RnMap = $RemoteHashMap
    $script:RnCrlf = $false
    $crlf = Invoke-RnGit -GitArgs @('config', '--get', 'core.autocrlf') -AllowFail
    if ($crlf.ExitCode -eq 0 -and $crlf.Output) {
        $v = ($crlf.Output -split "`r?`n" | Select-Object -First 1).Trim().ToLowerInvariant()
        if ($v -eq 'true' -or $v -eq 'input') { $script:RnCrlf = $true }
    }

    $loaded = Read-RnListText $ListFile
    $nl = if ($loaded.Text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $lines = @($loaded.Text -split "`r?`n", -1)
    $ignorePaths = @(Get-RnIgnorePaths $lines)

    $inRename = $false
    $actions = New-Object 'System.Collections.Generic.List[object]'
    $drop = New-Object 'System.Collections.Generic.HashSet[int]'
    $ignoreRewrites = New-Object 'System.Collections.Generic.List[object]'

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = [string]$lines[$i]
        if ($line -match '^\s*<Rename>\s*$') { $inRename = $true; continue }
        if ($line -match '^\s*</Rename>\s*$') { $inRename = $false; continue }
        if (-not $inRename) { continue }
        $pair = Parse-RnPair $line
        if ($null -eq $pair) { continue }

        $hits = New-Object 'System.Collections.Generic.List[string]'
        foreach ($ig in $ignorePaths) {
            if ((Test-RnRelated $pair.Old $ig) -or (Test-RnRelated $pair.New $ig)) {
                [void]$hits.Add($ig)
            }
        }
        if ($hits.Count -gt 0) {
            Write-RnLog ("Rename conflicts with Ignore: {0} -> {1} ({2})" -f $pair.Old, $pair.New, ($hits -join '; ')) 'WARN'
            $yes = Get-RnAnswerYes
            if (-not $yes) {
                [void]$drop.Add($i)
                Write-RnLog ("Rename skipped and removed from list: {0} -> {1}" -f $pair.Old, $pair.New) 'WARN'
                continue
            }
            [void]$ignoreRewrites.Add($pair)
            Write-RnLog ("Rename wins over Ignore: {0} -> {1}" -f $pair.Old, $pair.New)
        }
        [void]$actions.Add($pair)
    }

    $fileChanged = ($drop.Count -gt 0 -or $ignoreRewrites.Count -gt 0)
    if ($fileChanged) {
        $inIgnore = $false
        $inRename = $false
        $out = New-Object 'System.Collections.Generic.List[string]'
        for ($i = 0; $i -lt $lines.Count; $i++) {
            $line = [string]$lines[$i]
            if ($line -match '^\s*<Ignore>\s*$') { $inIgnore = $true; [void]$out.Add($line); continue }
            if ($line -match '^\s*</Ignore>\s*$') { $inIgnore = $false; [void]$out.Add($line); continue }
            if ($line -match '^\s*<Rename>\s*$') { $inRename = $true; [void]$out.Add($line); continue }
            if ($line -match '^\s*</Rename>\s*$') { $inRename = $false; [void]$out.Add($line); continue }
            if ($inRename -and $drop.Contains($i)) { continue }
            if ($inIgnore) {
                $t = $line.Trim()
                $g = $null
                if (-not [string]::IsNullOrWhiteSpace($t) -and -not $t.StartsWith('#')) { $g = ConvertTo-RnGit $t }
                if ($g) {
                    foreach ($rw in $ignoreRewrites) {
                        if ([string]::Equals($g, $rw.Old, [StringComparison]::OrdinalIgnoreCase) -or
                            $g.StartsWith($rw.Old + '/', [StringComparison]::OrdinalIgnoreCase)) {
                            $suffix = $g.Substring($rw.Old.Length)
                            $line = $rw.New + $suffix
                            Write-RnLog ("Ignore entry renamed: {0} -> {1}" -f $g, $line)
                            break
                        }
                        if ($g.StartsWith($rw.New + '/', [StringComparison]::OrdinalIgnoreCase) -or
                            [string]::Equals($g, $rw.New, [StringComparison]::OrdinalIgnoreCase)) {
                            break
                        }
                        if ($rw.Old.StartsWith($g + '/', [StringComparison]::OrdinalIgnoreCase) -or
                            $rw.New.StartsWith($g + '/', [StringComparison]::OrdinalIgnoreCase)) {
                            Write-RnLog ("Ignore parent left unchanged: {0}" -f $g) 'WARN'
                        }
                    }
                }
            }
            [void]$out.Add($line)
        }
        $newText = $out -join $nl
        Write-RnListText -Path $ListFile -Text $newText -Bom $loaded.Bom
    }

    $nRename = 0
    $nOver = 0
    $nAlready = 0
    $nSkip = 0
    $nFail = 0

    foreach ($pair in $actions) {
        try {
            $oldKind = Get-RnKind $pair.Old
            $newKind = Get-RnKind $pair.New
            if ($oldKind -eq 'mixed' -or $newKind -eq 'mixed' -or
                ($oldKind -eq 'file' -and $newKind -eq 'dir') -or
                ($oldKind -eq 'dir' -and $newKind -eq 'file')) {
                Write-RnLog ("Rename skipped (file/folder mismatch): {0} -> {1}" -f $pair.Old, $pair.New) 'WARN'
                $nSkip++
                continue
            }
            if ($oldKind -eq 'missing' -and $newKind -eq 'missing') {
                Write-RnLog ("Rename skipped (neither path exists): {0} -> {1}" -f $pair.Old, $pair.New) 'DEBUG'
                $nSkip++
                continue
            }

            if ($oldKind -eq 'dir' -or $newKind -eq 'dir') {
                if ($oldKind -eq 'dir' -and $newKind -eq 'missing') {
                    if (Invoke-WholeTreeRename -OldGit $pair.Old -NewGit $pair.New) {
                        Write-RnLog ("Folder renamed: {0} -> {1}" -f $pair.Old, $pair.New)
                        $nRename++
                        continue
                    }
                }
                $subs = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
                foreach ($k in @(Get-RnChildKeys $pair.Old)) {
                    [void]$subs.Add($k.Substring($pair.Old.Length).TrimStart('/'))
                }
                foreach ($k in @(Get-RnChildKeys $pair.New)) {
                    [void]$subs.Add($k.Substring($pair.New.Length).TrimStart('/'))
                }
                foreach ($s in @(Get-LocalSubPaths $pair.Old)) { [void]$subs.Add($s) }
                foreach ($s in @(Get-LocalSubPaths $pair.New)) { [void]$subs.Add($s) }
                $folderRename = 0
                $folderOver = 0
                foreach ($sub in @($subs)) {
                    if ([string]::IsNullOrWhiteSpace($sub)) { continue }
                    $st = Move-OneFile -OldGit ($pair.Old.TrimEnd('/') + '/' + $sub) -NewGit ($pair.New.TrimEnd('/') + '/' + $sub)
                    switch ($st) {
                        'renamed' { $folderRename++; $nRename++ }
                        'renamed-overwrite' { $folderOver++; $nOver++ }
                        'already' { $nAlready++ }
                        'failed' { $nFail++ }
                        default { $nSkip++ }
                    }
                }
                Remove-EmptyRnDir (Get-RnAbs $pair.Old)
                Write-RnLog ("Folder rename {0} -> {1}: files renamed={2}, overwritten={3}" -f $pair.Old, $pair.New, $folderRename, $folderOver)
                continue
            }

            $stFile = Move-OneFile -OldGit $pair.Old -NewGit $pair.New
            switch ($stFile) {
                'renamed' {
                    Write-RnLog ("File renamed: {0} -> {1}" -f $pair.Old, $pair.New)
                    $nRename++
                }
                'renamed-overwrite' {
                    Write-RnLog ("File renamed and overwritten: {0} -> {1}" -f $pair.Old, $pair.New)
                    $nOver++
                }
                'already' {
                    Write-RnLog ("Rename already applied: {0} -> {1}" -f $pair.Old, $pair.New) 'DEBUG'
                    $nAlready++
                }
                'failed' { $nFail++ }
                default {
                    Write-RnLog ("Rename skipped (not found): {0} -> {1}" -f $pair.Old, $pair.New) 'DEBUG'
                    $nSkip++
                }
            }
        } catch {
            $nFail++
            Write-RnLog ("Rename failed [{0} -> {1}]: {2}" -f $pair.Old, $pair.New, $_.Exception.Message) 'WARN'
        }
    }

    if ($actions.Count -eq 0 -and -not $fileChanged) {
        Write-RnLog 'No <Rename> entries.' 'DEBUG'
        return
    }
    Write-RnLog ("Rename stats: renamed={0}, overwritten={1}, already={2}, skipped={3}, failed={4}" -f $nRename, $nOver, $nAlready, $nSkip, $nFail)
}

if ($MyInvocation.InvocationName -ne '.') {
    Write-Host 'Apply-SyncGitHubRename.ps1 is called by Sync-GitHubLocal.ps1 during sync. It does not run by itself.'
}
