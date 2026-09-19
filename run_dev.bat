@echo off
title Kangra Hub Server Launcher
echo ======================================================================
echo Starting Kangra Hub Free Tally XML Local Servers...
echo ======================================================================

echo [1/2] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "Kangra-Hub-Backend-8000" cmd /k "cd /d "%~dp0backend" && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Launching Next.js Frontend on http://localhost:3000 ...
start "Kangra-Hub-Frontend-3000" cmd /k "cd /d "%~dp0frontend" && node "node_modules/next/dist/bin/next" dev -p 3000"

echo.
echo Both servers have been launched in separate dedicated command windows!
echo - Backend:  http://127.0.0.1:8000
echo - Frontend: http://localhost:3000
echo.
echo You can keep these terminal windows open to monitor logs.
echo To stop servers at any time, run: stop_dev.bat
