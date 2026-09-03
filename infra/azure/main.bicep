@description('Azure region for the RiegoBot pilot.')
param location string = resourceGroup().location

@description('Short lowercase resource prefix.')
param prefix string = 'riegobotdev'

@description('PostgreSQL administrator login used only for bootstrap.')
param postgresAdminLogin string = 'riegobotadmin'

@secure()
@description('PostgreSQL bootstrap administrator password.')
param postgresAdminPassword string

var suffix = uniqueString(subscription().subscriptionId, resourceGroup().id)
var storageName = take(replace(toLower('${prefix}${suffix}'), '-', ''), 24)
var keyVaultName = take(toLower('${prefix}-kv-${suffix}'), 24)
var postgresName = take(toLower('${prefix}-pg-${suffix}'), 63)
var serviceBusName = take(toLower('${prefix}-sb-${suffix}'), 50)
var acrName = take(replace(toLower('${prefix}${suffix}acr'), '-', ''), 50)
var containerEnvName = take(toLower('${prefix}-cae-${suffix}'), 60)

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource evidenceContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'incident-evidence'
  properties: { publicAccess: 'None' }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 30
    publicNetworkAccess: 'Enabled'
  }
}

resource serviceBus 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: serviceBusName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
}

resource notificationQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  parent: serviceBus
  name: 'incident-notifications'
  properties: {
    lockDuration: 'PT1M'
    maxDeliveryCount: 10
    deadLetteringOnMessageExpiration: true
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource containerEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerEnvName
  location: location
  properties: {}
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    version: '16'
    authConfig: {
      activeDirectoryAuth: 'Disabled'
      passwordAuth: 'Enabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: { mode: 'Disabled' }
    network: { publicNetworkAccess: 'Enabled' }
    storage: { storageSizeGB: 32 }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: 'riegobot'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

output storageAccountName string = storage.name
output evidenceContainerName string = evidenceContainer.name
output keyVaultName string = keyVault.name
output serviceBusNamespace string = serviceBus.name
output notificationQueueName string = notificationQueue.name
output containerRegistryName string = acr.name
output containerAppsEnvironmentName string = containerEnvironment.name
output postgresServerName string = postgres.name
output postgresDatabaseName string = database.name
output postgresHost string = '${postgres.name}.postgres.database.azure.com'
