# References

Only official Microsoft sources are cited as authoritative. Community posts (if any) are
clearly marked as "for reference" and never used to assert behavior. Verification baseline:
**2026-06**. Preview behavior changes — re-confirm against Microsoft Learn before acting.

## Foundry Agent Service — networking & standard setup

- **Set up private networking for Foundry Agent Service** (BYO VNet, subnets, private endpoints)
  <https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/virtual-networks>
- **Set up standard agent resources** (BYO Storage / Cosmos DB / AI Search; the Standard Agent model)
  <https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/standard-agent-setup>

## Official infrastructure samples (the diff baseline — "Template 16")

The Check 4 baseline is the official **network-secured Standard Agent + private APIM** pattern
published in the Foundry samples (Bicep + Terraform). The samples are organized by number and
evolve over time — **confirm the current template number for the private-APIM variant in the repo**.
This asset refers to it conceptually as *Template 16*.

- **Bicep infrastructure setup templates (index)**
  <https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep>
- **Network-secured Standard Agent (Bicep), `15-private-network-standard-agent-setup`**
  <https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup>
- **BYO VNet Standard Agent (Terraform), `15b-private-network-standard-agent-setup-byovnet`**
  <https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-terraform/15b-private-network-standard-agent-setup-byovnet>

## Azure API Management — private endpoint & DNS

- **Connect to API Management using a private endpoint** (`privatelink.azure-api.net`)
  <https://learn.microsoft.com/en-us/azure/api-management/api-management-using-with-private-endpoints>
- **Azure Private Endpoint DNS integration**
  <https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-dns>

## DNS resolution in a VNet

- **Azure DNS Private Resolver overview**
  <https://learn.microsoft.com/en-us/azure/dns/dns-private-resolver-overview>
- **Private DNS zones overview**
  <https://learn.microsoft.com/en-us/azure/dns/private-dns-overview>

## Notes on verified facts (2026-06)

- A **supported private-APIM isolation pattern exists** for Foundry Agents (the network-secured
  Standard Agent samples above). The claim "Foundry Agents support only public endpoints" is
  **inaccurate**.
- There is **no publicly documented, supported method** to inject a custom DNS server or a custom
  Private Resolver directly into the managed Data Proxy. This asset therefore does **not** assert
  that the Data Proxy "never" consults this VNet's DNS; Check 5 reports only what was observed and
  marks the rest "needs verification".
