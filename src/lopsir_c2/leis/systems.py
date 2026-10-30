"""Retrieval systems over the leis-mcp acervo (Manticore at MANTICORE_URL, read-only queries).

M0  the leis system as served: busca.buscar_dispositivos / normas_candidatas / buscar_precedentes
M1  plain BM25 (bm25f k1=1.2, b=0.75 frozen from JurisTCU dev, uniform field weights, OR semantics)
M2  Query2doc: LLM pseudo-document terms OR'd with the query, same BM25 as M1
M3  SPLADE-PT-BR, M4 BGE-M3 (dense+sparse, w=0.5), M5 BM25+Nemotron 8B convex fusion: rerankers of
    the M1 top-100 candidates (JUA "rerank" protocol), because encoding 358k documents does not fit
    this machine's time budget. All configurations come frozen from JurisTCU; nothing is tuned here.
"""
import hashlib
import json
import re
import time

import numpy as np

from ..common import ARTIFACTS, portuguese_stopwords
from . import leis_modules
from .gold import dispositivo_key, precedente_key

busca, consulta_mod, manticore, apelidos = leis_modules()
quote = manticore.quote

DEPTH = 100
TEXT_CHARS = 1600
BM25_K1, BM25_B = 1.2, 0.75  # frozen M1 values from JurisTCU dev
UNIFORM = {"dispositivos": "titulo=1, apelidos=1, ementa=1, rotulo=1, hierarquia=1, texto=1",
           "precedentes": "titulo=1, enunciado=1, texto=1"}


def plain_terms(text, extra=""):
    """Content words of the query (leis syntax operators and quotes removed), stopwords out."""
    stop = portuguese_stopwords()
    words = re.findall(r"[^\W_]+", f"{text} {extra}".lower())
    return list(dict.fromkeys(w for w in words if w not in stop and len(w) > 1))


def key_of(task, row):
    if task == "precedente":
        return precedente_key(row["tribunal"], row["tipo"], row["numero"])
    norma = apelidos.chave_da_urn(row["urn"]) if "urn" in row else row["chave_norma"]
    return norma if task == "norma" else dispositivo_key(norma, row["artigo"])


def collapse(task, rows):
    """Keep the first (best) row per evaluation unit: sliced articles and norms collapse here."""
    seen, out = set(), []
    for row in rows:
        key = key_of(task, row)
        if key not in seen:
            seen.add(key)
            out.append((key, row))
    return out


# ---------------------------------------------------------------- M0: the leis system

def leis_system(task, query, timer):
    with timer.stage("search"):
        if task == "dispositivo":
            result = busca.buscar_dispositivos(consulta=query["text"], limite=DEPTH, max_por_norma=3)
            rows = result["resultados"]
        elif task == "norma":
            result = busca.normas_candidatas(consulta=query["text"], limite=DEPTH)
            rows = result["normas"]
        else:
            result = busca.buscar_precedentes(consulta=query["text"], tribunais=query.get("tribunais"), limite=DEPTH)
            rows = result["resultados"]
    timer.samples.setdefault("response_chars", []).append(len(json.dumps(result, ensure_ascii=False)))
    return [(key, 1.0 / rank) for rank, (key, _) in enumerate(collapse(task, rows), 1)]


def leis_system_norma_by_articles(query, timer):
    """The second norm mode of the leis benchmark: articles search with one article per norm."""
    with timer.stage("search"):
        result = busca.buscar_dispositivos(consulta=query["text"], limite=DEPTH, max_por_norma=1)
    timer.samples.setdefault("response_chars", []).append(len(json.dumps(result, ensure_ascii=False)))
    return [(key, 1.0 / rank) for rank, (key, _) in enumerate(collapse("norma", result["resultados"]), 1)]


# ---------------------------------------------------------------- M1/M2: BM25 on the same index

def bm25_rows(task, terms, tribunais=None, limit=300):
    if not terms:
        return []
    table = "precedentes" if task == "precedente" else "dispositivos"
    fields = ("id, chave, titulo, enunciado, tribunal, tipo, numero, texto" if table == "precedentes"
              else "id, urn, chave_norma, artigo, titulo, rotulo, texto")
    where = f"MATCH({quote(chr(34) + ' '.join(terms) + chr(34) + '/1')}) AND revogada = 0"
    if tribunais:
        where += f" AND tribunal IN ({', '.join(quote(t.upper()) for t in tribunais)})"
    return manticore.sql(
        f"SELECT {fields}, WEIGHT() AS relevancia FROM {table} WHERE {where} LIMIT {limit} "
        f"OPTION ranker=expr('10000*bm25f({BM25_K1}, {BM25_B})'), field_weights=({UNIFORM[table]}), "
        f"max_matches=1000", timeout=120)


def candidate_text(task, row):
    if task == "precedente":
        return f"{row['titulo']}. {row['enunciado']} {row['texto'][:TEXT_CHARS // 2]}"[:TEXT_CHARS]
    return f"{row['titulo']}. {row['rotulo']}. {row['texto']}"[:TEXT_CHARS]


