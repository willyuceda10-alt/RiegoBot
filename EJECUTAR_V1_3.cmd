@echo off
setlocal
set "BASE=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%BASE%scripts\INICIAR_V1_3.ps1" -BaseDirectory "%BASE%"
if errorlevel 1 exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%BASE%scripts\VALIDAR_V1_3.ps1" -BaseDirectory "%BASE%"
exit /b %errorlevel%
