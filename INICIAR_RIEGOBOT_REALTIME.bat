@echo off
setlocal EnableDelayedExpansion
title RiegoBot - Collector Realtime

set "BASE=%~dp0"
pushd "%BASE%" >nul 2>nul

echo ============================================
echo   RiegoBot - Collector Realtime
echo ============================================
echo.
echo El collector actualizara los datos automaticamente.
echo No cierre esta ventana durante la prueba.
echo.

where python.exe >nul 2>nul
if not errorlevel 1 (
  python -m dreamreader realtime
  set "RC=!ERRORLEVEL!"
  goto :END
)

where py.exe >nul 2>nul
if not errorlevel 1 (
  py -3 -m dreamreader realtime
  set "RC=!ERRORLEVEL!"
  goto :END
)

echo [ERROR] Python 3.11 o posterior no fue encontrado.
set "RC=3"

:END
echo.
echo Collector finalizado. Codigo: !RC!
pause
popd >nul 2>nul
exit /b !RC!
