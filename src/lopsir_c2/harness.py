"""Experiment harness shared by the five C2 methods.

A method exposes `search(text) -> [(doc_id, score), ...]` (best first) and may record
its own stages on the StageTimer it receives. The harness tunes on dev, freezes the
best configuration, evaluates it once on test, and writes one result file per method.
"""
import subprocess
import time
from datetime import datetime, timezone

from .common import REPORTS, ROOT, StageTimer, evaluate_run, latency_summary, load_queries, peak_rss_bytes, write_json, write_run

SELECTION_METRIC = "ndcg_linear@10"
DEPTH = 100


def code_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run_split(search, dataset, split, run_path, timer=None, depth=DEPTH):
    """Execute every query of a split once and write the run file."""
    timer = timer or StageTimer()
    ranked = {}
    for query in load_queries(dataset, "C2", split):
        start = time.perf_counter()
        hits = search(query["text"], timer)
        timer.samples.setdefault("total", []).append((time.perf_counter() - start) * 1000)
        ranked[query["query_id"]] = hits[:depth]
    write_run(run_path, ranked, depth)
    return ranked, timer


def measure_latency(search, dataset, rounds, warmup_split="dev"):
    """Warm up on dev queries (never test), then time the test queries for `rounds`
    full passes; returns the per-stage summary over all repetitions."""
    for query in load_queries(dataset, "C2", warmup_split):
        search(query["text"], StageTimer())
    timer = StageTimer()
    test_queries = load_queries(dataset, "C2", "test")
    for _ in range(rounds):
        for query in test_queries:
            start = time.perf_counter()
            search(query["text"], timer)
            timer.samples.setdefault("total", []).append((time.perf_counter() - start) * 1000)
    summary = timer.summary()
    total = timer.samples["total"]
    summary["qps_sequential"] = 1000 * len(total) / sum(total) if total else None
    summary["rounds"] = rounds
    summary["warmup"] = f"one pass over {warmup_split} queries"
    return summary


def tune(build_search, grid, dataset, method_id, label):
    """Evaluate every configuration on dev; return rows sorted best-first by the selection metric."""
    rows = []
    for config in grid:
        search = build_search(config)
        run_path = REPORTS / method_id / "runs" / f"dev-{label(config)}.tsv"
        run_split(search, dataset, "dev", run_path)
        result = evaluate_run(dataset, run_path, "dev")
        metrics = result["aggregate"]["overall"]["metrics"]
        rows.append({"config": config, "label": label(config), "dev": {k: metrics[k] for k in
                     ("ndcg_linear@10", "ndcg_linear@20", "precision@10", "recall@20", "recall@100", "mrr@10")}})
        print(f"[{method_id}] dev {label(config)}: nDCG@10={metrics['ndcg_linear@10']:.4f}", flush=True)
        run_path.unlink()  # dev runs of non-selected configs are not kept
    rows.sort(key=lambda row: row["dev"][SELECTION_METRIC], reverse=True)
    return rows


def finalize(method_id, card, dataset, search, config, *, dev_grid=None, build_info=None,
             latency_rounds=5, usage=None, extra=None, depth=DEPTH):
    """Run the frozen configuration on dev (kept) and once on test, then write result.json."""
    out = REPORTS / method_id
    runs, first_pass = {}, None
    for split in ("dev", "test"):
        path = out / "runs" / f"{split}.tsv"
        _, timer = run_split(search, dataset, split, path, depth=depth)
        runs[split] = evaluate_run(dataset, path, split)
        if split == "test":
            # for API-backed methods this is the only pass that pays the remote call (later passes hit caches)
            first_pass = timer.summary()
    latency = measure_latency(search, dataset, latency_rounds) if latency_rounds else None
    payload = {
        "kind": "c2_method_result", "method_id": method_id, **card,
        "dataset": dataset, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_commit": code_commit(),
        "selection": {"metric": SELECTION_METRIC, "split": "dev", "configs_tried": len(dev_grid or [])},
        "config_selected": config, "dev_grid": dev_grid,
        "dev": runs["dev"], "test": runs["test"],
        "latency": latency, "latency_first_pass_test": first_pass,
        "resources": {"peak_rss_bytes": peak_rss_bytes(), **(build_info or {})},
        "usage": usage, **(extra or {}),
    }
    write_json(out / "result.json", payload)
    test = runs["test"]["aggregate"]["overall"]["metrics"]
    print(f"[{method_id}] TEST nDCG@10={test['ndcg_linear@10']:.4f} P@10={test['precision@10']:.4f} "
          f"R@100={test['recall@100']:.4f}", flush=True)
    return payload


def latency_from_samples(values):
    return latency_summary(values)
