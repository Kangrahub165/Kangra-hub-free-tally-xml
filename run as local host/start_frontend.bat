@echo off
title Kangra Hub - Frontend App (Port 3000)
color 09
echo ===============================================================================
echo            KANGRA HUB - FRONTEND WEB APPLICATION (NEXT.JS)
echo ===============================================================================
echo.
set "ROOT_DIR=%~dp0.."
set "FRONTEND_DIR=%ROOT_DIR%\frontend"

echo Navigating to: %FRONTEND_DIR%
cd /d "%FRONTEND_DIR%"

echo.
echo Starting Next.js development server on http://localhost:3000 ...
echo.
npm run dev
pause
