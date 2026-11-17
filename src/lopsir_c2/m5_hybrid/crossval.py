"""Exploratory 5-fold cross-validation of the convex fusion weight over all 100 C2 queries.

Each fold picks alpha on the other four folds (whole near-duplicate groups stay together) and
scores its own queries with that alpha; every query is thus scored by an alpha it did not help
choose. Repeated over several fold seeds. This uses test queries for tuning inside the CV, so
it is exploratory evidence for the next cycle, never a replacement for the frozen M5 result.

Usage: python -m lopsir_c2.m5_hybrid.crossval --dataset juristcu
"""
import argparse
import random
from collections import Counter

import numpy as np

from ..common import REPORTS, evaluate_run, load_queries, write_json
from ..harness import run_split
from ..m1_bm25.bm25 import load_frozen
from ..results.stats import paired_bootstrap
from .__main__ import DenseIndex, HybridSearch
from .sensitivity import ALPHAS

FOLDS, REPEATS = 5, 10


def per_query_scores(bm25, dense, dataset):
    """alpha -> {query_id: nDCG@10} over dev and test (stored query vectors, no API calls)."""
    table = {}
    for alpha in ALPHAS:
        search = HybridSearch(bm25, dense, "convex", 1000, alpha)
        scores = {}
        for split in ("dev", "test"):
            path = REPORTS / "m5_hybrid" / "runs" / f"crossval-{split}.tsv"
            run_split(search, dataset, split, path)
            per_query = evaluate_run(dataset, path, split)["per_query"]
            scores.update({q: row["metrics"]["ndcg_linear@10"] for q, row in per_query.items() if row["eligible"]})
            path.unlink()
        table[alpha] = scores
    return table


def cross_validate(table, groups, seed):
    keys = sorted(set(groups.values()))
    random.Random(seed).shuffle(keys)
    fold_of = {g: i % FOLDS for i, g in enumerate(keys)}
    held_out, chosen = {}, []
    for fold in range(FOLDS):
        train = [q for q in groups if fold_of[groups[q]] != fold]
        best = max(ALPHAS, key=lambda a: (np.mean([table[a][q] for q in train]), -a))
        chosen.append(best)
        held_out.update({q: table[best][q] for q in groups if fold_of[groups[q]] == fold})
    return held_out, chosen


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="juristcu")
    args = parser.parse_args()
    bm25, _, _ = load_frozen(args.dataset)
    table = per_query_scores(bm25, DenseIndex(args.dataset), args.dataset)
    groups = {q["query_id"]: q["group_id"] for q in load_queries(args.dataset, "C2")}
    bm25_only, dense_only = table[0.0], table[1.0]
    repeats, picks = [], Counter()
    for seed in range(REPEATS):
        held_out, chosen = cross_validate(table, groups, seed)
        picks.update(chosen)
        repeats.append({"seed": seed, "alphas_chosen": chosen, "ndcg10": float(np.mean(list(held_out.values()))),
                        "delta_vs_bm25": paired_bootstrap(held_out, bm25_only, groups),
                        "delta_vs_dense": paired_bootstrap(held_out, dense_only, groups)})
        print(f"seed {seed}: alphas {chosen} cv nDCG@10 {repeats[-1]['ndcg10']:.4f} "
              f"vs BM25 {repeats[-1]['delta_vs_bm25']['ci95']}", flush=True)
    write_json(REPORTS / "m5_hybrid" / "fusion_crossval.json", {
        "kind": "exploratory_cross_validation_uses_test_queries", "queries": len(groups), "folds": FOLDS,
        "repeats": REPEATS, "grouping": "near-duplicate group_id", "alpha_grid": ALPHAS,
        "alpha_meaning": "weight of the dense branch (0 = BM25 only, 1 = dense only)",
        "all_queries_fixed_alpha": {str(a): float(np.mean(list(table[a].values()))) for a in ALPHAS},
        "alpha_pick_counts": {str(a): picks[a] for a in ALPHAS if picks[a]},
        "cv_ndcg10_mean": float(np.mean([r["ndcg10"] for r in repeats])),
        "cv_ndcg10_sd": float(np.std([r["ndcg10"] for r in repeats])),
        "bm25_ndcg10_all": float(np.mean(list(bm25_only.values()))),
        "dense_ndcg10_all": float(np.mean(list(dense_only.values()))),
        "repeats_detail": repeats})


if __name__ == "__main__":
    main()
