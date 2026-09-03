@echo off
call "%~dp0EJECUTAR_DREAMREADER.cmd" extract-candidates /nopause
if errorlevel 1 exit /b %ERRORLEVEL%
echo.
echo ============================================
echo   Cobertura Dream en bases compartidas
echo ============================================
echo.
call "%~dp0EJECUTAR_DREAMREADER.cmd" shared-dream-coverage /nopause
if errorlevel 1 exit /b %ERRORLEVEL%
echo.
echo ============================================
echo   Analisis historico Reports
echo ============================================
echo.
call "%~dp0EJECUTAR_DREAMREADER.cmd" reports-history-summary /nopause
if errorlevel 1 exit /b %ERRORLEVEL%
echo.
echo ============================================
echo   Cobertura de eventos ReportsRT
echo ============================================
echo.
call "%~dp0EJECUTAR_DREAMREADER.cmd" reportsrt-coverage /nopause
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
call "%~dp0EJECUTAR_DREAMREADER.cmd" candidate-operational-state /nopause
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo ============================================
echo   Estado de riego candidato
echo ============================================
echo.
call "%~dp0EJECUTAR_DREAMREADER.cmd" irrigation-state-candidate /nopause
if errorlevel 1 exit /b %ERRORLEVEL%
echo.
echo ============================================
echo   Corroboracion de estado de riego
echo ============================================
echo.
call "%~dp0EJECUTAR_DREAMREADER.cmd" irrigation-confidence-candidate /nopause

echo.
echo ============================================
echo   Analisis completado
echo ============================================
echo.
echo Presione una tecla para cerrar esta ventana.
pause >nul
