@echo off
call "%~dp0EJECUTAR_DREAMREADER.cmd" extract-candidates /nopause
if errorlevel 1 exit /b %ERRORLEVEL%
echo.
echo ============================================
echo   Resumen de eventos operativos candidatos
echo ============================================
echo.
call "%~dp0EJECUTAR_DREAMREADER.cmd" candidate-events-summary /nopause
if errorlevel 1 exit /b %ERRORLEVEL%
echo.
echo ============================================
echo   Estado operativo candidato
echo ============================================
echo.
call "%~dp0EJECUTAR_DREAMREADER.cmd" candidate-operational-state
