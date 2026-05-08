@echo off
set VENV_PYTHON=%~dp0.venv\Scripts\python.exe
set VENV_PIP=%~dp0.venv\Scripts\pip.exe
set PATH=C:\nodejs;C:\Python311;C:\Python311\Scripts;%PATH%
cd /d "%~dp0backend"

echo Checking dependencies...
call "%VENV_PIP%" install -r requirements.txt -q --exists-action i

echo.
echo ================================
echo  Starting FastAPI on port 8002...
echo  URL: http://localhost:8002
echo  Press Ctrl+C to stop.
echo ================================
echo.

"%VENV_PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
