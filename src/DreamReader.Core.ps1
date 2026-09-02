Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:KnownSharedDatabases = @('TGDStatistics.mdb', 'TGDReports.mdb', 'Prog.mdb', 'Cont.mdb', 'Sat.mdb', 'WM.mdb', 'ans.mdb')
$script:Providers = @('Microsoft.Jet.OLEDB.4.0', 'Microsoft.ACE.OLEDB.16.0', 'Microsoft.ACE.OLEDB.12.0')

function New-SessionDirectory {
    param([string]$OutputRoot, [string]$SiteId, [string]$CollectorId)
    $safeHost = ($env:COMPUTERNAME -replace '[^A-Za-z0-9_-]', '_'); if ([string]::IsNullOrWhiteSpace($safeHost)) { $safeHost = 'host' }
    $safeUser = ($env:USERNAME -replace '[^A-Za-z0-9_-]', '_'); if ([string]::IsNullOrWhiteSpace($safeUser)) { $safeUser = 'user' }
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $sessionId = $stamp + '_' + $safeHost + '_' + $safeUser + '_' + ([guid]::NewGuid().ToString('N').Substring(0, 6))
    $collectorRoot = Join-Path (Join-Path $OutputRoot $SiteId) $CollectorId
    $candidate = Join-Path $collectorRoot $sessionId
    New-Item -ItemType Directory -Path $candidate -Force | Out-Null
    $candidate
}

function Resolve-ConfiguredPath {
    param([string]$BaseDirectory, [string]$ConfiguredPath)
    if (-not [string]::IsNullOrWhiteSpace($env:RIEGOBOT_DREAM_ROOT)) {
        return [System.IO.Path]::GetFullPath($env:RIEGOBOT_DREAM_ROOT)
    }
    if ([System.IO.Path]::IsPathRooted($ConfiguredPath)) { return $ConfiguredPath }
    return [System.IO.Path]::GetFullPath((Join-Path $BaseDirectory $ConfiguredPath))
}

function Write-ReaderLog {
    param([string]$LogPath, [string]$Level, [string]$Component, [string]$DreamKey, [string]$Database, [string]$Message)
    $line = '{0} | {1} | {2} | {3} | {4} | {5}' -f (Get-Date -Format 'o'), $Level, $Component, $DreamKey, $Database, $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding utf8
}

function Add-PerformanceRecord {
    param([System.Collections.Generic.List[object]]$Records, [string]$CollectorId, [string]$DreamKey, [string]$Database, [string]$Operation, [string]$Provider, [long]$DurationMs, [long]$RowsRead, [bool]$Success, [string]$ErrorMessage)
    $Records.Add([pscustomobject]@{ Timestamp=(Get-Date -Format 'o'); CollectorId=$CollectorId; DreamKey=$DreamKey; Database=$Database; Operation=$Operation; Provider=$Provider; DurationMs=$DurationMs; RowsRead=$RowsRead; Success=$Success; Error=$ErrorMessage })
}

function Get-DreamKey { param([string]$SiteId, [string]$DreamId) "${SiteId}-DREAM-${DreamId}" }

function Get-ConfiguredDreamIndex {
    param($Config)
    $index = @{}
    foreach ($dream in @($Config.dreams)) {
        if ($null -ne $dream -and -not [string]::IsNullOrWhiteSpace([string]$dream.dreamId)) { $index[[string]$dream.dreamId] = $dream }
    }
    $index
}

