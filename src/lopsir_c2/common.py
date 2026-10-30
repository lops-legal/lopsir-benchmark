"""Shared plumbing for the five C2 methods: paths, canonical I/O, text analysis,
timing and resource accounting. Every method writes the same run/metrics contract."""
import hashlib
import json
import math
import re
import sys
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "c2"            # canonical data (ignored by Git)
ARTIFACTS = ROOT / "artifacts" / "c2"  # indexes, vectors, caches (ignored by Git)
REPORTS = ROOT / "reports" / "c2"      # versioned aggregated results

sys.path.insert(0, str(ROOT / "scripts"))
from evaluate import evaluate, load_inputs  # noqa: E402  shared evaluator, same conventions as C1

CUTOFFS = [1, 10, 20, 100]


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path, items):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def dataset_dir(name):
    return DATA / name


def load_corpus(name):
    return read_jsonl(dataset_dir(name) / "corpus.jsonl")


def load_queries(name, case_type="C2", split=None):
    items = read_jsonl(dataset_dir(name) / "queries.jsonl")
    return [q for q in items if q["case_type"] == case_type and (split is None or q["split"] == split)]


def split_view(name, case_type="C2", split=None):
    """Write the filtered queries/qrels pair that evaluate.py reads; returns both paths.
    evaluate.py rejects qrels of queries outside the view, so both are filtered together."""
    suffix = f"{case_type}-{split or 'all'}"
    queries = load_queries(name, case_type, split)
    keep = {q["query_id"] for q in queries}
    qpath = dataset_dir(name) / f"queries.{suffix}.jsonl"
    rpath = dataset_dir(name) / f"qrels.{suffix}.tsv"
    write_jsonl(qpath, queries)
    lines = (dataset_dir(name) / "qrels.tsv").read_text(encoding="utf-8").splitlines()
    kept = [lines[0]] + [line for line in lines[1:] if line.split("\t", 1)[0] in keep]
    rpath.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
    return qpath, rpath


# ---------------------------------------------------------------- text analysis

TOKEN = re.compile(r"\d+(?:[./-]\d+)*|[^\W\d_]+", re.UNICODE)
_STOPWORDS = None


def fold_accents(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def portuguese_stopwords():
    global _STOPWORDS
    if _STOPWORDS is None:
        import bm25s.stopwords as sw
        _STOPWORDS = frozenset(sw.STOPWORDS_PORTUGUESE)
    return _STOPWORDS


class Analyzer:
    """Lowercase, regex tokenization that keeps legal numbers (e.g. 4.657/1942) whole,
    optional accent folding, Portuguese stopwords and Snowball stemming.
    Numbers are never stemmed or folded."""

    def __init__(self, fold=True, stem=True, stopwords=True):
        self.fold, self.stem, self.stopwords = fold, stem, stopwords
        self._stemmer = None
        if stem:
            import Stemmer
            self._stemmer = Stemmer.Stemmer("portuguese")

    @property
    def name(self):
        return f"fold={int(self.fold)}-stem={int(self.stem)}-stop={int(self.stopwords)}"

    def __call__(self, text):
        tokens = TOKEN.findall(text.lower())
        if self.stopwords:
            stop = portuguese_stopwords()
            tokens = [t for t in tokens if t not in stop and fold_accents(t) not in stop]
        out = []
        for token in tokens:
            if token[0].isdigit():
                out.append(token)
                continue
            # fold before stemming so unaccented user typing ("fiscalizacao") and the
            # accented document form ("fiscalização") reach the same stem
            if self.fold:
                token = fold_accents(token)
            out.append(self._stemmer.stemWord(token) if self.stem else token)
        return out


# ---------------------------------------------------------------- runs and timing

def write_run(path, ranked, depth=100):
    """ranked: {query_id: [(doc_id, score), ...]} already sorted best-first."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("query_id\tdoc_id\trank\tscore\n")
        for qid, hits in ranked.items():
            seen = set()
            rank = 0
            for doc_id, score in hits:
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                rank += 1
                if rank > depth:
                    break
                handle.write(f"{qid}\t{doc_id}\t{rank}\t{float(score):.6f}\n")
    return path


class StageTimer:
    """Collects per-query latencies by stage, in milliseconds."""

    def __init__(self):
        self.samples = {}

    @contextmanager
    def stage(self, name):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.samples.setdefault(name, []).append((time.perf_counter() - start) * 1000)

    def summary(self):
        return {name: latency_summary(values) for name, values in self.samples.items()}


def percentile(values, q):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * q / 100
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def latency_summary(values):
    return {"n": len(values), "mean_ms": sum(values) / len(values) if values else None,
            "p50_ms": percentile(values, 50), "p95_ms": percentile(values, 95),
            "p99_ms": percentile(values, 99)}


def peak_rss_bytes():
    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", None) or info.rss


def dir_bytes(path):
    path = Path(path)
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.exists() else 0


# ---------------------------------------------------------------- evaluation

def evaluate_run(dataset, run_path, split, cutoffs=CUTOFFS, case_type="C2"):
    qpath, rpath = split_view(dataset, case_type, split)
    queries, qrels, runs = load_inputs(qpath, rpath, run_path)
    return evaluate(queries, qrels, runs, sorted(cutoffs))
