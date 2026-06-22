// =============================================================================
// foundry-agent-network-diagnostic — reproduction lab infrastructure
// -----------------------------------------------------------------------------
// Builds a SMALL, real network path that reproduces the shape of a Foundry
// Standard Agent BYO VNet -> private backend (APIM / private endpoint) topology
// so the READ-ONLY diagnostic in this repo can be exercised end to end against
// live Azure resources.
//
// scenario = 'lab'  (default) : VNet + delegated agent subnet + PE subnet +
//                               custom private DNS zone + Storage account fronted
//                               by a Private Endpoint. Fast (~2-3 min) and cheap.
//                               Reproduces the "custom private FQDN -> private VIP"
//                               path that Checks 1/2/4 inspect.
// scenario = 'apim' (opt-in)  : Adds an API Management service in INTERNAL VNet
//                               mode as the private backend. Faithful to the real
//                               BYO AI Gateway path but SLOW (~45 min) and costs
//                               more. Use only when you need Checks 3/5/6 against
//                               a real APIM gateway.
//
// This template only creates resources you own in your own subscription. The
// diagnostic itself never mutates anything.
// =============================================================================

targetScope = 'resourceGroup'

@description('Azure region for all resources. Defaults to the resource group region.')
param location string = resourceGroup().location

@description('Short prefix for resource names. Lowercase letters/numbers only.')
@minLength(3)
@maxLength(12)
param namePrefix string = 'fandx${take(uniqueString(resourceGroup().id), 6)}'

@description('Reproduction scenario. "lab" is fast/cheap; "apim" is faithful but slow.')
@allowed([
  'lab'
  'apim'
])
param scenario string = 'lab'

@description('Custom (private-only) DNS zone that stands in for the BYO custom domain.')
param customDnsZoneName string = 'internal.agentlab.example'

@description('Host label under the custom zone used as the backend FQDN, e.g. "llm".')
param customBackendHost string = 'llm'

@description('Deploy an optional small jump VM inside the VNet to run the diagnostic from in-network.')
param deployJumpVm bool = false

@description('Admin username for the optional jump VM.')
param adminUsername string = 'azureuser'

@description('Admin password for the optional jump VM. Required only when deployJumpVm = true.')
@secure()
param adminPassword string = ''

@description('Tags applied to every resource.')
param tags object = {
  project: 'foundry-agent-network-diagnostic'
  purpose: 'repro-lab'
}

// -----------------------------------------------------------------------------
// Address plan
// -----------------------------------------------------------------------------
var vnetAddressSpace = '10.40.0.0/16'
var agentSubnetPrefix = '10.40.1.0/24'
var peSubnetPrefix = '10.40.2.0/24'
var jumpSubnetPrefix = '10.40.3.0/24'
var apimSubnetPrefix = '10.40.4.0/24'

var vnetName = '${namePrefix}-vnet'
var agentSubnetName = 'agent-subnet'
var peSubnetName = 'pe-subnet'
var jumpSubnetName = 'jump-subnet'
var apimSubnetName = 'apim-subnet'

var storageAccountName = toLower('${namePrefix}sa${take(uniqueString(resourceGroup().id, 'sa'), 4)}')
var apimName = '${namePrefix}-apim'
var backendFqdn = '${customBackendHost}.${customDnsZoneName}'

var blobPrivateDnsZoneName = 'privatelink.blob.${environment().suffixes.storage}'

// -----------------------------------------------------------------------------
// Networking
// -----------------------------------------------------------------------------
resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressSpace
      ]
    }
    subnets: [
      {
        // Agent subnet: delegated to Microsoft.App/environments, matching the
        // Standard Agent BYO VNet requirement that the diagnostic checks for.
        name: agentSubnetName
        properties: {
          addressPrefix: agentSubnetPrefix
          delegations: [
            {
              name: 'aca-delegation'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        // Private endpoint subnet.
        name: peSubnetName
        properties: {
          addressPrefix: peSubnetPrefix
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: jumpSubnetName
        properties: {
          addressPrefix: jumpSubnetPrefix
        }
      }
      {
        name: apimSubnetName
        properties: {
          addressPrefix: apimSubnetPrefix
        }
      }
    ]
  }
}

resource agentSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-11-01' existing = {
  parent: vnet
  name: agentSubnetName
}

resource peSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-11-01' existing = {
  parent: vnet
  name: peSubnetName
}

resource jumpSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-11-01' existing = {
  parent: vnet
  name: jumpSubnetName
}

resource apimSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-11-01' existing = {
  parent: vnet
  name: apimSubnetName
}

// -----------------------------------------------------------------------------
// Private backend stand-in (lab scenario): Storage account behind a PE
// -----------------------------------------------------------------------------
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource blobPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: blobPrivateDnsZoneName
  location: 'global'
  tags: tags
}

