@echo off
setlocal
title RiegoBot - Instalar Azure PowerShell
cd /d "%~dp0"

echo ============================================
echo   RiegoBot - Instalacion Azure PowerShell
echo ============================================
echo.
echo Proyecto:
echo %CD%
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\azure\INSTALAR_AZURE_POWERSHELL.ps1"
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
  echo ============================================
  echo Instalacion no completada. Codigo: %RC%
  echo ============================================
  echo.
  pause
  exit /b %RC%
)

echo.
echo ============================================
echo   Verificando Azure despues de instalar
echo ============================================
echo.

call "%~dp0PROBAR_AZURE_RIEGOBOT.bat"
set "RC=%ERRORLEVEL%"

exit /b %RC%
