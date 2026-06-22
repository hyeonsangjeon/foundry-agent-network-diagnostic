"""
Shared infrastructure for the diagnostic checks.

Design constraints (see ``docs/PLATFORM_PATTERN.md`` and the repo README):
  * READ-ONLY. Helpers here only *read* — they never create, update, or delete.
  * No third-party dependencies. Standard library only, so the tool runs in
    closed/air-gapped networks.
  * Never crash on missing permissions or tools. Fall back to SKIPPED with a clear,
    actionable message and (where relevant) a manual-input path.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

# --- Status vocabulary -------------------------------------------------------
PASS = "PASS"        # behaved as the healthy baseline expects
WARN = "WARN"        # works but diverges from the recommended/official pattern
FAIL = "FAIL"        # a concrete break was observed
SKIPPED = "SKIPPED"  # could not run (missing perms/tools/inputs) — not a failure
INFO = "INFO"        # neutral context, no pass/fail meaning

ALL_STATUSES = (PASS, WARN, FAIL, SKIPPED, INFO)


@dataclass
class CheckResult:
    """Structured, machine-readable result for a single check."""

    id: str
    name: str
    status: str = SKIPPED
    summary: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "evidence": self.evidence,
            "remediation": self.remediation,
            "timestamp": self.timestamp,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Read-only command execution --------------------------------------------
def have_tool(name: str) -> bool:
    """True if an executable is on PATH."""
    return shutil.which(name) is not None


def run_cmd(args: list[str], timeout: int = 20) -> dict[str, Any]:
    """
    Run a read-only command and capture output without ever raising.

    Returns {ok, rc, stdout, stderr, error}. ``ok`` is True only when the command
    ran and exited 0. Missing executables and timeouts come back as ok=False with a
    populated ``error`` string rather than an exception.
    """
    if not args:
        return {"ok": False, "rc": None, "stdout": "", "stderr": "", "error": "empty command"}
    if not have_tool(args[0]):
        return {
            "ok": False,
            "rc": None,
            "stdout": "",
            "stderr": "",
            "error": f"'{args[0]}' not found on PATH",
        }
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "rc": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "error": "" if proc.returncode == 0 else (proc.stderr.strip() or f"exit {proc.returncode}"),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": None, "stdout": "", "stderr": "", "error": f"timed out after {timeout}s"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "rc": None, "stdout": "", "stderr": "", "error": str(exc)}


def az_json(args: list[str], timeout: int = 40) -> dict[str, Any]:
    """
    Run ``az <args> -o json`` and parse the result.

    Returns {ok, data, error, raw}. Never raises. If ``az`` is missing, not logged in,
    or the call fails, ok=False and ``error`` explains why so the caller can SKIP.
    """
    res = run_cmd(["az", *args, "-o", "json"], timeout=timeout)
    if not res["ok"]:
        return {"ok": False, "data": None, "error": res["error"], "raw": res.get("stdout", "")}
    try:
        data = json.loads(res["stdout"]) if res["stdout"] else None
        return {"ok": True, "data": data, "error": "", "raw": res["stdout"]}
    except json.JSONDecodeError as exc:
        return {"ok": False, "data": None, "error": f"could not parse az output: {exc}", "raw": res["stdout"]}


# --- Context passed to every check ------------------------------------------
@dataclass
class CheckContext:
    """Everything a check needs: the validated config, mock flag, and mock data."""

    config: dict[str, Any]
    mock: bool = False
    mock_data: dict[str, Any] = field(default_factory=dict)
    # Evidence from checks that already ran this session, keyed by check id.
    prior: dict[str, Any] = field(default_factory=dict)

    def cfg(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def mock_for(self, check_id: str) -> dict[str, Any]:
        return self.mock_data.get(check_id, {})

    def prior_evidence(self, check_id: str) -> dict[str, Any]:
        return self.prior.get(check_id, {})


# A check is a callable taking a context and returning a CheckResult.
CheckFn = Callable[[CheckContext], CheckResult]
