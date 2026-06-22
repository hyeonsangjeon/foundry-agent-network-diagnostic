#!/usr/bin/env python3
"""Build config.json from FANDX_* environment variables.

Used by deploy/verify-existing.sh so shell values never have to be hand-assembled
into JSON. Empty optional values are omitted.

Usage:
    FANDX_SUBSCRIPTION_ID=... FANDX_BACKEND_FQDN=... \
        python3 deploy/_write_config_manual.py <path-to-config.json>
"""
from __future__ import annotations

import json
import os
import sys

REQUIRED = {
    "subscription_id": "FANDX_SUBSCRIPTION_ID",
    "resource_group": "FANDX_RESOURCE_GROUP",
    "region": "FANDX_REGION",
    "foundry_account": "FANDX_FOUNDRY_ACCOUNT",
    "foundry_project": "FANDX_FOUNDRY_PROJECT",
    "backend_fqdn": "FANDX_BACKEND_FQDN",
    "expected_private_vip": "FANDX_EXPECTED_VIP",
}

OPTIONAL = {
    "agent_subnet_id": "FANDX_AGENT_SUBNET_ID",
    "pe_subnet_id": "FANDX_PE_SUBNET_ID",
    "apim_resource_id": "FANDX_APIM_RESOURCE_ID",
    "apim_mode": "FANDX_APIM_MODE",
}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _write_config_manual.py <config-path>", file=sys.stderr)
        return 2
    config_path = sys.argv[1]

    config: dict[str, object] = {
        "_generated_by": "deploy/verify-existing.sh — existing environment",
    }
    missing = []
    for key, env in REQUIRED.items():
        value = os.environ.get(env, "").strip()
        if not value:
            missing.append(key)
        config[key] = value

    for key, env in OPTIONAL.items():
        value = os.environ.get(env, "").strip()
        if value:
            config[key] = value

    if missing:
        print("missing required values: " + ", ".join(missing), file=sys.stderr)
        return 1

    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
