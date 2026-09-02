@echo off
setlocal
title RiegoBot - DreamReader 1.3.3-alpha
set "BASE=%~dp0"
set "RC=0"

echo ============================================
echo   RiegoBot - DreamReader 1.3.3-alpha
echo ============================================
echo.
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
  echo Ejecutando discovery...
  echo.
  python -m dreamreader discovery
  set "RC=%ERRORLEVEL%"
  goto :AFTER_RUN
)

where py.exe >nul 2>nul
if not errorlevel 1 (
  echo Python Launcher detectado:
  py -3 --version
  echo.
  echo Ejecutando discovery...
  echo.
  py -3 -m dreamreader discovery
  set "RC=%ERRORLEVEL%"
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
echo Presione una tecla para cerrar esta ventana.
pause >nul

popd >nul 2>nul
exit /b %RC%
