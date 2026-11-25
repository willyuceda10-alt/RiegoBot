# Valvi local compatibility test. Only synthetic local fixtures; no live/remote sources or SQL.
param([string]$Fixture = '')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$allowed = @('Microsoft.Jet.OLEDB.4.0','Microsoft.ACE.OLEDB.16.0','Microsoft.ACE.OLEDB.12.0')
$result = [ordered]@{ status='PROVIDERS_CHECKED'; providers=@(); process_bits=([IntPtr]::Size * 8); fixture_checked=$false; table_count=$null; read_only=$true }
try {
    $enumerator = New-Object System.Data.OleDb.OleDbEnumerator
    $available = @($enumerator.GetElements().Rows | ForEach-Object { [string]$_['SOURCES_NAME'] })
    $result.providers = @($allowed | Where-Object { $_ -in $available })
} catch { $result.status = 'PROVIDER_CHECK_FAILED' }
if ($Fixture -and $result.status -eq 'PROVIDERS_CHECKED') {
    $result.status = 'INVALID_FIXTURE'
    $valid = $false
    try {
        # Explicit local fixed-drive copy only. Reject mapped drives and reparse points.
        if ($Fixture -notmatch '^[A-Za-z]:\\' -or [IO.Path]::GetExtension($Fixture) -ine '.mdb') { throw 'Invalid fixture' }
        $full = [IO.Path]::GetFullPath($Fixture)
        $drive = [System.IO.DriveInfo]::new([IO.Path]::GetPathRoot($full))
        if ($drive.DriveType -ne [IO.DriveType]::Fixed) { throw 'Non-local fixture' }
        $file = Get-Item -LiteralPath $full
        if ($file.PSIsContainer -or $file.Length -gt 52428800) { throw 'Invalid fixture' }
        $node = $file
        while ($null -ne $node) {
            if ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point' }
            if ($node -is [IO.FileInfo]) { $node = $node.Directory } else { $node = $node.Parent }
        }
        $valid = $true
    } catch { $valid = $false }
    if ($valid) {
        $result.fixture_checked = $true
        $result.status = 'FIXTURE_UNREADABLE'
        $scratch = $null
        try {
            $scratch = Join-Path ([IO.Path]::GetTempPath()) ('ValviFixture_' + [guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Path $scratch | Out-Null
            $copy = Join-Path $scratch 'fixture.mdb'
            Copy-Item -LiteralPath $full -Destination $copy
            foreach ($provider in $result.providers) {
                $connection = $null
                try {
                    $builder = New-Object System.Data.OleDb.OleDbConnectionStringBuilder
                    $builder.Provider = $provider
                    $builder['Data Source'] = $copy
                    $builder['Mode'] = 'Read'
                    $builder['Persist Security Info'] = $false
                    $connection = [System.Data.OleDb.OleDbConnection]::new($builder.ConnectionString)
                    $connection.Open()
                    $result.table_count = @($connection.GetSchema('Tables').Rows | Where-Object { $_['TABLE_TYPE'] -eq 'TABLE' }).Count
                    $result.status = 'FIXTURE_READ'
                    break
                } catch { $result.table_count = $null }
                finally { if ($null -ne $connection) { $connection.Dispose() } }
            }
        } catch { $result.status = 'FIXTURE_UNREADABLE'; $result.table_count = $null }
        finally { if ($scratch -and (Test-Path -LiteralPath $scratch)) { Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue } }
    }
}
$result | ConvertTo-Json -Depth 3 -Compress
