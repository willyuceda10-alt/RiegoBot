param([string]$BaseDirectory = (Split-Path $PSScriptRoot -Parent))

$findings = [System.Collections.Generic.List[object]]::new()
$codeExtensions = @('.py','.ps1','.cmd','.json','.toml')
$excluded = @('.git','.venv','venv','output','logs','docs')

Get-ChildItem -LiteralPath $BaseDirectory -Recurse -File | Where-Object {
    $codeExtensions -contains $_.Extension -and
    -not ($_.FullName.Split([IO.Path]::DirectorySeparatorChar) | Where-Object { $excluded -contains $_ })
} | ForEach-Object {
    $lineNumber = 0
    Get-Content -LiteralPath $_.FullName | ForEach-Object {
        $lineNumber++
        if ($_ -match '(?i)C:\\Users\\|\\Downloads\\|\\Desktop\\|wuceda') {
            $findings.Add([pscustomobject]@{ Status='BLOCKED'; File=$_.PSPath; Line=$lineNumber; Reason='User-specific absolute path'; Text=$_.Trim() })
        }
        if ($_ -match '(?i)DreamId\s*(==|-eq)\s*["'']?(11|13|17)') {
            $findings.Add([pscustomobject]@{ Status='BLOCKED'; File=$_.PSPath; Line=$lineNumber; Reason='Dream-specific business logic'; Text=$_.Trim() })
        }
    }
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if ($null -eq $python) {
    $findings.Add([pscustomobject]@{ Status='WARNING'; File='PATH'; Line=0; Reason='Python not available'; Text='Python 3.11+ is required for the portable control plane.' })
} else {
    $launcherName = [IO.Path]::GetFileNameWithoutExtension($python.Source).ToLowerInvariant()
    $versionArgs = if ($launcherName -eq 'py') { @('-3','-c','import sys; print(sys.version_info.major, sys.version_info.minor)') } else { @('-c','import sys; print(sys.version_info.major, sys.version_info.minor)') }
    $version = & $python.Source @versionArgs
    if ($LASTEXITCODE -ne 0) { $findings.Add([pscustomobject]@{ Status='WARNING'; File='PATH'; Line=0; Reason='Python version check failed'; Text='' }) }
}

$blocked = @($findings | Where-Object Status -eq 'BLOCKED').Count
$status = if ($blocked -gt 0) { 'BLOCKED' } elseif ($findings.Count -gt 0) { 'WARNING' } else { 'SAFE' }
$report = [pscustomobject]@{ Status=$status; CheckedAt=(Get-Date -Format 'o'); Findings=@($findings) }
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $BaseDirectory 'portability_report.json') -Encoding utf8
$report.Findings | Format-Table -AutoSize | Out-Host
Write-Host "TEST_PORTABILITY: $status"
$report
