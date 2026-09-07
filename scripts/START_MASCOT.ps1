$ErrorActionPreference = 'Stop'
$base = Split-Path $PSScriptRoot -Parent
$python = (Get-Command pythonw.exe -ErrorAction Stop).Source
Start-Process -FilePath $python -ArgumentList '-m dreamreader.mascot' -WorkingDirectory $base -WindowStyle Hidden
