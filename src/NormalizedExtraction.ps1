Set-StrictMode -Version Latest

function Resolve-Mapping {
    param([string]$MappingsDirectory, [string]$Entity, [bool]$AllowCandidateMappings)
    $path = Join-Path $MappingsDirectory ($Entity.ToLowerInvariant() + '.json')
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $null }
    $mapping = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    if ($mapping.status -eq 'REJECTED') { return $null }
    if ($mapping.status -eq 'CANDIDATE' -and -not $AllowCandidateMappings) { return $null }
    $mapping
}

function Invoke-SafeRead {
    param([System.Data.OleDb.OleDbConnection]$Connection, [string]$Sql, [int]$QueryTimeoutSeconds, [int]$MaxRowsPerQuery)
    Invoke-SafeSelect -Connection $Connection -Sql $Sql -QueryTimeoutSeconds $QueryTimeoutSeconds -MaxRowsPerQuery $MaxRowsPerQuery
}

function Convert-ToNormalizedEntity {
    param($SourceRow, $Dream, $Config, $Mapping)
    $timestamp = $null
    if ($null -ne $SourceRow.RepDate -and $null -ne $SourceRow.RepTime) {
        $timestamp = ([datetime]$SourceRow.RepDate).Date.Add(([datetime]$SourceRow.RepTime).TimeOfDay).ToString('o')
    }
    [pscustomobject]@{ CollectorId=[string]$Config.collector.collectorId; SiteId=[string]$Config.collector.siteId; DreamKey=[string]$Dream.DreamKey; DreamId=[string]$Dream.DreamId; Timestamp=$timestamp; SourceDatabase=[string]$Mapping.sourceDatabase; SourceTable=[string]$Mapping.sourceTable; MappingStatus=[string]$Mapping.status; Confidence=[double]$Mapping.confidence; ReportCode=$SourceRow.RepCode; ReportText=[string]$SourceRow.RepCodeStr; SourceStateRaw=$SourceRow.State }
}

function Invoke-NormalizedExtraction {
    param([string]$BaseDirectory, $Config, [object[]]$Dreams, [string]$SessionDirectory, [System.Collections.Generic.List[object]]$Metrics, [string]$LogPath, [bool]$AllowCandidateMappings)
    $normalizedDirectory = Join-Path $SessionDirectory 'normalized'; New-Item -ItemType Directory -Path $normalizedDirectory -Force | Out-Null
    $mapping = Resolve-Mapping -MappingsDirectory (Join-Path $BaseDirectory 'mappings') -Entity 'DreamStatus' -AllowCandidateMappings $AllowCandidateMappings
    if ($null -eq $mapping) { return @() }
    $databaseRoot = Resolve-ConfiguredPath $BaseDirectory ([string]$Config.discovery.rootPath); $databasePath = Join-Path $databaseRoot ([string]$mapping.sourceDatabase)
    if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) { Write-ReaderLog $LogPath 'WARN' 'Normalizer' 'UNRESOLVED' $mapping.sourceDatabase 'Mapped database does not exist.'; return @() }
    $rows = [System.Collections.Generic.List[object]]::new(); $opened = $null
    try {
        $opened = Open-DatabaseReadOnly -DatabasePath $databasePath -QueryTimeoutSeconds ([int]$Config.runtime.queryTimeoutSeconds)
        foreach ($dream in @($Dreams | Where-Object { $_.FileExists -and $_.Status -in @('CONFIGURED','DISCOVERED') })) {
            if ([string]$dream.DreamId -notmatch '^[0-9]+$') { continue }
            $sql = "SELECT TOP 1 [Dream], [RepDate], [RepTime], [RepCode], [RepCodeStr], [State] FROM [ReportsRT] WHERE [Dream] = $($dream.DreamId) ORDER BY [RepDate] DESC, [RepTime] DESC"
            foreach ($sourceRow in @(Invoke-SafeRead -Connection $opened.Connection -Sql $sql -QueryTimeoutSeconds ([int]$Config.runtime.queryTimeoutSeconds) -MaxRowsPerQuery 1)) { $rows.Add((Convert-ToNormalizedEntity -SourceRow $sourceRow -Dream $dream -Config $Config -Mapping $mapping)) }
        }
    } finally { if ($null -ne $opened) { $opened.Connection.Close(); $opened.Connection.Dispose() } }
    $rows | Export-Csv -LiteralPath (Join-Path $normalizedDirectory 'dream_status.csv') -NoTypeInformation -Encoding utf8
    $rows | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $normalizedDirectory 'dream_status.json') -Encoding utf8
    @($rows)
}
