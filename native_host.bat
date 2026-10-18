@echo off
if exist "%~dp0Wrecziser backend\.venv\Scripts\python.exe" (
    "%~dp0Wrecziser backend\.venv\Scripts\python.exe" "%~dp0native_host.py"
) else (
    python "%~dp0native_host.py"
)
