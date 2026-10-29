"""C2-M5 - Hybrid lexical + dense retrieval with tuned fusion.

Paper: Bruch, Gai & Ingber, An Analysis of Fusion Functions for Hybrid Retrieval
(arXiv:2210.11934): compares Reciprocal Rank Fusion with a convex combination of
normalized scores and finds the tuned convex combination competitive or better.
Fusion functions follow the paper; github.com/AmenRa/ranx implements the same RRF/convex
fusions and is cited as public reference code (not imported).

Branches: lexical = frozen M1 BM25 configuration; dense = nvidia/nemotron-3.5-embed-8b
(NVIDIA API Catalog, free endpoint, 4096-d, input_type query/passage, truncate END) with
exact cosine scoring over the whole corpus (no ANN error). Fusion and depth tuned on dev.

Usage: python -m lopsir_c2.m5_hybrid --dataset juristcu
(run `python -m lopsir_c2.m5_hybrid.encode` first)
"""
import argparse
import time

import numpy as np

from ..common import load_queries
from ..harness import finalize, tune
from ..m1_bm25.bm25 import load_frozen
from ..providers import EMBEDDERS, LEDGER, EmbeddingStore, embed_batch

METHOD_ID = "m5_hybrid"
EMBEDDER = "nemotron-3.5-embed-8b"
CARD = {
    "method_name": "Híbrido BM25 + denso Nemotron 8B com fusão ajustada no dev (RRF ou convexa)",
    "advantage_hypothesis": "junta tudo: precisão lexical do BM25 com cobertura semântica do embedding (H3/H11)",
    "paper": "https://arxiv.org/abs/2210.11934",
    "code": "https://github.com/AmenRa/ranx",
    "code_note": "fusion functions re-implemented from the paper (RRF; min-max convex); ranx cited as reference implementation",
    "implementation": "bm25s lucene (M1 frozen) + exact cosine over NVIDIA embeddings",
    "models": {"dense": EMBEDDERS[EMBEDDER], "lexical": "frozen M1 BM25"},
    "api": {"provider": "NVIDIA API Catalog", "endpoint": "POST https://integrate.api.nvidia.com/v1/embeddings",
            "key_env": "NVIDIA_API_KEY", "billing": "free trial endpoint"},
    "gpu": False,
    "deviation_from_reference": "Fusion tuned on 30 dev queries; dense scoring exact (no ANN); Nemotron embedder replaces the "
                                "paper's encoders.",
}
DENSE_CARD = {
    "method_name": "Referência: denso Nemotron 8B puro (ramo denso do M5)",
    "advantage_hypothesis": "controle: mede o ramo semântico isolado para atribuir o ganho da fusão",
    "paper": "https://arxiv.org/abs/2210.11934", "code": "https://github.com/AmenRa/ranx",
    "models": {"dense": EMBEDDERS[EMBEDDER]}, "api": CARD["api"], "gpu": False, "ablation_of": METHOD_ID,
}


def normalize_rows(matrix):
    return matrix / np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)


class DenseIndex:
    def __init__(self, dataset):
        self.doc_ids, matrix = EmbeddingStore(dataset, EMBEDDER, "corpus").load()
        self.matrix = normalize_rows(matrix)
        q_ids, q_matrix = EmbeddingStore(dataset, EMBEDDER, "queries-C2").load()
        texts = {q["query_id"]: q["text"] for q in load_queries(dataset, "C2")}
        self.query_vectors = {texts[qid]: vec for qid, vec in zip(q_ids, normalize_rows(q_matrix))}

    def query_vector(self, text, live):
        if live or text not in self.query_vectors:
            return normalize_rows(embed_batch(EMBEDDER, [text], "query"))[0]
        return self.query_vectors[text]


def top_k(doc_ids, scores, k):
    k = min(k, len(scores) - 1)
    top = np.argpartition(-scores, k)[:k]
    top = top[np.argsort(-scores[top], kind="stable")]
    return [(str(doc_ids[i]), float(scores[i])) for i in top]


def rrf(lists, k):
    fused = {}
    for hits in lists:
        for rank, (doc_id, _) in enumerate(hits, 1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda item: -item[1])


def convex(lexical, dense, alpha):
    """alpha * minmax(dense) + (1 - alpha) * minmax(bm25); a document missing from one
    branch's candidate list gets that branch's normalized minimum (0)."""
    def minmax(hits):
        if not hits:
            return {}
        values = np.asarray([s for _, s in hits])
        low, high = values.min(), values.max()
        return {d: (s - low) / (high - low) if high > low else 1.0 for d, s in hits}
    lex, den = minmax(lexical), minmax(dense)
    fused = {d: alpha * den.get(d, 0.0) + (1 - alpha) * lex.get(d, 0.0) for d in set(lex) | set(den)}
    return sorted(fused.items(), key=lambda item: -item[1])


class HybridSearch:
    def __init__(self, bm25, dense, fusion, depth, param, live=False):
        self.bm25, self.dense, self.fusion, self.depth, self.param, self.live = bm25, dense, fusion, depth, param, live

    def __call__(self, text, timer):
        with timer.stage("lexical"):
            lexical = self.bm25.top(self.bm25.scores(self.bm25.analyzer(text)), self.depth) if self.fusion != "dense_only" else []
        with timer.stage("encode_query"):
            vector = self.dense.query_vector(text, self.live)
        with timer.stage("dense"):
            dense = top_k(self.dense.doc_ids, self.dense.matrix @ vector, self.depth)
        with timer.stage("fuse"):
            if self.fusion == "rrf":
                return rrf([lexical, dense], self.param)[:100]
            if self.fusion == "convex":
                return convex(lexical, dense, self.param)[:100]
            return dense[:100]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="juristcu")
    args = parser.parse_args()
    started = time.perf_counter()
    bm25, _, frozen = load_frozen(args.dataset)
    dense = DenseIndex(args.dataset)
    if [str(d) for d in bm25.doc_ids] != list(dense.doc_ids):
        raise ValueError("BM25 and dense indexes must share document order")
    build_info = {"index_build_seconds": time.perf_counter() - started, "bm25_frozen_from_m1": frozen,
                  "dense_matrix_bytes": dense.matrix.nbytes, "dense_shape": list(dense.matrix.shape)}

    grid = [{"fusion": "rrf", "depth": d, "param": k} for d in (100, 1000) for k in (10, 60, 100)]
    grid += [{"fusion": "convex", "depth": 1000, "param": a} for a in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
    label = lambda c: f"{c['fusion']}-depth={c['depth']}-p={c['param']}"
    build = lambda c: HybridSearch(bm25, dense, c["fusion"], c["depth"], c["param"])
    rows = tune(build, grid, args.dataset, METHOD_ID, label)
    best = rows[0]["config"]
    usage = lambda: {"ledger": LEDGER.snapshot(), "billed_usd": 0.0,
                     "note": "corpus/query vectors from the free NVIDIA endpoint; tuning reused stored query vectors, "
                             "the timed passes call the API for every query"}
    finalize(METHOD_ID, CARD, args.dataset, HybridSearch(bm25, dense, best["fusion"], best["depth"], best["param"], live=True),
             best, dev_grid=rows, build_info=build_info, latency_rounds=1, usage=usage)

    reference = {"fusion": "dense_only", "depth": 100, "param": None}
    finalize("m5_dense_reference", DENSE_CARD, args.dataset, HybridSearch(bm25, dense, "dense_only", 100, None, live=True),
             reference, build_info=build_info, latency_rounds=1, usage=usage)


if __name__ == "__main__":
    main()
