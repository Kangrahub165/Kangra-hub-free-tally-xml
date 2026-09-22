@echo off
title Kangra Hub - Stop All Servers
color 0C
echo ===============================================================================
echo            KANGRA HUB - STOPPING LOCALHOST SERVERS
echo ===============================================================================
echo.

echo Checking and stopping any processes on Port 8000 (Backend)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo Stopping process PID: %%a on port 8000...
    taskkill /F /PID %%a >nul 2>&1
)

echo Checking and stopping any processes on Port 3000 (Frontend)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    echo Stopping process PID: %%a on port 3000...
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo ===============================================================================
echo All Kangra Hub servers on ports 8000 and 3000 have been stopped.
echo ===============================================================================
echo.
pause
