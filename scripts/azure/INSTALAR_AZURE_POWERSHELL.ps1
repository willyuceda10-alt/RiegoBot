[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "============================================"
Write-Host "  RiegoBot - Instalar Azure PowerShell"
Write-Host "============================================"
Write-Host ""

Write-Host "PowerShell:"
Write-Host $($PSVersionTable.PSVersion.ToString())
Write-Host ""

if ($PSVersionTable.PSVersion.Major -lt 5) {
    Write-Host "[ERROR] Se requiere Windows PowerShell 5.1 o PowerShell 7+."
    exit 2
}

if (Get-Module -Name AzureRM -ListAvailable) {
    Write-Host "[BLOQUEADO] Se detecto AzureRM."
    Write-Host "Microsoft no recomienda coexistencia AzureRM + Az en Windows PowerShell 5.1."
    Write-Host "No se realizo ninguna instalacion."
    exit 3
}

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
}
catch {
    Write-Host "[INFO] No fue necesario ajustar TLS para esta sesion."
}

Write-Host "Comprobando PSGallery..."
$gallery = Get-PSRepository -Name PSGallery -ErrorAction SilentlyContinue
if (-not $gallery) {
    Write-Host "[INFO] Registrando PSGallery..."
    Register-PSRepository -Default
}

$nuget = Get-PackageProvider -Name NuGet -ListAvailable -ErrorAction SilentlyContinue | Sort-Object Version -Descending | Select-Object -First 1
if (-not $nuget) {
    Write-Host "Instalando proveedor NuGet para el usuario actual..."
    Install-PackageProvider -Name NuGet -Scope CurrentUser -Force | Out-Null
}

Write-Host ""
Write-Host "Instalando modulo Az para CurrentUser..."
Write-Host "Esto puede descargar varios submodulos de Azure PowerShell."
Write-Host ""

$installParams = @{
    Name = 'Az'
    Repository = 'PSGallery'
    Scope = 'CurrentUser'
    Force = $true
    AllowClobber = $true
}
Install-Module @installParams

Write-Host ""
Import-Module Az.Accounts -Force
Import-Module Az.Resources -Force

$accounts = Get-Module -Name Az.Accounts -ListAvailable | Sort-Object Version -Descending | Select-Object -First 1
$resources = Get-Module -Name Az.Resources -ListAvailable | Sort-Object Version -Descending | Select-Object -First 1

if (-not $accounts -or -not $resources) {
    Write-Host "[ERROR] La instalacion termino, pero faltan modulos requeridos."
    exit 4
}

Write-Host "[OK] Az.Accounts  $($accounts.Version)"
Write-Host "[OK] Az.Resources $($resources.Version)"
Write-Host ""
Write-Host "[OK] Azure PowerShell quedo instalado para el usuario actual."
Write-Host ""
Write-Host "El siguiente paso sera iniciar sesion con Connect-AzAccount."
exit 0
