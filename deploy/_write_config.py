#!/usr/bin/env python3
"""Translate `az deployment group show` outputs (on stdin) into config.json.

Usage:
    az deployment group show ... --query properties.outputs -o json \
        | python3 deploy/_write_config.py <path-to-config.json>

Only used by deploy/deploy.sh. Keeps shell quoting out of the picture.
"""
from __future__ import annotations

import json
import os
import sys


def _val(outputs: dict, key: str) -> str:
    entry = outputs.get(key) or {}
    return str(entry.get("value", "") or "")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _write_config.py <config-path>", file=sys.stderr)
        return 2
    config_path = sys.argv[1]

    raw = sys.stdin.read().strip()
    if not raw:
        print("no deployment outputs received on stdin", file=sys.stderr)
        return 1
    outputs = json.loads(raw)

    config = {
        "_generated_by": "deploy/deploy.sh — reproduction lab outputs",
        "subscription_id": _val(outputs, "subscriptionId"),
        "resource_group": _val(outputs, "resourceGroupName"),
        "region": _val(outputs, "region"),
        # The lab does not provision a Foundry account; these labels give the
        # report context. Foundry-specific checks degrade gracefully (SKIPPED).
        "foundry_account": "agentlab-no-foundry",
        "foundry_project": "agentlab-no-foundry",
        "agent_subnet_id": _val(outputs, "agentSubnetId"),
        "pe_subnet_id": _val(outputs, "peSubnetId"),
        "backend_fqdn": _val(outputs, "backendFqdn"),
        "expected_private_vip": _val(outputs, "expectedPrivateVip"),
    }

    apim_id = _val(outputs, "apimResourceId")
    if apim_id:
        config["apim_resource_id"] = apim_id
        config["apim_mode"] = _val(outputs, "apimMode") or "internal"

    # deploy.sh resolves the lab private endpoint VIP from the live NIC and passes it
    # here, because Bicep cannot reliably read the PE IP at deployment time.
    vip_override = os.environ.get("FANDX_VIP_OVERRIDE", "").strip()
    if vip_override:
        config["expected_private_vip"] = vip_override

    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
