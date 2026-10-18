@echo off
title Wrecz Summarizer Backend
cd /d "%~dp0"
echo Starting Wrecz Summarizer Backend on http://localhost:8000 ...

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" main.py
) else if exist "%~dp0..\.venv\Scripts\python.exe" (
    "%~dp0..\.venv\Scripts\python.exe" main.py
) else (
    python main.py
)
pause
