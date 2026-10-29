"""C2-M4 - BGE-M3: one multilingual model producing dense vectors and lexical (sparse) weights.

Paper: M3-Embedding (Chen et al., arXiv:2402.03216). Code: github.com/FlagOpen/FlagEmbedding
(BGEM3FlagModel). Checkpoint BAAI/bge-m3 (XLM-RoBERTa large, 568M parameters), revision
pinned below, run locally on the GPU in fp32 (fp16 is ~5x slower on this GTX 1650).

The paper's hybrid retrieval scores s = w_dense * s_dense + w_sparse * s_lex (+ colbert).
Dense, sparse and dense+sparse (w_sparse grid) are compared on dev and the best is frozen.
The multi-vector (ColBERT) head is not used: storing token vectors for the corpus would need
tens of GB, beyond the machine budget; this is recorded as a deviation.

Usage: python -m lopsir_c2.m4_bgem3 --dataset juristcu --max-length 1024
"""
import argparse
import json
import time
from collections import defaultdict

import numpy as np
import scipy.sparse as sp
import torch

from ..common import ARTIFACTS, dir_bytes, load_corpus, load_queries, peak_rss_bytes
from ..harness import finalize, tune

METHOD_ID = "m4_bgem3"
MODEL_DIR = ARTIFACTS / "models" / "bge-m3"
MODEL = {"hf_id": "BAAI/bge-m3", "revision": "5617a9f61b028005a4858fdac845db406aefb181", "license": "MIT",
         "architecture": "XLM-RoBERTa large", "dense_dim": 1024, "vocab": 250002}
CARD = {
    "method_name": "BGE-M3 unificado (denso + pesos lexicais aprendidos, combinação no dev)",
    "advantage_hypothesis": "modelo único multilíngue: sinal lexical e semântico numa só passada, local e sem chave",
    "paper": "https://arxiv.org/abs/2402.03216",
    "code": "https://github.com/FlagOpen/FlagEmbedding",
    "models": MODEL, "api": None, "gpu": "local CUDA fp32 (GTX 1650 4 GB)",
    "deviation_from_reference": "ColBERT multi-vector head not used (corpus token vectors exceed disk/RAM budget); documents "
                                "truncated to --max-length tokens; dense+sparse weights tuned on dev instead of the paper defaults.",
}


def load_model(device):
    from FlagEmbedding import BGEM3FlagModel
    return BGEM3FlagModel(str(MODEL_DIR), use_fp16=False, devices=device)


def lexical_matrix(weights, vocab=MODEL["vocab"]):
    rows, cols, vals = [], [], []
    for row, item in enumerate(weights):
        for token, value in item.items():
            rows.append(row)
            cols.append(int(token))
            vals.append(float(value))
    return sp.csr_matrix((np.asarray(vals, dtype=np.float32), (rows, cols)), shape=(len(weights), vocab))


