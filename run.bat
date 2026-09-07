@echo off
cd /d "%~dp0"

rem Requires admin: global hotkey/wheel hooks must bypass UIPI to capture other elevated apps
powershell -NoProfile -Command "if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { exit 1 }"
if errorlevel 1 (
    echo [setup] requesting administrator privileges...
    > "%temp%\eo_getadmin.vbs" echo Set UAC = CreateObject^("Shell.Application"^)
    >> "%temp%\eo_getadmin.vbs" echo UAC.ShellExecute "%~f0", "", "", "runas", 1
    "%temp%\eo_getadmin.vbs"
    del "%temp%\eo_getadmin.vbs"
    exit /b
)

if not exist ".venv\Scripts\pythonw.exe" (
    echo [setup] creating virtual environment and installing dependencies...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
start "" ".venv\Scripts\pythonw.exe" main.py
