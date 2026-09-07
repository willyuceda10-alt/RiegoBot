param([string]$PythonPath='python.exe',[string]$TaskName='RiegoBot Collector')
$base=Split-Path $PSScriptRoot -Parent
$exe=(Get-Command $PythonPath -ErrorAction Stop).Source
$action=New-ScheduledTaskAction -Execute $exe -Argument '-m dreamreader.collector' -WorkingDirectory $base
$trigger=New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Dream read-only collector. Starts on operator logon.' -Force