resource blobZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: blobPrivateDnsZone
  name: '${vnetName}-blob-link'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource storagePe 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: '${namePrefix}-pe-blob'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: peSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: 'blob'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

resource storagePeDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: storagePe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: {
          privateDnsZoneId: blobPrivateDnsZone.id
        }
      }
    ]
  }
}

// Resolvable storage blob FQDN. Inside the VNet, the linked privatelink.blob zone
// (populated by the private DNS zone group above) resolves this to the PE's private
// IP. The custom record below CNAMEs to it, so we never have to read the PE IP at
// deploy time (customDnsConfigs can be empty when a zone group is attached).
var storageBlobFqdn = '${storage.name}.blob.${environment().suffixes.storage}'

// -----------------------------------------------------------------------------
// Custom private DNS zone — reproduces the "custom private-only FQDN" path
// -----------------------------------------------------------------------------
resource customZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: customDnsZoneName
  location: 'global'
  tags: tags
}

resource customZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: customZone
  name: '${vnetName}-custom-link'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

// lab scenario: custom FQDN -> CNAME -> storage blob FQDN (resolves to the PE IP
// via the linked privatelink zone). Robust regardless of customDnsConfigs state.
resource customRecordLab 'Microsoft.Network/privateDnsZones/CNAME@2020-06-01' = if (scenario == 'lab') {
  parent: customZone
  name: customBackendHost
  properties: {
    ttl: 300
    cnameRecord: {
      cname: storageBlobFqdn
    }
  }
  dependsOn: [
    storagePeDnsGroup
  ]
}

// -----------------------------------------------------------------------------
// Faithful backend (apim scenario): API Management in INTERNAL VNet mode
// -----------------------------------------------------------------------------
resource apim 'Microsoft.ApiManagement/service@2023-05-01-preview' = if (scenario == 'apim') {
  name: apimName
  location: location
  tags: tags
  sku: {
    name: 'Developer'
    capacity: 1
  }
  properties: {
    publisherEmail: 'lab@agentlab.example'
    publisherName: 'Agent Network Lab'
    virtualNetworkType: 'Internal'
    virtualNetworkConfiguration: {
      subnetResourceId: apimSubnet.id
    }
  }
}

// apim scenario: custom FQDN -> APIM internal VIP
resource customRecordApim 'Microsoft.Network/privateDnsZones/A@2020-06-01' = if (scenario == 'apim') {
  parent: customZone
  name: customBackendHost
  properties: {
    ttl: 300
    aRecords: [
      {
        #disable-next-line BCP318
        ipv4Address: apim.properties.privateIPAddresses[0]
      }
    ]
  }
}

// -----------------------------------------------------------------------------
// Optional in-network jump VM
// -----------------------------------------------------------------------------
resource jumpNic 'Microsoft.Network/networkInterfaces@2023-11-01' = if (deployJumpVm) {
  name: '${namePrefix}-jump-nic'
  location: location
  tags: tags
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: jumpSubnet.id
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
  }
}

resource jumpVm 'Microsoft.Compute/virtualMachines@2023-09-01' = if (deployJumpVm) {
  name: '${namePrefix}-jump'
  location: location
  tags: tags
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_B1s'
    }
    osProfile: {
      computerName: 'jump'
      adminUsername: adminUsername
      adminPassword: adminPassword
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: '0001-com-ubuntu-server-jammy'
        sku: '22_04-lts-gen2'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'StandardSSD_LRS'
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: jumpNic.id
        }
      ]
    }
  }
}

// -----------------------------------------------------------------------------
// Outputs — consumed by deploy.sh to generate config.json
// -----------------------------------------------------------------------------
output subscriptionId string = subscription().subscriptionId
output resourceGroupName string = resourceGroup().name
output region string = location
output vnetId string = vnet.id
output agentSubnetId string = agentSubnet.id
output peSubnetId string = peSubnet.id
output backendFqdn string = backendFqdn
// For apim the internal VIP is reliably populated. For lab the VIP is resolved from
// the live private endpoint NIC by deploy.sh (see privateEndpointName below).
#disable-next-line BCP318
output expectedPrivateVip string = scenario == 'apim' ? apim.properties.privateIPAddresses[0] : ''
output storageAccountName string = storageAccountName
output storageBlobFqdn string = storageBlobFqdn
output privateEndpointName string = storagePe.name
output customDnsZoneName string = customDnsZoneName
#disable-next-line BCP318
output apimResourceId string = scenario == 'apim' ? apim.id : ''
output apimMode string = scenario == 'apim' ? 'internal' : ''
output scenario string = scenario
