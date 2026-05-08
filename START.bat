@echo off
title Crypto Pump Detector V2 - WebSocket Edition
color 0A

echo.
echo  ==========================================
echo   CRYPTO PUMP DETECTOR V2 - WebSocket
echo  ==========================================
echo.

:: Kill any existing instances on port 8002 / 3001 (robust: dung ca tokens=4 va tokens=5)
echo [0/3] Freeing ports 8002 and 3001...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr /R "[ :]8002[ ]"') do (
    if not "%%a"=="" taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr /R "[ :]3001[ ]"') do (
    if not "%%a"=="" taskkill /f /pid %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: Install backend deps silently if needed
echo [1/3] Checking backend dependencies...
cd /d "%~dp0backend"
pip install -r requirements.txt -q --disable-pip-version-check >nul 2>&1
echo       Done.

:: Install frontend deps silently if node_modules missing
echo [2/3] Checking frontend dependencies...
if not exist "%~dp0frontend\node_modules" (
    cd /d "%~dp0frontend"
    call npm install --silent >nul 2>&1
)
echo       Done.

:: Start backend in new window
echo [3/3] Launching backend ^& frontend...
cd /d "%~dp0backend"
start "Backend - FastAPI :8002" cmd /k "uvicorn main:app --host 0.0.0.0 --port 8002"

:: Wait for backend to be ready
timeout /t 4 /nobreak >nul

:: Start frontend in new window
cd /d "%~dp0frontend"
start "Frontend - React :3001" cmd /k "npm start"

:: Wait and open browser
timeout /t 8 /nobreak >nul
start http://localhost:3001

echo.
echo  ==========================================
echo   Backend  : http://localhost:8002
echo   Frontend : http://localhost:3001
echo   API Docs : http://localhost:8002/docs
echo  ==========================================
echo.
echo  Close this window or press any key to exit.
pause >nul
