@echo off
setlocal EnableDelayedExpansion
title Wrecziser - One-Click Setup

echo ========================================================
echo        Wrecziser - One-Click Automated Setup
echo ========================================================
echo.

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "BACKEND_DIR=%ROOT_DIR%\Wrecziser backend"

:: If Setup.exe exists and not invoked with --cli, launch the GUI Installer
if "%1"=="" (
    if exist "%ROOT_DIR%\Setup.exe" (
        start "" "%ROOT_DIR%\Setup.exe"
        exit /b 0
    )
)

:: 1. Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found on your system PATH!
    echo Please download and install Python 3.10+ from https://www.python.org/downloads/
    echo NOTE: Be sure to check the box "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [1/4] Setting up Python virtual environment...
if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
    python -m venv "%BACKEND_DIR%\.venv"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment in %BACKEND_DIR%\.venv
        pause
        exit /b 1
    )
)
echo [OK] Virtual environment ready.
echo.

echo [2/4] Installing backend dependencies...
"%BACKEND_DIR%\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
"%BACKEND_DIR%\.venv\Scripts\pip.exe" install -r "%BACKEND_DIR%\requirements.txt"
if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies failed to install. Continuing...
) else (
    echo [OK] All Python dependencies installed successfully.
)
echo.

echo [3/4] Checking Kokoro Neural TTS weights...
if not exist "%BACKEND_DIR%\models\kokoro\kokoro-v1_0.pth" (
    echo Kokoro weights not found. Downloading (~327MB)...
    "%BACKEND_DIR%\.venv\Scripts\python.exe" "%BACKEND_DIR%\download_model.py"
) else (
    echo [OK] Kokoro voice model is already installed.
)
echo.

echo [4/4] Registering Chrome Native Messaging Host...
call "%ROOT_DIR%\setup_native_host.bat"

echo.
echo ========================================================
echo        [SUCCESS] Wrecziser Setup Complete!
echo ========================================================
echo.
echo Quick Next Steps:
echo   1. Make sure Ollama is installed (https://ollama.com) and run:
echo      ollama pull qwen3:4b-instruct-2507-q4_K_M
echo   2. Load the extension in Chrome:
echo      - Go to chrome://extensions
echo      - Enable "Developer mode" (top-right)
echo      - Click "Load unpacked" and select:
echo        %ROOT_DIR%
echo   3. Launch Wrecziser by double-clicking wrecziser.exe!
echo.
pause
