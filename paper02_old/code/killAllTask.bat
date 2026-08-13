@echo off
echo Killing all tasks occupying ports 5000-5003, 6000-6003, 7000...

rem Loop through all ports we want to free (adjust port numbers as needed)

for /l %%p in (6000, 1, 6003) do (
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%%p') do (
        echo Killing process with PID %%a on port %%p...
        taskkill /F /PID %%a >nul 2>&1
    )
)

for /l %%p in (7000, 1, 7003) do (
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%%p') do (
        echo Killing process with PID %%a on port %%p...
        taskkill /F /PID %%a >nul 2>&1
    )
)

for /l %%p in (8000, 1, 8001) do (
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%%p') do (
        echo Killing process with PID %%a on port %%p...
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo All tasks using ports 5000-5003, 6000-6003, 7000... have been killed.

