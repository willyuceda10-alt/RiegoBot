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
    if ($null -eq $mapping) {
        Write-ReaderLog $LogPath 'INFO' 'Normalizer' 'SKIPPED' 'DreamStatus' 'Mapping CANDIDATE deshabilitado o no disponible.'
        return @()
    }
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
            $meterName = $null
            if (-not [string]::IsNullOrWhiteSpace([string]$source.WM_SName)) { $meterName = [string]$source.WM_SName }
            [pscustomobject]@{ CollectorId=$Config.collector.collectorId; SiteId=$Config.collector.siteId; DreamKey=$dream.DreamKey; DreamId=$dream.DreamId; Timestamp=$timestamp; MeterId=([string]$source.WM_GType + ':' + [string]$source.WM_Number); MeterName=$meterName; MeterIndex=$source.WM_Ind; MeterGroupRaw=$source.WM_GType; MeterNumberRaw=$source.WM_Number; MeterRatioRaw=$source.WM_Ratio; RawValue=$source.ValueA; Unit=$null; UnitStatus='UNRESOLVED'; SourceDatabase=$mapping.sourceDatabase; SourceTable='Water_Meters + LastWM'; MappingStatus=$mapping.status; Confidence=$mapping.confidence }
        }
        @($rows) | Export-Csv -LiteralPath (Join-Path $normalizedDirectory 'water_meters.csv') -NoTypeInformation -Encoding utf8
        @($rows) | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $normalizedDirectory 'water_meters.json') -Encoding utf8
        Add-PerformanceRecord $Metrics $Config.collector.collectorId 'SHARED' $mapping.sourceDatabase 'Query' $opened.Provider 0 @($rows).Count $true ''
        return @($rows)
    } finally { $opened.Connection.Close(); $opened.Connection.Dispose() }
}

