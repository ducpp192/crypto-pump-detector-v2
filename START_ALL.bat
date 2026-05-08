@echo off
title Crypto Pump Detector v2
echo.
echo  ============================================
echo   Crypto Pump Detector v2 - Starting...
echo  ============================================
echo.

echo  [1/2] Starting Backend (FastAPI :8002)...
start "Backend - FastAPI :8002" cmd /k "%~dp0start_backend.bat"

timeout /t 3 /nobreak >nul

echo  [2/2] Starting Frontend (React :3001)...
start "Frontend - React :3001" cmd /k "%~dp0start_frontend.bat"

echo.
echo  ============================================
echo   Done! 2 terminals opened.
echo  ============================================
echo.
echo   Backend  ^> http://localhost:8002
echo   Frontend ^> http://localhost:3001
echo   Dong Tien^> http://localhost:8002/api/dong-tien/alerts
echo.
echo  This window will close in 5s...
timeout /t 5 /nobreak >nul
