@echo off
setlocal
title RiegoBot - Actualizar y probar candidatos

call "%~dp0ACTUALIZAR_RIEGOBOT.bat"
if errorlevel 1 (
  echo.
  echo [ERROR] La actualizacion fallo. No se ejecutara la prueba.
  pause
  exit /b 1
)

call "%~dp0EJECUTAR_ANALISIS_CANDIDATOS.cmd"
exit /b %ERRORLEVEL%
