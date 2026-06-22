"""End-to-end smoke test: the ``--mock`` run must work with no Azure/network."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tests import _bootstrap  # noqa: F401  (sys.path side effect)

from src import diagnose


def _run_main(argv):
    """Run diagnose.main(argv) with stdout/stderr suppressed; return its exit code."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = diagnose.main(argv)
    return code, out.getvalue()


class TestMockSmoke(unittest.TestCase):
    def test_end_to_end_mock_writes_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = _run_main(["--mock", "--out-dir", tmp, "--no-color"])
            self.assertEqual(code, 0)

            html_path = os.path.join(tmp, "report.html")
            json_path = os.path.join(tmp, "report.json")
            self.assertTrue(os.path.exists(html_path))
            self.assertTrue(os.path.exists(json_path))

            raw = Path(json_path).read_text(encoding="utf-8")
            report = json.loads(raw)

            self.assertEqual(report["version"], diagnose.VERSION)
            self.assertEqual(report["mode"], "mock")
            self.assertEqual(len(report["checks"]), 6)
            self.assertIn("summary_counts", report)
            self.assertIn("support_block", report)

            verdict = report["verdict"]
            for key in ("direction", "headline", "detail", "corroboration"):
                self.assertIn(key, verdict)

    def test_mock_report_is_neutralized(self):
        """The report must not leak customer-framing vocabulary post-cleanup."""
        with tempfile.TemporaryDirectory() as tmp:
            _run_main(["--mock", "--out-dir", tmp, "--no-color"])
            raw = Path(os.path.join(tmp, "report.json")).read_text(encoding="utf-8")
            self.assertNotIn("customer", raw.lower())

            report = json.loads(raw)
            check4 = next(c for c in report["checks"] if c["id"] == "check4")
            row = check4["evidence"]["rows"][0]
            self.assertIn("observed", row)
            self.assertNotIn("customer", row)

    def test_checks_subset(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = _run_main(["--mock", "--checks", "1,2", "--out-dir", tmp, "--no-color"])
            self.assertEqual(code, 0)
            report = json.loads(Path(os.path.join(tmp, "report.json")).read_text(encoding="utf-8"))
            self.assertEqual([c["id"] for c in report["checks"]], ["check1", "check2"])

    def test_missing_config_live_exits_2(self):
        missing = os.path.join(tempfile.gettempdir(), "fand_does_not_exist_xyz.json")
        if os.path.exists(missing):
            os.remove(missing)
        code, _ = _run_main(["--config", missing])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