def encode_corpus(model, corpus, max_length, batch_size, out_dir):
    """Resumable corpus encoding; length-sorted so batches carry little padding."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "dense.npy").exists():
        return np.load(out_dir / "dense.npy"), sp.load_npz(out_dir / "lexical.npz"), json.loads((out_dir / "build.json").read_text())
    shards = out_dir / "shards"
    shards.mkdir(exist_ok=True)
    order = sorted(range(len(corpus)), key=lambda i: len(corpus[i]["text"]))
    shard_size, started = 1024, time.perf_counter()
    for start in range(0, len(order), shard_size):
        path = shards / f"{start:08d}.npz"
        if path.exists():
            continue
        ids = order[start:start + shard_size]
        out = model.encode([corpus[i]["text"] for i in ids], batch_size=batch_size, max_length=max_length,
                           return_dense=True, return_sparse=True, return_colbert_vecs=False)
        np.savez(path, ids=np.asarray(ids), dense=out["dense_vecs"].astype(np.float32))
        sp.save_npz(shards / f"{start:08d}.lex.npz", lexical_matrix(out["lexical_weights"]))
        done = min(start + shard_size, len(order))
        rate = done / (time.perf_counter() - started)
        print(f"[{METHOD_ID}] encoded {done}/{len(order)} docs, ETA {(len(order) - done) / rate / 60:.1f} min", flush=True)
    dense = np.zeros((len(corpus), MODEL["dense_dim"]), dtype=np.float32)
    lexical_rows = [None] * len(corpus)
    for start in range(0, len(order), shard_size):
        block = np.load(shards / f"{start:08d}.npz")
        lex = sp.load_npz(shards / f"{start:08d}.lex.npz").tocsr()
        dense[block["ids"]] = block["dense"]
        for k, i in enumerate(block["ids"]):
            lexical_rows[i] = lex[k]
    lexical = sp.vstack(lexical_rows).tocsr()
    info = {"max_length": max_length, "batch_size": batch_size, "encode_seconds": time.perf_counter() - started,
            "lexical_nnz": int(lexical.nnz), "mean_lexical_terms_per_doc": lexical.nnz / lexical.shape[0]}
    np.save(out_dir / "dense.npy", dense)
    sp.save_npz(out_dir / "lexical.npz", lexical)
    (out_dir / "build.json").write_text(json.dumps(info), encoding="utf-8")
    for shard in shards.glob("*.npz"):
        shard.unlink()
    shards.rmdir()
    return dense, lexical, info


class BGEM3Search:
    def __init__(self, model, dense, lexical_csc, doc_ids, mode, w_sparse, query_cache):
        self.model, self.dense, self.lexical = model, dense, lexical_csc
        self.doc_ids, self.mode, self.w_sparse, self.query_cache = np.asarray(doc_ids), mode, w_sparse, query_cache

    def encode(self, text):
        if text not in self.query_cache:
            out = self.model.encode([text], batch_size=1, max_length=256, return_dense=True, return_sparse=True)
            self.query_cache[text] = (out["dense_vecs"][0].astype(np.float32), out["lexical_weights"][0])
        return self.query_cache[text]

    def __call__(self, text, timer, use_cache=True):
        with timer.stage("encode_query"):
            if not use_cache:
                self.query_cache.pop(text, None)
            q_dense, q_lex = self.encode(text)
        with timer.stage("score"):
            scores = np.zeros(len(self.doc_ids), dtype=np.float32)
            if self.mode in ("dense", "dense+sparse"):
                scores += self.dense @ q_dense
            if self.mode in ("sparse", "dense+sparse") and q_lex:
                cols = np.asarray([int(t) for t in q_lex])
                vals = np.asarray(list(q_lex.values()), dtype=np.float32)
                weight = 1.0 if self.mode == "sparse" else self.w_sparse
                scores += weight * np.asarray(self.lexical[:, cols] @ vals).ravel()
        with timer.stage("rank"):
            top = np.argpartition(-scores, 100)[:100]
            top = top[np.argsort(-scores[top], kind="stable")]
            return [(str(self.doc_ids[i]), float(scores[i])) for i in top]


class Uncached:
    """Wrapper used for latency rounds so query encoding is paid on every call."""

    def __init__(self, search):
        self.search = search

    def __call__(self, text, timer):
        return self.search(text, timer, use_cache=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="juristcu")
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    model = load_model(device)
    corpus = load_corpus(args.dataset)
    doc_ids = [d["doc_id"] for d in corpus]
    out_dir = ARTIFACTS / "indexes" / args.dataset / METHOD_ID / f"len{args.max_length}"
    dense, lexical, info = encode_corpus(model, corpus, args.max_length, args.batch_size, out_dir)
    del corpus
    lexical = lexical.tocsc()
    cache = {}
    grid = [{"mode": "dense", "w_sparse": 0.0}, {"mode": "sparse", "w_sparse": 1.0}] + \
           [{"mode": "dense+sparse", "w_sparse": w} for w in (0.05, 0.1, 0.2, 0.3, 0.5)]
    label = lambda c: f"{c['mode']}-ws={c['w_sparse']}"
    rows = tune(lambda c: BGEM3Search(model, dense, lexical, doc_ids, c["mode"], c["w_sparse"], cache), grid,
                args.dataset, METHOD_ID, label)
    best = rows[0]["config"]
    search = BGEM3Search(model, dense, lexical, doc_ids, best["mode"], best["w_sparse"], cache)
    build_info = {**info, "index_bytes": dir_bytes(out_dir), "peak_rss_bytes_after_build": peak_rss_bytes(),
                  "peak_vram_bytes": torch.cuda.max_memory_allocated() if device.startswith("cuda") else None}
    finalize(METHOD_ID, CARD, args.dataset, Uncached(search), best, dev_grid=rows, build_info=build_info,
             latency_rounds=3, usage={"api_requests": 0, "billed_usd": 0.0})


if __name__ == "__main__":
    main()
