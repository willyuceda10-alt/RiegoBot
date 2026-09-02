@echo off
setlocal
title RiegoBot - Configurar autoinicio

set "BASE=%~dp0"
set "PS1=%BASE%scripts\CONFIGURAR_AUTOINICIO_RIEGOBOT.ps1"

echo ============================================
echo   RiegoBot - Autoinicio Windows
echo ============================================
echo.
echo 1. Instalar autoinicio
echo 2. Ver estado
echo 3. Quitar autoinicio
echo 4. Salir
echo.
set /p OPCION=Seleccione una opcion: 

if "%OPCION%"=="1" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Action install -BaseDirectory "%BASE%"
if "%OPCION%"=="2" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Action status -BaseDirectory "%BASE%"
if "%OPCION%"=="3" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Action remove -BaseDirectory "%BASE%"
if "%OPCION%"=="4" exit /b 0

echo.
pause