class BM25:
    def __init__(self, expansion=None):
        self.expansion = expansion  # callable(text, timer) -> extra words, for Query2doc

    def candidates(self, task, query, timer):
        extra = ""
        if self.expansion:
            with timer.stage("llm_generate"):
                extra = self.expansion(query["text"])
        with timer.stage("search"):
            rows = bm25_rows(task, plain_terms(query["text"], extra), query.get("tribunais"))
        return collapse(task, rows)[:DEPTH]

    def __call__(self, task, query, timer):
        return [(key, float(row["relevancia"])) for key, row in self.candidates(task, query, timer)]


# ---------------------------------------------------------------- rerankers over M1 candidates

class VectorCache:
    """Embeddings of candidate texts keyed by text hash, persisted between runs."""

    def __init__(self, name):
        self.path = ARTIFACTS / "cache" / f"leis-{name}.npz"
        self.items = dict(np.load(self.path)) if self.path.exists() else {}

    @staticmethod
    def key(text):
        return hashlib.sha256(text.encode()).hexdigest()

    def missing(self, texts):
        return [t for t in dict.fromkeys(texts) if self.key(t) not in self.items]

    def put(self, texts, vectors):
        for text, vector in zip(texts, vectors):
            self.items[self.key(text)] = np.asarray(vector, dtype=np.float32)

    def get(self, text):
        return self.items[self.key(text)]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(self.path, **self.items)


def minmax(values):
    values = np.asarray(values, dtype=np.float64)
    low, high = values.min(), values.max()
    return (values - low) / (high - low) if high > low else np.ones_like(values)


class Rerank:
    """Score the M1 candidates with `score(query_text, candidate_texts, timer) -> array`.
    alpha=None: the reranker score alone; alpha=a: a*minmax(reranker) + (1-a)*minmax(BM25)."""

    def __init__(self, first_stage, score, alpha=None):
        self.first_stage, self.score, self.alpha = first_stage, score, alpha

    def __call__(self, task, query, timer):
        candidates = self.first_stage.candidates(task, query, timer)
        if not candidates:
            return []
        texts = [candidate_text(task, row) for _, row in candidates]
        plain = " ".join(plain_terms(query["text"])) or query["text"]
        scores = self.score(plain, texts, timer)
        if self.alpha is not None:
            with timer.stage("fuse"):
                bm25 = [float(row["relevancia"]) for _, row in candidates]
                scores = self.alpha * minmax(scores) + (1 - self.alpha) * minmax(bm25)
        order = sorted(range(len(candidates)), key=lambda i: (-scores[i], candidates[i][0]))
        return [(candidates[i][0], float(scores[i])) for i in order]


def nemotron_scorer(cache):
    from ..m5_hybrid.__main__ import normalize_rows
    from ..providers import embed_batch

    def score(query_text, texts, timer):
        with timer.stage("encode_candidates"):
            todo = cache.missing(texts)
            for start in range(0, len(todo), 32):
                chunk = todo[start:start + 32]
                cache.put(chunk, embed_batch("nemotron-3.5-embed-8b", chunk, "passage"))
        with timer.stage("encode_query"):
            q = normalize_rows(embed_batch("nemotron-3.5-embed-8b", [query_text], "query"))[0]
        with timer.stage("score"):
            return normalize_rows(np.stack([cache.get(t) for t in texts])) @ q
    return score


def splade_scorer():
    import torch
    from ..m3_splade.__main__ import SpladeEncoder
    encoder = SpladeEncoder("cuda" if torch.cuda.is_available() else "cpu")

    def score(query_text, texts, timer):
        with timer.stage("encode_candidates"):
            docs = encoder.encode_texts(texts)  # first 254 tokens, as FirstP
        with timer.stage("encode_query"):
            q = encoder.encode_texts([query_text])
        with timer.stage("score"):
            return np.asarray((docs @ q.T).todense()).ravel()
    return score


def bgem3_scorer(w_sparse=0.5, max_length=512):
    import torch
    from ..m4_bgem3.__main__ import load_model
    model = load_model("cuda:0" if torch.cuda.is_available() else "cpu")

    def lexical(q, d):
        return sum(w * d.get(t, 0.0) for t, w in q.items())

    def score(query_text, texts, timer):
        with timer.stage("encode_candidates"):
            docs = model.encode(texts, batch_size=4, max_length=max_length, return_dense=True, return_sparse=True)
        with timer.stage("encode_query"):
            q = model.encode([query_text], batch_size=1, max_length=256, return_dense=True, return_sparse=True)
        with timer.stage("score"):
            dense = docs["dense_vecs"] @ q["dense_vecs"][0]
            sparse = np.asarray([lexical(q["lexical_weights"][0], d) for d in docs["lexical_weights"]])
            return dense + w_sparse * sparse
    return score
