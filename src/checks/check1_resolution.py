"""
Check 1 — Hostname resolution (VM perspective).

Establishes the baseline: "from inside the VNet VM, the backend hostname resolves
correctly to the expected private VIP." This is the control case — if the VM resolves
fine but the agent path fails, the problem is on the managed path, not your DNS data.

READ-ONLY: performs name lookups and reads /etc/resolv.conf. Changes nothing.
"""

from __future__ import annotations

import socket

from .common import FAIL, PASS, SKIPPED, WARN, CheckContext, CheckResult, run_cmd

CHECK_ID = "check1"
CHECK_NAME = "Hostname resolution (VM perspective)"


def _read_resolv_conf() -> list[str]:
    try:
        with open("/etc/resolv.conf", "r", encoding="utf-8", errors="replace") as fh:
            return [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    except FileNotFoundError:
        return []
    except OSError:
        return []


def _custom_dns_servers(resolv_lines: list[str]) -> list[str]:
    return [ln.split()[1] for ln in resolv_lines if ln.startswith("nameserver") and len(ln.split()) > 1]


def run(ctx: CheckContext) -> CheckResult:
    result = CheckResult(id=CHECK_ID, name=CHECK_NAME)

    if ctx.mock:
        m = ctx.mock_for(CHECK_ID)
        result.status = PASS if m.get("match") else WARN
        result.summary = (
            f"VM resolves {ctx.cfg('backend_fqdn')} to {m.get('resolved_ip')} "
            f"(expected {m.get('expected_vip')}) — baseline OK."
        )
        result.evidence = dict(m)
        return result

    fqdn = ctx.cfg("backend_fqdn")
    expected = ctx.cfg("expected_private_vip")
    if not fqdn:
        result.status = SKIPPED
        result.summary = "No 'backend_fqdn' in config — cannot test resolution."
        return result

    evidence: dict = {
        "backend_fqdn": fqdn,
        "expected_vip": expected,
        "resolv_conf": _read_resolv_conf(),
    }
    evidence["custom_dns_servers"] = _custom_dns_servers(evidence["resolv_conf"])

    # socket-level resolution (what most clients actually use)
    resolved_ips: list[str] = []
    try:
        infos = socket.getaddrinfo(fqdn, 443, proto=socket.IPPROTO_TCP)
        resolved_ips = sorted({i[4][0] for i in infos})
        evidence["socket_ok"] = True
    except socket.gaierror as exc:
        evidence["socket_ok"] = False
        evidence["socket_error"] = str(exc)
    evidence["resolved_ips"] = resolved_ips

    # dig / nslookup for an authoritative second opinion (best effort)
    dig = run_cmd(["dig", "+short", fqdn], timeout=10)
    if dig["ok"]:
        evidence["dig_answer"] = dig["stdout"]
    else:
        ns = run_cmd(["nslookup", fqdn], timeout=10)
        evidence["nslookup"] = ns["stdout"] or ns["error"]

    if not resolved_ips:
        result.status = FAIL
        result.summary = f"VM could NOT resolve {fqdn}. Fix VM/VNet DNS before going further."
        result.remediation = "Check /etc/resolv.conf, the VNet's custom DNS servers, and the private DNS zone link."
        result.evidence = evidence
        return result

    if expected and expected not in resolved_ips:
        result.status = WARN
        result.summary = f"VM resolves {fqdn} to {resolved_ips}, which does not include expected {expected}."
        result.remediation = "Confirm expected_private_vip, or that the right private DNS zone is linked to this VNet."
    else:
        result.status = PASS
        result.summary = f"VM resolves {fqdn} to {resolved_ips} — baseline OK."
    result.evidence = evidence
    return result
