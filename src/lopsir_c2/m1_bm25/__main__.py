"""C2-M1 - BM25 with analyzer and (k1, b) tuned on dev.

Paper: Robertson & Zaragoza, The Probabilistic Relevance Framework: BM25 and Beyond
(doi:10.1561/1500000019). Implementation: bm25s (arXiv:2407.03618,
github.com/xhluca/bm25s) with method="lucene", the scoring used by Lucene/Anserini,
which is the JUA "bm25/anserini" baseline. Pyserini was not used because Java is not
installed on the benchmark machine; this deviation is recorded in the result.

Usage: python -m lopsir_c2.m1_bm25 --dataset juristcu
"""
import argparse
import itertools
import shutil
import time

import bm25s
import numpy as np

from ..common import ARTIFACTS, Analyzer, dir_bytes, load_corpus, peak_rss_bytes
from ..harness import finalize, tune

METHOD_ID = "m1_bm25"
CARD = {
    "method_name": "BM25 ajustado (analisador PT + k1/b no dev)",
    "advantage_hypothesis": "mais barata: CPU, sem modelo, sem chave; baseline dificil de superar em C2 (H2)",
    "paper": "https://doi.org/10.1561/1500000019",
    "implementation_paper": "https://arxiv.org/abs/2407.03618",
    "code": "https://github.com/xhluca/bm25s",
    "implementation": f"bm25s {bm25s.__version__}, method=lucene, numpy backend, PyStemmer Snowball portuguese",
    "models": None, "api": None, "gpu": False,
    "deviation_from_reference": "JUA baseline uses Anserini (Lucene). bm25s reproduces Lucene BM25 scoring in Python; analyzers differ from Lucene's default Portuguese analyzer and are tuned here.",
}

ANALYZERS = [dict(fold=f, stem=s, stopwords=True) for f, s in itertools.product((True, False), repeat=2)]
K1 = [0.6, 0.9, 1.2, 1.5, 1.8]
B = [0.2, 0.4, 0.6, 0.75, 0.9, 1.0]


class BM25Search:
    def __init__(self, doc_ids, tokens, analyzer, k1, b):
        self.doc_ids = np.asarray(doc_ids)
        self.analyzer = analyzer
        started = time.perf_counter()
        self.index = bm25s.BM25(method="lucene", k1=k1, b=b)
        self.index.index(tokens, show_progress=False)
        self.index_seconds = time.perf_counter() - started

    def __call__(self, text, timer):
        with timer.stage("analyze"):
            query = self.analyzer(text)
        with timer.stage("score"):
            scores = self.index.get_scores(query)
        with timer.stage("rank"):
            top = np.argpartition(-scores, 100)[:100]
            top = top[np.argsort(-scores[top], kind="stable")]
            hits = [(self.doc_ids[i], float(scores[i])) for i in top if scores[i] > 0]
        return hits


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="juristcu")
    args = parser.parse_args()

    corpus = load_corpus(args.dataset)
    doc_ids, texts = [d["doc_id"] for d in corpus], [d["text"] for d in corpus]
    tokenized, analyze_seconds = {}, {}
    for options in ANALYZERS:
        analyzer = Analyzer(**options)
        started = time.perf_counter()
        tokenized[analyzer.name] = (analyzer, [analyzer(t) for t in texts])
        analyze_seconds[analyzer.name] = time.perf_counter() - started
        print(f"[{METHOD_ID}] tokenized corpus with {analyzer.name} in {analyze_seconds[analyzer.name]:.0f}s", flush=True)

    def build(config):
        analyzer, tokens = tokenized[config["analyzer"]]
        return BM25Search(doc_ids, tokens, analyzer, config["k1"], config["b"])

    grid = [{"analyzer": name, "k1": k1, "b": b} for name in tokenized for k1 in K1 for b in B]
    grid.append({"analyzer": "fold=1-stem=1-stop=1", "k1": 0.9, "b": 0.4})  # Anserini default, kept for reference
    rows = tune(build, grid, args.dataset, METHOD_ID, lambda c: f"{c['analyzer']}-k1={c['k1']}-b={c['b']}")
    best = rows[0]["config"]
    search = build(best)

    index_dir = ARTIFACTS / "indexes" / args.dataset / METHOD_ID
    shutil.rmtree(index_dir, ignore_errors=True)
    search.index.save(str(index_dir))
    build_info = {"corpus_analyze_seconds": analyze_seconds[best["analyzer"]], "index_build_seconds": search.index_seconds,
                  "index_bytes": dir_bytes(index_dir), "peak_rss_bytes_after_build": peak_rss_bytes()}
    finalize(METHOD_ID, CARD, args.dataset, search, best, dev_grid=rows, build_info=build_info, latency_rounds=5,
             usage={"api_requests": 0, "billed_usd": 0.0})


if __name__ == "__main__":
    main()
