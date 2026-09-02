param([string]$BaseDirectory = (Split-Path $PSScriptRoot -Parent))

$required = @(
  'config','src','scripts','mappings','docs','output','logs','tests',
  'README.md','CHANGELOG.md','VERSION.txt','EJECUTAR_V1_3.cmd','EJECUTAR_DREAMREADER.cmd',
  'src\DreamReader.Core.ps1','src\NormalizedExtraction.ps1',
  'mappings\dreamstatus.json','mappings\watermeters.json',
  'scripts\INICIAR_V1_3.ps1','scripts\TEST_READONLY.ps1',
  'scripts\TEST_PORTABILITY.ps1','scripts\TEST_MULTIUSER.ps1',
  'scripts\EMPAQUETAR_RESULTADOS.ps1',
  'dreamreader\__main__.py','dreamreader\session.py','dreamreader\runtime.py'
)

$checks = [System.Collections.Generic.List[object]]::new()

foreach ($item in $required) {
  $checks.Add([pscustomobject]@{
    Check = "Exists: $item"
    Passed = (Test-Path -LiteralPath (Join-Path $BaseDirectory $item))
    Details = ''
  })
}

try {
  $config = Get-Content -Raw -LiteralPath (Join-Path $BaseDirectory 'config\config.json') | ConvertFrom-Json
  $checks.Add([pscustomobject]@{ Check='config.json valid'; Passed=$true; Details="CollectorId=$($config.collector.collectorId)" })
  $checks.Add([pscustomobject]@{ Check='readOnly and realtime settings'; Passed=([bool]$config.readOnly -and -not [bool]$config.runtime.realtimeMode); Details='readOnly=true; realtimeMode=false required.' })
  $checks.Add([pscustomobject]@{ Check='extraction mode valid'; Passed=([string]$config.extractionMode -in @('DISCOVERY','NORMALIZED')); Details=[string]$config.extractionMode })
} catch {
  $checks.Add([pscustomobject]@{ Check='config.json valid'; Passed=$false; Details=$_.Exception.Message })
}

$corePath = Join-Path $BaseDirectory 'src\DreamReader.Core.ps1'
$core = Get-Content -Raw -LiteralPath $corePath
$checks.Add([pscustomobject]@{
  Check='No instance-specific business logic'
  Passed=($core -notmatch 'DreamId\s*-eq\s*(11|13|17)')
  Details='Examples in config are permitted.'
})

$readonly = & (Join-Path $BaseDirectory 'scripts\TEST_READONLY.ps1') -BaseDirectory $BaseDirectory -Quiet
$checks.Add([pscustomobject]@{ Check='TEST_READONLY'; Passed=($readonly.Status -eq 'SAFE'); Details=$readonly.Status })

$portability = & (Join-Path $BaseDirectory 'scripts\TEST_PORTABILITY.ps1') -BaseDirectory $BaseDirectory
$checks.Add([pscustomobject]@{ Check='TEST_PORTABILITY'; Passed=($portability.Status -ne 'BLOCKED'); Details=$portability.Status })

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { $python = Get-Command py -ErrorAction SilentlyContinue }

if ($null -ne $python) {
  try {
    & (Join-Path $BaseDirectory 'scripts\TEST_MULTIUSER.ps1') -BaseDirectory $BaseDirectory | Out-Host
    $checks.Add([pscustomobject]@{ Check='TEST_MULTIUSER'; Passed=($LASTEXITCODE -eq 0); Details="ExitCode=$LASTEXITCODE" })
  } catch {
    $checks.Add([pscustomobject]@{ Check='TEST_MULTIUSER'; Passed=$false; Details=$_.Exception.Message })
  }
} else {
  $checks.Add([pscustomobject]@{ Check='TEST_MULTIUSER'; Passed=$false; Details='Python 3.11+ not found.' })
}

$latest = Get-ChildItem -LiteralPath (Join-Path $BaseDirectory 'output') -Recurse -Filter 'session.json' -File -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 |
  ForEach-Object { $_.Directory }

if ($null -ne $latest) {
  foreach ($file in @('session.json','dream_inventory.json','dream_inventory.csv','shared_databases.csv','schema_tables.csv','schema_columns.csv','schema_comparison.csv','performance.csv')) {
    $path = Join-Path $latest.FullName $file
    $checks.Add([pscustomobject]@{ Check="Session artifact: $file"; Passed=(Test-Path -LiteralPath $path); Details=$latest.Name })
  }

  try {
    $inventory = Get-Content -Raw -LiteralPath (Join-Path $latest.FullName 'dream_inventory.json') | ConvertFrom-Json
    $session = Get-Content -Raw -LiteralPath (Join-Path $latest.FullName 'session.json') | ConvertFrom-Json

    $checks.Add([pscustomobject]@{
      Check='DreamKey and CollectorId present'
      Passed=(@($inventory | Where-Object { $_.DreamKey -and $_.CollectorId }).Count -eq @($inventory).Count)
      Details="Rows=$(@($inventory).Count)"
    })

    $checks.Add([pscustomobject]@{
      Check='Session completed without database errors'
      Passed=(@($session.Errors).Count -eq 0)
      Details="Errors=$(@($session.Errors).Count)"
    })

    if ($session.ExtractionMode -eq 'NORMALIZED') {
      $normalizedCsv = Join-Path $latest.FullName 'normalized\dream_status.csv'
      $normalizedJson = Join-Path $latest.FullName 'normalized\dream_status.json'
      $checks.Add([pscustomobject]@{
        Check='Normalized DreamStatus artifacts'
        Passed=((Test-Path -LiteralPath $normalizedCsv) -and (Test-Path -LiteralPath $normalizedJson))
        Details=$latest.Name
      })
    }
  } catch {
    $checks.Add([pscustomobject]@{ Check='Session JSON is readable'; Passed=$false; Details=$_.Exception.Message })
  }
} else {
  $checks.Add([pscustomobject]@{ Check='PowerShell session output available'; Passed=$true; Details='No historical runtime output is stored in Git; execute locally to validate MDB artifacts.' })
}

$report = [pscustomobject]@{
  ValidatedAt=(Get-Date -Format 'o')
  Version=(Get-Content -Raw -LiteralPath (Join-Path $BaseDirectory 'VERSION.txt')).Trim()
  Passed=(@($checks | Where-Object { -not $_.Passed }).Count -eq 0)
  Checks=@($checks)
}

$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $BaseDirectory 'validation_report.json') -Encoding utf8
$report.Checks | Format-Table -AutoSize | Out-Host
Write-Host "VALIDAR_V1_3: $(if ($report.Passed) {'SAFE'} else {'WARNING'})"
$report
