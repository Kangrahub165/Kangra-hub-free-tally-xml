@echo off
title Kangra Hub - Start All (Localhost)
color 0B
echo ===============================================================================
echo            KANGRA HUB - FREE TALLY XML CONVERTER PLATFORM
echo                        Starting Localhost Servers
echo ===============================================================================
echo.

set "ROOT_DIR=%~dp0.."
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"

echo [1/3] Launching FastAPI Backend Server on http://localhost:8000 ...
start "Kangra Hub - Backend (Port 8000)" cmd /k "cd /d "%BACKEND_DIR%" && title Kangra Hub Backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/3] Launching Next.js Frontend App on http://localhost:3000 ...
start "Kangra Hub - Frontend (Port 3000)" cmd /k "cd /d "%FRONTEND_DIR%" && title Kangra Hub Frontend && npm run dev"

echo [3/3] Waiting for servers to initialize...
timeout /t 5 /nobreak >nul

echo Opening Kangra Hub in your default browser...
start http://localhost:3000

echo.
echo ===============================================================================
echo                      LOCAL SERVERS ARE NOW ACTIVE!
echo ===============================================================================
echo  - Frontend Web App:  http://localhost:3000
echo  - Statement Convert: http://localhost:3000/convert
echo  - Admin Dashboard:   http://localhost:3000/admin
echo  - Backend API:       http://localhost:8000
echo  - API Swagger Docs:  http://localhost:8000/docs
echo ===============================================================================
echo  Keep the opened command windows running while using the app.
echo  To stop all servers cleanly at any time, run: stop_all.bat
echo ===============================================================================
echo.
pause
