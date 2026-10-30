"""BM25 searcher shared by M1 and by the methods that build on the frozen M1 config (M2, M5)."""
import json
import time

import bm25s
import numpy as np

from ..common import REPORTS, Analyzer, load_corpus


def analyzer_from_name(name):
    """Inverse of Analyzer.name, e.g. 'fold=1-stem=0-stop=1'."""
    flags = dict(part.split("=") for part in name.split("-"))
    return Analyzer(fold=flags["fold"] == "1", stem=flags["stem"] == "1", stopwords=flags["stop"] == "1")


class BM25Search:
    def __init__(self, doc_ids, tokens, analyzer, k1, b):
        self.doc_ids = np.asarray(doc_ids)
        self.analyzer = analyzer
        started = time.perf_counter()
        self.index = bm25s.BM25(method="lucene", k1=k1, b=b)
        self.index.index(tokens, show_progress=False)
        self.index_seconds = time.perf_counter() - started

    def scores(self, terms, weights=None):
        """Score all documents; weighted queries are scored term by term."""
        if weights is None:
            return self.index.get_scores(terms)
        total = np.zeros(len(self.doc_ids), dtype=np.float32)
        for term, weight in zip(terms, weights):
            total += weight * self.index.get_scores([term])
        return total

    def top(self, scores, k=100):
        k = min(k, len(scores) - 1)
        top = np.argpartition(-scores, k)[:k]
        top = top[np.argsort(-scores[top], kind="stable")]
        return [(str(self.doc_ids[i]), float(scores[i])) for i in top if scores[i] > 0]

    def __call__(self, text, timer):
        with timer.stage("analyze"):
            query = self.analyzer(text)
        with timer.stage("score"):
            scores = self.scores(query)
        with timer.stage("rank"):
            return self.top(scores)


def load_frozen(dataset, corpus=None):
    """Rebuild the BM25 configuration frozen by M1 on dev."""
    config = json.loads((REPORTS / "m1_bm25" / "result.json").read_text(encoding="utf-8"))["config_selected"]
    corpus = corpus or load_corpus(dataset)
    analyzer = analyzer_from_name(config["analyzer"])
    tokens = [analyzer(d["text"]) for d in corpus]
    return BM25Search([d["doc_id"] for d in corpus], tokens, analyzer, config["k1"], config["b"]), tokens, config
