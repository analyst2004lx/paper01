#Requires -Version 5.1
<#
.SYNOPSIS
  Convert a LaTeX paper to Word (native equations) via Pandoc.

.DESCRIPTION
  Edit the CONFIG block, then run this script (or double-click the .bat).
  Pandoc runs in the LaTeX folder so \input / figures resolve.
  The .docx is written next to this script, same base name as the .tex file.

.NOTES
  Requires Pandoc (https://pandoc.org). \textsc in math is rewritten to \text
  for Word; the original .tex is not modified.
#>
param(
    [switch]$NoPause
)

# ======================== USER CONFIG ========================
# Only these two usually need changing.
$Config = @{
    # Folder that contains the .tex (and figures / \input files)
    LatexFolder = 'C:\Users\analy\Desktop\AI_Folder\paper04'
    # File name only, or a path relative to LatexFolder
    TexFile     = 'paper04.tex'
    # Empty = auto-detect from \bibliography / \addbibresource / folder *.bib
    # Example: 'reference-base.bib'
    BibFile     = ''
}
# =============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string]$Message, [string]$Level = 'INFO')
    $color = switch ($Level) {
        'ERROR' { 'Red' }
        'WARN'  { 'Yellow' }
        'OK'    { 'Green' }
        default { 'Cyan' }
    }
    Write-Host ('[{0}] {1}' -f $Level, $Message) -ForegroundColor $color
}

function Get-PandocExe {
    $cmd = Get-Command pandoc -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    foreach ($c in @(
        'C:\Program Files\Pandoc\pandoc.exe',
        'C:\Program Files (x86)\Pandoc\pandoc.exe',
        (Join-Path $env:LOCALAPPDATA 'Pandoc\pandoc.exe')
    )) {
        if (Test-Path -LiteralPath $c -PathType Leaf) { return $c }
    }
    return $null
}

function Ensure-TrailingNewline {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -eq 0) { return $false }
    if ($bytes[$bytes.Length - 1] -eq 10) { return $false }
    [System.IO.File]::WriteAllBytes($Path, ($bytes + [byte[]](13, 10)))
    return $true
}

function Get-BibliographyFiles {
    param(
        [string]$TexPath,
        [string]$LatexFolder,
        [string]$ConfiguredBib
    )
    $found = New-Object 'System.Collections.Generic.List[string]'

    if (-not [string]::IsNullOrWhiteSpace($ConfiguredBib)) {
        $p = $ConfiguredBib
        if (-not [System.IO.Path]::IsPathRooted($p)) {
            $p = Join-Path $LatexFolder $p
        }
        if (-not ($p -like '*.bib')) { $p = "$p.bib" }
        if (Test-Path -LiteralPath $p -PathType Leaf) {
            [void]$found.Add((Resolve-Path -LiteralPath $p).Path)
            return @($found)
        }
        Write-Step ("Configured BibFile not found: {0}" -f $p) -Level WARN
    }

    $tex = [System.IO.File]::ReadAllText($TexPath)
    $names = New-Object 'System.Collections.Generic.List[string]'
    foreach ($m in [regex]::Matches($tex, '\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}')) {
        foreach ($part in ($m.Groups[1].Value -split ',')) {
            $n = $part.Trim()
            if ([string]::IsNullOrWhiteSpace($n)) { continue }
            $n = $n -replace '\\string', ''
            if ($n -notlike '*.bib') { $n = "$n.bib" }
            [void]$names.Add($n)
        }
    }

    foreach ($n in $names) {
        $p = $n
        if (-not [System.IO.Path]::IsPathRooted($p)) {
            $p = Join-Path $LatexFolder $n
        }
        if (Test-Path -LiteralPath $p -PathType Leaf) {
            $full = (Resolve-Path -LiteralPath $p).Path
            if (-not ($found -contains $full)) { [void]$found.Add($full) }
        } else {
            Write-Step ("TeX references bibliography but file missing: {0}" -f $p) -Level WARN
        }
    }

    if ($found.Count -gt 0) { return @($found) }

    $usesCite = [regex]::IsMatch($tex, '\\(cite|citep|citet|parencite|textcite|autocite)\b')
    $bibs = @(Get-ChildItem -LiteralPath $LatexFolder -Filter '*.bib' -File -ErrorAction SilentlyContinue)
    if ($usesCite -and $bibs.Count -eq 1) {
        Write-Step ('No \\bibliography in TeX; using the only .bib in the folder: {0}' -f $bibs[0].Name)
        return @($bibs[0].FullName)
    }
    if ($usesCite -and $bibs.Count -gt 1) {
        $prefer = @($bibs | Where-Object { $_.BaseName -in @('reference-base', 'references', 'ref', 'refs') })
        if ($prefer.Count -eq 1) {
            Write-Step ('No \\bibliography in TeX; using {0}' -f $prefer[0].Name)
            return @($prefer[0].FullName)
        }
        Write-Step 'Found \cite and multiple .bib files; set $Config.BibFile. Skipping bibliography.' -Level WARN
        foreach ($b in $bibs) { Write-Step ('  - {0}' -f $b.Name) -Level WARN }
    }
    return @()
}

