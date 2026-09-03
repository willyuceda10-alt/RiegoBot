@echo off
setlocal EnableDelayedExpansion
title RiegoBot - Analisis de candidatos
set "RC=0"
set "FAILED_STAGE="

call :RUN_STAGE "Extraccion de candidatos" extract-candidates
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Cobertura Dream en bases compartidas" shared-dream-coverage
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Analisis historico Reports" reports-history-summary
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Cobertura de eventos ReportsRT" reportsrt-coverage
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Resumen de eventos operativos candidatos" candidate-events-summary
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Estado operativo candidato" candidate-operational-state
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Estado de riego candidato" irrigation-state-candidate
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Corroboracion de estado de riego" irrigation-confidence-candidate
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Fuentes candidatas mas frescas" freshness-sources
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Motor de incidencias candidato" incident-candidates
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Agrupacion de incidencias por episodio" incident-episodes
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Plan SLA y escalamiento candidato" incident-sla-plan
if not "!RC!"=="0" goto :END

call :RUN_STAGE "Enrutamiento de responsables candidato" incident-routing-candidate

:END
echo.
echo ============================================
if "!RC!"=="0" (
  echo   Analisis completado correctamente
) else (
  echo   Analisis detenido por error
  echo   Etapa: !FAILED_STAGE!
  echo   Codigo: !RC!
)
echo ============================================
echo.
echo Presione una tecla para cerrar esta ventana.
pause >nul
exit /b !RC!

:RUN_STAGE
set "STAGE=%~1"
set "COMMAND=%~2"
echo.
echo ============================================
echo   !STAGE!
echo ============================================
echo.
call "%~dp0EJECUTAR_DREAMREADER.cmd" !COMMAND! /nopause
set "RC=!ERRORLEVEL!"
if not "!RC!"=="0" set "FAILED_STAGE=!STAGE!"
exit /b 0