function Invoke-FlowObservationExtraction {
    param([string]$BaseDirectory, $Config, [object[]]$Dreams, [string]$SessionDirectory, [System.Collections.Generic.List[object]]$Metrics, [string]$LogPath, [bool]$AllowCandidateMappings)
    $mapping = Resolve-Mapping -MappingsDirectory (Join-Path $BaseDirectory 'mappings') -Entity 'FlowObservations' -AllowCandidateMappings $AllowCandidateMappings
    if ($null -eq $mapping) { Write-ReaderLog $LogPath 'INFO' 'Normalizer' 'SKIPPED' 'FlowObservations' 'Mapping no disponible.'; return @() }
    $normalizedDirectory = Join-Path $SessionDirectory 'normalized'; New-Item -ItemType Directory -Path $normalizedDirectory -Force | Out-Null
    $databasePath = Join-Path (Resolve-ConfiguredPath $BaseDirectory ([string]$Config.discovery.rootPath)) ([string]$mapping.sourceDatabase)
    if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) { Write-ReaderLog $LogPath 'WARN' 'FlowObservations' 'UNRESOLVED' ([string]$mapping.sourceDatabase) 'Flow database does not exist.'; return @() }
    $opened = $null
    try {
        $opened = Open-DatabaseReadOnly -DatabasePath $databasePath -QueryTimeoutSeconds ([int]$Config.runtime.queryTimeoutSeconds)
        $definitions = @(Invoke-SafeRead -Connection $opened.Connection -Sql 'SELECT [Dream], [WM_Ind], [WM_GType], [WM_Number], [WM_SName] FROM [Water_Meters]' -QueryTimeoutSeconds ([int]$Config.runtime.queryTimeoutSeconds) -MaxRowsPerQuery ([int]$Config.runtime.maxRowsPerQuery))
        $rows = [System.Collections.Generic.List[object]]::new()
        foreach ($definition in $definitions) {
            if ([string]$definition.Dream -notmatch '^[0-9]+$') { continue }
            if ([string]$definition.WM_GType -notmatch '^[0-9]+$') { continue }
            if ([string]$definition.WM_Number -notmatch '^[0-9]+$') { continue }
            $dream = $Dreams | Where-Object { $_.DreamId -eq [string]$definition.Dream } | Select-Object -First 1
            if ($null -eq $dream) { continue }
            $sql = "SELECT TOP 1 [Dream], [ObjSubType], [ObjNum], [DateA], [TimeA], [ValueA] FROM [RTWMFlow] WHERE [Dream] = $($definition.Dream) AND [ObjSubType] = $($definition.WM_GType) AND [ObjNum] = $($definition.WM_Number) ORDER BY [DateA] DESC, [TimeA] DESC"
            $observations = @(Invoke-SafeRead -Connection $opened.Connection -Sql $sql -QueryTimeoutSeconds ([int]$Config.runtime.queryTimeoutSeconds) -MaxRowsPerQuery 1)
            foreach ($source in $observations) {
                $timestamp = $null
                if ($null -ne $source.DateA -and $null -ne $source.TimeA) { $timestamp = ([datetime]$source.DateA).Date.Add(([datetime]$source.TimeA).TimeOfDay).ToString('o') }
                $meterName = $null
                if (-not [string]::IsNullOrWhiteSpace([string]$definition.WM_SName)) { $meterName = [string]$definition.WM_SName }
                $rows.Add([pscustomobject]@{ CollectorId=[string]$Config.collector.collectorId; SiteId=[string]$Config.collector.siteId; DreamKey=[string]$dream.DreamKey; DreamId=[string]$dream.DreamId; Timestamp=$timestamp; MeterId=([string]$definition.WM_GType + ':' + [string]$definition.WM_Number); MeterName=$meterName; MeterIndex=$definition.WM_Ind; MeterGroupRaw=$definition.WM_GType; MeterNumberRaw=$definition.WM_Number; RawValue=$source.ValueA; Unit=$null; UnitStatus='UNRESOLVED'; SourceDatabase=[string]$mapping.sourceDatabase; SourceTable=[string]$mapping.sourceTable; MappingStatus=[string]$mapping.status; Confidence=[double]$mapping.confidence })
            }
        }
        @($rows) | Export-Csv -LiteralPath (Join-Path $normalizedDirectory 'flow_observations.csv') -NoTypeInformation -Encoding utf8
        @($rows) | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $normalizedDirectory 'flow_observations.json') -Encoding utf8
        Add-PerformanceRecord $Metrics $Config.collector.collectorId 'SHARED' $mapping.sourceDatabase 'FlowObservationQuery' $opened.Provider 0 @($rows).Count $true ''
        return @($rows)
    } catch {
        $message = $_.Exception.Message
        Add-PerformanceRecord $Metrics $Config.collector.collectorId 'SHARED' $mapping.sourceDatabase 'FlowObservationQuery' '' 0 0 $false $message
        Write-ReaderLog $LogPath 'ERROR' 'FlowObservations' 'SHARED' $mapping.sourceDatabase $message
        throw
    } finally {
        if ($null -ne $opened) { $opened.Connection.Close(); $opened.Connection.Dispose() }
    }
}

function Export-RomeoSnapshot {
    param(
        [object[]]$WaterMeters,
        [object[]]$FlowObservations,
        [string]$SessionDirectory
    )

    $normalizedDirectory = Join-Path $SessionDirectory 'normalized'
    New-Item -ItemType Directory -Path $normalizedDirectory -Force | Out-Null

    $flowIndex = @{}
    foreach ($flow in @($FlowObservations)) {
        $key = ([string]$flow.DreamKey + '|' + [string]$flow.MeterId)
        $flowIndex[$key] = $flow
    }

    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($meter in @($WaterMeters)) {
        $key = ([string]$meter.DreamKey + '|' + [string]$meter.MeterId)
        $flow = $flowIndex[$key]

        $rows.Add([pscustomobject]@{
            RomeoKey            = [string]$meter.DreamKey
            RomeoId             = [string]$meter.DreamId
            MeterId             = [string]$meter.MeterId
            MeterName           = $meter.MeterName
            MeterTimestamp      = $meter.Timestamp
            MeterRawValue       = $meter.RawValue
            FlowTimestamp       = if ($null -ne $flow) { $flow.Timestamp } else { $null }
            FlowRawValue        = if ($null -ne $flow) { $flow.RawValue } else { $null }
            FlowUnit            = $null
            FlowUnitStatus      = 'UNRESOLVED'
            MeterMappingStatus  = $meter.MappingStatus
            FlowMappingStatus   = if ($null -ne $flow) { $flow.MappingStatus } else { $null }
        })
    }

    @($rows) | Export-Csv -LiteralPath (Join-Path $normalizedDirectory 'romeo_snapshot.csv') -NoTypeInformation -Encoding utf8
    @($rows) | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $normalizedDirectory 'romeo_snapshot.json') -Encoding utf8

    return @($rows)
}

