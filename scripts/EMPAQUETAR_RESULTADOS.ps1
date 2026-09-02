param([string]$BaseDirectory = (Split-Path $PSScriptRoot -Parent))
$outputRoot = Join-Path $BaseDirectory 'output'
$latest = Get-ChildItem -LiteralPath $outputRoot -Recurse -Filter 'session.json' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { $_.Directory }
if ($null -eq $latest) { throw 'No output session exists to package.' }
$zipPath = Join-Path $outputRoot ($latest.Name + '.zip')
Compress-Archive -LiteralPath $latest.FullName -DestinationPath $zipPath -Force
Write-Host "Package created: $zipPath"
$zipPath
