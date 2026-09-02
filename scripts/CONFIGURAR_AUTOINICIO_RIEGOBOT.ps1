param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('install','status','remove')]
    [string]$Action,
    [string]$BaseDirectory = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$TaskName = 'RiegoBot-Realtime-Collector'
$runner = Join-Path $BaseDirectory 'scripts\RIEGOBOT_REALTIME_TASK.ps1'

function Get-Task {
    Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
}

switch ($Action) {
    'install' {
        if (-not (Test-Path -LiteralPath $runner)) { throw "No se encontro el runner realtime: $runner" }
        $quotedRunner = '"' + $runner + '"'
        $taskAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File $quotedRunner"
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
        Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger $trigger -Settings $settings -Description 'RiegoBot realtime read-only collector' -Force | Out-Null
        Write-Host "[OK] Autoinicio instalado: $TaskName"
        Write-Host 'Se ejecutara automaticamente al iniciar sesion en Windows.'
    }
    'status' {
        $task = Get-Task
        if ($null -eq $task) { Write-Host "[NO INSTALADO] $TaskName"; exit 2 }
        Write-Host "[OK] Tarea encontrada: $TaskName"
        Write-Host "Estado: $($task.State)"
        Write-Host "Ruta RiegoBot: $BaseDirectory"
    }
    'remove' {
        $task = Get-Task
        if ($null -eq $task) { Write-Host '[OK] No habia autoinicio instalado.'; exit 0 }
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "[OK] Autoinicio eliminado: $TaskName"
    }
}
