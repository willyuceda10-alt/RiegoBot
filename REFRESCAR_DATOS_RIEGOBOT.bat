@echo off
setlocal EnableDelayedExpansion
title RiegoBot - Refrescar datos

set "BASE=%~dp0"
set "NO_PAUSE=0"
if /I "%~1"=="/nopause" set "NO_PAUSE=1"
pushd "%BASE%" >nul 2>nul

echo ============================================
echo   RiegoBot - Refrescar datos Dream
echo ============================================
echo.
echo Este proceso crea una nueva sesion normalizada
echo leyendo las bases Dream en modo solo lectura.
echo.

call "%BASE%EJECUTAR_DREAMREADER.cmd" extract
set "RC=!ERRORLEVEL!"

if not "!RC!"=="0" (
  echo.
  echo [ERROR] No se pudo refrescar la informacion de RiegoBot.
  goto :END
)

echo.
echo ============================================
echo [OK] Datos de RiegoBot refrescados.
echo ============================================
echo.
echo Las proximas consultas usaran la nueva sesion.

:END
echo.
echo Codigo de salida: !RC!
echo.
if "!NO_PAUSE!"=="0" pause
popd >nul 2>nul
exit /b !RC!
