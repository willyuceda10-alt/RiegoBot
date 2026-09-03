[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,

    [string]$ResourceGroupName = 'rg-riegobot-dev',
    [string]$Location = 'eastus2',
    [string]$Prefix = 'riegobotdev',
    [string]$PostgresAdminLogin = 'riegobotadmin',
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

if (-not $Apply) {
    Write-Host "Despliegue bloqueado por seguridad."
    Write-Host "Este script crea recursos Azure con costo."
    Write-Host "Vuelva a ejecutarlo con -Apply cuando aprobemos el despliegue."
    exit 10
}

if (-not (Get-Module -ListAvailable -Name Az.Accounts) -or
    -not (Get-Module -ListAvailable -Name Az.Resources)) {
    throw "Faltan modulos Az. Ejecute: Install-Module Az -Scope CurrentUser"
}

if (-not (Get-AzContext -ErrorAction SilentlyContinue)) {
    Connect-AzAccount | Out-Null
}

Set-AzContext -SubscriptionId $SubscriptionId | Out-Null

$resourceGroup = Get-AzResourceGroup -Name $ResourceGroupName -ErrorAction SilentlyContinue
if (-not $resourceGroup) {
    $resourceGroup = New-AzResourceGroup -Name $ResourceGroupName -Location $Location
}

$password = Read-Host "Password temporal de bootstrap para PostgreSQL" -AsSecureString
$template = Join-Path $PSScriptRoot '..\..\infra\azure\main.bicep'

$params = @{
    Name = "riegobot-foundation-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    ResourceGroupName = $ResourceGroupName
    TemplateFile = $template
    location = $Location
    prefix = $Prefix
    postgresAdminLogin = $PostgresAdminLogin
    postgresAdminPassword = $password
}

Write-Host ""
Write-Host "Desplegando fundacion Azure de RiegoBot..."
Write-Host "Resource Group: $ResourceGroupName"
Write-Host "Location:       $Location"
Write-Host ""

$result = New-AzResourceGroupDeployment @params

if ($result.ProvisioningState -ne 'Succeeded') {
    throw "El despliegue no termino correctamente: $($result.ProvisioningState)"
}

Write-Host ""
Write-Host "[OK] Fundacion Azure creada."
$result.Outputs | Format-List
Write-Host ""
Write-Host "IMPORTANTE:"
Write-Host "- La API central aun no se publica automaticamente."
Write-Host "- PostgreSQL no debe quedar expuesto ampliamente."
Write-Host "- El siguiente paso configura red, identidad administrada y secretos."
