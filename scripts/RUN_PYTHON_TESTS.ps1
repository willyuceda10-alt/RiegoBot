param([string]$BaseDirectory = (Split-Path $PSScriptRoot -Parent))

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if ($null -eq $python) {
    Write-Host 'PYTHON_TESTS: BLOCKED - Python not found'
    exit 2
}

$launcherName = [IO.Path]::GetFileNameWithoutExtension($python.Source).ToLowerInvariant()
Push-Location $BaseDirectory
try {
    if ($launcherName -eq 'py') { & $python.Source -3 -m unittest discover -s tests -p 'test_*.py' -v }
    else { & $python.Source -m unittest discover -s tests -p 'test_*.py' -v }

    if ($LASTEXITCODE -ne 0) {
        Write-Host 'PYTHON_TESTS: FAILED'
        exit $LASTEXITCODE
    }
    Write-Host 'PYTHON_TESTS: SAFE'
} finally {
    Pop-Location
}
