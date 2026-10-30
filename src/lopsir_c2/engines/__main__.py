"""Engine track on JurisTCU: one method, several databases (SDD section 4.1, track B).

Lexical BM25, analyzer frozen by M1 (accents folded, no stemmer, Portuguese stopwords), k1=1.2 b=0.75,
OR semantics:
  bm25s (Python, eager sparse; the M1 run) · Manticore RT table · DuckDB FTS match_bm25
Dense, the same Nemotron 3.5 Embed 8B vectors (stored query vectors, so timings are "vectors ready"):
  numpy exact (the M5r run) · DuckDB exact array_cosine_similarity · DuckDB VSS HNSW (approximate)
Hybrid in one SQL statement: DuckDB BM25 + cosine with min-max convex fusion (alpha 0.2, frozen M5).

Per engine: test nDCG@10 and the other ranking metrics, ANN-recall against exact search, build time,
on-disk size, peak RSS, and per-query latency (warm-up on dev, 5 rounds on test). No tuning here.

Usage: python -m lopsir_c2.engines --dataset juristcu
"""
import argparse
import os
import time

import numpy as np

os.environ.setdefault("MANTICORE_URL", "http://127.0.0.1:9318")

from ..common import ARTIFACTS, REPORTS, StageTimer, dir_bytes, evaluate_run, load_corpus, load_queries, peak_rss_bytes, portuguese_stopwords, write_json, write_run  # noqa: E402
from ..harness import code_commit, measure_latency  # noqa: E402
from ..leis import leis_modules  # noqa: E402
from ..m1_bm25.bm25 import load_frozen  # noqa: E402
from ..m5_hybrid.__main__ import DenseIndex  # noqa: E402

K1, B, ALPHA, DEPTH = 1.2, 0.75, 0.2, 100
_, _, manticore, _ = leis_modules()


def timed(fn):
    start = time.perf_counter()
    value = fn()
    return value, time.perf_counter() - start


def evaluate(dataset, name, search):
    """Run test once for the ranking, then latency rounds; returns metrics and timings."""
    ranked, timer = {}, StageTimer()
    for query in load_queries(dataset, "C2", "test"):
        ranked[query["query_id"]] = search(query["text"], timer)[:DEPTH]
    path = REPORTS / "engines" / "runs" / f"{name}.tsv"
    write_run(path, ranked, DEPTH)
    metrics = evaluate_run(dataset, path, "test")["aggregate"]["overall"]["metrics"]
    latency = measure_latency(lambda text, t: search(text, t), dataset, rounds=5)
    print(f"[engines] {name}: nDCG@10={metrics['ndcg_linear@10']:.4f} p50={latency['total']['p50_ms']:.2f} ms", flush=True)
    return ranked, {"metrics": metrics, "latency": latency}


def overlap(approx, exact, k):
    values = [len(set(d for d, _ in approx[q][:k]) & set(d for d, _ in exact[q][:k])) / k for q in exact]
    return sum(values) / len(values)


# ---------------------------------------------------------------- Manticore

def manticore_bm25(corpus):
    stopfile = ARTIFACTS / "manticore" / "stopwords_pt.txt"
    stopfile.write_text("\n".join(sorted(portuguese_stopwords())), encoding="utf-8")
    table = "bench_juristcu_bm25"
    manticore.sql(f"DROP TABLE IF EXISTS {table}")
    manticore.sql(f"CREATE TABLE {table} (texto text, doc string) charset_table='non_cjk' morphology='none' "
                  f"stopwords='{stopfile.as_posix()}' index_field_lengths='1'")

    def load():
        for start in range(0, len(corpus), 500):
            manticore.bulk_replace(table, [{"id": int(d["doc_id"]), "texto": d["text"], "doc": d["doc_id"]}
                                           for d in corpus[start:start + 500]])
        manticore.sql(f"FLUSH RAMCHUNK {table}")
    _, seconds = timed(load)
    status = {r["Variable_name"]: r["Value"] for r in manticore.sql(f"SHOW TABLE {table} STATUS")}
    analyzer = load_frozen.__globals__["analyzer_from_name"]("fold=1-stem=0-stop=1")

    def search(text, timer):
        with timer.stage("search"):
            terms = analyzer(text)
            if not terms:
                return []
            rows = manticore.sql(
                f"SELECT doc, WEIGHT() AS w FROM {table} WHERE MATCH({manticore.quote(chr(34) + ' '.join(terms) + chr(34) + '/1')}) "
                f"LIMIT {DEPTH} OPTION ranker=expr('10000*bm25f({K1}, {B})'), max_matches=1000")
        return [(r["doc"], float(r["w"])) for r in rows]
    return search, {"build_seconds": seconds, "index_bytes": int(status.get("disk_bytes", 0)),
                    "engine": "Manticore 9.3.2 RT table (HTTP SQL)"}


