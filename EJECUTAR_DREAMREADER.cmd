@echo off
setlocal
set "BASE=%~dp0"
where python.exe >nul 2>nul && (python -m dreamreader discovery & exit /b %errorlevel%)
where py.exe >nul 2>nul && (py -3 -m dreamreader discovery & exit /b %errorlevel%)
echo Python 3.11 or later was not found. Install Python, then run this file again.
exit /b 2
