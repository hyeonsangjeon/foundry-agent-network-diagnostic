"""
Official Foundry "Standard Agent + Private APIM" reference pattern (Template 16).

This module encodes the *supported* topology that the Foundry samples publish as
Template 16 (Standard Agent setup with a private Azure API Management gateway behind
an inbound Private Endpoint, fronted by the ``privatelink.azure-api.net`` private DNS
zone). Check 4 diffs a customer's actual configuration against these expectations.

We keep this as plain data (no Azure calls) so the diff is transparent and reviewable.
Nothing here is customer specific. See ``docs/REFERENCES.md`` for the source links and
``docs/PLATFORM_PATTERN.md`` for the architectural explanation.

Verification note (2026-06): "Foundry Agents support only public endpoints" is INACCURATE.
A supported private-APIM isolation pattern exists (Template 16). What is *not* documented
publicly is a supported way to inject custom DNS / a custom Private Resolver directly into
the managed Data Proxy. Items we cannot verify are surfaced as "needs verification" rather
than asserted as fact.
"""

from __future__ import annotations

# Canonical private DNS zone used by the official private-APIM pattern.
OFFICIAL_APIM_PRIVATE_DNS_ZONE = "privatelink.azure-api.net"

# Foundry connection category recommended when wiring a *direct* Azure APIM gateway.
RECOMMENDED_APIM_CONNECTION_CATEGORY = "ApiManagement"

# Subnet delegation required for the agent (managed) subnet in a Standard Agent setup.
REQUIRED_AGENT_SUBNET_DELEGATION = "Microsoft.App/environments"


# Each dimension is one row of the Check 4 topology-diff table.
#   key       : machine id
#   dimension : human label
#   official  : what Template 16 expects
#   why       : why it matters for the private network path
TEMPLATE16_DIMENSIONS = [
    {
        "key": "apim_exposure",
        "dimension": "APIM exposure",
        "official": "Inbound Private Endpoint on the APIM service",
        "why": (
            "Template 16 reaches APIM through a Private Endpoint whose private IP is "
            "registered in a private DNS zone the platform resolver can see. Classic "
            "internal-VNet mode publishes a VIP that the managed resolver path may not "
            "resolve."
        ),
    },
    {
        "key": "dns_zone",
        "dimension": "Backend DNS zone",
        "official": f"{OFFICIAL_APIM_PRIVATE_DNS_ZONE} (Azure-managed private DNS zone)",
        "why": (
            "The official pattern resolves the APIM hostname inside the "
            f"{OFFICIAL_APIM_PRIVATE_DNS_ZONE} zone. A custom private-only FQDN "
            "(e.g. *.<your-domain>) lives in a zone that must be explicitly linked to "
            "the resolver path the Data Proxy uses — otherwise resolution fails before "
            "the backend is ever reached."
        ),
    },
    {
        "key": "connection_category",
        "dimension": "Foundry connection category",
        "official": f"{RECOMMENDED_APIM_CONNECTION_CATEGORY}",
        "why": (
            "Connecting a direct Azure APIM gateway with the ApiManagement category is "
            "the documented path. A generic ModelGateway/custom connection can change "
            "how the hostname is presented to the Data Proxy."
        ),
    },
    {
        "key": "agent_subnet_delegation",
        "dimension": "Agent subnet delegation",
        "official": f"Delegated to {REQUIRED_AGENT_SUBNET_DELEGATION}",
        "why": (
            "The managed agent (Data Proxy) subnet must be delegated to "
            f"{REQUIRED_AGENT_SUBNET_DELEGATION} so the platform can place its managed "
            "hosts and consume delegated IPs on the expected network path."
        ),
    },
    {
        "key": "dns_zone_link",
        "dimension": "Private DNS zone link to resolver path",
        "official": "Backend private DNS zone is linked to the VNet/resolver the agent path uses",
        "why": (
            "Even a correct zone fails if it is not linked to the resolver the managed "
            "path consults. This is the single most common break in BYO custom-FQDN setups."
        ),
    },
]


def official_summary() -> str:
    """One-line description of the official reference pattern."""
    return (
        "Standard Agent + Private APIM (Template 16): APIM via inbound Private Endpoint, "
        f"hostname in {OFFICIAL_APIM_PRIVATE_DNS_ZONE}, Foundry connection category "
        f"'{RECOMMENDED_APIM_CONNECTION_CATEGORY}', agent subnet delegated to "
        f"{REQUIRED_AGENT_SUBNET_DELEGATION}, backend private DNS zone linked to the "
        "resolver path the agent uses."
    )