function Invoke-AccumulationObservationExtraction {
    param(
        [string]$BaseDirectory,
        $Config,
        [object[]]$Dreams,
        [string]$SessionDirectory,
        [System.Collections.Generic.List[object]]$Metrics,
        [string]$LogPath,
        [bool]$AllowCandidateMappings
    )

    $mapping = Resolve-Mapping -MappingsDirectory (Join-Path $BaseDirectory 'mappings') -Entity 'AccumulationObservations' -AllowCandidateMappings $AllowCandidateMappings
    if ($null -eq $mapping) {
        Write-ReaderLog $LogPath 'INFO' 'Normalizer' 'SKIPPED' 'AccumulationObservations' 'Mapping CANDIDATE deshabilitado o no disponible.'
        return @()
    }

    $normalizedDirectory = Join-Path $SessionDirectory 'normalized'
    New-Item -ItemType Directory -Path $normalizedDirectory -Force | Out-Null

    $databaseRoot = Resolve-ConfiguredPath $BaseDirectory ([string]$Config.discovery.rootPath)
    $databasePath = Join-Path $databaseRoot ([string]$mapping.sourceDatabase)

    if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) {
        Write-ReaderLog $LogPath 'WARN' 'AccumulationObservations' 'UNRESOLVED' ([string]$mapping.sourceDatabase) 'Accumulation database does not exist.'
        return @()
    }

    $opened = $null
    try {
        $opened = Open-DatabaseReadOnly -DatabasePath $databasePath -QueryTimeoutSeconds ([int]$Config.runtime.queryTimeoutSeconds)
        $rows = [System.Collections.Generic.List[object]]::new()

        foreach ($dream in @($Dreams | Where-Object { $_.FileExists -and $_.Status -in @('CONFIGURED','DISCOVERED') })) {
            if ([string]$dream.DreamId -notmatch '^[0-9]+$') {
                continue
            }

            $sql = "SELECT [Dream], [Line], [Tact_Number], [Tact_Index], [Date], [Time], [WAccum_Vol], [WAccum_Time] FROM [LastAccum] WHERE [Dream] = $($dream.DreamId)"
            $sourceRows = @(
                Invoke-SafeRead -Connection $opened.Connection -Sql $sql -QueryTimeoutSeconds ([int]$Config.runtime.queryTimeoutSeconds) -MaxRowsPerQuery 500
            )

            foreach ($source in $sourceRows) {
                $timestamp = $null
                if ($null -ne $source.Date -and $null -ne $source.Time) {
                    $timestamp = ([datetime]$source.Date).Date.Add(([datetime]$source.Time).TimeOfDay).ToString('o')
                }

                $rows.Add([pscustomobject]@{
                    CollectorId     = [string]$Config.collector.collectorId
                    SiteId          = [string]$Config.collector.siteId
                    DreamKey        = [string]$dream.DreamKey
                    DreamId         = [string]$dream.DreamId
                    Timestamp       = $timestamp
                    LineRaw         = $source.Line
                    TactNumberRaw   = $source.Tact_Number
                    TactIndexRaw    = $source.Tact_Index
                    RawVolume       = $source.WAccum_Vol
                    RawTime         = $source.WAccum_Time
                    VolumeUnit      = $null
                    TimeUnit        = $null
                    UnitStatus      = 'UNRESOLVED'
                    SourceDatabase  = [string]$mapping.sourceDatabase
                    SourceTable     = [string]$mapping.sourceTable
                    MappingStatus   = [string]$mapping.status
                    Confidence      = [double]$mapping.confidence
                })
            }
        }

        @($rows) | Export-Csv -LiteralPath (Join-Path $normalizedDirectory 'accumulation_observations.csv') -NoTypeInformation -Encoding utf8
        @($rows) | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $normalizedDirectory 'accumulation_observations.json') -Encoding utf8

        Add-PerformanceRecord $Metrics $Config.collector.collectorId 'SHARED' $mapping.sourceDatabase 'AccumulationObservationQuery' $opened.Provider 0 @($rows).Count $true ''
        return @($rows)
    }
    catch {
        $message = $_.Exception.Message
        Add-PerformanceRecord $Metrics $Config.collector.collectorId 'SHARED' $mapping.sourceDatabase 'AccumulationObservationQuery' '' 0 0 $false $message
        Write-ReaderLog $LogPath 'ERROR' 'AccumulationObservations' 'SHARED' $mapping.sourceDatabase $message
        throw
    }
    finally {
        if ($null -ne $opened) {
            $opened.Connection.Close()
            $opened.Connection.Dispose()
        }
    }
}

