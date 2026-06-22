"""Template 16 reference data integrity (it drives the Check 4 diff)."""

from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401  (sys.path side effect)

from src.checks import check4_topology_diff
from src.reference import template16_pattern as t16


class TestTemplate16(unittest.TestCase):
    def test_dimensions_shape(self):
        dims = t16.TEMPLATE16_DIMENSIONS
        self.assertEqual(len(dims), 5)
        for dim in dims:
            for key in ("key", "dimension", "official", "why"):
                self.assertIn(key, dim)
                self.assertTrue(str(dim[key]).strip())

    def test_keys_are_unique(self):
        keys = [d["key"] for d in t16.TEMPLATE16_DIMENSIONS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_keys_match_check4_derivers(self):
        dim_keys = {d["key"] for d in t16.TEMPLATE16_DIMENSIONS}
        self.assertEqual(dim_keys, set(check4_topology_diff._DERIVERS.keys()))

    def test_official_summary_mentions_pattern(self):
        summary = t16.official_summary()
        self.assertIn("Template 16", summary)
        self.assertIn(t16.OFFICIAL_APIM_PRIVATE_DNS_ZONE, summary)


if __name__ == "__main__":
    unittest.main()
