#!/usr/bin/env python3
"""
foundry-agent-network-diagnostic — entrypoint.

Runs the 6 read-only checks against a Foundry Agent BYO VNet environment, computes a
3-way root-cause verdict, and writes a self-contained HTML dashboard + JSON report.

Usage:
  python src/diagnose.py --config config.json
  python src/diagnose.py --config config.sample.json --mock      # demo, no Azure needed
  python src/diagnose.py --config config.json --checks 1,2,4      # run a subset

This tool is READ-ONLY: it never creates, updates, or deletes any Azure resource.
"""

from __future__ import annotations

import argparse
import os
import sys

# Make 'src' importable whether run as 'python src/diagnose.py' or as a module.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.checks import (  # noqa: E402
    check1_resolution,
    check2_reachability,
    check3_connection,
    check4_topology_diff,
    check5_dns_query,
    check6_apim_log,
)
from src.checks.common import CheckContext, utc_now_iso  # noqa: E402
from src.checks.mock_data import (  # noqa: E402
    MOCK_BACKEND_FQDN,
    MOCK_EXPECTED_VIP,
    MOCK_SCENARIO,
)
from src.config_loader import ConfigError, load_config  # noqa: E402
from src.report.html_renderer import write_html  # noqa: E402
from src.report.json_writer import write_json  # noqa: E402

VERSION = "0.3.0"

# Ordered registry: check number → (id, module).
CHECKS = [
    (1, check1_resolution),
    (2, check2_reachability),
    (3, check3_connection),
    (4, check4_topology_diff),
    (5, check5_dns_query),
    (6, check6_apim_log),
]

_VERDICT_MAP = {
    "no_query": (
        "DNS query never reached your resolver — the managed agent path appears to bypass this VNet DNS path",
        "No query for the backend FQDN was observed at the resolver during the agent call. "
        "Direction: platform supportability. Marked needs-verification — this does not prove "
        "the Data Proxy never consults customer DNS; it shows none arrived in this window.",
    ),
    "nxdomain_or_timeout": (
        "DNS query reached the resolver but failed (NXDOMAIN/timeout) — a DNS zone-link / forwarding issue",
        "The query arrived but did not resolve. Direction: customer configuration — link the "
        "backend's private DNS zone to the resolver path and verify conditional forwarding.",
    ),
    "answered_but_failed": (
        "DNS resolved correctly yet the agent call still failed — platform cache or an alternate resolver path",
        "A normal A record was returned but the call failed anyway. Direction: platform "
        "(needs verification). Capture timing and compare against the APIM log.",
    ),
}


def _mock_config_defaults() -> dict:
    return {
        "region": "<your-azure-region>",
        "foundry_account": "contoso-foundry",
        "foundry_project": "contoso-project",
        "backend_fqdn": MOCK_BACKEND_FQDN,
        "expected_private_vip": MOCK_EXPECTED_VIP,
        "apim_mode": "internal",
    }


def parse_checks(spec: str | None) -> list[int]:
    if not spec:
        return [n for n, _ in CHECKS]
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= 6:
            out.append(int(part))
    return out or [n for n, _ in CHECKS]


def build_verdict(results_by_id: dict) -> dict:
    c5 = results_by_id.get("check5")
    c6 = results_by_id.get("check6")

    code = (c5.evidence.get("verdict") if c5 else None)
    headline, detail = _VERDICT_MAP.get(
        code,
        (
            "Undetermined — provide a DNS resolver log or manual input for Check 5",
            "Check 5 could not observe DNS resolver activity. Re-run with dns_resolver_log "
            "configured, or use the manual fallback described in the report.",
        ),
    )

    if c6 is None:
        corroboration = "Check 6 (APIM log) was not run."
    elif c6.status == "FAIL":
        corroboration = "Check 6 corroborates: no request reached APIM in the window — the break is before the backend."
    elif c6.status == "INFO":
        corroboration = "Check 6: a request DID reach APIM — reconsider the DNS hypothesis; the break may be at/after APIM."
    else:
        corroboration = "Check 6 unavailable (APIM log not provided) — corroborate manually."

    direction = "platform" if code in ("no_query", "answered_but_failed") else (
        "customer" if code == "nxdomain_or_timeout" else "unknown"
    )
    return {"direction": direction, "headline": headline, "detail": detail, "corroboration": corroboration}


