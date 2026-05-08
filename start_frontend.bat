@echo off
set PATH=C:\nodejs;C:\Python311;C:\Python311\Scripts;%PATH%
cd /d "%~dp0frontend"

echo Checking dependencies...
call npm install --legacy-peer-deps --silent

echo.
echo ================================
echo  Starting React on port 3001...
echo  URL: http://localhost:3001
echo  Press Ctrl+C to stop.
echo ================================
echo.

set PORT=3001
set BROWSER=none
set REACT_APP_API_URL=http://localhost:8002
set REACT_APP_API_WS_URL=ws://localhost:8002

call npm start
