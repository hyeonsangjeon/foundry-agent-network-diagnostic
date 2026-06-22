"""Report rendering: single-file HTML guarantee + JSON round-trip."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from tests import _bootstrap  # noqa: F401  (sys.path side effect)

from src.report.html_renderer import render_html
from src.report.json_writer import write_json

_REPORT = {
    "tool": "foundry-agent-network-diagnostic",
    "version": "1.0.1",
    "generated_utc": "2026-06-22T00:00:00+00:00",
    "mode": "mock",
    "summary_counts": {"PASS": 1, "WARN": 1, "FAIL": 1},
    "verdict": {
        "direction": "platform",
        "headline": "DNS query never reached your resolver",
        "detail": "No query observed in the window.",
        "corroboration": "Check 6 corroborates.",
    },
    "support_block": "Support case summary\n  line",
    "checks": [
        {
            "id": "check4",
            "name": "Topology diff vs official Template 16",
            "status": "WARN",
            "summary": "4 of 5 dimensions diverge.",
            "remediation": "",
            "evidence": {
                "diverge_count": 4,
                "rows": [
                    {
                        "dimension": "APIM exposure",
                        "official": "Inbound Private Endpoint",
                        "observed": "Classic internal VNet mode",
                        "verdict": "diverge",
                        "impact": "Publishes a VIP the resolver may not resolve.",
                    }
                ],
            },
        }
    ],
}


class TestHtmlSingleFile(unittest.TestCase):
    def setUp(self):
        self.html = render_html(_REPORT)

    def test_is_standalone_document(self):
        self.assertTrue(self.html.lstrip().startswith("<!DOCTYPE html>"))

    def test_no_external_resources(self):
        lowered = self.html.lower()
        self.assertNotIn("<script", lowered)
        self.assertNotIn("http://", lowered)
        self.assertNotIn("https://", lowered)
        self.assertNotIn("cdn", lowered)
        self.assertNotIn("src=", lowered)

    def test_topology_header_is_neutral(self):
        self.assertIn("Your environment", self.html)
        self.assertNotIn("customer", self.html.lower())
        self.assertIn("Classic internal VNet mode", self.html)


class TestJsonWriter(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_json(_REPORT, os.path.join(tmp, "report.json"))
            self.assertTrue(os.path.exists(path))
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), _REPORT)


if __name__ == "__main__":
    unittest.main()
