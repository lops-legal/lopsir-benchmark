"""Flat JSON tables for the results dashboard: one row per method, one row per test query."""
from ..common import write_json
from .stats import MAIN, SHORT, load_results, per_query, query_table

ADVANTAGE = {"m1_bm25": "mais barata", "m2_query2doc": "expansão por LLM", "m2_rm3_ablation": "expansão sem LLM",
             "m3_splade": "esparso aprendido", "m4_bgem3": "modelo único multilíngue", "m5_hybrid": "junta tudo",
             "m5_dense_reference": "ramo denso isolado", "m5_hybrid_1b_ablation": "encoder 8x menor",
             "m5_dense_1b_reference": "ramo denso 1B isolado"}


def method_rows(summary):
    rows = []
    for m, r in summary["methods"].items():
        t, ci, d = r["test"], r["ndcg10_ci"]["ci95"], r["delta_vs_bm25"]
        latency = r["latency_end_to_end_first_pass"] or {}
        rows.append({
            "method_id": m, "method": r["name"], "role": "principal" if r["role"] == "main" else "ablação",
            "advantage": ADVANTAGE[m], "ndcg10": t["ndcg_linear@10"], "ndcg10_low": ci[0], "ndcg10_high": ci[1],
            "delta": d["mean"] if d else 0.0, "delta_low": d["ci95"][0] if d else 0.0, "delta_high": d["ci95"][1] if d else 0.0,
            "verdict": r["verdict_vs_bm25"] or "baseline",
            "wins": (r["wins_ties_losses_vs_bm25"] or [0, 0, 0])[0], "losses": (r["wins_ties_losses_vs_bm25"] or [0, 0, 0])[2],
            "p10": t["precision@10"], "r20": t["recall@20"], "r100": t["recall@100"], "mrr10": t["mrr@10"], "hit1": t["hit@1"],
            "real_ndcg10": r["by_origin"].get("real_keyword", {}).get("ndcg10"),
            "synthetic_ndcg10": r["by_origin"].get("synthetic_keyword", {}).get("ndcg10"),
            "p50_ms": latency.get("p50_ms"), "p95_ms": latency.get("p95_ms"),
            "ram_mib": round((r["resources"] or {}).get("peak_rss_bytes", 0) / 2**20),
            "api_tokens": r["api_prompt_tokens"], "dev_ndcg10": r["dev_ndcg10"], "configs_tried": r["configs_tried"],
            "paper": r["paper"], "code": r["code"] or "",
        })
    return sorted(rows, key=lambda row: -row["ndcg10"])


def query_rows(dataset):
    results = load_results(dataset)
    queries = query_table(dataset)
    scores = {m: per_query(r, "ndcg_linear@10") for m, r in results.items()}
    methods = [m for m in MAIN + ["m2_rm3_ablation", "m5_dense_reference"] if m in scores]
    rows = []
    for qid in sorted(next(iter(scores.values())), key=int):
        q = queries[qid]
        row = {"query_id": qid, "query": q["text"], "origin": "real" if q["origin"] == "real_keyword" else "sintética"}
        for m in methods:
            row[SHORT[m].split(" ")[0]] = round(scores[m][qid], 4)
        rows.append(row)
    return rows


def export(summary, dataset, out):
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "methods.json", {"rows": method_rows(summary)})
    write_json(out / "per_query.json", {"rows": query_rows(dataset)})
    return out
