@echo off
setlocal EnableDelayedExpansion
title RiegoBot - DreamReader
set "BASE=%~dp0"
set "RC=0"
set "COMMAND=%~1"
set "NO_PAUSE=0"
if /I "%~2"=="/nopause" set "NO_PAUSE=1"
if "%COMMAND%"=="" set "COMMAND=discovery"

if /I not "%COMMAND%"=="discovery" if /I not "%COMMAND%"=="extract" if /I not "%COMMAND%"=="extract-candidates" if /I not "%COMMAND%"=="candidate-events-summary" if /I not "%COMMAND%"=="doctor" (
  echo [ERROR] Comando no valido: %COMMAND%
  echo Use: discovery, extract, extract-candidates, candidate-events-summary o doctor.
  set "RC=4"
  goto :END
)

echo ============================================
echo   RiegoBot - DreamReader
echo ============================================
echo.
echo Comando: %COMMAND%
echo Carpeta del proyecto:
echo %BASE%
echo.

pushd "%BASE%" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se pudo acceder a la carpeta del proyecto.
  echo %BASE%
  set "RC=3"
  goto :END
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  echo Python detectado:
  python --version
  echo.
  echo Ejecutando %COMMAND%...
  echo.
  python -m dreamreader %COMMAND%
  set "RC=!ERRORLEVEL!"
  goto :AFTER_RUN
)

where py.exe >nul 2>nul
if not errorlevel 1 (
  echo Python Launcher detectado:
  py -3 --version
  echo.
  echo Ejecutando %COMMAND%...
  echo.
  py -3 -m dreamreader %COMMAND%
  set "RC=!ERRORLEVEL!"
  goto :AFTER_RUN
)

echo [ERROR] Python 3.11 o posterior no fue encontrado.
echo Instale Python y vuelva a ejecutar este archivo.
set "RC=2"
goto :END

:AFTER_RUN
echo.
if "%RC%"=="0" (
  echo [OK] DreamReader termino correctamente.
) else (
  echo [ERROR] DreamReader termino con codigo %RC%.
)

:END
echo.
echo ============================================
echo Codigo de salida: %RC%
echo ============================================
echo.
if exist "%BASE%logs" (
  echo Los logs se guardan dentro de:
  echo %BASE%logs
  echo.
)
if "%NO_PAUSE%"=="0" (
  echo Presione una tecla para cerrar esta ventana.
  pause >nul
)

popd >nul 2>nul
exit /b %RC%
