"""Config loading + validation."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from tests import _bootstrap  # noqa: F401  (sys.path side effect)

from src import config_loader
from src.config_loader import ConfigError

_FULL = {
    "subscription_id": "00000000-0000-0000-0000-000000000000",
    "resource_group": "rg-demo",
    "region": "koreacentral",
    "foundry_account": "demo-foundry",
    "foundry_project": "demo-project",
    "backend_fqdn": "llm.demo-apim.demo.example",
    "expected_private_vip": "10.20.30.40",
    "apim_mode": "internal",
}


class TestValidate(unittest.TestCase):
    def test_empty_lists_all_required(self):
        problems = config_loader.validate({}, mock=False)
        self.assertEqual(len(problems), len(config_loader.REQUIRED_FIELDS))

    def test_full_config_is_valid(self):
        self.assertEqual(config_loader.validate(_FULL, mock=False), [])

    def test_placeholder_rejected_in_live(self):
        cfg = dict(_FULL, backend_fqdn="<your-backend-fqdn>")
        problems = config_loader.validate(cfg, mock=False)
        self.assertTrue(any("backend_fqdn" in p for p in problems))

    def test_placeholder_allowed_in_mock(self):
        cfg = dict(_FULL, backend_fqdn="<your-backend-fqdn>")
        self.assertEqual(config_loader.validate(cfg, mock=True), [])

    def test_invalid_apim_mode(self):
        cfg = dict(_FULL, apim_mode="bogus")
        problems = config_loader.validate(cfg, mock=False)
        self.assertTrue(any("apim_mode" in p for p in problems))


class TestLoad(unittest.TestCase):
    def test_strip_doc_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            payload = dict(_FULL)
            payload["_comment"] = "documentation only"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            loaded = config_loader.load_raw(path)
            self.assertNotIn("_comment", loaded)
            self.assertIn("subscription_id", loaded)

    def test_missing_file_live_raises(self):
        with self.assertRaises(ConfigError):
            config_loader.load_config("/no/such/file.json", mock=False)

    def test_missing_file_mock_returns_empty(self):
        self.assertEqual(config_loader.load_config("/no/such/file.json", mock=True), {})

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{ not json ")
            with self.assertRaises(ConfigError):
                config_loader.load_raw(path)


if __name__ == "__main__":
    unittest.main()
