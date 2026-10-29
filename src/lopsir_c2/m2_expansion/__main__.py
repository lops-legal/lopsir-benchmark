"""C2-M2 - Query expansion over the frozen M1 BM25.

Main line: Query2doc (Wang, Yang & Wei, arXiv:2303.07678). An LLM writes a pseudo-document
for the query; for sparse retrieval the query is repeated n times and concatenated with the
pseudo-document (paper section 3). No official code was released; the method is implemented
from the paper on top of bm25s. LLM: nvidia/nemotron-3.5-lightning-30b-a3b on the free NVIDIA
API Catalog (the OpenRouter :free mirror hit its 50 requests/day cap), thinking disabled, temperature 0 (deterministic; the paper samples), 128 new tokens as in
the paper. Prompt and few-shot policy are tuned on dev only.

Identified ablation: RM3 pseudo-relevance feedback (Abdul-Jaleel et al., UMass at TREC 2004;
reference implementation in Anserini/Pyserini, arXiv:2102.10073), no LLM and no API.

Usage: python -m lopsir_c2.m2_expansion --dataset juristcu
"""
import argparse
import time
from collections import Counter

import numpy as np

from ..common import dataset_dir, load_queries, read_jsonl
from ..harness import finalize, tune
from ..m1_bm25.bm25 import load_frozen
from ..providers import LEDGER, ChatCache, chat

LLM = "nemotron-3.5-lightning"
MAX_NEW_TOKENS = 128
INSTRUCTION = ("Escreva um trecho de jurisprudência do Tribunal de Contas da União (TCU) que trate da consulta, "
               "usando a terminologia jurídica que costuma aparecer nessas decisões. Responda apenas com o trecho, "
               "em um parágrafo, sem título nem introdução.")

Q2D_CARD = {
    "method_name": "Query2doc: expansão por pseudodocumento gerado por LLM + BM25",
    "advantage_hypothesis": "recall barato: reduz desencontro de vocabulário com ~1 chamada de LLM gratuita por consulta (H5)",
    "paper": "https://arxiv.org/abs/2303.07678",
    "code": None,
    "code_note": "no official repository; implemented from the paper over github.com/xhluca/bm25s (frozen M1 configuration)",
    "implementation": "bm25s lucene (M1 frozen) + NVIDIA API Catalog chat completions",
    "models": {"llm": "nvidia/nemotron-3.5-lightning-30b-a3b", "provider": "NVIDIA API Catalog", "reasoning": "disabled",
               "temperature": 0, "max_new_tokens": MAX_NEW_TOKENS},
    "api": {"provider": "NVIDIA API Catalog", "endpoint": "POST https://integrate.api.nvidia.com/v1/chat/completions",
            "key_env": "NVIDIA_API_KEY", "billing": "free trial endpoint",
            "note": "OpenRouter nvidia/nemotron-3.5-lightning:free was tried first and hit the free-model cap of "
                    "50 requests/day; its 54 expansions were discarded so every M2 number comes from one endpoint"},
    "gpu": False,
    "deviation_from_reference": "Portuguese legal prompt; temperature 0 instead of sampling; few-shot exemplars from dev "
                                "queries instead of MS MARCO; BM25 not retuned.",
}
RM3_CARD = {
    "method_name": "RM3 (ablação de M2): realimentação por pseudo-relevância sobre BM25",
    "advantage_hypothesis": "expansão sem LLM, sem chave e sem rede; controle do ganho atribuível ao LLM",
    "paper": "https://ciir.cs.umass.edu/pubfiles/ir-338.pdf",
    "implementation_paper": "https://arxiv.org/abs/2102.10073",
    "code": "https://github.com/castorini/anserini",
    "implementation": "RM3 re-implemented in Python over bm25s (Anserini formulation: fbDocs, fbTerms, originalQueryWeight)",
    "models": None, "api": None, "gpu": False, "ablation_of": "m2_query2doc",
    "deviation_from_reference": "Python re-implementation (no Java); weights from analyzed tokens of the frozen M1 analyzer.",
}


