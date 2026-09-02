@echo off
setlocal EnableDelayedExpansion
title RiegoBot - Refrescar y preguntar

set "BASE=%~dp0"
pushd "%BASE%" >nul 2>nul

call "%BASE%REFRESCAR_DATOS_RIEGOBOT.bat" /nopause
set "RC=!ERRORLEVEL!"
if not "!RC!"=="0" (
  echo.
  echo [ERROR] No se ejecutara la consulta porque el refresco fallo.
  pause
  exit /b !RC!
)

call "%BASE%RIEGOBOT_PREGUNTA.bat"
set "RC=!ERRORLEVEL!"

popd >nul 2>nul
exit /b !RC!
