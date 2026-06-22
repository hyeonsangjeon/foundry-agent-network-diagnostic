"""
Config loading + validation.

Reads a JSON config (default ``config.json``), strips documentation-only keys (those
starting with ``_``), and validates required fields with friendly, actionable errors.

In mock mode validation is relaxed: the sample placeholders are accepted so the demo runs
with no real values.
"""

from __future__ import annotations

import json
import os
from typing import Any

REQUIRED_FIELDS = [
    "subscription_id",
    "resource_group",
    "region",
    "foundry_account",
    "foundry_project",
    "backend_fqdn",
    "expected_private_vip",
]


class ConfigError(Exception):
    """Raised for missing/invalid configuration, with a friendly message."""


def _strip_doc_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_doc_keys(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [_strip_doc_keys(v) for v in obj]
    return obj


def load_raw(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        raise ConfigError(
            f"Config file not found: {path}\n"
            f"  → Copy the sample and fill it in:  cp config.sample.json config.json"
        )
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Config file {path} must contain a JSON object.")
    return _strip_doc_keys(data)


def _is_placeholder(value: Any) -> bool:
    s = str(value)
    return ("<" in s and ">" in s) or s.strip() == ""


def validate(config: dict[str, Any], *, mock: bool) -> list[str]:
    """Return a list of human-readable problems. Empty list = valid."""
    problems: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in config:
            problems.append(f"missing required field: '{field}'")
        elif not mock and _is_placeholder(config[field]):
            problems.append(f"field '{field}' still has a placeholder value — replace it with your real value")

    mode = str(config.get("apim_mode", "")).lower()
    if mode and mode not in ("internal", "external", "pe", "unknown"):
        problems.append("'apim_mode' must be one of: internal | external | PE | unknown")
    return problems


def load_config(path: str, *, mock: bool) -> dict[str, Any]:
    """
    Load and validate config. In mock mode, a missing file is tolerated (returns {}),
    and placeholder values are allowed.
    """
    if mock and not os.path.exists(path):
        return {}
    config = load_raw(path)
    problems = validate(config, mock=mock)
    if problems and not mock:
        bullet = "\n  - ".join(problems)
        raise ConfigError(
            f"Config validation failed for {path}:\n  - {bullet}\n\n"
            f"Fix these fields in {path} (see config.sample.json for the schema)."
        )
    return config
