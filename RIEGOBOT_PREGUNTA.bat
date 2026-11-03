@echo off
setlocal EnableDelayedExpansion
title RiegoBot - Pregunta natural

set "BASE=%~dp0"
pushd "%BASE%" >nul 2>nul

echo ============================================
echo   RiegoBot - Consulta natural
echo ============================================
echo.
set /p PREGUNTA=Escriba su pregunta: 
if "%PREGUNTA%"=="" (
  echo.
  echo [ERROR] Debe escribir una pregunta.
  pause
  exit /b 2
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python -m dreamreader ask "%PREGUNTA%"
  set "RC=!ERRORLEVEL!"
  goto :END
)

where py.exe >nul 2>nul
if not errorlevel 1 (
  py -3 -m dreamreader ask "%PREGUNTA%"
  set "RC=!ERRORLEVEL!"
  goto :END
)

echo [ERROR] Python 3.11 o posterior no fue encontrado.
set "RC=3"

:END
echo.
echo Codigo de salida: !RC!
echo.
pause
popd >nul 2>nul
exit /b !RC!
