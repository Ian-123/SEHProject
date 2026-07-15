@echo off
setlocal
cd /d "%~dp0"

REM 1) Create a private Python env (first run only)
if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment...
  py -3.11 -m venv .venv
)

REM 2) Ensure required packages are installed (quietly)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt

REM 3) Start the browser (optional)
start "" http://localhost:8501

REM 4) Launch the app on a fixed port so the shortcut always works
".venv\Scripts\python.exe" -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501
