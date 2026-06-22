"""
Mock scenario for ``--mock`` runs (no Azure, no network, no permissions needed).

This models the canonical break this tool was built to diagnose, using ONLY
placeholders (no real identifiers / FQDN / VIP / subscription):

  BYO VNet Standard Agent, classic *internal-mode* APIM behind a *custom private-only
  FQDN*. The jump-box VM resolves the hostname fine, APIM is reachable, but the Foundry
  Data Proxy call fails with "Name or service not known" — and neither this VNet's DNS
  resolver nor the APIM gateway ever sees the request. Root cause points to the platform
  resolver path, not the backend.

Each check's mock branch reads its raw values here so mock evidence has the same shape
as real evidence.
"""

from __future__ import annotations

MOCK_BACKEND_FQDN = "llm.contoso-apim.contoso.example"
MOCK_EXPECTED_VIP = "10.20.30.40"

MOCK_SCENARIO: dict[str, dict] = {
    "check1": {
        "resolved_ip": MOCK_EXPECTED_VIP,
        "expected_vip": MOCK_EXPECTED_VIP,
        "socket_ok": True,
        "dig_answer": f"{MOCK_BACKEND_FQDN}. 30 IN A {MOCK_EXPECTED_VIP}",
        "resolv_conf": ["nameserver 10.20.0.10", "search internal.contoso.example"],
        "custom_dns_servers": ["10.20.0.10"],
        "match": True,
    },
    "check2": {
        "vip": MOCK_EXPECTED_VIP,
        "port": 443,
        "tcp_connect_ok": True,
        "tls_handshake_ok": True,
        "tls_sni": MOCK_BACKEND_FQDN,
        "peer_cert_subject": "CN=*.contoso.example",
        "https_status": 200,
    },
    "check3": {
        "connection_name": "byo-apim-gateway",
        "connection_category": "ModelGateway",
        "recommended_category": "ApiManagement",
        "agent_subnet_delegation": "Microsoft.App/environments",
        "delegation_ok": True,
    },
    "check4": {
        # observed values, keyed by the Template 16 dimension keys
        "observed": {
            "apim_exposure": "Classic internal VNet mode (no inbound Private Endpoint)",
            "dns_zone": "custom private-only zone: *.contoso.example",
            "connection_category": "ModelGateway",
            "agent_subnet_delegation": "Microsoft.App/environments",
            "dns_zone_link": "Not linked to the resolver path the managed agent uses (unverified — confirm)",
        },
        # per-dimension verdicts: match | diverge | unknown
        "verdicts": {
            "apim_exposure": "diverge",
            "dns_zone": "diverge",
            "connection_category": "diverge",
            "agent_subnet_delegation": "match",
            "dns_zone_link": "diverge",
        },
    },
    "check5": {
        "source": "Azure Private Resolver query log (mock)",
        "query_window_utc": "2026-06-18T02:10:00Z .. 2026-06-18T02:12:00Z",
        "backend_fqdn": MOCK_BACKEND_FQDN,
        "query_arrived": False,          # the decisive signal
        "response_code": None,
        "verdict": "no_query",           # one of: no_query | nxdomain_or_timeout | answered_but_failed
    },
    "check6": {
        "source": "APIM gateway requests (mock)",
        "query_window_utc": "2026-06-18T02:10:00Z .. 2026-06-18T02:12:00Z",
        "request_arrived": False,        # corroborates check5
    },
}