# ---------------------------------------------------------------- DuckDB

def duckdb_database(corpus, dense):
    import duckdb
    path = ARTIFACTS / "duckdb" / "juristcu.duckdb"
    path.parent.mkdir(parents=True, exist_ok=True)
    for stale in (path, path.with_suffix(".duckdb.wal")):
        stale.unlink(missing_ok=True)
    con = duckdb.connect(str(path))
    for ext in ("fts", "vss"):
        con.install_extension(ext)
        con.load_extension(ext)
    con.execute("SET hnsw_enable_experimental_persistence = true")
    con.execute("CREATE TABLE docs (doc_id VARCHAR PRIMARY KEY, text VARCHAR)")
    con.executemany("INSERT INTO docs VALUES (?, ?)", [(d["doc_id"], d["text"]) for d in corpus])
    con.execute("CREATE TABLE pt_stopwords (sw VARCHAR)")
    con.executemany("INSERT INTO pt_stopwords VALUES (?)", [(w,) for w in sorted(portuguese_stopwords())])
    builds = {}
    _, builds["fts_seconds"] = timed(lambda: con.execute(
        "PRAGMA create_fts_index('docs', 'doc_id', 'text', stemmer='none', stopwords='pt_stopwords', "
        "ignore='[^a-z0-9]+', strip_accents=1, lower=1, overwrite=1)"))
    dim = dense.matrix.shape[1]
    con.execute(f"CREATE TABLE vecs (doc_id VARCHAR, v FLOAT[{dim}])")

    def load_vectors():
        batch = 1000
        for start in range(0, len(dense.doc_ids), batch):
            rows = [(d, v.tolist()) for d, v in zip(dense.doc_ids[start:start + batch], dense.matrix[start:start + batch])]
            con.executemany("INSERT INTO vecs VALUES (?, ?)", rows)
    _, builds["vectors_load_seconds"] = timed(load_vectors)
    _, builds["hnsw_seconds"] = timed(lambda: con.execute(
        "CREATE INDEX vecs_hnsw ON vecs USING HNSW (v) WITH (metric = 'cosine')"))
    con.execute("CHECKPOINT")
    builds["database_bytes"] = path.stat().st_size
    return con, dim, builds


def duckdb_searchers(con, dim, dense):
    bm25_sql = ("SELECT doc_id, score FROM (SELECT doc_id, fts_main_docs.match_bm25(doc_id, ?, k := 1.2, b := 0.75) AS score "
                "FROM docs) WHERE score IS NOT NULL ORDER BY score DESC, doc_id LIMIT ?")
    exact_sql = (f"SELECT doc_id, array_cosine_similarity(v, ?::FLOAT[{dim}]) AS s FROM vecs "
                 f"ORDER BY s DESC, doc_id LIMIT {DEPTH}")
    hnsw_sql = (f"SELECT doc_id, 1 - array_cosine_distance(v, ?::FLOAT[{dim}]) AS s FROM vecs "
                f"ORDER BY array_cosine_distance(v, ?::FLOAT[{dim}]) LIMIT {DEPTH}")
    hybrid_sql = f"""
        WITH lex AS (
            SELECT doc_id, score FROM (SELECT doc_id, fts_main_docs.match_bm25(doc_id, $q, k := 1.2, b := 0.75) AS score FROM docs)
            WHERE score IS NOT NULL ORDER BY score DESC LIMIT 1000),
        den AS (SELECT doc_id, array_cosine_similarity(v, $v::FLOAT[{dim}]) AS score FROM vecs ORDER BY score DESC LIMIT 1000),
        nlex AS (SELECT doc_id, (score - min(score) OVER ()) / nullif(max(score) OVER () - min(score) OVER (), 0) AS s FROM lex),
        nden AS (SELECT doc_id, (score - min(score) OVER ()) / nullif(max(score) OVER () - min(score) OVER (), 0) AS s FROM den)
        SELECT coalesce(nlex.doc_id, nden.doc_id) AS doc_id,
               {ALPHA} * coalesce(nden.s, 0) + {1 - ALPHA} * coalesce(nlex.s, 0) AS fused
        FROM nlex FULL OUTER JOIN nden ON nlex.doc_id = nden.doc_id
        ORDER BY fused DESC, doc_id LIMIT {DEPTH}"""

    def bm25(text, timer):
        with timer.stage("search"):
            return [(d, float(s)) for d, s in con.execute(bm25_sql, [text, DEPTH]).fetchall()]

    def vector(text):
        return dense.query_vector(text, live=False).astype(np.float32).tolist()

    def exact(text, timer):
        q = vector(text)
        with timer.stage("search"):
            return [(d, float(s)) for d, s in con.execute(exact_sql, [q]).fetchall()]

    def hnsw(text, timer):
        q = vector(text)
        with timer.stage("search"):
            return [(d, float(s)) for d, s in con.execute(hnsw_sql, [q, q]).fetchall()]

    def hybrid(text, timer):
        q = vector(text)
        with timer.stage("search"):
            return [(d, float(s)) for d, s in con.execute(hybrid_sql, {"q": text, "v": q}).fetchall()]
    return bm25, exact, hnsw, hybrid


