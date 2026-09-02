param([string]$BaseDirectory = (Split-Path $PSScriptRoot -Parent), [switch]$Quiet)
$extensions = @('.vbs','.ps1','.cs','.cmd','.json')
$excludedDirectories = @('docs','output','logs')
$blocked = '(?i)\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|EXECUTE|MERGE|ADOX)\b'
$allowedSafetyLines = '(?i)(blocked|prohibited|readonly|safequery|pattern|regex|documentation)'
$findings = [System.Collections.Generic.List[object]]::new()
Get-ChildItem -LiteralPath $BaseDirectory -Recurse -File | Where-Object { $extensions -contains $_.Extension -and $excludedDirectories -notcontains $_.Directory.Name } | ForEach-Object {
    $lineNumber = 0
    Get-Content -LiteralPath $_.FullName | ForEach-Object {
        $lineNumber++
        if ($_ -match $blocked -and $_ -notmatch $allowedSafetyLines) { $findings.Add([pscustomobject]@{ Status='BLOCKED_PATTERN'; File=$_.PSPath; Line=$lineNumber; Text=$_.Trim() }) }
    }
}
$status = if ($findings.Count -eq 0) {'SAFE'} else {'BLOCKED_PATTERN'}
$result = [pscustomobject]@{ Status=$status; CheckedAt=(Get-Date -Format 'o'); FilesInspected=(Get-ChildItem -LiteralPath $BaseDirectory -Recurse -File | Where-Object { $extensions -contains $_.Extension }).Count; Findings=@($findings) }
if (-not $Quiet) { $result | ConvertTo-Json -Depth 5; Write-Host "TEST_READONLY: $status" }
$result
