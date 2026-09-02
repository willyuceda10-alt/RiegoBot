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
    [pscustomobject]@{
        CollectorId = [string]$Config.collector.collectorId
        SiteId = [string]$Config.collector.siteId
        DreamKey = [string]$Dream.DreamKey
        DreamId = [string]$Dream.DreamId
        Timestamp = $timestamp
        SourceDatabase = [string]$Mapping.sourceDatabase
        SourceTable = [string]$Mapping.sourceTable
        MappingStatus = [string]$Mapping.status
        Confidence = [double]$Mapping.confidence
        ReportCode = $SourceRow.RepCode
        ReportText = [string]$SourceRow.RepCodeStr
        SourceStateRaw = $SourceRow.State
    }
}

function Invoke-NormalizedExtraction {
    param([string]$BaseDirectory, $Config, [object[]]$Dreams, [string]$SessionDirectory, [System.Collections.Generic.List[object]]$Metrics, [string]$LogPath, [bool]$AllowCandidateMappings)
    $normalizedDirectory = Join-Path $SessionDirectory 'normalized'
    New-Item -ItemType Directory -Path $normalizedDirectory -Force | Out-Null
    $mapping = Resolve-Mapping -MappingsDirectory (Join-Path $BaseDirectory 'mappings') -Entity 'DreamStatus' -AllowCandidateMappings $AllowCandidateMappings
    $databaseRoot = Resolve-ConfiguredPath $BaseDirectory ([string]$Config.discovery.rootPath)
    $databasePath = Join-Path $databaseRoot ([string]$mapping.sourceDatabase)
    if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) { Write-ReaderLog $LogPath 'WARN' 'Normalizer' 'UNRESOLVED' $mapping.sourceDatabase 'Mapped database does not exist.'; return @() }
    $rows = [System.Collections.Generic.List[object]]::new(); $opened = $null
    $openWatch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $opened = Open-DatabaseReadOnly -DatabasePath $databasePath -QueryTimeoutSeconds ([int]$Config.runtime.queryTimeoutSeconds)
        $openWatch.Stop(); Add-PerformanceRecord $Metrics $Config.collector.collectorId 'SHARED' $mapping.sourceDatabase 'DatabaseOpen' $opened.Provider $openWatch.ElapsedMilliseconds 0 $true ''
        foreach ($dream in @($Dreams | Where-Object { $_.FileExists -and $_.Status -in @('CONFIGURED','DISCOVERED') })) {
            if ([string]$dream.DreamId -notmatch '^[0-9]+$') { continue }
            $queryWatch = [System.Diagnostics.Stopwatch]::StartNew()
            $sql = "SELECT TOP 1 [Dream], [RepDate], [RepTime], [RepCode], [RepCodeStr], [State] FROM [ReportsRT] WHERE [Dream] = $($dream.DreamId) ORDER BY [RepDate] DESC, [RepTime] DESC"
            $sourceRows = @(Invoke-SafeRead -Connection $opened.Connection -Sql $sql -QueryTimeoutSeconds ([int]$Config.runtime.queryTimeoutSeconds) -MaxRowsPerQuery 1)
            $queryWatch.Stop(); Add-PerformanceRecord $Metrics $Config.collector.collectorId $dream.DreamKey $mapping.sourceDatabase 'Query' $opened.Provider $queryWatch.ElapsedMilliseconds $sourceRows.Count $true ''
            foreach ($sourceRow in $sourceRows) { $rows.Add((Convert-ToNormalizedEntity -SourceRow $sourceRow -Dream $dream -Config $Config -Mapping $mapping)); Write-ReaderLog $LogPath 'INFO' 'Normalizer' $dream.DreamKey $mapping.sourceDatabase 'Candidate DreamStatus observation written.' }
        }
    } catch {
        $message = $_.Exception.Message; Add-PerformanceRecord $Metrics $Config.collector.collectorId 'UNRESOLVED' $mapping.sourceDatabase 'Query' '' 0 0 $false $message; Write-ReaderLog $LogPath 'ERROR' 'Normalizer' 'UNRESOLVED' $mapping.sourceDatabase $message; throw
    } finally {
        if ($null -ne $opened) { $closeWatch = [System.Diagnostics.Stopwatch]::StartNew(); $opened.Connection.Close(); $opened.Connection.Dispose(); $closeWatch.Stop(); Add-PerformanceRecord $Metrics $Config.collector.collectorId 'SHARED' $mapping.sourceDatabase 'DatabaseClose' $opened.Provider $closeWatch.ElapsedMilliseconds 0 $true '' }
    }
    $rows | Export-Csv -LiteralPath (Join-Path $normalizedDirectory 'dream_status.csv') -NoTypeInformation -Encoding utf8
    $rows | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $normalizedDirectory 'dream_status.json') -Encoding utf8
    @($rows)
}

