"""Post-hoc diagnostic: nDCG@10 of the convex fusion as alpha goes from 0 (BM25 only) to 1
(dense only), on dev and on test. It is NOT used for selection (M5 stays frozen at the
dev choice); it shows whether the frozen alpha sits on a stable plateau or on a noisy peak.

Usage: python -m lopsir_c2.m5_hybrid.sensitivity --dataset juristcu
"""
import argparse
import json

from ..common import REPORTS, evaluate_run, write_json
from ..harness import run_split
from ..m1_bm25.bm25 import load_frozen
from .__main__ import DenseIndex, HybridSearch

ALPHAS = [round(0.1 * i, 1) for i in range(11)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="juristcu")
    args = parser.parse_args()
    bm25, _, _ = load_frozen(args.dataset)
    dense = DenseIndex(args.dataset)
    frozen = json.loads((REPORTS / "m5_hybrid" / "result.json").read_text(encoding="utf-8"))["config_selected"]
    rows = []
    for alpha in ALPHAS:
        search = HybridSearch(bm25, dense, "convex", 1000, alpha)  # stored query vectors, no API calls
        row = {"alpha": alpha}
        for split in ("dev", "test"):
            path = REPORTS / "m5_hybrid" / "runs" / f"sensitivity-{split}.tsv"
            run_split(search, args.dataset, split, path)
            row[split] = evaluate_run(args.dataset, path, split)["aggregate"]["overall"]["metrics"]["ndcg_linear@10"]
            path.unlink()
        rows.append(row)
        print(f"alpha={alpha}: dev {row['dev']:.4f} test {row['test']:.4f}", flush=True)
    write_json(REPORTS / "m5_hybrid" / "fusion_sensitivity.json", {
        "kind": "post_hoc_diagnostic_not_used_for_selection", "fusion": "convex min-max", "depth": 1000,
        "frozen_config": frozen, "alpha_meaning": "weight of the dense branch (0 = BM25 only, 1 = dense only)",
        "rows": rows})


if __name__ == "__main__":
    main()