$exitCode = 0
$tmpTex = $null
try {
    Write-Host ''
    Write-Step 'LaTeX -> Word (Pandoc)'
    Write-Step ('Script folder (output): {0}' -f $PSScriptRoot)

    $latexFolder = $Config.LatexFolder.Trim().Trim('"')
    if (-not (Test-Path -LiteralPath $latexFolder -PathType Container)) {
        throw ("LatexFolder not found: {0}" -f $latexFolder)
    }
    $latexFolder = (Resolve-Path -LiteralPath $latexFolder).Path

    $texName = $Config.TexFile.Trim().Trim('"')
    $texPath = if ([System.IO.Path]::IsPathRooted($texName)) { $texName } else { Join-Path $latexFolder $texName }
    if (-not (Test-Path -LiteralPath $texPath -PathType Leaf)) {
        throw ("TeX file not found: {0}" -f $texPath)
    }
    $texPath = (Resolve-Path -LiteralPath $texPath).Path
    $texBase = [System.IO.Path]::GetFileNameWithoutExtension($texPath)
    $outDocx = Join-Path $PSScriptRoot ($texBase + '.docx')

    Write-Step ('LaTeX folder: {0}' -f $latexFolder)
    Write-Step ('TeX file:     {0}' -f $texPath)
    Write-Step ('Word output:  {0}' -f $outDocx)

    $pandoc = Get-PandocExe
    if (-not $pandoc) {
        throw 'pandoc.exe not found. Install from https://pandoc.org and reopen PowerShell.'
    }
    Write-Step ('Pandoc: {0}' -f $pandoc)

    $bibs = @(Get-BibliographyFiles -TexPath $texPath -LatexFolder $latexFolder -ConfiguredBib $Config.BibFile)
    if ($bibs.Count -gt 0) {
        foreach ($b in $bibs) {
            if (Ensure-TrailingNewline -Path $b) {
                Write-Step ('Added missing newline at end of {0}' -f $b) -Level WARN
            } else {
                Write-Step ('Bibliography: {0}' -f $b)
            }
        }
    } else {
        Write-Step 'No .bib will be passed to Pandoc (text-only conversion).'
    }

    # Word math has no \textsc; keep the original .tex untouched.
    $raw = [System.IO.File]::ReadAllText($texPath)
    $forPandoc = $raw -replace '\\textsc\{', '\text{'
    $tmpTex = Join-Path $latexFolder ('_pandoc_tmp_{0}.tex' -f $texBase)
    [System.IO.File]::WriteAllText($tmpTex, $forPandoc)

    Write-Step ('Working directory -> {0}' -f $latexFolder)
    Set-Location -LiteralPath $latexFolder

    $args = @(
        [System.IO.Path]::GetFileName($tmpTex)
        '-o', $outDocx
    )
    if ($bibs.Count -gt 0) {
        foreach ($b in $bibs) {
            $args += @('--bibliography', $b)
        }
        $args += '--citeproc'
    }

    Write-Step ('Running: pandoc {0}' -f ($args -join ' '))
    $outLog = Join-Path $env:TEMP 'pandoc-latex2word.log'
    $errLog = Join-Path $env:TEMP 'pandoc-latex2word.err'
    $p = Start-Process -FilePath $pandoc -ArgumentList $args -WorkingDirectory $latexFolder `
        -Wait -PassThru -NoNewWindow -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    $stdout = ''
    $stderr = ''
    if (Test-Path -LiteralPath $outLog) { $stdout = [System.IO.File]::ReadAllText($outLog).Trim() }
    if (Test-Path -LiteralPath $errLog) { $stderr = [System.IO.File]::ReadAllText($errLog).Trim() }
    if ($stdout) { Write-Host $stdout }

    if ($p.ExitCode -ne 0) {
        if ($stderr) {
            foreach ($line in ($stderr -split "`r?`n")) {
                if ($line.Trim()) { Write-Step $line -Level ERROR }
            }
        }
        throw ("Pandoc failed (exit {0}). Word file was not produced." -f $p.ExitCode)
    }

    if ($stderr) {
        foreach ($line in ($stderr -split "`r?`n")) {
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            if ($line -match 'WARNING|Could not convert') {
                Write-Step $line -Level WARN
            } else {
                Write-Step $line -Level WARN
            }
        }
        Write-Step 'Pandoc finished with warnings (docx was still created).' -Level WARN
    }

    if (-not (Test-Path -LiteralPath $outDocx -PathType Leaf)) {
        throw ("Pandoc exit 0 but output missing: {0}" -f $outDocx)
    }
    $len = (Get-Item -LiteralPath $outDocx).Length
    Write-Step ('Done: {0}  ({1:N0} bytes)' -f $outDocx, $len) -Level OK
}
catch {
    $exitCode = 1
    Write-Step $_.Exception.Message -Level ERROR
    Write-Step 'Fix the message above, then run the script again.' -Level ERROR
}
finally {
    if ($tmpTex -and (Test-Path -LiteralPath $tmpTex)) {
        Remove-Item -LiteralPath $tmpTex -Force -ErrorAction SilentlyContinue
    }
}

if (-not $NoPause) {
    Write-Host ''
    if ($exitCode -eq 0) {
        Write-Host 'Press Enter to close...' -ForegroundColor DarkGray
    } else {
        Write-Host 'There was an error. Press Enter to close...' -ForegroundColor Yellow
    }
    [void][Console]::ReadLine()
}

exit $exitCode
