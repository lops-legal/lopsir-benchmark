"""C2-M3 - Learned sparse retrieval (SPLADE) with a Portuguese checkpoint.

Method: SPLADE v2 (Formal et al., arXiv:2109.10086; SPLADE-v3 report arXiv:2403.06789),
framework github.com/naver/splade. Checkpoint: AxelPCG/splade-pt-br (BERTimbau base,
trained with the naver/splade recipe on mMARCO-pt, FLOPS regularization, max pooling,
max length 256; code github.com/AxelPCG/SPLADE-PT-BR), revision pinned below.

Representation: w_j = max_i log(1 + ReLU(MLM logit_ij)) over the passage tokens, one shared
encoder for queries and documents; score = dot product on the vocabulary dimensions.
Documents average ~1.5k tokens, longer than the 256-token limit, so each document is split
into consecutive 254-token windows; document score = max over its passages (MaxP) or first
passage only (FirstP), selected on dev. Runs locally on the GPU in fp32, no API.

Usage: python -m lopsir_c2.m3_splade --dataset juristcu
"""
import argparse
import json
import time

import numpy as np
import scipy.sparse as sp
import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer

from ..common import ARTIFACTS, dir_bytes, load_corpus, peak_rss_bytes
from ..harness import finalize, tune

METHOD_ID = "m3_splade"
MODEL_DIR = ARTIFACTS / "models" / "splade-pt-br"
MODEL = {"hf_id": "AxelPCG/splade-pt-br", "revision": "b44dd3d0336b5c386cccb5e76608348386768745",
         "base": "neuralmind/bert-base-portuguese-cased", "vocab": 29794, "max_length": 256}
WINDOW = 254  # 256 minus [CLS] and [SEP]
CARD = {
    "method_name": "SPLADE esparso aprendido (SPLADE-PT-BR, passagens + agregação no dev)",
    "advantage_hypothesis": "mais precisa no paradigma lexical: pesos e expansão aprendidos, ainda em índice invertido (H7)",
    "paper": "https://arxiv.org/abs/2109.10086",
    "additional_paper": "https://arxiv.org/abs/2403.06789",
    "code": "https://github.com/naver/splade",
    "checkpoint_code": "https://github.com/AxelPCG/SPLADE-PT-BR",
    "implementation": "transformers BertForMaskedLM + SPLADE max pooling re-implemented as in modeling_splade.py; scipy CSC inverted index",
    "models": MODEL, "api": None, "gpu": "local CUDA fp32 (GTX 1650 4 GB; fp16 measured 5x slower on this card)",
    "deviation_from_reference": "Checkpoint trained on general Portuguese QA (mMARCO), not on legal text; documents split into "
                                "254-token windows because of the 256-token limit; no pruning of document weights.",
}


class SpladeEncoder:
    def __init__(self, device):
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        # fp32 on purpose: on this GTX 1650 (TU117) fp16 matmul measured 0.34 TFLOPS vs 1.72 in fp32,
        # and BERT encoding ran at 7 vs 36 passages/s
        self.model = AutoModelForMaskedLM.from_pretrained(MODEL_DIR, dtype=torch.float32)
        self.model.to(device).eval()

    @torch.inference_mode()
    def encode_ids(self, batches_of_ids):
        """Encode lists of content token ids (each <= WINDOW) into a CSR matrix."""
        cls, sep, pad = self.tokenizer.cls_token_id, self.tokenizer.sep_token_id, self.tokenizer.pad_token_id
        width = max(len(ids) for ids in batches_of_ids) + 2
        input_ids = torch.full((len(batches_of_ids), width), pad, dtype=torch.long)
        mask = torch.zeros_like(input_ids)
        for row, ids in enumerate(batches_of_ids):
            seq = [cls] + ids + [sep]
            input_ids[row, :len(seq)] = torch.tensor(seq)
            mask[row, :len(seq)] = 1
        input_ids, mask = input_ids.to(self.device), mask.to(self.device)
        logits = self.model(input_ids=input_ids, attention_mask=mask).logits
        weights = torch.log1p(torch.relu(logits.float())) * mask.unsqueeze(-1)
        values = weights.max(dim=1).values.cpu().numpy()
        return sp.csr_matrix(values)

    def encode_texts(self, texts):
        ids = [self.tokenizer(t, add_special_tokens=False)["input_ids"][:WINDOW] for t in texts]
        return self.encode_ids(ids)


