@echo off
setlocal
set "BASE=%~dp0"
pushd "%BASE%" >nul 2>nul
if errorlevel 1 (
  echo No se pudo acceder a la carpeta del proyecto:
  echo %BASE%
  exit /b 3
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python -m dreamreader discovery
  set "RC=%ERRORLEVEL%"
  popd
  exit /b %RC%
)

where py.exe >nul 2>nul
if not errorlevel 1 (
  py -3 -m dreamreader discovery
  set "RC=%ERRORLEVEL%"
  popd
  exit /b %RC%
)

echo Python 3.11 o posterior no fue encontrado.
echo Instale Python y vuelva a ejecutar este archivo.
popd
exit /b 2
