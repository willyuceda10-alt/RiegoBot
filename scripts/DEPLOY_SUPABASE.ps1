param([string]$ProjectRef='zdgfjepoptlwjaoxvuju',[string]$SecretsFile='supabase/functions/.env.production.local')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if($ProjectRef -ne 'zdgfjepoptlwjaoxvuju'){throw 'Unexpected target project. Review this script before using another project.'}
if(-not(Test-Path -LiteralPath $SecretsFile)){throw 'Create the production secrets file from supabase/functions/.env.example first. Keep DRY_RUN=true until WhatsApp is configured.'}
& npx.cmd supabase link --project-ref $ProjectRef
if($LASTEXITCODE -ne 0){throw 'Supabase link failed. Run npx supabase login.'}
& npx.cmd supabase db push --linked
if($LASTEXITCODE -ne 0){throw 'Migration failed'}
& npx.cmd supabase secrets set --env-file $SecretsFile --project-ref $ProjectRef
if($LASTEXITCODE -ne 0){throw 'Secrets configuration failed'}
foreach($function in @('api','ingest','whatsapp-webhook','worker')){
 & npx.cmd supabase functions deploy $function --project-ref $ProjectRef --no-verify-jwt
 if($LASTEXITCODE -ne 0){throw "Deploy failed: $function"}
}
Write-Host 'Backend deployed. Configure dispatcher Vault values, staff access and WhatsApp before enabling real deliveries.'
