param([string]$PythonPath = 'python.exe', [switch]$Controls)
$ErrorActionPreference = 'Stop'
$base = Split-Path $PSScriptRoot -Parent
$python = (Get-Command $PythonPath -ErrorAction Stop).Source
& $python -c 'import tkinter, PIL' 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'Este Python no tiene Tkinter o Pillow. Instala requirements.txt en ese entorno o indica -PythonPath con el Python preparado.'
}
$windowless = Join-Path (Split-Path $python -Parent) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $windowless)) { $windowless = $python }
$arguments = '-m dreamreader.mascot'
if ($Controls) { $arguments += ' --controls' }
Start-Process -FilePath $windowless -ArgumentList $arguments -WorkingDirectory $base -WindowStyle Hidden
