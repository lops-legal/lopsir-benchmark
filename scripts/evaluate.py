"""Evaluate one corpus/split using canonical queries JSONL, qrels TSV and run TSV.

Educational evaluator, linear nDCG. Not yet certified equivalent to the JUÁ scorer.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def rows(path, required):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not set(required).issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: missing columns {required}")
        return list(reader)


def load_inputs(queries_path, qrels_path, run_path):
    queries = {}
    for line in Path(queries_path).read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        qid = item.get("query_id")
        if not isinstance(qid, str) or not qid or qid in queries:
            raise ValueError("Query IDs must be unique nonempty strings")
        if item.get("case_type") not in {"C1", "C2", "C3", "mixed", "unclassified"}:
            raise ValueError(f"Unknown case_type for {qid}")
        queries[qid] = item
    if not queries:
        raise ValueError("No queries")
    qrels = defaultdict(dict)
    for row in rows(qrels_path, ["query_id", "doc_id", "relevance"]):
        qid, did = row["query_id"], row["doc_id"]
        rel = float(row["relevance"])
        if qid not in queries or not did or not math.isfinite(rel) or rel < 0:
            raise ValueError("Invalid qrel")
        if did in qrels[qid]:
            raise ValueError(f"Duplicate qrel pair: {qid}/{did}")
        qrels[qid][did] = rel
    runs, ranks = defaultdict(dict), defaultdict(set)
    for row in rows(run_path, ["query_id", "doc_id", "rank", "score"]):
        qid, did = row["query_id"], row["doc_id"]
        rank, score = int(row["rank"]), float(row["score"])
        if qid not in queries or not did or rank < 1 or not math.isfinite(score):
            raise ValueError("Invalid run row")
        if did in runs[qid] or rank in ranks[qid]:
            raise ValueError(f"Duplicate document or rank in run: {qid}/{did}")
        ranks[qid].add(rank)
        runs[qid][did] = rank
    ordered = {}
    for qid, hits in runs.items():
        if sorted(ranks[qid]) != list(range(1, len(hits) + 1)):
            raise ValueError(f"Run ranks must be contiguous from 1: {qid}")
        ordered[qid] = sorted(hits, key=hits.get)
    return queries, qrels, ordered


def metrics(rels, ranking, k, threshold=1):
    if k < 1 or threshold <= 0:
        raise ValueError("k and relevance threshold must be positive")
    if len(ranking) != len(set(ranking)):
        raise ValueError("Duplicate document in ranking")
    positives = {did for did, rel in rels.items() if rel >= threshold}
    if not positives:
        return None
    top = ranking[:k]
    hits = [int(did in positives) for did in top]
    count = sum(hits)
    ap_sum, seen = 0.0, 0
    first = 0.0
    for position, hit in enumerate(hits, 1):
        if hit:
            seen += 1
            ap_sum += seen / position
            if first == 0:
                first = 1 / position
    dcg = sum(rels.get(did, 0.0) / math.log2(i + 1) for i, did in enumerate(top, 1))
    ideal = sorted(rels.values(), reverse=True)[:k]
    idcg = sum(rel / math.log2(i + 1) for i, rel in enumerate(ideal, 1))
    return {"recall": count / len(positives), "precision": count / k,
            "hit": float(count > 0), "mrr": first,
            "ndcg_linear": dcg / idcg if idcg else 0.0,
            "ap_at_k_minrel": ap_sum / min(len(positives), k),
            "judged_fraction": sum(did in rels for did in top) / k}


def evaluate(queries, qrels, runs, cutoffs, threshold=1):
    per_query, buckets = {}, defaultdict(list)
    for qid, query in queries.items():
        scores = {}
        for k in cutoffs:
            result = metrics(qrels.get(qid, {}), runs.get(qid, []), k, threshold)
            if result is not None:
                scores.update({f"{name}@{k}": value for name, value in result.items()})
        eligible = bool(scores)
        per_query[qid] = {"case_type": query["case_type"], "eligible": eligible,
                          "returned": len(runs.get(qid, [])), "metrics": scores}
        if eligible:
            buckets["overall"].append(scores)
            buckets[query["case_type"]].append(scores)
    means = {}
    for name, values in buckets.items():
        means[name] = {"queries": len(values), "metrics": {
            key: sum(row[key] for row in values) / len(values) for key in values[0]}}
    return {"kind": "ranking_evaluation", "cutoffs": cutoffs,
            "conventions": {"ndcg_gain": "linear", "binary_threshold": threshold,
                            "ap_denominator": "min(total_positive_qrels,k)",
                            "unjudged": "zero", "missing_run": "zero_for_eligible_query",
                            "no_positive_qrels": "excluded_and_counted",
                            "judged_fraction_denominator": "k_even_if_fewer_results_returned"},
            "counts": {"queries": len(queries), "eligible": len(buckets.get("overall", [])),
                       "excluded_no_positive": sum(not x["eligible"] for x in per_query.values())},
            "aggregate": means, "per_query": per_query}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("queries", "qrels", "run", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--cutoffs", type=int, nargs="+", default=[10, 20])
    parser.add_argument("--threshold", type=float, default=1)
    args = parser.parse_args()
    try:
        if any(k < 1 for k in args.cutoffs) or not math.isfinite(args.threshold) or args.threshold <= 0:
            raise ValueError("Cutoffs and finite threshold must be positive")
        inputs = load_inputs(args.queries, args.qrels, args.run)
        result = evaluate(*inputs, sorted(set(args.cutoffs)), args.threshold)
        result["input_files"] = {name: str(getattr(args, name)) for name in ("queries", "qrels", "run")}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps(result["counts"], ensure_ascii=False))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(2, f"Invalid evaluation: {error}\n")


if __name__ == "__main__":
    main()
