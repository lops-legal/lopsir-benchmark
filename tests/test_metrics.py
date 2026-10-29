"""Hand-computable checks for ranking metrics and input integrity."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evaluate import evaluate, load_inputs, metrics


class MetricsTests(unittest.TestCase):
    def test_recall_is_not_precision(self):
        rels = {f"d{i}": 1 for i in range(10)}
        ranking = [f"d{i}" for i in range(6)] + [f"x{i}" for i in range(14)]
        result = metrics(rels, ranking, 20)
        self.assertAlmostEqual(result["recall"], 0.6)
        self.assertAlmostEqual(result["precision"], 0.3)

    def test_first_hit_and_cutoff(self):
        ranking = [f"x{i}" for i in range(16)] + ["gold"]
        self.assertEqual(metrics({"gold": 1}, ranking, 10)["hit"], 0)
        result = metrics({"gold": 1}, ranking, 20)
        self.assertEqual(result["recall"], 1)
        self.assertAlmostEqual(result["mrr"], 1 / 17)

    def test_graded_ndcg(self):
        result = metrics({"a": 3, "b": 1}, ["b", "a"], 2)
        expected = (1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3))
        self.assertAlmostEqual(result["ndcg_linear"], expected)

    def test_no_results_counts_zero(self):
        queries = {"q": {"case_type": "C3"}}
        result = evaluate(queries, {"q": {"gold": 1}}, {}, [20])
        self.assertEqual(result["aggregate"]["overall"]["metrics"]["recall@20"], 0)
        self.assertEqual(result["counts"]["eligible"], 1)

    def test_no_positive_excluded(self):
        self.assertIsNone(metrics({"x": 0}, ["x"], 20))
        result = evaluate({"q": {"case_type": "C1"}}, {"q": {"x": 0}}, {}, [20])
        self.assertEqual(result["counts"]["excluded_no_positive"], 1)

    def test_duplicate_cannot_inflate_recall(self):
        with self.assertRaises(ValueError):
            metrics({"a": 1}, ["a", "a"], 20)

    def test_unjudged_is_not_judged_negative(self):
        result = metrics({"gold": 1, "negative": 0}, ["negative", "unjudged", "gold"], 3)
        self.assertAlmostEqual(result["judged_fraction"], 2 / 3)
        self.assertEqual(result["recall"], 1)

    def test_ap_convention(self):
        result = metrics({"a": 1, "b": 1, "c": 1}, ["x", "a"], 2)
        self.assertAlmostEqual(result["ap_at_k_minrel"], 0.25)

    def test_fixture_includes_missing_query(self):
        root = Path(__file__).resolve().parents[1] / "examples"
        data = load_inputs(root / "queries.jsonl", root / "qrels.tsv", root / "run.tsv")
        result = evaluate(*data, [20])
        self.assertEqual(result["counts"]["eligible"], 4)
        self.assertAlmostEqual(result["aggregate"]["overall"]["metrics"]["recall@20"], 0.625)


if __name__ == "__main__":
    unittest.main()
