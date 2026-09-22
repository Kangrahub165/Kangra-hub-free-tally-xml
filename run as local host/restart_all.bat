@echo off
title Kangra Hub - Restart All Servers
color 0E
echo ===============================================================================
echo            KANGRA HUB - RESTARTING ALL LOCALHOST SERVERS
echo ===============================================================================
echo.

echo [1/4] Stopping existing processes on ports 8000 and 3000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

set "ROOT_DIR=%~dp0.."
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"

echo [2/4] Launching FastAPI Backend Server on http://localhost:8000 ...
start "Kangra Hub - Backend (Port 8000)" cmd /k "cd /d "%BACKEND_DIR%" && title Kangra Hub Backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo [3/4] Launching Next.js Frontend App on http://localhost:3000 ...
start "Kangra Hub - Frontend (Port 3000)" cmd /k "cd /d "%FRONTEND_DIR%" && title Kangra Hub Frontend && npm run dev"

echo [4/4] Waiting 5 seconds for initialization...
timeout /t 5 /nobreak >nul

echo Opening browser...
start http://localhost:3000

echo.
echo ===============================================================================
echo Kangra Hub servers restarted successfully!
echo ===============================================================================
echo.
pause
