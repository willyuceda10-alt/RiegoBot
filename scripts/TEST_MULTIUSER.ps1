param([string]$BaseDirectory = (Split-Path $PSScriptRoot -Parent))

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if ($null -eq $python) {
    Write-Host 'TEST_MULTIUSER: BLOCKED - Python not found'
    exit 2
}

$command = @'
from dreamreader.session import build_session_id
values = [build_session_id() for _ in range(1000)]
assert len(values) == len(set(values)), "SessionId collision detected"
print("COUNT=" + str(len(values)))
print("UNIQUE=" + str(len(set(values))))
'@

Push-Location $BaseDirectory
try {
    if ($python.Name -like 'py*') { $result = $command | & $python.Source -3 - }
    else { $result = $command | & $python.Source - }
    if ($LASTEXITCODE -ne 0) { throw 'Python multiuser test failed.' }
    $result | ForEach-Object { Write-Host $_ }
    Write-Host 'TEST_MULTIUSER: SAFE'
} finally {
    Pop-Location
}
