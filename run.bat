@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [提示] 未找到虚拟环境，正在创建并安装依赖...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" main.py
