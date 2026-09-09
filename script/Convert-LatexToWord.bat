@echo off
setlocal
cd /d "%~dp0"
title LaTeX to Word
echo Opening PowerShell...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Convert-LatexToWord.ps1"
exit /b %ERRORLEVEL%
