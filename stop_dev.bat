@echo off
title Stop Kangra Hub Servers
echo Stopping any running Kangra Hub servers on ports 8000 and 3000...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo Stopping process on port 8000 (PID: %%a)...
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    echo Stopping process on port 3000 (PID: %%a)...
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo All Kangra Hub servers stopped.
