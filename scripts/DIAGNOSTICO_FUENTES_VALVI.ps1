<#
.SYNOPSIS
    Valvi: read-only compatibility check for explicitly authorized DREAM folders.
.DESCRIPTION
    Checks only the exact folder paths supplied by the operator. No network discovery,
    recursive search, database reads, writes to source folders, credentials or uploads.
    Detailed paths stay in the current user's LocalAppData. The Git-ready report
    contains aggregate compatibility counts only. Review before publishing.
.PARAMETER SourcesFile
    Optional local text file with one authorized UNC folder per line.
    Keep this file outside the repository.
#>
[CmdletBinding()]
param(
    [string]$SourcesFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $env:LOCALAPPDATA) {
    throw 'LOCALAPPDATA is unavailable.'
}

$privateDir = Join-Path $env:LOCALAPPDATA 'Valvi\diagnostics'
$publicDir = Join-Path $repoRoot 'diagnostics'
New-Item -ItemType Directory -Path $privateDir -Force | Out-Null
New-Item -ItemType Directory -Path $publicDir -Force | Out-Null

$paths = @()
if ($SourcesFile) {
    $paths = @(Get-Content -LiteralPath $SourcesFile -ErrorAction Stop |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and -not $_.StartsWith('#') })
} else {
    Write-Host 'Enter the exact authorized folder containing DREAM MDB files.'
    Write-Host 'Use a UNC share folder (\\server\share\folder), not a bare server IP.'
    Write-Host 'Press Enter on an empty line when finished.'
    while ($true) {
        $entry = Read-Host 'Authorized folder'
        if ([string]::IsNullOrWhiteSpace($entry)) { break }
        $paths += $entry.Trim()
    }
}
$paths = @($paths | Select-Object -Unique)
if ($paths.Count -eq 0) { throw 'No folders supplied.' }

# Require an explicit share path; do not try to discover shares or subfolders.
foreach ($path in $paths) {
    if ($path -notmatch '^\\\\[^\\]+\\[^\\]+' -or $path -match '[*?]') {
        throw 'Every source must be an exact UNC share folder, without wildcards.'
    }
}

$known = [ordered]@{
    dream_files = '^Dream[0-9]+_1\.mdb$'
    statistics = '^TGDStatistics\.mdb$'
    reports = '^TGDReports\.mdb$'
}
$records = @()
foreach ($path in $paths) {
    $record = [ordered]@{
        folder = $path
        status = 'UNAVAILABLE'
        dream_files = $false
        statistics = $false
        reports = $false
        mdb_present = $false
    }
    try {
        # Only direct directory metadata. Never open the MDB contents.
        $files = @(Get-ChildItem -LiteralPath $path -File -Filter '*.mdb' -ErrorAction Stop)
        $record.status = 'ACCESSIBLE'
        $record.mdb_present = ($files.Count -gt 0)
        foreach ($key in $known.Keys) {
            $record[$key] = (@($files | Where-Object { $_.Name -match $known[$key] }).Count -gt 0)
        }
    } catch {
        # Do not include exception text, paths, hostnames or credentials in the public report.
        $record.status = 'UNAVAILABLE'
    }
    $records += [pscustomobject]$record
}

$accessible = @($records | Where-Object { $_.status -eq 'ACCESSIBLE' })
$summary = [ordered]@{
    report_version = 1
    check = 'explicit_folder_metadata_only'
    folders_supplied = $records.Count
    folders_accessible = $accessible.Count
    folders_unavailable = $records.Count - $accessible.Count
    accessible_with_mdb = @($accessible | Where-Object { $_.mdb_present }).Count
    accessible_with_dream_files = @($accessible | Where-Object { $_.dream_files }).Count
    accessible_with_statistics = @($accessible | Where-Object { $_.statistics }).Count
    accessible_with_reports = @($accessible | Where-Object { $_.reports }).Count
    database_contents_read = $false
    database_connectivity_tested = $false
    source_writes = $false
    automatic_upload = $false
}

$privatePath = Join-Path $privateDir 'remote_sources_private.json'
$publicPath = Join-Path $publicDir 'remote_sources_summary.json'
ConvertTo-Json -InputObject @($records) -Depth 4 | Set-Content -LiteralPath $privatePath -Encoding UTF8
ConvertTo-Json -InputObject $summary -Depth 4 | Set-Content -LiteralPath $publicPath -Encoding UTF8

Write-Host ''
Write-Host 'Private report (do not publish):' $privatePath
Write-Host 'Aggregate report (review before sharing):' $publicPath
$summary | ConvertTo-Json -Depth 4

