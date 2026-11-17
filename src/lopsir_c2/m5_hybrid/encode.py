"""Encode corpus and C2 queries with a remote embedder into the resumable vector store.

Usage: python -m lopsir_c2.m5_hybrid.encode --dataset juristcu --embedder nemotron-3.5-embed-8b
"""
import argparse
import time

from ..common import REPORTS, load_corpus, read_jsonl, dataset_dir, write_json
from ..providers import LEDGER, EmbeddingStore


def encode(dataset, embedder, batch_size, workers):
    corpus = load_corpus(dataset)
    queries = [q for q in read_jsonl(dataset_dir(dataset) / "queries.jsonl") if q["case_type"] == "C2"]
    started = time.perf_counter()

    def progress(done, total, seconds):
        rate = done / seconds if seconds else 0
        print(f"[{embedder}] {done}/{total} docs  {seconds/60:.1f} min  ETA {((total - done) / rate / 60) if rate else 0:.1f} min", flush=True)

    query_store = EmbeddingStore(dataset, embedder, "queries-C2")
    query_store.build([q["query_id"] for q in queries], [q["text"] for q in queries], "query", batch_size=50, workers=1)
    doc_store = EmbeddingStore(dataset, embedder, "corpus")
    doc_store.build([d["doc_id"] for d in corpus], [d["text"] for d in corpus], "passage",
                    batch_size=batch_size, workers=workers, progress=progress)
    write_json(REPORTS / "usage" / f"encode-{dataset}-{embedder}.json", {
        "kind": "encoding_usage", "dataset": dataset, "embedder": embedder,
        "wall_seconds_this_session": time.perf_counter() - started, "ledger": LEDGER.snapshot(),
        "billed_usd": 0.0, "billing_note": "free-tier endpoint; tokens recorded from API usage field"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="juristcu")
    parser.add_argument("--embedder", default="nemotron-3.5-embed-8b")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    encode(args.dataset, args.embedder, args.batch_size, args.workers)


if __name__ == "__main__":
    main()
