"""Validate the study contract, without inventing legal documents or queries."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from c1_preflight import inspect_study


class C1PreflightTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "configs/c1.methods.json").read_text(encoding="utf-8"))

    def test_current_study_does_not_claim_results(self):
        report = inspect_study(self.config, ROOT)
        self.assertEqual(report["status"], "blocked")
        self.assertIsNone(report["research_metrics"])
        self.assertIsNone(report["verified_record_count"])

    def test_five_methods_have_sources_and_no_api_key(self):
        self.assertEqual(len(self.config["methods"]), 5)
        for method in self.config["methods"]:
            self.assertFalse(method["api_key_required"])
            self.assertFalse(method["gpu_required"])
        report = inspect_study(self.config, ROOT)
        self.assertEqual(len(report["methods"]), 5)

    def test_historical_fixture_is_not_a_real_research_input(self):
        self.config["data"]["queries_path"] = "examples/queries.jsonl"
        report = inspect_study(self.config, ROOT)
        self.assertTrue(any(x["code"] == "HISTORICAL_FIXTURE_FORBIDDEN_FOR_RESEARCH" for x in report["issues"]))

    def test_wrong_case_or_method_count_is_rejected(self):
        changed = copy.deepcopy(self.config)
        changed["case_type"] = "C2"
        with self.assertRaises(ValueError):
            inspect_study(changed, ROOT)
        self.config["methods"].pop()
        with self.assertRaises(ValueError):
            inspect_study(self.config, ROOT)

    def test_policy_cannot_silently_accept_synthetic_research_data(self):
        self.config["policy"]["allow_synthetic_research_data"] = True
        with self.assertRaises(ValueError):
            inspect_study(self.config, ROOT)


if __name__ == "__main__":
    unittest.main()
