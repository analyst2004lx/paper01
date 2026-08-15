# Build all paper03 figures
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "== export_data =="
py export_data.py
Write-Host "== plot_all =="
py plot_all.py
Write-Host "== tikz =="
& .\build_tikz.ps1
Write-Host "All figures built in $PSScriptRoot"
Get-ChildItem *.pdf | Select-Object Name, Length, LastWriteTime