def numpy_exact(dense):
    def search(text, timer):
        q = dense.query_vector(text, live=False)
        with timer.stage("search"):
            scores = dense.matrix @ q
            top = np.argpartition(-scores, DEPTH)[:DEPTH]
            top = top[np.argsort(-scores[top], kind="stable")]
            return [(str(dense.doc_ids[i]), float(scores[i])) for i in top]
    return search


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="juristcu")
    args = parser.parse_args()
    corpus = load_corpus(args.dataset)
    dense = DenseIndex(args.dataset)
    rows, runs = {}, {}

    bm25s_search, _, _ = load_frozen(args.dataset, corpus)
    runs["bm25s"], rows["lexical_bm25s"] = evaluate(args.dataset, "lexical_bm25s", bm25s_search)
    rows["lexical_bm25s"]["build"] = {"engine": "bm25s 0.3.16 (numpy)", "index_bytes": dir_bytes(ARTIFACTS / "indexes" / args.dataset / "m1_bm25")}

    search, info = manticore_bm25(corpus)
    runs["manticore"], rows["lexical_manticore"] = evaluate(args.dataset, "lexical_manticore", search)
    rows["lexical_manticore"]["build"] = info

    con, dim, builds = duckdb_database(corpus, dense)
    del corpus
    bm25, exact, hnsw, hybrid = duckdb_searchers(con, dim, dense)
    runs["duckdb_bm25"], rows["lexical_duckdb_fts"] = evaluate(args.dataset, "lexical_duckdb_fts", bm25)
    rows["lexical_duckdb_fts"]["build"] = {"engine": "DuckDB FTS match_bm25", "build_seconds": builds["fts_seconds"]}

    runs["numpy_exact"], rows["dense_numpy_exact"] = evaluate(args.dataset, "dense_numpy_exact", numpy_exact(dense))
    rows["dense_numpy_exact"]["build"] = {"engine": "numpy float32 matrix", "index_bytes": dense.matrix.nbytes}
    runs["duckdb_exact"], rows["dense_duckdb_exact"] = evaluate(args.dataset, "dense_duckdb_exact", exact)
    rows["dense_duckdb_exact"]["build"] = {"engine": "DuckDB array_cosine_similarity (scan)", "load_seconds": builds["vectors_load_seconds"]}
    runs["duckdb_hnsw"], rows["dense_duckdb_hnsw"] = evaluate(args.dataset, "dense_duckdb_hnsw", hnsw)
    rows["dense_duckdb_hnsw"]["build"] = {"engine": "DuckDB VSS HNSW (cosine)", "build_seconds": builds["hnsw_seconds"]}
    rows["dense_duckdb_hnsw"]["ann_recall_vs_exact"] = {f"@{k}": overlap(runs["duckdb_hnsw"], runs["numpy_exact"], k) for k in (10, 100)}
    runs["duckdb_hybrid"], rows["hybrid_duckdb_sql"] = evaluate(args.dataset, "hybrid_duckdb_sql", hybrid)
    rows["hybrid_duckdb_sql"]["build"] = {"engine": "DuckDB one SQL statement (FTS + cosine + convex fusion)", "alpha": ALPHA}
    rows["lexical_duckdb_fts"]["agreement_top10_vs_bm25s"] = overlap(runs["duckdb_bm25"], runs["bm25s"], 10)
    rows["lexical_manticore"]["agreement_top10_vs_bm25s"] = overlap(runs["manticore"], runs["bm25s"], 10)
    rows["dense_duckdb_exact"]["agreement_top10_vs_numpy"] = overlap(runs["duckdb_exact"], runs["numpy_exact"], 10)

    write_json(REPORTS / "engines" / "result.json", {
        "kind": "engine_track", "dataset": args.dataset, "code_commit": code_commit(),
        "duckdb_database_bytes": builds["database_bytes"], "peak_rss_bytes": peak_rss_bytes(),
        "notes": ["Lexical engines share k1/b and the M1 analyzer choice; tokenizers still differ (DuckDB FTS splits "
                  "numbers like 4.657/1942; Manticore and bm25s keep their own rules).",
                  "Dense timings use stored query vectors (vectors-ready timing); query encoding is reported in M5.",
                  "No configuration was tuned in this track."],
        "engines": rows})


if __name__ == "__main__":
    main()
