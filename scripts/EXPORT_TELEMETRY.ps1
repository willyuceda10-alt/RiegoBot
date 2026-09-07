param([Parameter(Mandatory=$true)][string]$DatabaseRoot,[string]$Since='2026-01-01')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'src/DreamReader.Core.ps1')
$cutoff=[datetime]::ParseExact($Since,'yyyy-MM-dd',[cultureinfo]::InvariantCulture)
$plans=@{
 'TGDReports.mdb'=,@('Reports','RepDate','RepTime');
 'TGDStatistics.mdb'=@(@('LastWM','DateA','TimeA'),@('DailyWM','DateA',''),@('RTWMFlow','DateA','TimeA'),@('LastAccum','Date','Time'),@('DailyAccum','Date',''),@('RTAccum','Date','Time'),@('LastFert','DateF','TimeF'),@('DailyFert','DateF',''),@('RTFert','DateF','TimeF'),@('RTFertFlow','DateF','TimeF'),@('Programs','',''),@('Water_Meters','',''))
}
foreach($dreamFile in Get-ChildItem -LiteralPath $DatabaseRoot -Filter 'Dream*_1.mdb'){$plans[$dreamFile.Name]=,@('TactName10','','')}
foreach($file in $plans.Keys){
 $path=Join-Path $DatabaseRoot $file
 if(-not(Test-Path -LiteralPath $path)){throw "Falta base requerida: $file"}
 # Catalog tables share one file timestamp; avoid a filesystem lookup per row.
 $fileTimestamp=(Get-Item -LiteralPath $path).LastWriteTime
 $opened=Open-DatabaseReadOnly $path 30
 try{
 foreach($plan in $plans[$file]){
 $table=$plan[0];$dateCol=$plan[1];$timeCol=$plan[2]
 $cmd=$opened.Connection.CreateCommand();$cmd.CommandTimeout=30
 $cmd.CommandText="SELECT * FROM [$table]"
 if($dateCol){$cmd.CommandText+=" WHERE [$dateCol] >= ?";[void]$cmd.Parameters.Add('since',[System.Data.OleDb.OleDbType]::Date);$cmd.Parameters[0].Value=$cutoff}
 $reader=$null
 try{
 $reader=$cmd.ExecuteReader()
 while($reader.Read()){
 $row=[ordered]@{}
 for($n=0;$n -lt $reader.FieldCount;$n++){
 $value=if($reader.IsDBNull($n)){$null}else{$reader.GetValue($n)}
 if($value -is [byte[]]){$value=[Convert]::ToBase64String($value)}
 elseif($value -is [datetime]){$value=$value.ToString('yyyy-MM-ddTHH:mm:ss')}
 $row[$reader.GetName($n)]=$value
 }
 $dream=if($file -match '^Dream([0-9]+)_1.mdb$'){$Matches[1]}elseif($row.Contains('Dream')){[string]$row['Dream']}else{[string]$row['Unit']}
 $timestamp=if($dateCol -and $row[$dateCol]){[datetime]$row[$dateCol]}else{$fileTimestamp}
 if($timeCol -and $row[$timeCol]){$timestamp=$timestamp.Date.Add(([datetime]$row[$timeCol]).TimeOfDay)}
 [pscustomobject]@{dream_id=$dream;entity=$table;source_at=$timestamp.ToString('yyyy-MM-ddTHH:mm:ss');data=$row}|ConvertTo-Json -Depth 5 -Compress
 }
 }finally{if($reader){$reader.Dispose()};$cmd.Dispose()}
 }
 }finally{$opened.Connection.Dispose()}
}
