"""
Check 5 — DNS query observation (★ root-cause heart, 3-way verdict).

Looks at this VNet's DNS resolver / Azure DNS Private Resolver query log to see whether
a query for the backend FQDN actually *arrived* at the resolver around the time the agent
made its call. This is the single most decisive signal for splitting "environment config" from
"platform path":

  * no query arrived            → the managed Data Proxy is not using this VNet DNS path
                                  (points toward platform supportability — needs verification)
  * query arrived + NXDOMAIN/timeout → DNS forwarding / zone-link problem (environment config)
  * normal A answer yet it failed   → platform DNS cache / a different resolver path (platform)

Log access depends on your permissions. We attempt an automatic Log Analytics read and,
if that is not possible, fall back to a manual-input path with the exact question to answer.

READ-ONLY: a Log Analytics *query* only. We assert nothing we did not observe.
"""

from __future__ import annotations

from .common import FAIL, SKIPPED, WARN, CheckContext, CheckResult, az_json

CHECK_ID = "check5"
CHECK_NAME = "DNS query observation (root-cause)"

NO_QUERY = "no_query"
NXDOMAIN_OR_TIMEOUT = "nxdomain_or_timeout"
ANSWERED_BUT_FAILED = "answered_but_failed"

_MANUAL = (
    "Manual fallback: in your DNS resolver / Azure DNS Private Resolver query log, filter for "
    "the backend FQDN around the agent-call UTC time and answer: (a) did a query arrive? "
    "(b) if so, was the response NXDOMAIN/timeout or a normal A record? Record the answer in "
    "config (dns_resolver_log) or share it with support."
)


def _verdict_result(result: CheckResult, verdict: str, fqdn: str, evidence: dict) -> CheckResult:
    evidence["verdict"] = verdict
    result.evidence = evidence
    if verdict == NO_QUERY:
        result.status = FAIL
        result.summary = (
            f"No DNS query for {fqdn} arrived at the resolver in the window → the managed "
            f"Data Proxy is not using this VNet DNS path. Direction: platform supportability "
            f"(needs verification — do not assert the Data Proxy never uses this VNet's DNS)."
        )
        result.remediation = (
            "Cross-check with Check 6 (APIM log). If APIM also saw no request, the break is "
            "before the backend. Capture this for a support case (docs/SUPPORT_CASE_GUIDE.md)."
        )
    elif verdict == NXDOMAIN_OR_TIMEOUT:
        result.status = FAIL
        result.summary = (
            f"A query for {fqdn} arrived but returned NXDOMAIN/timeout → DNS forwarding / "
            f"private DNS zone-link problem. Direction: environment configuration."
        )
        result.remediation = (
            "Link the backend's private DNS zone to the resolver path, and verify conditional "
            "forwarding for the custom domain."
        )
    elif verdict == ANSWERED_BUT_FAILED:
        result.status = WARN
        result.summary = (
            f"DNS answered {fqdn} with a normal A record yet the agent call still failed → "
            f"platform DNS cache or a different resolver path. Direction: platform (needs verification)."
        )
        result.remediation = "Capture timing + answer for a support case; compare against Check 6."
    else:
        result.status = SKIPPED
        result.summary = "DNS query verdict undetermined."
    return result


def run(ctx: CheckContext) -> CheckResult:
    result = CheckResult(id=CHECK_ID, name=CHECK_NAME)
    fqdn = ctx.cfg("backend_fqdn", "<backend_fqdn>")

    if ctx.mock:
        m = ctx.mock_for(CHECK_ID)
        return _verdict_result(result, m.get("verdict", NO_QUERY), fqdn, dict(m))

    log = ctx.cfg("dns_resolver_log") or {}
    workspace = log.get("workspace_id") if isinstance(log, dict) else None
    if not workspace or "<" in str(workspace):
        result.status = SKIPPED
        result.summary = "No dns_resolver_log workspace configured — using manual fallback."
        result.remediation = _MANUAL
        result.evidence = {"mode": "manual_fallback", "backend_fqdn": fqdn}
        return result

    # Best-effort automatic read. Schema varies by resolver product, so tolerate failure.
    kql = (
        f"DnsQueryLogs | where TimeGenerated > ago(1h) "
        f"| where QueryName has '{fqdn}' | summarize count() by ResponseCode"
    )
    res = az_json(["monitor", "log-analytics", "query", "--workspace", workspace,
                   "--analytics-query", kql], timeout=60)
    if not res["ok"]:
        result.status = SKIPPED
        result.summary = f"Could not auto-query DNS log ({res['error']}) — using manual fallback."
        result.remediation = _MANUAL
        result.evidence = {"mode": "manual_fallback", "backend_fqdn": fqdn, "error": res["error"]}
        return result

    rows = res["data"] or []
    evidence = {"mode": "auto", "backend_fqdn": fqdn, "rows": rows}
    if not rows:
        return _verdict_result(result, NO_QUERY, fqdn, evidence)
    codes = " ".join(str(r).upper() for r in rows)
    if "NXDOMAIN" in codes or "SERVFAIL" in codes or "TIMEOUT" in codes:
        return _verdict_result(result, NXDOMAIN_OR_TIMEOUT, fqdn, evidence)
    return _verdict_result(result, ANSWERED_BUT_FAILED, fqdn, evidence)
