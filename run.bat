@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py") else (set "PY=python")
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating Python virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 goto error
)
echo [2/3] Installing/updating dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo [3/3] Starting DataPilot Studio...
".venv\Scripts\python.exe" -m streamlit run app.py
goto end
:error
echo.
echo Setup failed. Install Python 3.10+ and ensure "Add Python to PATH" is enabled.
pause
:end
endlocal