def build_support_block(report: dict) -> str:
    cs = report["config_summary"]
    lines = [
        "Foundry Agent Network Diagnostic — Support Case Summary",
        f"Generated (UTC): {report['generated_utc']}",
        f"Tool version: {report['version']}  |  Mode: {report['mode']}",
        "",
        "Environment (placeholders shown if values were not provided):",
        f"  Region:                  {cs.get('region','-')}",
        f"  Foundry account/project: {cs.get('foundry_account','-')} / {cs.get('foundry_project','-')}",
        f"  Backend FQDN:            {cs.get('backend_fqdn','-')}",
        f"  Expected private VIP:    {cs.get('expected_private_vip','-')}",
        f"  APIM mode:               {cs.get('apim_mode','-')}",
        "",
        f"Root-cause verdict: {report['verdict']['headline']}",
        f"  {report['verdict']['detail']}",
        f"  {report['verdict']['corroboration']}",
        "",
        "Check results:",
    ]
    for c in report["checks"]:
        lines.append(f"  [{c['status']:^7}] {c['name']}: {c['summary']}")
    lines += [
        "",
        "Notes:",
        "  - This tool is READ-ONLY; no Azure resources were created/modified/deleted.",
        "  - Items marked 'needs verification' are not asserted as fact.",
        "  - See docs/SUPPORT_CASE_GUIDE.md for what to include in an MS support case.",
    ]
    return "\n".join(lines)


_CONSOLE_COLOR = {
    "PASS": "\033[32m", "WARN": "\033[33m", "FAIL": "\033[31m",
    "SKIPPED": "\033[90m", "INFO": "\033[36m",
}
_RESET = "\033[0m"


def print_console(report: dict, color: bool) -> None:
    def paint(status: str) -> str:
        if not color:
            return f"[{status}]"
        return f"{_CONSOLE_COLOR.get(status,'')}[{status}]{_RESET}"

    print("\nFoundry Agent Network Diagnostic")
    print(f"  mode={report['mode']}  generated={report['generated_utc']}  v{report['version']}")
    print("-" * 72)
    for c in report["checks"]:
        print(f"  {paint(c['status']):>16}  {c['name']}")
        print(f"                    {c['summary']}")
    print("-" * 72)
    counts = report["summary_counts"]
    print("  " + "  ".join(f"{k}={counts.get(k,0)}" for k in ("PASS", "WARN", "FAIL", "SKIPPED", "INFO")))
    print(f"\n  VERDICT: {report['verdict']['headline']}")
    print(f"           {report['verdict']['corroboration']}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="diagnose.py",
        description="Read-only diagnostic for the Foundry Agent private network path (BYO VNet + private APIM).",
    )
    parser.add_argument("--config", default="config.json", help="Path to config JSON (default: config.json).")
    parser.add_argument("--mock", action="store_true", help="Run with built-in mock data (no Azure/network needed).")
    parser.add_argument("--checks", default=None, help="Comma-separated subset, e.g. '1,2,4' (default: all).")
    parser.add_argument("--out-dir", default=".", help="Directory for report.html / report.json (default: cwd).")
    parser.add_argument("--no-color", action="store_true", help="Disable colored console output.")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config, mock=args.mock)
    except ConfigError as exc:
        print(f"\n[config error]\n{exc}\n", file=sys.stderr)
        return 2

    if args.mock:
        merged = dict(config or {})
        merged.update(_mock_config_defaults())  # mock scenario is authoritative in --mock
        config = merged

    ctx = CheckContext(config=config, mock=args.mock, mock_data=MOCK_SCENARIO)

    selected = parse_checks(args.checks)
    results = []
    results_by_id = {}
    for number, module in CHECKS:
        if number not in selected:
            continue
        result = module.run(ctx)
        results.append(result)
        results_by_id[result.id] = result
        ctx.prior[result.id] = result.evidence  # let later checks reuse evidence

    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    report = {
        "tool": "foundry-agent-network-diagnostic",
        "version": VERSION,
        "generated_utc": utc_now_iso(),
        "mode": "mock" if args.mock else "live",
        "config_summary": {
            "region": config.get("region"),
            "foundry_account": config.get("foundry_account"),
            "foundry_project": config.get("foundry_project"),
            "backend_fqdn": config.get("backend_fqdn"),
            "expected_private_vip": config.get("expected_private_vip"),
            "apim_mode": config.get("apim_mode"),
        },
        "summary_counts": counts,
        "checks": [r.to_dict() for r in results],
    }
    report["verdict"] = build_verdict(results_by_id)
    report["support_block"] = build_support_block(report)

    os.makedirs(args.out_dir, exist_ok=True)
    html_path = write_html(report, os.path.join(args.out_dir, "report.html"))
    json_path = write_json(report, os.path.join(args.out_dir, "report.json"))

    print_console(report, color=not args.no_color)
    print(f"  Wrote: {html_path}")
    print(f"  Wrote: {json_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