function Invoke-WaterMeterExtraction {
    param([string]$BaseDirectory, $Config, [object[]]$Dreams, [string]$SessionDirectory, [System.Collections.Generic.List[object]]$Metrics, [string]$LogPath, [bool]$AllowCandidateMappings)
    $mapping = Resolve-Mapping -MappingsDirectory (Join-Path $BaseDirectory 'mappings') -Entity 'WaterMeters' -AllowCandidateMappings $AllowCandidateMappings
    if ($null -eq $mapping) { return @() }
    $normalizedDirectory = Join-Path $SessionDirectory 'normalized'; New-Item -ItemType Directory -Path $normalizedDirectory -Force | Out-Null
    $databasePath = Join-Path (Resolve-ConfiguredPath $BaseDirectory ([string]$Config.discovery.rootPath)) ([string]$mapping.sourceDatabase)
    $opened = Open-DatabaseReadOnly -DatabasePath $databasePath -QueryTimeoutSeconds ([int]$Config.runtime.queryTimeoutSeconds)
    try {
        $sql = 'SELECT W.[Dream], W.[WM_Ind], W.[WM_GType], W.[WM_Number], W.[WM_Ratio], W.[WM_SName], L.[DateA], L.[TimeA], L.[ValueA] FROM [Water_Meters] AS W INNER JOIN [LastWM] AS L ON W.[Dream]=L.[Dream] AND W.[WM_GType]=L.[ObjSubType] AND W.[WM_Number]=L.[ObjNum]'
        $sourceRows = @(Invoke-SafeRead -Connection $opened.Connection -Sql $sql -QueryTimeoutSeconds ([int]$Config.runtime.queryTimeoutSeconds) -MaxRowsPerQuery ([int]$Config.runtime.maxRowsPerQuery))
        $rows = foreach ($source in $sourceRows) {
            $dream = $Dreams | Where-Object { $_.DreamId -eq [string]$source.Dream } | Select-Object -First 1
            if ($null -eq $dream) { continue }
            $timestamp = ([datetime]$source.DateA).Date.Add(([datetime]$source.TimeA).TimeOfDay).ToString('o')
            [pscustomobject]@{ CollectorId=$Config.collector.collectorId; SiteId=$Config.collector.siteId; DreamKey=$dream.DreamKey; DreamId=$dream.DreamId; Timestamp=$timestamp; MeterId=([string]$source.WM_GType + ':' + [string]$source.WM_Number); MeterName=(if ([string]::IsNullOrWhiteSpace([string]$source.WM_SName)) {$null} else {$source.WM_SName}); MeterIndex=$source.WM_Ind; MeterGroupRaw=$source.WM_GType; MeterNumberRaw=$source.WM_Number; MeterRatioRaw=$source.WM_Ratio; RawValue=$source.ValueA; Unit=$null; UnitStatus='UNRESOLVED'; SourceDatabase=$mapping.sourceDatabase; SourceTable='Water_Meters + LastWM'; MappingStatus=$mapping.status; Confidence=$mapping.confidence }
        }
        @($rows) | Export-Csv -LiteralPath (Join-Path $normalizedDirectory 'water_meters.csv') -NoTypeInformation -Encoding utf8
        @($rows) | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $normalizedDirectory 'water_meters.json') -Encoding utf8
        Add-PerformanceRecord $Metrics $Config.collector.collectorId 'SHARED' $mapping.sourceDatabase 'Query' $opened.Provider 0 @($rows).Count $true ''
        return @($rows)
    } finally { $opened.Connection.Close(); $opened.Connection.Dispose() }
}
