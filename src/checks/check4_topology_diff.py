"""
Check 4 — Topology diff vs official Template 16 (★ platform-IP centerpiece).

Compares the customer's configuration against the official Foundry "Standard Agent +
Private APIM" pattern (Template 16), one dimension at a time, and explains the network
*impact* of each divergence. The output is a 3-column table: official / customer / impact.

This is where Foundry platform understanding shows up — it explains *why* the path
breaks against the reference architecture, not just "nslookup failed". A divergence is
WARN (configuration differs from the supported pattern), not proof of the break itself;
the break is confirmed by Checks 5/6. Items that cannot be determined are marked
"needs verification" rather than asserted.

READ-ONLY: derives from config + prior check evidence only.
"""

from __future__ import annotations

from .common import INFO, PASS, WARN, CheckContext, CheckResult
from src.reference.template16_pattern import (
    OFFICIAL_APIM_PRIVATE_DNS_ZONE,
    RECOMMENDED_APIM_CONNECTION_CATEGORY,
    REQUIRED_AGENT_SUBNET_DELEGATION,
    TEMPLATE16_DIMENSIONS,
    official_summary,
)

CHECK_ID = "check4"
CHECK_NAME = "Topology diff vs official Template 16"

MATCH, DIVERGE, UNKNOWN = "match", "diverge", "unknown"


def _customer_apim_exposure(ctx: CheckContext):
    mode = str(ctx.cfg("apim_mode", "")).lower()
    if mode == "pe":
        return "Inbound Private Endpoint", MATCH
    if mode == "internal":
        return "Classic internal VNet mode (no inbound Private Endpoint)", DIVERGE
    if mode == "external":
        return "External VNet mode", DIVERGE
    return "needs verification (set apim_mode: internal|external|PE)", UNKNOWN


def _customer_dns_zone(ctx: CheckContext):
    fqdn = str(ctx.cfg("backend_fqdn", ""))
    if not fqdn or "<" in fqdn:
        return "needs verification (set backend_fqdn)", UNKNOWN
    if fqdn.endswith("azure-api.net"):
        return f"{OFFICIAL_APIM_PRIVATE_DNS_ZONE} zone", MATCH
    domain = ".".join(fqdn.split(".")[1:]) if "." in fqdn else fqdn
    return f"custom private-only zone (*.{domain})", DIVERGE


def _customer_connection_category(ctx: CheckContext):
    cats = ctx.prior_evidence("check3").get("connection_categories") or []
    gateway = next((c for c in cats if c in ("ApiManagement", "ModelGateway")), None)
    if gateway == RECOMMENDED_APIM_CONNECTION_CATEGORY:
        return gateway, MATCH
    if gateway:
        return gateway, DIVERGE
    return "needs verification (check Foundry connection category)", UNKNOWN


def _customer_delegation(ctx: CheckContext):
    delegations = ctx.prior_evidence("check3").get("agent_subnet_delegations")
    if delegations is None:
        return "needs verification (set agent_subnet_id)", UNKNOWN
    if REQUIRED_AGENT_SUBNET_DELEGATION in delegations:
        return f"Delegated to {REQUIRED_AGENT_SUBNET_DELEGATION}", MATCH
    return f"Not delegated ({delegations or 'none'})", DIVERGE


def _customer_dns_zone_link(ctx: CheckContext):
    # Cannot be reliably determined from config alone; honest about it.
    return ("needs verification — confirm the backend private DNS zone is linked to the "
            "resolver path the managed agent uses"), UNKNOWN


_DERIVERS = {
    "apim_exposure": _customer_apim_exposure,
    "dns_zone": _customer_dns_zone,
    "connection_category": _customer_connection_category,
    "agent_subnet_delegation": _customer_delegation,
    "dns_zone_link": _customer_dns_zone_link,
}


def run(ctx: CheckContext) -> CheckResult:
    result = CheckResult(id=CHECK_ID, name=CHECK_NAME)
    rows = []

    if ctx.mock:
        m = ctx.mock_for(CHECK_ID)
        customer = m.get("customer", {})
        verdicts = m.get("verdicts", {})
        for dim in TEMPLATE16_DIMENSIONS:
            k = dim["key"]
            rows.append({
                "dimension": dim["dimension"],
                "official": dim["official"],
                "customer": customer.get(k, "needs verification"),
                "verdict": verdicts.get(k, UNKNOWN),
                "impact": dim["why"],
            })
    else:
        for dim in TEMPLATE16_DIMENSIONS:
            value, verdict = _DERIVERS[dim["key"]](ctx)
            rows.append({
                "dimension": dim["dimension"],
                "official": dim["official"],
                "customer": value,
                "verdict": verdict,
                "impact": dim["why"],
            })

    diverges = sum(1 for r in rows if r["verdict"] == DIVERGE)
    unknowns = sum(1 for r in rows if r["verdict"] == UNKNOWN)

    if diverges:
        result.status = WARN
        result.summary = (
            f"{diverges} of {len(rows)} dimensions diverge from the official private-APIM "
            f"pattern (Template 16). These divergences explain why the managed resolver path "
            f"can fail before the backend is reached."
        )
        result.remediation = (
            "Align the divergent dimensions with Template 16, or open a support case citing "
            "this diff (see docs/SUPPORT_CASE_GUIDE.md)."
        )
    elif unknowns == len(rows):
        result.status = INFO
        result.summary = "Could not determine topology automatically — fill config / run Checks 3 first."
    else:
        result.status = PASS
        result.summary = "Configuration aligns with the official Template 16 private-APIM pattern."

    result.evidence = {
        "official_pattern": official_summary(),
        "rows": rows,
        "diverge_count": diverges,
        "unknown_count": unknowns,
    }
    return result
