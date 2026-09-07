@echo off
setlocal
pushd "%~dp0"
python -m dreamreader discovery
set "RESULT=%errorlevel%"
popd
exit /b %RESULT%
