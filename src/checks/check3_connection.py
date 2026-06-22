"""
Check 3 — Foundry connection topology (az / REST).

Screens for first-order configuration mistakes:
  * the BYO gateway connection's *category* (ModelGateway vs ApiManagement). For a
    direct Azure APIM gateway, ApiManagement is the documented category.
  * the agent (managed) subnet delegation (should be Microsoft.App/environments).

The exact Foundry connections control-plane API is in preview and its shape may change,
so the connection lookup is best-effort: if it cannot be read it is reported as
"needs verification" with a portal path, never asserted. Subnet delegation uses the
stable ``az network vnet subnet show`` command.

READ-ONLY: only ``show``/``list`` style reads.
"""

from __future__ import annotations

from .common import (
    INFO,
    PASS,
    SKIPPED,
    WARN,
    CheckContext,
    CheckResult,
    az_json,
)
from src.reference.template16_pattern import (
    RECOMMENDED_APIM_CONNECTION_CATEGORY,
    REQUIRED_AGENT_SUBNET_DELEGATION,
)

CHECK_ID = "check3"
CHECK_NAME = "Foundry connection topology"


def _check_delegation(ctx: CheckContext, evidence: dict) -> bool | None:
    """Return True/False if delegation could be determined, else None."""
    subnet_id = ctx.cfg("agent_subnet_id")
    if not subnet_id or "<" in str(subnet_id):
        evidence["agent_subnet_delegation"] = "not provided (set agent_subnet_id to check)"
        return None
    res = az_json(["network", "vnet", "subnet", "show", "--ids", subnet_id])
    if not res["ok"]:
        evidence["agent_subnet_delegation"] = f"could not read: {res['error']}"
        return None
    delegations = [d.get("serviceName") for d in (res["data"] or {}).get("delegations", [])]
    evidence["agent_subnet_delegations"] = delegations
    return REQUIRED_AGENT_SUBNET_DELEGATION in delegations


def run(ctx: CheckContext) -> CheckResult:
    result = CheckResult(id=CHECK_ID, name=CHECK_NAME)

    if ctx.mock:
        m = ctx.mock_for(CHECK_ID)
        category = m.get("connection_category")
        result.status = WARN if category != m.get("recommended_category") else PASS
        result.summary = (
            f"Connection '{m.get('connection_name')}' category is '{category}' "
            f"(recommended '{m.get('recommended_category')}' for direct Azure APIM); "
            f"agent subnet delegation = {m.get('agent_subnet_delegation')}."
        )
        result.evidence = dict(m)
        return result

    evidence: dict = {"recommended_category": RECOMMENDED_APIM_CONNECTION_CATEGORY}

    # --- Connection category (best-effort, preview API) ---
    account = ctx.cfg("foundry_account")
    project = ctx.cfg("foundry_project")
    category = None
    if account and "<" not in str(account):
        # Best-effort: list connections on the account. Shape is preview; tolerate failure.
        res = az_json(["cognitiveservices", "account", "connection", "list",
                       "--name", account, "--resource-group", ctx.cfg("resource_group", "")])
        if res["ok"] and isinstance(res["data"], list):
            cats = [c.get("properties", {}).get("category") for c in res["data"]]
            evidence["connection_categories"] = [c for c in cats if c]
            gateway = next((c for c in evidence["connection_categories"]
                            if c in ("ApiManagement", "ModelGateway")), None)
            category = gateway
        else:
            evidence["connection_lookup"] = (
                "needs verification — could not list connections via az "
                f"({res['error']}). Verify in the Foundry portal: Project > Connected resources."
            )
    else:
        evidence["connection_lookup"] = "foundry_account not provided; verify category in the Foundry portal."

    # --- Agent subnet delegation ---
    delegation_ok = _check_delegation(ctx, evidence)

    # --- Verdict ---
    notes = []
    status = INFO
    if category == "ApiManagement":
        notes.append("connection category = ApiManagement (recommended).")
        status = PASS
    elif category == "ModelGateway":
        notes.append("connection category = ModelGateway; ApiManagement is recommended for a direct Azure APIM gateway.")
        status = WARN
    else:
        notes.append("connection category could not be read automatically (needs verification).")
        status = SKIPPED

    if delegation_ok is True:
        notes.append(f"agent subnet delegated to {REQUIRED_AGENT_SUBNET_DELEGATION}.")
    elif delegation_ok is False:
        notes.append(f"agent subnet is NOT delegated to {REQUIRED_AGENT_SUBNET_DELEGATION}.")
        status = WARN
    # delegation None → leave note from evidence

    result.status = status
    result.summary = " ".join(notes)
    if status == WARN:
        result.remediation = (
            "For a direct Azure APIM gateway use the ApiManagement connection category, "
            f"and delegate the agent subnet to {REQUIRED_AGENT_SUBNET_DELEGATION}."
        )
    result.evidence = evidence
    return result
