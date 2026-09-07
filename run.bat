@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [setup] creating virtual environment and installing dependencies...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" main.py
