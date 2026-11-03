@echo off
setlocal
title RiegoBot - Estado Collector

set "BASE=%~dp0"
if exist "%BASE%runtime\collector_status.json" (
  type "%BASE%runtime\collector_status.json"
) else (
  echo Todavia no existe estado del collector realtime.
)
echo.
pause
