@echo off
setlocal
title RiegoBot - Probar Azure
cd /d "%~dp0"

echo ============================================
echo   RiegoBot - Verificacion Azure
echo ============================================
echo.
echo Proyecto:
echo %CD%
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\azure\TEST_AZURE_PREREQUISITOS.ps1"
set "RC=%ERRORLEVEL%"

echo.
echo ============================================
echo Codigo de salida: %RC%
echo ============================================
echo.
pause
exit /b %RC%
