$ErrorActionPreference = 'Stop'
$BaseDirectory = Split-Path -Parent $PSScriptRoot
Push-Location $BaseDirectory
try {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $python) { & $python.Source -m dreamreader realtime; exit $LASTEXITCODE }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -ne $py) { & $py.Source -3 -m dreamreader realtime; exit $LASTEXITCODE }
    $runtime = Join-Path $BaseDirectory 'runtime'
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    @{ running=$false; success=$false; error='Python 3.11 o posterior no fue encontrado.'; timestamp=(Get-Date).ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'collector_status.json') -Encoding utf8
    exit 3
} finally {
    Pop-Location
}
