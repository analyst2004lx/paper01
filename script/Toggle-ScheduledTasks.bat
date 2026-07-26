@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
title Toggle AI_Folder Scheduled Tasks

:: 双击切换：注册 <-> 删除
::   AIFolder-GitHubSync          白天周期性同步（脚本内限制 10:00-17:00）
::   AIFolder-WireGuardDisconnect 每天 20:00 断开 WireGuard
:: 再次双击则删除。

set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%Toggle-ScheduledTasks.ps1"

echo.
echo ============================================================
echo   AI_Folder 计划任务 切换工具
echo ============================================================
echo   目录: %SCRIPT_DIR%
echo.

if not exist "%PS1%" (
  echo [ERROR] 找不到: %PS1%
  goto :FAIL
)

where powershell >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 未找到 powershell.exe
  goto :FAIL
)

:: 自提升管理员
net session >nul 2>&1
if errorlevel 1 (
  echo [INFO] 需要管理员权限，正在请求 UAC...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b 0
)

echo [INFO] 已以管理员身份运行。
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Mode Auto
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" goto :FAIL

echo [RESULT] 操作完成。再次双击本脚本可执行相反操作（注册/删除切换）。
echo.
pause
exit /b 0

:FAIL
echo [RESULT] 操作失败，退出码=%RC%
echo.
pause
exit /b 1