function Find-DreamDatabases {
    param([string]$RootPath, [string]$Pattern, $Config, [string]$DetectedAt)
    $configured = Get-ConfiguredDreamIndex $Config
    $items = [System.Collections.Generic.List[object]]::new()
    if (-not (Test-Path -LiteralPath $RootPath -PathType Container)) { return $items }
    foreach ($file in Get-ChildItem -LiteralPath $RootPath -File -Filter $Pattern | Sort-Object Name) {
        $match = [regex]::Match($file.Name, '^Dream(?<id>[0-9]+)_[0-9]+\.mdb$', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if (-not $match.Success) { continue }
        $dreamId = $match.Groups['id'].Value
        $entry = $configured[$dreamId]
        $enabled = $true
        $name = "Dream $dreamId"
        $status = 'DISCOVERED'
        if ($null -ne $entry) {
            if ($null -ne $entry.enabled) { $enabled = [bool]$entry.enabled }
            if (-not [string]::IsNullOrWhiteSpace([string]$entry.name)) { $name = [string]$entry.name }
            if ($enabled) { $status = 'CONFIGURED' } else { $status = 'DISABLED' }
        }
        $items.Add([pscustomobject]@{ CollectorId=[string]$Config.collector.collectorId; SiteId=[string]$Config.collector.siteId; DreamKey=(Get-DreamKey $Config.collector.siteId $dreamId); DreamId=$dreamId; DreamName=$name; DatabasePath=$file.FullName; FileName=$file.Name; Status=$status; FileExists=$true; LastModified=$file.LastWriteTime.ToString('o'); DetectedAt=$DetectedAt })
    }
    foreach ($entry in @($Config.dreams)) {
        if ($null -eq $entry -or [string]::IsNullOrWhiteSpace([string]$entry.dreamId)) { continue }
        $expected = Join-Path $RootPath ('Dream' + [string]$entry.dreamId + '_1.mdb')
        if (-not (Test-Path -LiteralPath $expected)) {
            $enabled = if ($null -eq $entry.enabled) { $true } else { [bool]$entry.enabled }
            $missingName = if ($entry.name) { [string]$entry.name } else { "Dream $($entry.dreamId)" }
            $missingStatus = if ($enabled) { 'UNKNOWN' } else { 'DISABLED' }
            $items.Add([pscustomobject]@{ CollectorId=[string]$Config.collector.collectorId; SiteId=[string]$Config.collector.siteId; DreamKey=(Get-DreamKey $Config.collector.siteId ([string]$entry.dreamId)); DreamId=[string]$entry.dreamId; DreamName=$missingName; DatabasePath=$expected; FileName=(Split-Path $expected -Leaf); Status=$missingStatus; FileExists=$false; LastModified=''; DetectedAt=$DetectedAt })
        }
    }
    $items
}

function Find-SharedDatabases {
    param([string]$RootPath)
    foreach ($databaseName in $script:KnownSharedDatabases) {
        $path = Join-Path $RootPath $databaseName
        $exists = Test-Path -LiteralPath $path -PathType Leaf
        $status = if ($exists) { 'SHARED_CANDIDATE' } else { 'UNKNOWN' }
        $lastModified = if ($exists) { (Get-Item -LiteralPath $path).LastWriteTime.ToString('o') } else { '' }
        [pscustomobject]@{ DatabaseName=$databaseName; Path=$path; Status=$status; Tables=''; LastModified=$lastModified; Notes='Association with a Dream is not inferred.' }
    }
}

function Open-DatabaseReadOnly {
    param([string]$DatabasePath, [int]$QueryTimeoutSeconds)
    $errors = [System.Collections.Generic.List[string]]::new()
    foreach ($provider in $script:Providers) {
        $connection = $null
        try {
            $connection = [System.Data.OleDb.OleDbConnection]::new("Provider=$provider;Data Source=$DatabasePath;Mode=Read;Persist Security Info=False;")
            $connection.Open()
            return [pscustomobject]@{ Connection=$connection; Provider=$provider }
        } catch {
            $errors.Add("${provider}: $($_.Exception.Message)")
            if ($null -ne $connection) { $connection.Dispose() }
        }
    }
    throw ('Unable to open read-only database. ' + ($errors -join ' | '))
}

function Invoke-SafeSelect {
    param([System.Data.OleDb.OleDbConnection]$Connection, [string]$Sql, [int]$QueryTimeoutSeconds, [int]$MaxRowsPerQuery)
    if ([string]::IsNullOrWhiteSpace($Sql) -or $Sql -notmatch '^\s*SELECT\b') { throw 'SafeQueryExecutor blocked a non-SELECT statement.' }
    if ($Sql -match '\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|MERGE|ADOX)\b') { throw 'SafeQueryExecutor blocked a prohibited SQL token.' }
    $command = $null; $reader = $null
    try {
        $command = $Connection.CreateCommand(); $command.CommandText = $Sql; $command.CommandTimeout = $QueryTimeoutSeconds
        $reader = $command.ExecuteReader(); $rows = [System.Collections.Generic.List[object]]::new(); $count = 0
        while ($reader.Read() -and $count -lt $MaxRowsPerQuery) {
            $row = [ordered]@{}
            for ($i = 0; $i -lt $reader.FieldCount; $i++) { $row[$reader.GetName($i)] = if ($reader.IsDBNull($i)) { $null } else { $reader.GetValue($i) } }
            $rows.Add([pscustomobject]$row); $count++
        }
        return $rows
    } finally {
        if ($null -ne $reader) { $reader.Dispose() }
        if ($null -ne $command) { $command.Dispose() }
    }
}

function Read-DatabaseSchema {
    param([string]$DatabasePath, [string]$DreamKey, [string]$DatabaseName, [int]$QueryTimeoutSeconds, [System.Collections.Generic.List[object]]$TableRows, [System.Collections.Generic.List[object]]$ColumnRows)
    $opened = $null
    $openWatch = [System.Diagnostics.Stopwatch]::StartNew()
    $opened = Open-DatabaseReadOnly $DatabasePath $QueryTimeoutSeconds
    $openWatch.Stop()
    $schemaWatch = [System.Diagnostics.Stopwatch]::StartNew()
    $result = $null
    try {
        $schemaTables = $opened.Connection.GetSchema('Tables')
        $schemaColumns = $opened.Connection.GetSchema('Columns')
        foreach ($table in $schemaTables.Rows) {
            $name = [string]$table['TABLE_NAME']; $type = [string]$table['TABLE_TYPE']
            if ($type -ne 'TABLE' -or $name -match '^MSys') { continue }
            $escapedName = $name.Replace("'", "''")
            $columns = @($schemaColumns.Select("TABLE_NAME = '$escapedName'"))
            $TableRows.Add([pscustomobject]@{ DreamKey=$DreamKey; Database=$DatabaseName; TableName=$name; TableType=$type; ColumnCount=$columns.Count; ProviderUsed=$opened.Provider })
            foreach ($column in $columns) {
                $ColumnRows.Add([pscustomobject]@{ DreamKey=$DreamKey; Database=$DatabaseName; TableName=$name; ColumnName=[string]$column['COLUMN_NAME']; DataType=[string]$column['DATA_TYPE']; TypeName='Provider type name unavailable'; OrdinalPosition=[string]$column['ORDINAL_POSITION']; ProviderUsed=$opened.Provider })
            }
        }
        $schemaWatch.Stop()
        $result = [pscustomobject]@{ Provider=$opened.Provider; TableCount=(@($TableRows | Where-Object { $_.Database -eq $DatabaseName -and $_.DreamKey -eq $DreamKey })).Count; OpenDurationMs=$openWatch.ElapsedMilliseconds; SchemaDurationMs=$schemaWatch.ElapsedMilliseconds; CloseDurationMs=0 }
    } finally {
        if ($schemaWatch.IsRunning) { $schemaWatch.Stop() }
        $closeWatch = [System.Diagnostics.Stopwatch]::StartNew()
        if ($null -ne $opened -and $null -ne $opened.Connection) { $opened.Connection.Close(); $opened.Connection.Dispose() }
        $closeWatch.Stop()
        if ($null -ne $result) { $result.CloseDurationMs = $closeWatch.ElapsedMilliseconds }
    }
    return $result
}

function Get-SchemaComparison {
    param([object[]]$Columns)
    $output = [System.Collections.Generic.List[object]]::new()
    $dreamColumns = @($Columns | Where-Object { $_.DreamKey -ne 'SHARED' })
    $groups = $dreamColumns | Group-Object TableName, ColumnName
    $dreamKeys = @($dreamColumns | Select-Object -ExpandProperty DreamKey -Unique)
    foreach ($group in $groups) {
        $parts = $group.Name -split ', ', 2; $tableName = $parts[0]; $columnName = $parts[1]
        $types = @($group.Group | Select-Object -ExpandProperty DataType -Unique)
        foreach ($dreamKey in $dreamKeys) {
            $entry = $group.Group | Where-Object { $_.DreamKey -eq $dreamKey } | Select-Object -First 1
            $exists = $null -ne $entry
            $difference = if (-not $exists) {'MISSING'} elseif ($types.Count -gt 1) {'TYPE_DIFFERENCE'} elseif ($group.Group.Count -eq $dreamKeys.Count) {'COMMON'} else {'EXTRA'}
            $dataType = if ($entry) { $entry.DataType } else { '' }
            $output.Add([pscustomobject]@{ TableName=$tableName; ColumnName=$columnName; DataType=$dataType; DreamKey=$dreamKey; Exists=$exists; DifferenceType=$difference })
        }
    }
    $output
}

function Invoke-DreamReader {
    param([string]$BaseDirectory, [string]$ExtractionMode = '', [bool]$AllowCandidateMappings = $false)
    $configPath = Join-Path $BaseDirectory 'config\config.json'
    $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
    if (-not $config.readOnly) { throw 'Configuration rejected: readOnly must be true.' }
    if ($config.runtime.realtimeMode) { throw 'Configuration rejected: realtimeMode must be false in 1.3.0-alpha.' }
    if ([string]::IsNullOrWhiteSpace($ExtractionMode)) { $ExtractionMode = if ($config.extractionMode) { [string]$config.extractionMode } else { 'DISCOVERY' } }
    $ExtractionMode = $ExtractionMode.ToUpperInvariant()
    if ($ExtractionMode -notin @('DISCOVERY','NORMALIZED')) { throw 'Configuration rejected: extractionMode must be DISCOVERY or NORMALIZED.' }
    if (-not $AllowCandidateMappings -and $config.allowCandidateMappings) { $AllowCandidateMappings = $true }
    $outputRoot = Join-Path $BaseDirectory 'output'; $logRoot = Join-Path $BaseDirectory 'logs'
    New-Item -ItemType Directory -Path $outputRoot,$logRoot -Force | Out-Null
    $sessionDir = New-SessionDirectory $outputRoot $config.collector.siteId $config.collector.collectorId; $sessionId = Split-Path $sessionDir -Leaf
    $logDirectory = Join-Path (Join-Path $logRoot $config.collector.siteId) $config.collector.collectorId; New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $logPath = Join-Path $logDirectory ('DreamReader_' + $sessionId + '.log'); New-Item -ItemType File -Path $logPath -Force | Out-Null
    $started = Get-Date; $detectedAt = $started.ToString('o'); $metrics = [System.Collections.Generic.List[object]]::new(); $tables = [System.Collections.Generic.List[object]]::new(); $columns = [System.Collections.Generic.List[object]]::new(); $errors = [System.Collections.Generic.List[string]]::new(); $warnings = [System.Collections.Generic.List[string]]::new()
    $root = Resolve-ConfiguredPath $BaseDirectory ([string]$config.discovery.rootPath); $pattern = [string]$config.discovery.dreamPattern
    $watch = [System.Diagnostics.Stopwatch]::StartNew(); $dreams = @(Find-DreamDatabases $root $pattern $config $detectedAt); $shared = @(Find-SharedDatabases $root); $watch.Stop()
    Add-PerformanceRecord $metrics $config.collector.collectorId '' '' 'Discovery' '' $watch.ElapsedMilliseconds $dreams.Count $true ''
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { $warnings.Add("Discovery root does not exist: $root"); Write-ReaderLog $logPath 'WARN' 'Discovery' '' '' "Discovery root does not exist: $root" }
    foreach ($dream in $dreams) { Write-ReaderLog $logPath 'INFO' 'Discovery' $dream.DreamKey $dream.FileName "Dream status: $($dream.Status)" }
    $dreams | Export-Csv -LiteralPath (Join-Path $sessionDir 'dream_inventory.csv') -NoTypeInformation -Encoding utf8
    $dreams | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $sessionDir 'dream_inventory.json') -Encoding utf8
    foreach ($item in $shared) { if ($item.Status -eq 'SHARED_CANDIDATE') { Write-ReaderLog $logPath 'INFO' 'Discovery' 'SHARED' $item.DatabaseName 'Shared candidate detected.' } }
    foreach ($database in @($shared | Where-Object Status -eq 'SHARED_CANDIDATE')) {
        $watch.Restart(); try { $readResult = Read-DatabaseSchema $database.Path 'SHARED' $database.DatabaseName ([int]$config.runtime.queryTimeoutSeconds) $tables $columns; $database.Tables = $readResult.TableCount; Add-PerformanceRecord $metrics $config.collector.collectorId 'SHARED' $database.DatabaseName 'DatabaseOpen' $readResult.Provider $readResult.OpenDurationMs 0 $true ''; Add-PerformanceRecord $metrics $config.collector.collectorId 'SHARED' $database.DatabaseName 'SchemaRead' $readResult.Provider $readResult.SchemaDurationMs $database.Tables $true ''; Add-PerformanceRecord $metrics $config.collector.collectorId 'SHARED' $database.DatabaseName 'DatabaseClose' $readResult.Provider $readResult.CloseDurationMs 0 $true '' } catch { $message = $_.Exception.Message; $errors.Add("$($database.DatabaseName): $message"); Add-PerformanceRecord $metrics $config.collector.collectorId 'SHARED' $database.DatabaseName 'SchemaRead' '' $watch.ElapsedMilliseconds 0 $false $message; Write-ReaderLog $logPath 'ERROR' 'SchemaRead' 'SHARED' $database.DatabaseName $message } }
    foreach ($dream in @($dreams | Where-Object { $_.FileExists -and $_.Status -in @('CONFIGURED','DISCOVERED') })) {
        $watch.Restart(); try { $readResult = Read-DatabaseSchema $dream.DatabasePath $dream.DreamKey $dream.FileName ([int]$config.runtime.queryTimeoutSeconds) $tables $columns; Add-PerformanceRecord $metrics $config.collector.collectorId $dream.DreamKey $dream.FileName 'DatabaseOpen' $readResult.Provider $readResult.OpenDurationMs 0 $true ''; Add-PerformanceRecord $metrics $config.collector.collectorId $dream.DreamKey $dream.FileName 'SchemaRead' $readResult.Provider $readResult.SchemaDurationMs $readResult.TableCount $true ''; Add-PerformanceRecord $metrics $config.collector.collectorId $dream.DreamKey $dream.FileName 'DatabaseClose' $readResult.Provider $readResult.CloseDurationMs 0 $true '' } catch { $message = $_.Exception.Message; $errors.Add("$($dream.FileName): $message"); Add-PerformanceRecord $metrics $config.collector.collectorId $dream.DreamKey $dream.FileName 'SchemaRead' '' $watch.ElapsedMilliseconds 0 $false $message; Write-ReaderLog $logPath 'ERROR' 'SchemaRead' $dream.DreamKey $dream.FileName $message } }
    $shared | Export-Csv -LiteralPath (Join-Path $sessionDir 'shared_databases.csv') -NoTypeInformation -Encoding utf8
    $tables | Export-Csv -LiteralPath (Join-Path $sessionDir 'schema_tables.csv') -NoTypeInformation -Encoding utf8
    $columns | Export-Csv -LiteralPath (Join-Path $sessionDir 'schema_columns.csv') -NoTypeInformation -Encoding utf8
    $comparison = @(Get-SchemaComparison $columns); $comparison | Export-Csv -LiteralPath (Join-Path $sessionDir 'schema_comparison.csv') -NoTypeInformation -Encoding utf8
    $metrics | Export-Csv -LiteralPath (Join-Path $sessionDir 'performance.csv') -NoTypeInformation -Encoding utf8
    $normalizedRows = @(); $waterMeterRows = @(); $flowObservationRows = @(); $romeoSnapshotRows = @(); $accumulationRows = @(); $accumulationSummaryRows = @()
    if ($ExtractionMode -eq 'NORMALIZED') {
        . (Join-Path $BaseDirectory 'src\NormalizedExtraction.ps1')

        try {
            $normalizedRows = @(Invoke-NormalizedExtraction -BaseDirectory $BaseDirectory -Config $config -Dreams $dreams -SessionDirectory $sessionDir -Metrics $metrics -LogPath $logPath -AllowCandidateMappings $AllowCandidateMappings)
        } catch {
            $errors.Add("DreamStatus extraction: $($_.Exception.Message)")
        }

        try {
            $waterMeterRows = @(Invoke-WaterMeterExtraction -BaseDirectory $BaseDirectory -Config $config -Dreams $dreams -SessionDirectory $sessionDir -Metrics $metrics -LogPath $logPath -AllowCandidateMappings $AllowCandidateMappings)
        } catch {
            $errors.Add("WaterMeters extraction: $($_.Exception.Message)")
        }

        try {
            $flowObservationRows = @(Invoke-FlowObservationExtraction -BaseDirectory $BaseDirectory -Config $config -Dreams $dreams -SessionDirectory $sessionDir -Metrics $metrics -LogPath $logPath -AllowCandidateMappings $AllowCandidateMappings)
        } catch {
            $errors.Add("FlowObservations extraction: $($_.Exception.Message)")
        }

        try {
            $romeoSnapshotRows = @(Export-RomeoSnapshot -WaterMeters $waterMeterRows -FlowObservations $flowObservationRows -SessionDirectory $sessionDir)
        } catch {
            $errors.Add("RomeoSnapshot export: $($_.Exception.Message)")
        }

        try {
            $accumulationRows = @(Invoke-AccumulationObservationExtraction -BaseDirectory $BaseDirectory -Config $config -Dreams $dreams -SessionDirectory $sessionDir -Metrics $metrics -LogPath $logPath -AllowCandidateMappings $AllowCandidateMappings)
            if ($accumulationRows.Count -gt 0) {
                $accumulationSummaryRows = @(Export-AccumulationSummary -AccumulationObservations $accumulationRows -SessionDirectory $sessionDir)
            }
        } catch {
            $errors.Add("AccumulationObservations extraction: $($_.Exception.Message)")
        }
    }
    $metrics | Export-Csv -LiteralPath (Join-Path $sessionDir 'performance.csv') -NoTypeInformation -Encoding utf8
    $ended = Get-Date
    $session = [ordered]@{ SessionId=$sessionId; StartTime=$started.ToString('o'); EndTime=$ended.ToString('o'); CollectorId=[string]$config.collector.collectorId; SiteId=[string]$config.collector.siteId; DreamsDiscovered=@($dreams | Where-Object FileExists).Count; DatabasesRead=@($metrics | Where-Object { $_.Operation -eq 'SchemaRead' -and $_.Success }).Count; ExtractionMode=$ExtractionMode; NormalizedEntities=@{ DreamStatus=$normalizedRows.Count; WaterMeters=$waterMeterRows.Count; FlowObservations=$flowObservationRows.Count; RomeoSnapshot=$romeoSnapshotRows.Count; AccumulationObservations=$accumulationRows.Count; AccumulationSummary=$accumulationSummaryRows.Count }; Errors=@($errors); Warnings=@($warnings); Version=[string]$config.version }
    $session | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $sessionDir 'session.json') -Encoding utf8
    $comparisonSummary = "## Automated comparison results`n`nSession: $sessionId`n`nRows generated: $($comparison.Count). This section is produced from actual schema discovery; databases that could not be opened are represented by the session errors, not guessed.`n"
    Set-Content -LiteralPath (Join-Path $sessionDir 'schema_comparison_summary.md') -Value $comparisonSummary -Encoding utf8
    Write-ReaderLog $logPath 'INFO' 'Session' '' '' "Completed with $($errors.Count) error(s)."
    [pscustomobject]@{ SessionDirectory=$sessionDir; Session=$session; Errors=$errors; LogPath=$logPath }
}
