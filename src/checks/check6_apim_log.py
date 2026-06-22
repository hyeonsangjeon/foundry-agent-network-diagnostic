"""
Check 6 — APIM gateway log correlation (cross-check for Check 5).

Asks a single corroborating question: at the same UTC moment the agent call failed, did a
request actually *reach* APIM?

  * no request reached APIM  → the failure happened before the backend — consistent with a
                               DNS-stage break (cross-validates Check 5's "no query").
  * a request did reach APIM → the break is at/after APIM, not DNS resolution — which would
                               redirect the investigation away from the DNS hypothesis.

Log access depends on customer permissions. We attempt an automatic Log Analytics read and
fall back to a manual-input path otherwise.

READ-ONLY: a Log Analytics *query* only.
"""

from __future__ import annotations

from .common import FAIL, INFO, SKIPPED, CheckContext, CheckResult, az_json

CHECK_ID = "check6"
CHECK_NAME = "APIM gateway log correlation"

_MANUAL = (
    "Manual fallback: in the APIM gateway logs (ApiManagementGatewayLogs), filter for the "
    "agent-call UTC window and answer one question — did ANY request arrive at APIM? "
    "If no request arrived, the break is before APIM (DNS stage), corroborating Check 5."
)


def run(ctx: CheckContext) -> CheckResult:
    result = CheckResult(id=CHECK_ID, name=CHECK_NAME)

    if ctx.mock:
        m = ctx.mock_for(CHECK_ID)
        arrived = m.get("request_arrived")
        result.evidence = dict(m)
        if arrived is False:
            result.status = FAIL
            result.summary = (
                "No request reached APIM in the window → the break is BEFORE APIM (DNS stage). "
                "This corroborates Check 5."
            )
        elif arrived is True:
            result.status = INFO
            result.summary = "A request reached APIM → the break is at/after APIM, not DNS resolution."
        else:
            result.status = SKIPPED
            result.summary = "APIM request arrival undetermined."
        return result

    log = ctx.cfg("apim_gateway_log") or {}
    workspace = log.get("workspace_id") if isinstance(log, dict) else None
    if not workspace or "<" in str(workspace):
        result.status = SKIPPED
        result.summary = "No apim_gateway_log workspace configured — using manual fallback."
        result.remediation = _MANUAL
        result.evidence = {"mode": "manual_fallback"}
        return result

    apim_id = ctx.cfg("apim_resource_id", "")
    kql = (
        "ApiManagementGatewayLogs | where TimeGenerated > ago(1h) "
        "| summarize requests = count()"
    )
    res = az_json(["monitor", "log-analytics", "query", "--workspace", workspace,
                   "--analytics-query", kql], timeout=60)
    if not res["ok"]:
        result.status = SKIPPED
        result.summary = f"Could not auto-query APIM log ({res['error']}) — using manual fallback."
        result.remediation = _MANUAL
        result.evidence = {"mode": "manual_fallback", "error": res["error"], "apim_resource_id": apim_id}
        return result

    rows = res["data"] or []
    total = 0
    try:
        total = int((rows[0] or {}).get("requests", 0)) if rows else 0
    except (ValueError, TypeError, IndexError):
        total = 0
    evidence = {"mode": "auto", "rows": rows, "request_count": total}

    if total == 0:
        result.status = FAIL
        result.summary = "No request reached APIM in the window → break is BEFORE APIM (DNS stage). Corroborates Check 5."
        result.remediation = "Treat as a pre-backend (DNS) break; capture for support (docs/SUPPORT_CASE_GUIDE.md)."
    else:
        result.status = INFO
        result.summary = f"{total} request(s) reached APIM → break is at/after APIM, not DNS resolution."
    result.evidence = evidence
    return result
