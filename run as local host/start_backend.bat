@echo off
title Kangra Hub - Backend Server (Port 8000)
color 0A
echo ===============================================================================
echo            KANGRA HUB - BACKEND API SERVER (FASTAPI / UVICORN)
echo ===============================================================================
echo.
set "ROOT_DIR=%~dp0.."
set "BACKEND_DIR=%ROOT_DIR%\backend"

echo Navigating to: %BACKEND_DIR%
cd /d "%BACKEND_DIR%"

echo.
echo Starting FastAPI engine on http://0.0.0.0:8000 with auto-reload...
echo Swagger Docs available at: http://localhost:8000/docs
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
