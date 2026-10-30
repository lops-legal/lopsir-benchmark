"""Engine track on the central corpus (leis-mcp acervo): the same BM25 in Manticore and in DuckDB.

M1 BM25 (k1=1.2, b=0.75, OR semantics, revoked items excluded) runs on the leis Manticore index
(reports/c2/leis/m1_bm25) and here on a DuckDB database built straight from the leis normalized JSONL
(read_json, no Python row loop) with the FTS extension: Portuguese Snowball stemmer and folded accents,
the same analyzer choice as the leis Manticore tables. Measures quality on the gold set, per-query
latency, build time and on-disk size. Dense search over the 358k documents is not run here (encoding
cost); that gap is covered by the JurisTCU engine track (reports/c2/engines).

Usage: python -m lopsir_c2.leis.engines
"""
import time
from pathlib import Path

from ..common import ARTIFACTS, REPORTS, StageTimer, evaluate_run, load_queries, peak_rss_bytes, portuguese_stopwords, write_json, write_run
from ..harness import code_commit
from .gold import TASKS
from .systems import DEPTH, collapse, plain_terms

NORMALIZED = Path.home() / "Nova pasta" / "leis-mcp" / ".local" / "normalizado"
DB = ARTIFACTS / "duckdb" / "leis.duckdb"
FIELDS = {"dispositivos": "'titulo', 'apelidos', 'ementa', 'rotulo', 'hierarquia', 'texto'",
          "precedentes": "'titulo', 'enunciado', 'texto'"}


def build(con):
    timings = {}
    con.execute("CREATE TABLE pt_stopwords (sw VARCHAR)")
    con.executemany("INSERT INTO pt_stopwords VALUES (?)", [(w,) for w in sorted(portuguese_stopwords())])
    for table, columns in (("dispositivos", "id, urn, chave_norma, artigo, titulo, apelidos, ementa, rotulo, hierarquia, texto, revogada"),
                           ("precedentes", "id, chave, tribunal, tipo, numero, titulo, enunciado, texto, revogada")):
        start = time.perf_counter()
        con.execute(f"CREATE TABLE {table} AS SELECT {columns} FROM read_json('{(NORMALIZED / f'{table}.jsonl').as_posix()}', "
                    f"format='newline_delimited', maximum_object_size=67108864)")
        timings[f"{table}_load_seconds"] = time.perf_counter() - start
        start = time.perf_counter()
        con.execute(f"PRAGMA create_fts_index('{table}', 'id', {FIELDS[table]}, stemmer='portuguese', "
                    f"stopwords='pt_stopwords', strip_accents=1, lower=1, overwrite=1)")
        timings[f"{table}_fts_seconds"] = time.perf_counter() - start
        timings[f"{table}_rows"] = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    con.execute("CHECKPOINT")
    return timings


def searcher(con):
    def search(task, query, timer):
        table = "precedentes" if task == "precedente" else "dispositivos"
        keys = ("tribunal, tipo, numero" if table == "precedentes" else "urn, chave_norma, artigo")
        tribunais = query.get("tribunais")
        where = " AND tribunal IN (" + ", ".join(f"'{t.upper()}'" for t in tribunais) + ")" if tribunais else ""
        terms = " ".join(plain_terms(query["text"]))
        with timer.stage("search"):
            rows = con.execute(
                f"SELECT {keys}, score FROM (SELECT *, fts_main_{table}.match_bm25(id, ?, k := 1.2, b := 0.75) AS score "
                f"FROM {table}) WHERE score IS NOT NULL AND NOT revogada{where} ORDER BY score DESC, id LIMIT 300",
                [terms]).fetchall()
        names = keys.split(", ") + ["relevancia"]
        rows = [dict(zip(names, r)) for r in rows]
        return [(key, float(row["relevancia"])) for key, row in collapse(task, rows)][:DEPTH]
    return search


def main():
    import duckdb
    DB.parent.mkdir(parents=True, exist_ok=True)
    for stale in (DB, Path(str(DB) + ".wal")):
        stale.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))
    # the machine has ~8 GB and other jobs running: cap DuckDB and let it spill to disk
    spill = ARTIFACTS / "duckdb" / "spill"
    spill.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET memory_limit = '2GB'; SET temp_directory = '{spill.as_posix()}'; SET threads = 4")
    con.install_extension("fts")
    con.load_extension("fts")
    timings = build(con)
    search = searcher(con)
    tasks = {}
    for task in TASKS:
        queries = load_queries(f"leis-{task}", "C2", "test")
        timer, ranked = StageTimer(), {}
        for repetition in range(3):
            for query in queries:
                start = time.perf_counter()
                hits = search(task, query, timer)
                timer.samples.setdefault("total", []).append((time.perf_counter() - start) * 1000)
                if repetition == 0:
                    ranked[query["query_id"]] = hits
        path = REPORTS / "leis" / "engines" / "runs" / f"duckdb_bm25-{task}.tsv"
        write_run(path, ranked, DEPTH)
        evaluation = evaluate_run(f"leis-{task}", path, "test", [1, 3, 10, 100])
        tasks[task] = {"metrics": evaluation["aggregate"]["overall"]["metrics"], "latency": timer.summary(), "rounds": 3}
        m = tasks[task]["metrics"]
        print(f"[leis-engines] duckdb_bm25 {task}: nDCG@10={m['ndcg_linear@10']:.3f} "
              f"p50={tasks[task]['latency']['total']['p50_ms']:.1f} ms", flush=True)
    write_json(REPORTS / "leis" / "engines" / "result.json", {
        "kind": "leis_engine_track", "code_commit": code_commit(), "engine": "DuckDB FTS (match_bm25)",
        "duckdb_version": duckdb.__version__, "database_bytes": DB.stat().st_size, "build": timings,
        "peak_rss_bytes": peak_rss_bytes(), "compare_with": "reports/c2/leis/m1_bm25 (same BM25 on Manticore)",
        "tasks": tasks})


if __name__ == "__main__":
    main()
