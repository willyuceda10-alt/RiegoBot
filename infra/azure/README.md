# Azure Foundation - RiegoBot 2.0

This folder starts the central Azure phase. It is intentionally separated from the Windows Dream collector.

Architecture target:

Dream MDB -> DreamReader Collector -> HTTPS -> RiegoBot Central API (Azure Container Apps) -> Azure Database for PostgreSQL -> incident workflow / evidence policy / notification outbox -> Azure Service Bus -> WhatsApp worker.

Azure Blob Storage stores incident photos/evidence. Fabric and Power BI will consume the central operational/curated model.

Foundation resources:
- Azure Container Apps Environment
- Azure Container Registry
- Azure Database for PostgreSQL Flexible Server
- Azure Storage account and incident-evidence container
- Azure Service Bus and incident-notifications queue
- Azure Key Vault

The Container App itself is deliberately deployed in a later step, after network, managed identity and secret access are configured.

No GitHub Actions are used. Deployment is initiated from authorized Windows PowerShell/Azure PowerShell.

Prerequisite check:
scripts/azure/TEST_AZURE_PREREQUISITOS.ps1

The deployment script is safety locked and does nothing unless -Apply is explicitly supplied.

Security gates before production:
1. Restrict PostgreSQL networking/private connectivity.
2. Enable managed identity for the central workload.
3. Store application secrets in Key Vault.
4. Authenticate collector requests.
5. Keep TEST_REPLAY data blocked from production notifications.
6. Read evidence policies from Azure.
7. Enable WhatsApp only after routing users and assignments exist.

The current Bicep is a development foundation, not the final production network design.
