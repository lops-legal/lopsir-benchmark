"""Hand-checkable tests for the C2 pipeline pieces that do not need data or models."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lopsir_c2.common import Analyzer, percentile  # noqa: E402
from lopsir_c2.data import grouped_split, near_duplicate_groups, origin_of  # noqa: E402
from lopsir_c2.m1_bm25.bm25 import analyzer_from_name  # noqa: E402
from lopsir_c2.m5_hybrid.__main__ import convex, rrf  # noqa: E402
from lopsir_c2.results.stats import paired_bootstrap, verdict  # noqa: E402


class AnalyzerTests(unittest.TestCase):
    def test_legal_numbers_stay_whole(self):
        tokens = Analyzer()("Decreto-Lei 4.657/1942, art. 65")
        self.assertIn("4.657/1942", tokens)
        self.assertIn("65", tokens)

    def test_unaccented_typing_matches_accented_text(self):
        analyzer = Analyzer(fold=True, stem=True)
        self.assertEqual(analyzer("fiscalizacao"), analyzer("fiscalização"))

    def test_stopwords_removed_but_not_numbers(self):
        self.assertEqual(Analyzer(stem=False)("novo e improrrogável prazo"), ["novo", "improrrogavel", "prazo"])

    def test_analyzer_name_round_trip(self):
        for options in ({"fold": True, "stem": False, "stopwords": True}, {"fold": False, "stem": True, "stopwords": False}):
            analyzer = Analyzer(**options)
            self.assertEqual(analyzer_from_name(analyzer.name).name, analyzer.name)


class SplitTests(unittest.TestCase):
    def test_question_queries_are_not_c2(self):
        self.assertEqual(origin_of("50"), "real_keyword")
        self.assertEqual(origin_of("51"), "synthetic_keyword")
        self.assertEqual(origin_of("101"), "synthetic_question")

    def test_near_duplicates_share_a_split(self):
        queries = [{"query_id": "1", "text": "técnica e preço", "origin": "real_keyword"},
                   {"query_id": "2", "text": "técnica e preço ponderação", "origin": "real_keyword"},
                   {"query_id": "3", "text": "restos a pagar", "origin": "real_keyword"},
                   {"query_id": "4", "text": "medida cautelar", "origin": "real_keyword"}]
        groups = near_duplicate_groups(queries)
        self.assertEqual(groups["1"], groups["2"])
        for q in queries:
            q["group_id"] = groups[q["query_id"]]
        split = grouped_split(queries)
        self.assertEqual(split["1"], split["2"])
        self.assertEqual(split, grouped_split(queries))  # frozen by the seed


class FusionTests(unittest.TestCase):
    def test_rrf_by_hand(self):
        fused = dict(rrf([[("a", 9), ("b", 8)], [("b", 0.9), ("c", 0.8)]], k=60))
        self.assertAlmostEqual(fused["b"], 1 / 62 + 1 / 61)
        self.assertAlmostEqual(fused["a"], 1 / 61)
        self.assertEqual(max(fused, key=fused.get), "b")

    def test_ties_are_broken_by_doc_id(self):
        lexical = [(f"d{i}", 1.0) for i in (5, 3, 9, 1)]
        dense = [("d7", 0.4), ("d2", 0.4)]
        for alpha in (0.0, 0.5):
            ids = [d for d, _ in convex(lexical, dense, alpha)]
            tied = [d for d, s in convex(lexical, dense, alpha) if s == max(dict(convex(lexical, dense, alpha)).values())]
            self.assertEqual(tied, sorted(tied))
            self.assertEqual(ids, [d for d, _ in convex(list(reversed(lexical)), list(reversed(dense)), alpha)])

    def test_convex_minmax_and_missing_branch(self):
        fused = dict(convex([("a", 10), ("b", 5)], [("b", 0.9), ("c", 0.5)], alpha=0.5))
        self.assertAlmostEqual(fused["a"], 0.5)   # lexical max, absent from dense
        self.assertAlmostEqual(fused["b"], 0.5)   # lexical min, dense max
        self.assertAlmostEqual(fused["c"], 0.0)


class StatsTests(unittest.TestCase):
    def test_bootstrap_interval_contains_mean_and_detects_shift(self):
        values = {str(i): 0.5 + 0.01 * (i % 5) for i in range(40)}
        base = {q: v - 0.1 for q, v in values.items()}
        delta = paired_bootstrap(values, base, samples=2000)
        self.assertAlmostEqual(delta["mean"], 0.1)
        self.assertEqual(verdict(delta), "superior")
        noise = paired_bootstrap({q: (1 if int(q) % 2 else -1) * 0.1 for q in values}, samples=2000)
        self.assertEqual(verdict(noise), "inconclusivo")

    def test_percentile_interpolates(self):
        self.assertEqual(percentile([1, 2, 3, 4], 50), 2.5)


class MaxPTests(unittest.TestCase):
    def test_reduceat_takes_max_per_document(self):
        owner = np.array([0, 0, 1, 2, 2, 2])
        starts = np.flatnonzero(np.r_[True, owner[1:] != owner[:-1]])
        scores = np.array([0.1, 0.7, 0.3, 0.2, 0.9, 0.4])
        self.assertEqual(np.maximum.reduceat(scores, starts).tolist(), [0.7, 0.3, 0.9])
        self.assertEqual(scores[starts].tolist(), [0.1, 0.3, 0.2])


if __name__ == "__main__":
    unittest.main()
