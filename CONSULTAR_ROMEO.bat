@echo off
setlocal
title RiegoBot - Consultar Romeo

set "BASE=%~dp0"
pushd "%BASE%" >nul 2>nul

set /p ROMEO=Ingrese el numero de Romeo (ejemplo 11, 13 o 17): 
if "%ROMEO%"=="" (
  echo.
  echo [ERROR] Debe ingresar un numero de Romeo.
  pause
  exit /b 2
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python -m dreamreader romeo "%ROMEO%"
  set "RC=%ERRORLEVEL%"
  goto :END
)

where py.exe >nul 2>nul
if not errorlevel 1 (
  py -3 -m dreamreader romeo "%ROMEO%"
  set "RC=%ERRORLEVEL%"
  goto :END
)

echo [ERROR] Python 3.11 o posterior no fue encontrado.
set "RC=3"

:END
echo.
echo Codigo de salida: %RC%
echo.
pause
popd >nul 2>nul
exit /b %RC%
