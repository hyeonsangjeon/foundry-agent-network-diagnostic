"""Per-check verdict logic and the root-cause direction mapping."""

from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401  (sys.path side effect)

from src.checks import check4_topology_diff, check5_dns_query, check6_apim_log
from src.checks.common import CheckContext, CheckResult
from src.checks.mock_data import MOCK_SCENARIO
from src.diagnose import build_verdict


def _mock_ctx(mock_data=None):
    return CheckContext(config={"backend_fqdn": "llm.example"}, mock=True,
                        mock_data=mock_data if mock_data is not None else MOCK_SCENARIO)


class TestCheck4(unittest.TestCase):
    def test_diverge_count_and_observed_key(self):
        result = check4_topology_diff.run(_mock_ctx())
        self.assertEqual(result.status, "WARN")
        self.assertEqual(result.evidence["diverge_count"], 4)
        rows = result.evidence["rows"]
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertIn("observed", row)
            self.assertNotIn("customer", row)


class TestCheck5(unittest.TestCase):
    def test_three_verdicts_map_to_status(self):
        cases = {
            "no_query": "FAIL",
            "nxdomain_or_timeout": "FAIL",
            "answered_but_failed": "WARN",
        }
        for verdict, expected_status in cases.items():
            ctx = _mock_ctx({"check5": {"verdict": verdict}})
            result = check5_dns_query.run(ctx)
            self.assertEqual(result.status, expected_status, verdict)
            self.assertEqual(result.evidence["verdict"], verdict)

    def test_no_customer_in_summaries(self):
        for verdict in ("no_query", "nxdomain_or_timeout", "answered_but_failed"):
            ctx = _mock_ctx({"check5": {"verdict": verdict}})
            result = check5_dns_query.run(ctx)
            self.assertNotIn("customer", (result.summary + result.remediation).lower())


class TestCheck6(unittest.TestCase):
    def test_no_request_is_fail(self):
        result = check6_apim_log.run(_mock_ctx({"check6": {"request_arrived": False}}))
        self.assertEqual(result.status, "FAIL")

    def test_request_arrived_is_info(self):
        result = check6_apim_log.run(_mock_ctx({"check6": {"request_arrived": True}}))
        self.assertEqual(result.status, "INFO")


class TestVerdictDirection(unittest.TestCase):
    @staticmethod
    def _verdict_for(code):
        c5 = CheckResult(id="check5", name="c5", evidence={"verdict": code})
        c6 = CheckResult(id="check6", name="c6", status="FAIL")
        return build_verdict({"check5": c5, "check6": c6})

    def test_no_query_is_platform(self):
        self.assertEqual(self._verdict_for("no_query")["direction"], "platform")

    def test_nxdomain_is_configuration(self):
        self.assertEqual(self._verdict_for("nxdomain_or_timeout")["direction"], "configuration")

    def test_answered_is_platform(self):
        self.assertEqual(self._verdict_for("answered_but_failed")["direction"], "platform")

    def test_unknown_code_is_unknown(self):
        self.assertEqual(self._verdict_for("something_else")["direction"], "unknown")


if __name__ == "__main__":
    unittest.main()