def build_index(encoder, corpus, batch_size, out_dir):
    """Encode all passages; shards make the job resumable. Returns (matrix CSC, passage->doc array)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / "passages.npz"
    if final.exists():
        return sp.load_npz(final).tocsc(), np.load(out_dir / "passage_doc.npy"), json.loads((out_dir / "build.json").read_text())
    started = time.perf_counter()
    windows, owner = [], []
    for index, doc in enumerate(corpus):
        ids = encoder.tokenizer(doc["text"], add_special_tokens=False)["input_ids"] or [encoder.tokenizer.unk_token_id]
        for start in range(0, len(ids), WINDOW):
            windows.append(ids[start:start + WINDOW])
            owner.append(index)
    tokenize_seconds = time.perf_counter() - started
    print(f"[{METHOD_ID}] {len(windows)} passages from {len(corpus)} documents ({tokenize_seconds:.0f}s)", flush=True)
    shard_size = 4096
    shards = out_dir / "shards"
    shards.mkdir(exist_ok=True)
    encode_started = time.perf_counter()
    # sort by length inside each shard so batches waste little padding
    for shard_start in range(0, len(windows), shard_size):
        path = shards / f"{shard_start:08d}.npz"
        if path.exists():
            continue
        block = windows[shard_start:shard_start + shard_size]
        order = sorted(range(len(block)), key=lambda i: len(block[i]))
        parts = [None] * len(block)
        for b in range(0, len(order), batch_size):
            rows = order[b:b + batch_size]
            matrix = encoder.encode_ids([block[i] for i in rows])
            for k, i in enumerate(rows):
                parts[i] = matrix[k]
        sp.save_npz(path, sp.vstack(parts).tocsr())
        done = min(shard_start + shard_size, len(windows))
        rate = done / (time.perf_counter() - encode_started)
        print(f"[{METHOD_ID}] encoded {done}/{len(windows)} passages, ETA {(len(windows) - done) / rate / 60:.1f} min", flush=True)
    matrix = sp.vstack([sp.load_npz(shards / f"{s:08d}.npz") for s in range(0, len(windows), shard_size)]).tocsr()
    matrix.eliminate_zeros()
    owner = np.asarray(owner, dtype=np.int32)
    info = {"passages": len(windows), "documents": len(corpus), "tokenize_seconds": tokenize_seconds,
            "encode_seconds": time.perf_counter() - encode_started, "nnz": int(matrix.nnz),
            "mean_active_dims_per_passage": matrix.nnz / matrix.shape[0], "batch_size": batch_size,
            "device": encoder.device}
    sp.save_npz(final, matrix)
    np.save(out_dir / "passage_doc.npy", owner)
    (out_dir / "build.json").write_text(json.dumps(info), encoding="utf-8")
    for shard in shards.glob("*.npz"):
        shard.unlink()
    shards.rmdir()
    return matrix.tocsc(), owner, info


class SpladeSearch:
    def __init__(self, encoder, passages, owner, doc_ids, aggregation):
        self.encoder, self.passages, self.owner = encoder, passages, owner
        self.doc_ids, self.aggregation = np.asarray(doc_ids), aggregation
        self.starts = np.flatnonzero(np.r_[True, owner[1:] != owner[:-1]])  # passages are contiguous per document
        self.cache = {}

    def __call__(self, text, timer):
        with timer.stage("encode_query"):
            query = self.encoder.encode_texts([text])
        with timer.stage("score"):
            columns = query.indices
            scores = np.asarray(self.passages[:, columns] @ query.data, dtype=np.float32).ravel()
            if self.aggregation == "maxp":
                doc_scores = np.maximum.reduceat(scores, self.starts)
            else:
                doc_scores = scores[self.starts]
        with timer.stage("rank"):
            k = min(100, len(doc_scores) - 1)
            top = np.argpartition(-doc_scores, k)[:k]
            top = top[np.argsort(-doc_scores[top], kind="stable")]
            return [(str(self.doc_ids[self.owner[self.starts[i]]]), float(doc_scores[i])) for i in top if doc_scores[i] > 0]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="juristcu")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    corpus = load_corpus(args.dataset)
    doc_ids = [d["doc_id"] for d in corpus]
    encoder = SpladeEncoder(device)
    index_dir = ARTIFACTS / "indexes" / args.dataset / METHOD_ID
    passages, owner, info = build_index(encoder, corpus, args.batch_size, index_dir)
    del corpus
    if np.any(np.diff(owner) < 0):
        raise ValueError("passages must be contiguous per document")
    grid = [{"aggregation": "maxp"}, {"aggregation": "firstp"}]
    rows = tune(lambda c: SpladeSearch(encoder, passages, owner, doc_ids, c["aggregation"]), grid, args.dataset, METHOD_ID,
                lambda c: c["aggregation"])
    best = rows[0]["config"]
    build_info = {**info, "index_bytes": dir_bytes(index_dir), "peak_vram_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None,
                  "peak_rss_bytes_after_build": peak_rss_bytes()}
    finalize(METHOD_ID, CARD, args.dataset, SpladeSearch(encoder, passages, owner, doc_ids, best["aggregation"]), best,
             dev_grid=rows, build_info=build_info, latency_rounds=5, usage={"api_requests": 0, "billed_usd": 0.0})


if __name__ == "__main__":
    main()
