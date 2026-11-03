@echo off
setlocal
title RiegoBot - Probar conexion central
cd /d "%~dp0"

echo ============================================
echo   RiegoBot - Prueba Cliente Central
echo ============================================
echo.
call "%~dp0EJECUTAR_DREAMREADER.cmd" central-push /nopause
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="8" (
  echo [OK] El envio central esta bloqueado de forma segura.
  echo Esto es esperado mientras azureCentral.enabled sea false.
  set "RC=0"
)

echo.
echo ============================================
echo Codigo de salida: %RC%
echo ============================================
echo.
pause
exit /b %RC%
