param([string]$BaseDirectory = (Split-Path $PSScriptRoot -Parent))
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { throw 'Python was not found. Install Python 3.11 or later first.' }
& $python.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or later is required.' }
& $python.Source -m venv (Join-Path $BaseDirectory '.venv')
if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python virtual environment.' }
Write-Host 'Virtual environment created at .venv. Install dependencies from the project directory:'
Write-Host '.\.venv\Scripts\python.exe -m pip install -r requirements.txt'
