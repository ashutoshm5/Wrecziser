@echo off
setlocal EnableDelayedExpansion

echo ========================================================
echo   Wrecziser - Chrome Native Messaging Host Setup
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "EXT_ID=okagbogangoibgjiojfnmpbicaakcpbm"
if not "%~1"=="" (
    set "EXT_ID=%~1"
) else (
    echo Current default Chrome Extension ID: %EXT_ID%
    echo If your extension ID in chrome://extensions is different,
    echo enter it below, or press ENTER to keep the default.
    set /p "USER_EXT_ID=Extension ID [press ENTER for default]: "
    if not "!USER_EXT_ID!"=="" set "EXT_ID=!USER_EXT_ID!"
)

echo.
echo Configuring native messaging host for:
echo   Folder: %SCRIPT_DIR%
echo   Extension ID: %EXT_ID%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ext = $env:EXT_ID; $hostPath = Join-Path $env:SCRIPT_DIR 'native_host.exe'; $origins = @(('chrome-extension://{0}/' -f $ext), 'chrome-extension://okagbogangoibgjiojfnmpbicaakcpbm/', 'chrome-extension://iiphddcpdpgkpckolghngefkebjaoaak/') | Select-Object -Unique; $json = [ordered]@{ name = 'com.wrecz.wrecziser'; description = 'Wrecziser Local Backend Activator'; path = $hostPath; type = 'stdio'; allowed_origins = $origins } | ConvertTo-Json -Depth 5; [System.IO.File]::WriteAllText((Join-Path $env:SCRIPT_DIR 'com.wrecz.wrecziser.json'), $json)"

reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.wrecz.wrecziser" /ve /t REG_SZ /d "%SCRIPT_DIR%\com.wrecz.wrecziser.json" /f

echo.
echo ========================================================
echo [OK] Wrecziser native messaging host registered successfully!
echo Manifest: %SCRIPT_DIR%\com.wrecz.wrecziser.json
echo ========================================================
echo.
if "%~1"=="" pause
