@echo off
setlocal EnableDelayedExpansion
title RiegoBot - Actualizar desde GitHub

set "BASE=%~dp0"
set "BRANCH=feature/v1.3.2-python-portable"
set "RC=0"
set "NO_PAUSE=0"
if /I "%~1"=="/nopause" set "NO_PAUSE=1"

echo ============================================
echo   RiegoBot - Actualizacion automatica
echo ============================================
echo.
echo Carpeta:
echo %BASE%
echo.

pushd "%BASE%" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se pudo abrir la carpeta de RiegoBot.
  set "RC=2"
  goto :END
)

where git.exe >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Git no esta instalado o no esta en PATH.
  set "RC=3"
  goto :END
)

if not exist ".git" (
  echo [ERROR] Esta carpeta no esta conectada al repositorio Git.
  set "RC=4"
  goto :END
)

if exist "docs\DREAM_SCHEMA_COMPARISON.md" (
  git restore -- "docs/DREAM_SCHEMA_COMPARISON.md" >nul 2>nul
)

echo Verificando cambios remotos...
git fetch origin
if errorlevel 1 (
  echo.
  echo [ERROR] No se pudo conectar con GitHub.
  set "RC=5"
  goto :END
)

echo.
echo Cambiando a la rama de desarrollo...
git switch "%BRANCH%"
if errorlevel 1 (
  echo.
  echo [ERROR] No se pudo cambiar a la rama %BRANCH%.
  set "RC=6"
  goto :END
)

echo.
echo Actualizando RiegoBot...
git pull --ff-only origin "%BRANCH%"
if errorlevel 1 (
  echo.
  echo [ERROR] No se pudo actualizar automaticamente.
  echo Puede haber cambios locales pendientes.
  set "RC=7"
  goto :END
)

echo.
echo ============================================
echo [OK] RiegoBot actualizado correctamente.
echo ============================================
echo.

if exist "VERSION.txt" (
  echo Version actual:
  type VERSION.txt
  echo.
)

git status --short
if errorlevel 1 (
  echo [AVISO] No se pudo leer el estado del repositorio.
)

:END
echo.
echo Codigo de salida: %RC%
echo.
if "%NO_PAUSE%"=="0" (
  echo Presione una tecla para cerrar.
  pause >nul
)
popd >nul 2>nul
exit /b %RC%
