"""Mathematical evaluator checks; no fabricated legal research documents."""
import math
import unittest
from c1.results.metrics import ranking_metrics, summarize


class C1MetricsTest(unittest.TestCase):
    def test_multiple_positives_and_short_ranking(self):
        result=ranking_metrics(['a','b'],['x','b'])
        self.assertEqual(result['hit@1'],0)
        self.assertEqual(result['mrr@10'],0.5)
        self.assertEqual(result['recall@20'],0.5)
        self.assertEqual(result['precision@20'],0.05)
        self.assertAlmostEqual(result['ndcg@10'],(1/math.log2(3))/(1+1/math.log2(3)))

    def test_empty_run_is_zero_quality(self):
        self.assertTrue(all(v==0 for v in ranking_metrics(['a'],[]).values()))

    def test_failed_queries_stay_in_quality_denominator(self):
        rows=[{'status':'ok','query_ms':[1,2,3],'metrics':ranking_metrics(['a'],['a'])},
              {'status':'error','query_ms':[],'metrics':ranking_metrics(['b'],[])}]
        result=summarize(rows)
        self.assertEqual(result['failures'],1)
        self.assertEqual(result['quality']['hit@1'],0.5)
        self.assertEqual(result['measured_successful_calls'],3)
        self.assertEqual(result['latency_ms']['p50'],2)


if __name__=='__main__':unittest.main()
