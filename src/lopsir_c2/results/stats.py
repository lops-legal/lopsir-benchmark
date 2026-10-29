"""Collect method results and compute paired statistics on the test split."""
import json

import numpy as np

from ..common import REPORTS, dataset_dir, read_jsonl

MAIN = ["m1_bm25", "m2_query2doc", "m3_splade", "m4_bgem3", "m5_hybrid"]
ABLATIONS = ["m2_rm3_ablation", "m5_dense_reference"]
SHORT = {"m1_bm25": "M1 BM25", "m2_query2doc": "M2 Query2doc", "m2_rm3_ablation": "M2a RM3 (ablação)",
         "m3_splade": "M3 SPLADE-PT-BR", "m4_bgem3": "M4 BGE-M3", "m5_hybrid": "M5 Híbrido",
         "m5_dense_reference": "M5r Nemotron denso (ref.)"}
METRICS = ["ndcg_linear@10", "ndcg_linear@20", "precision@10", "precision@20", "recall@1", "recall@10", "recall@20",
           "recall@100", "mrr@10", "hit@1", "judged_fraction@10"]
BOOTSTRAP = 10_000
SEED = 42


def load_results(dataset):
    found = {}
    for method in MAIN + ABLATIONS:
        path = REPORTS / method / "result.json"
        if path.exists():
            result = json.loads(path.read_text(encoding="utf-8"))
            if result.get("dataset") == dataset:
                found[method] = result
    return found


def query_table(dataset):
    return {q["query_id"]: q for q in read_jsonl(dataset_dir(dataset) / "queries.jsonl") if q["case_type"] == "C2"}


def per_query(result, metric, split="test"):
    rows = result[split]["per_query"]
    return {qid: row["metrics"][metric] for qid, row in rows.items() if row["eligible"]}


def paired_bootstrap(values, baseline=None, groups=None, samples=BOOTSTRAP, seed=SEED):
    """95% percentile interval of the mean (or of the mean paired difference),
    resampling whole query groups so near-duplicates move together."""
    qids = sorted(values)
    diff = np.asarray([values[q] - (baseline[q] if baseline else 0.0) for q in qids])
    group_of = [groups.get(q, q) if groups else q for q in qids]
    unique = sorted(set(group_of))
    members = [np.asarray([i for i, g in enumerate(group_of) if g == u]) for u in unique]
    rng = np.random.default_rng(seed)
    means = np.empty(samples)
    for s in range(samples):
        picked = rng.integers(0, len(unique), len(unique))
        idx = np.concatenate([members[p] for p in picked])
        means[s] = diff[idx].mean()
    low, high = np.percentile(means, [2.5, 97.5])
    return {"mean": float(diff.mean()), "ci95": [float(low), float(high)], "n": len(qids), "groups": len(unique),
            "resamples": samples}


def verdict(delta):
    low, high = delta["ci95"]
    if low > 0:
        return "superior"
    if high < 0:
        return "inferior"
    return "inconclusivo"


def summarize(dataset):
    results = load_results(dataset)
    queries = query_table(dataset)
    groups = {qid: q["group_id"] for qid, q in queries.items()}
    base = per_query(results["m1_bm25"], "ndcg_linear@10") if "m1_bm25" in results else None
    rows = {}
    for method, result in results.items():
        overall = result["test"]["aggregate"]["overall"]["metrics"]
        ndcg = per_query(result, "ndcg_linear@10")
        delta = paired_bootstrap(ndcg, base, groups) if base and method != "m1_bm25" else None
        wins = ties = losses = 0
        if base and method != "m1_bm25":
            for qid, value in ndcg.items():
                d = value - base[qid]
                wins, ties, losses = wins + (d > 1e-9), ties + (abs(d) <= 1e-9), losses + (d < -1e-9)
        latency = result.get("latency_first_pass_test") or {}
        rounds = result.get("latency") or {}
        by_origin, by_label = {}, {}
        for qid, value in ndcg.items():
            q = queries[qid]
            by_origin.setdefault(q["origin"], []).append(value)
            labels = q["labels"]
            for key in ("multi_concept_e", "unaccented_typing", "cited_reference"):
                if labels[key]:
                    by_label.setdefault(key, []).append(value)
            by_label.setdefault(f"length_{labels['length']}", []).append(value)
        usage = result.get("usage") or {}
        tokens = sum(v.get("prompt_tokens", 0) for v in (usage.get("ledger") or {}).values())
        rows[method] = {
            "name": SHORT[method], "role": "main" if method in MAIN else "ablation",
            "method_name": result.get("method_name"), "advantage_hypothesis": result.get("advantage_hypothesis"),
            "paper": result.get("paper"), "code": result.get("code"), "config": result.get("config_selected"),
            "configs_tried": result["selection"]["configs_tried"],
            "dev_ndcg10": result["dev"]["aggregate"]["overall"]["metrics"]["ndcg_linear@10"],
            "test": {m: overall.get(m) for m in METRICS},
            "test_queries": result["test"]["counts"]["eligible"],
            "ndcg10_ci": paired_bootstrap(ndcg, None, groups),
            "delta_vs_bm25": delta, "verdict_vs_bm25": verdict(delta) if delta else None,
            "wins_ties_losses_vs_bm25": [wins, ties, losses] if delta else None,
            "by_origin": {k: {"n": len(v), "ndcg10": float(np.mean(v))} for k, v in sorted(by_origin.items())},
            "by_label": {k: {"n": len(v), "ndcg10": float(np.mean(v))} for k, v in sorted(by_label.items())},
            "latency_end_to_end_first_pass": latency.get("total"),
            "latency_stages_first_pass": {k: v for k, v in latency.items() if k != "total"},
            "latency_repeated": rounds.get("total") if rounds else None,
            "qps_sequential": rounds.get("qps_sequential") if rounds else None,
            "resources": result.get("resources"), "api_prompt_tokens": tokens,
            "api_requests": sum(v.get("requests", 0) for v in (usage.get("ledger") or {}).values()),
            "billed_usd": usage.get("billed_usd"),
        }
    return {"dataset": dataset, "split": "test", "bootstrap": {"resamples": BOOTSTRAP, "seed": SEED, "unit": "query group"},
            "methods": rows}