function Export-AccumulationSummary {
    param(
        [object[]]$AccumulationObservations,
        [string]$SessionDirectory
    )

    $normalizedDirectory = Join-Path $SessionDirectory 'normalized'
    New-Item -ItemType Directory -Path $normalizedDirectory -Force | Out-Null

    $rows = [System.Collections.Generic.List[object]]::new()

    foreach ($group in @($AccumulationObservations | Group-Object DreamKey)) {
        $items = @($group.Group)
        if ($items.Count -eq 0) {
            continue
        }

        $timestamps = @(
            $items |
                Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.Timestamp) } |
                ForEach-Object { [datetime]$_.Timestamp }
        )
        $volumes = @(
            $items |
                Where-Object { $null -ne $_.RawVolume } |
                ForEach-Object { [double]$_.RawVolume }
        )
        $times = @(
            $items |
                Where-Object { $null -ne $_.RawTime } |
                ForEach-Object { [double]$_.RawTime }
        )

        $latestTimestamp = $null
        if ($timestamps.Count -gt 0) {
            $latestTimestamp = ($timestamps | Measure-Object -Maximum).Maximum.ToString('o')
        }

        $rawVolumeMin = $null
        $rawVolumeMax = $null
        if ($volumes.Count -gt 0) {
            $rawVolumeMin = ($volumes | Measure-Object -Minimum).Minimum
            $rawVolumeMax = ($volumes | Measure-Object -Maximum).Maximum
        }

        $rawTimeMin = $null
        $rawTimeMax = $null
        if ($times.Count -gt 0) {
            $rawTimeMin = ($times | Measure-Object -Minimum).Minimum
            $rawTimeMax = ($times | Measure-Object -Maximum).Maximum
        }

        $rows.Add([pscustomobject]@{
            RomeoKey         = [string]$group.Name
            RomeoId          = [string]$items[0].DreamId
            ObservationCount = $items.Count
            LatestTimestamp  = $latestTimestamp
            RawVolumeMin     = $rawVolumeMin
            RawVolumeMax     = $rawVolumeMax
            RawTimeMin       = $rawTimeMin
            RawTimeMax       = $rawTimeMax
            VolumeUnit       = $null
            TimeUnit         = $null
            UnitStatus       = 'UNRESOLVED'
            MappingStatus    = 'CANDIDATE'
        })
    }

    @($rows) | Export-Csv -LiteralPath (Join-Path $normalizedDirectory 'accumulation_summary.csv') -NoTypeInformation -Encoding utf8
    @($rows) | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $normalizedDirectory 'accumulation_summary.json') -Encoding utf8

    return @($rows)
}
