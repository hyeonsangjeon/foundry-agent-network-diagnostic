"""Write the machine-readable JSON report."""

from __future__ import annotations

import json
from typing import Any


def write_json(report: dict[str, Any], path: str) -> str:
    """Write the full report dict as pretty JSON. Returns the path."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path
