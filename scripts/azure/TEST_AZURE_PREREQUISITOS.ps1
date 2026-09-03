[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$SubscriptionId
)

$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "============================================"
Write-Host "  RiegoBot - Azure Prerequisites"
Write-Host "============================================"
Write-Host ""

$requiredModules = @('Az.Accounts', 'Az.Resources')
$missing = @()

foreach ($module in $requiredModules) {
    if (-not (Get-Module -ListAvailable -Name $module)) {
        $missing += $module
        Write-Host "[FALTA] $module"
    }
    else {
        Write-Host "[OK]    $module"
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Instale los modulos faltantes:"
    Write-Host "Install-Module Az -Scope CurrentUser"
    exit 1
}

$context = Get-AzContext -ErrorAction SilentlyContinue
if (-not $context) {
    Write-Host ""
    Write-Host "[INFO] No hay sesion Azure activa. Ejecute Connect-AzAccount."
    exit 2
}

if ($SubscriptionId) {
    Set-AzContext -SubscriptionId $SubscriptionId | Out-Null
    $context = Get-AzContext
}

Write-Host ""
Write-Host "Tenant:       $($context.Tenant.Id)"
Write-Host "Subscription: $($context.Subscription.Name)"
Write-Host "ID:           $($context.Subscription.Id)"
Write-Host ""
Write-Host "[OK] El equipo esta listo para preparar el despliegue Azure."
Write-Host "No se creo ni modifico ningun recurso."
