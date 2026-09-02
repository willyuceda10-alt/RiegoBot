param([string]$BaseDirectory = (Split-Path $PSScriptRoot -Parent), [ValidateSet('DISCOVERY','NORMALIZED')][string]$ExtractionMode = '', [switch]$AllowCandidateMappings)
. (Join-Path $BaseDirectory 'src\DreamReader.Core.ps1')
Invoke-DreamReader -BaseDirectory $BaseDirectory -ExtractionMode $ExtractionMode -AllowCandidateMappings:$AllowCandidateMappings
