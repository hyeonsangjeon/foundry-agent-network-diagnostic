"""
Check 2 — Backend reachability (network layer).

Proves the backend (private APIM) is alive and reachable from the VNet: TCP connect to
the resolved VIP:443, then a TLS handshake using the custom FQDN as SNI. Optionally a
single HTTPS request for the status code only (no response body is stored).

If this PASSES, the backend itself is healthy and reachable — which pushes the problem
*outside* the backend, toward the managed agent's resolution path.

READ-ONLY: opens a socket and reads a status line. Sends no payload, stores no body.
"""

from __future__ import annotations

import socket
import ssl

from .common import FAIL, PASS, SKIPPED, WARN, CheckContext, CheckResult

CHECK_ID = "check2"
CHECK_NAME = "Backend reachability (network layer)"


def _pick_target_ip(ctx: CheckContext) -> str | None:
    expected = ctx.cfg("expected_private_vip")
    if expected and "x" not in str(expected):
        return expected
    fqdn = ctx.cfg("backend_fqdn")
    if not fqdn:
        return None
    try:
        return socket.getaddrinfo(fqdn, 443, proto=socket.IPPROTO_TCP)[0][4][0]
    except socket.gaierror:
        return None


def run(ctx: CheckContext) -> CheckResult:
    result = CheckResult(id=CHECK_ID, name=CHECK_NAME)

    if ctx.mock:
        m = ctx.mock_for(CHECK_ID)
        ok = m.get("tcp_connect_ok") and m.get("tls_handshake_ok")
        result.status = PASS if ok else FAIL
        result.summary = (
            f"TCP+TLS to {m.get('vip')}:{m.get('port')} (SNI={m.get('tls_sni')}) succeeded; "
            f"HTTPS status {m.get('https_status')} — backend is alive and reachable."
        )
        result.evidence = dict(m)
        return result

    fqdn = ctx.cfg("backend_fqdn")
    ip = _pick_target_ip(ctx)
    if not fqdn or not ip:
        result.status = SKIPPED
        result.summary = "Need backend_fqdn and a resolvable/expected VIP to test reachability."
        return result

    evidence: dict = {"vip": ip, "port": 443, "tls_sni": fqdn}

    # 1) TCP connect
    try:
        with socket.create_connection((ip, 443), timeout=8) as sock:
            evidence["tcp_connect_ok"] = True
            # 2) TLS handshake with SNI = custom FQDN
            context = ssl.create_default_context()
            context.check_hostname = False          # private/custom FQDN; we only test reachability
            context.verify_mode = ssl.CERT_NONE     # read-only reachability, not a cert audit
            try:
                with context.wrap_socket(sock, server_hostname=fqdn) as tls:
                    evidence["tls_handshake_ok"] = True
                    evidence["tls_version"] = tls.version()
                    cert = tls.getpeercert(binary_form=True)
                    evidence["peer_cert_present"] = cert is not None
            except ssl.SSLError as exc:
                evidence["tls_handshake_ok"] = False
                evidence["tls_error"] = str(exc)
    except (socket.timeout, OSError) as exc:
        evidence["tcp_connect_ok"] = False
        evidence["tcp_error"] = str(exc)

    if not evidence.get("tcp_connect_ok"):
        result.status = FAIL
        result.summary = f"Cannot TCP-connect to {ip}:443 from the VM. Backend/network layer issue."
        result.remediation = "Check NSG/UDR/route to the APIM VIP and that APIM is running."
    elif not evidence.get("tls_handshake_ok"):
        result.status = WARN
        result.summary = f"TCP reached {ip}:443 but TLS handshake failed (SNI={fqdn})."
        result.remediation = "Verify APIM TLS/listener config and that the custom FQDN is bound on the gateway."
    else:
        result.status = PASS
        result.summary = f"TCP+TLS to {ip}:443 (SNI={fqdn}) OK — backend is alive and reachable from the VM."
    result.evidence = evidence
    return result