def few_shot_examples(dataset, k=4, chars=600):
    """Dev queries with one grade-3 document excerpt each; never test queries."""
    qrels = {}
    for line in (dataset_dir(dataset) / "qrels.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        qid, did, rel = line.split("\t")
        if rel == "3":
            qrels.setdefault(qid, did)
    texts = {d["doc_id"]: d["text"] for d in read_jsonl(dataset_dir(dataset) / "corpus.jsonl")}
    dev = sorted(load_queries(dataset, "C2", "dev"), key=lambda q: int(q["query_id"]))
    picked = [q for q in dev if q["query_id"] in qrels][: k + 1]
    return [(q["query_id"], q["text"], " ".join(texts[qrels[q["query_id"]]][:chars].split())) for q in picked]


class Query2doc:
    def __init__(self, bm25, prompt, repeat, examples, cache):
        self.bm25, self.prompt, self.repeat, self.examples, self.cache = bm25, prompt, repeat, examples, cache

    def messages(self, text):
        parts = [INSTRUCTION, ""]
        if self.prompt == "few4":
            shots = [e for e in self.examples if e[1] != text][:4]  # a dev query never sees itself
            for _, query, passage in shots:
                parts += [f"Consulta: {query}", f"Trecho: {passage}", ""]
        parts += [f"Consulta: {text}", "Trecho:"]
        return [{"role": "user", "content": "\n".join(parts)}]

    def __call__(self, text, timer):
        with timer.stage("llm_generate"):
            pseudo = chat(LLM, self.messages(text), max_tokens=MAX_NEW_TOKENS, cache=self.cache)
        with timer.stage("analyze"):
            terms = self.bm25.analyzer(" ".join([text] * self.repeat) + " " + pseudo)
        with timer.stage("score"):
            scores = self.bm25.scores(terms)
        with timer.stage("rank"):
            return self.bm25.top(scores)


class RM3:
    def __init__(self, bm25, doc_tokens, fb_docs, fb_terms, original_weight):
        self.bm25, self.doc_tokens = bm25, doc_tokens
        self.fb_docs, self.fb_terms, self.original_weight = fb_docs, fb_terms, original_weight

    def __call__(self, text, timer):
        with timer.stage("analyze"):
            query = self.bm25.analyzer(text)
        with timer.stage("first_pass"):
            first = self.bm25.scores(query)
            top = np.argsort(-first)[: self.fb_docs]
            top = top[first[top] > 0]
        with timer.stage("feedback"):
            relevance = Counter()
            if len(top):
                doc_weights = first[top] / first[top].sum()
                for index, weight in zip(top, doc_weights):
                    tokens = self.doc_tokens[index]
                    for term, count in Counter(tokens).items():
                        relevance[term] += weight * count / len(tokens)
            expansion = dict(relevance.most_common(self.fb_terms))
            norm = sum(expansion.values()) or 1.0
            weights = Counter()
            for term, count in Counter(query).items():
                weights[term] += self.original_weight * count / max(len(query), 1)
            for term, value in expansion.items():
                weights[term] += (1 - self.original_weight) * value / norm
        with timer.stage("score"):
            terms = list(weights)
            scores = self.bm25.scores(terms, [weights[t] for t in terms]) if terms else np.zeros(len(self.bm25.doc_ids))
        with timer.stage("rank"):
            return self.bm25.top(scores)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="juristcu")
    parser.add_argument("--only", choices=["rm3", "q2d"])
    args = parser.parse_args()

    started = time.perf_counter()
    bm25, doc_tokens, frozen = load_frozen(args.dataset)
    build_info = {"index_build_seconds": time.perf_counter() - started, "bm25_frozen_from_m1": frozen}

    if args.only != "q2d":
        grid = [{"fb_docs": d, "fb_terms": t, "original_weight": w}
                for d in (5, 10, 20) for t in (10, 20, 30) for w in (0.3, 0.5, 0.7)]
        label = lambda c: f"fbd={c['fb_docs']}-fbt={c['fb_terms']}-w={c['original_weight']}"
        rows = tune(lambda c: RM3(bm25, doc_tokens, **c), grid, args.dataset, "m2_rm3_ablation", label)
        best = rows[0]["config"]
        finalize("m2_rm3_ablation", RM3_CARD, args.dataset, RM3(bm25, doc_tokens, **best), best, dev_grid=rows,
                 build_info=build_info, latency_rounds=5, usage={"api_requests": 0, "billed_usd": 0.0})

    if args.only != "rm3":
        cache = ChatCache(f"query2doc-{args.dataset}")
        examples = few_shot_examples(args.dataset)
        grid = [{"prompt": p, "repeat": n} for p in ("zero", "few4") for n in (3, 5)]
        label = lambda c: f"{c['prompt']}-n={c['repeat']}"
        rows = tune(lambda c: Query2doc(bm25, c["prompt"], c["repeat"], examples, cache), grid, args.dataset,
                    "m2_query2doc", label)
        best = rows[0]["config"]
        finalize("m2_query2doc", Q2D_CARD, args.dataset, Query2doc(bm25, best["prompt"], best["repeat"], examples, cache),
                 best, dev_grid=rows, build_info=build_info, latency_rounds=1,
                 usage={"ledger": LEDGER.snapshot(), "billed_usd": 0.0,
                        "note": "free model; latency rounds after the first pass reuse cached expansions"},
                 extra={"few_shot_exemplar_query_ids": [e[0] for e in examples], "instruction": INSTRUCTION})


if __name__ == "__main__":
    main()
