"""Run every system on the leis-mcp gold set and write reports/c2/leis/<system>/result.json.

Usage: python -m lopsir_c2.leis [--systems m0_leis m1_bm25 ...]
Requires the leis Manticore (MANTICORE_URL, default http://127.0.0.1:9308) with its index loaded.
"""
import argparse
import gc
import json
import time
from datetime import datetime, timezone

from ..common import REPORTS, StageTimer, evaluate_run, load_queries, write_json, write_run
from ..harness import code_commit
from ..providers import LEDGER, ChatCache, chat
from . import LEIS_REFERENCE
from .gold import TASKS, build
from .systems import (BM25, DEPTH, LeisCandidates, Rerank, VectorCache, bgem3_scorer, busca, leis_system,
                      leis_system_norma_by_articles, nemotron_scorer, splade_scorer)

CUTOFFS = [1, 3, 10, 100]
Q2D_LLM = "nemotron-3.5-lightning"
Q2D_INSTRUCTION = ("Escreva um trecho de legislação federal brasileira ou de precedente (súmula ou tese) que trate da "
                   "consulta, com a terminologia que costuma aparecer nesses textos. Responda apenas com o trecho, em um "
                   "parágrafo, sem título nem introdução.")

CARDS = {
    "m0_leis": "leis-mcp como servido (Manticore BM25F com pesos por campo, proximidade, bônus de códigos, sintaxe SCON, busca relaxada)",
    "m1_bm25": "BM25 (bm25f k1=1.2 b=0.75 congelado do JurisTCU, pesos uniformes, termos em OU) no mesmo índice",
    "m2_query2doc": "Query2doc: termos do pseudodocumento do Nemotron 3.5 Lightning em OU com a consulta, BM25 do M1",
    "m3_splade": "SPLADE-PT-BR reordenando os 100 primeiros do M1 (FirstP, 254 tokens)",
    "m4_bgem3": "BGE-M3 denso+esparso (peso 0,5 congelado do JurisTCU) reordenando os 100 primeiros do M1",
    "m5_hybrid": "Híbrido convexo M1 + Nemotron 8B, alfa 0,2 congelado no dev do JurisTCU, sobre os 100 primeiros do M1",
    "m5_hybrid_cv": "Híbrido convexo M1 + Nemotron 8B, alfa 0,8 indicado pela validação cruzada no JurisTCU",
    "m5_dense_reference": "Nemotron 8B denso puro reordenando os 100 primeiros do M1",
    "m0_m5_hybrid": "M0 leis + Nemotron 8B: fusão convexa (alfa 0,8 da validação cruzada) sobre os 100 primeiros do próprio leis",
    "m0_m5_hybrid_02": "M0 leis + Nemotron 8B: fusão convexa (alfa 0,2 congelado no dev) sobre os 100 primeiros do leis",
}


def query2doc_expansion():
    cache = ChatCache("query2doc-leis")

    def expand(text):
        return chat(Q2D_LLM, [{"role": "user", "content": f"{Q2D_INSTRUCTION}\n\nConsulta: {text}\nTrecho:"}],
                    max_tokens=128, cache=cache)
    return expand


def build_system(name):
    if name == "m0_leis":
        return lambda task, query, timer: leis_system(task, query, timer)
    if name == "m1_bm25":
        return BM25()
    if name == "m2_query2doc":
        return BM25(expansion=query2doc_expansion())
    if name == "m3_splade":
        return Rerank(BM25(), splade_scorer())
    if name == "m4_bgem3":
        return Rerank(BM25(), bgem3_scorer())
    cache = VectorCache("nemotron-3.5-embed-8b")
    alpha = {"m5_hybrid": 0.2, "m5_hybrid_cv": 0.8, "m5_dense_reference": None, "m0_m5_hybrid": 0.8, "m0_m5_hybrid_02": 0.2}[name]
    first = LeisCandidates() if name.startswith("m0_") else BM25()
    system = Rerank(first, nemotron_scorer(cache), alpha=alpha)
    system.cache = cache
    return system


def run_task(name, system, task, rounds, label=None):
    queries = load_queries(f"leis-{task}", "C2", "test")
    timer, ranked = StageTimer(), {}
    for repetition in range(rounds):
        for query in queries:
            start = time.perf_counter()
            hits = system(task, query, timer)
            timer.samples.setdefault("total", []).append((time.perf_counter() - start) * 1000)
            if repetition == 0:
                ranked[query["query_id"]] = hits[:DEPTH]
    path = REPORTS / "leis" / name / "runs" / f"{label or task}.tsv"
    write_run(path, ranked, DEPTH)
    evaluation = evaluate_run(f"leis-{task}", path, "test", CUTOFFS)
    latency = {k: v for k, v in timer.summary().items() if k != "response_chars"}
    if "response_chars" in timer.samples:
        chars = timer.samples["response_chars"]
        latency_extra = {"response_chars_mean": sum(chars) / len(chars), "response_tokens_mean": sum(chars) / len(chars) / 4}
    else:
        latency_extra = {}
    m = evaluation["aggregate"]["overall"]["metrics"]
    print(f"[leis:{name}] {label or task}: nDCG@10={m['ndcg_linear@10']:.3f} MRR@10={m['mrr@10']:.3f} "
          f"acerto@1={m['hit@1']:.2f} acerto@3={m['hit@3']:.2f} R@100={m['recall@100']:.2f}", flush=True)
    return {"evaluation": evaluation, "latency": latency, "rounds": rounds, **latency_extra}


def direct_lookups():
    """The leis gold set's consulta_direta (C1 identity lookups), scored as tests/metricas.py does."""
    from .systems import leis_modules
    busca_mod, _, _, _ = leis_modules()
    from leis_mcp import conferir
    reference = json.loads(LEIS_REFERENCE.read_text(encoding="utf-8"))["consulta_direta"]
    tools = {"obter_dispositivo": busca_mod.obter_dispositivo, "obter_precedente": busca_mod.obter_precedente,
             "conferir_citacoes": conferir.conferir_citacoes}
    rows = []
    for item in reference:
        times, result, error = [], None, None
        for _ in range(3):
            start = time.perf_counter()
            try:
                result = tools[item["tool"]](**item["args"])
            except Exception as exc:  # recorded, not raised
                error = f"{type(exc).__name__}: {exc}"
            times.append((time.perf_counter() - start) * 1000)
        text = json.dumps(result, ensure_ascii=False).lower() if result else ""
        rows.append({"tool": item["tool"], "args": item["args"], "hit@1": bool(not error and item["contem"].lower() in text),
                     "ms_median": sorted(times)[1], "error": error})
    return {"n": len(rows), "hit@1": sum(r["hit@1"] for r in rows) / len(rows), "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--systems", nargs="+", default=list(CARDS))
    args = parser.parse_args()
    build()
    for name in args.systems:
        LEDGER.reset()
        system = build_system(name)
        rounds = 3 if name in ("m0_leis", "m1_bm25", "m2_query2doc") else 1
        tasks = {task: run_task(name, system, task, rounds) for task in TASKS}
        extra = {}
        if name == "m0_leis":
            tasks["norma_por_artigos"] = run_task(name, lambda task, query, timer: leis_system_norma_by_articles(query, timer),
                                                  "norma", rounds, label="norma_por_artigos")
            extra["direct_lookups_c1"] = direct_lookups()
        if hasattr(system, "cache"):
            system.cache.save()
        write_json(REPORTS / "leis" / name / "result.json", {
            "kind": "leis_corpus_result", "system": name, "description": CARDS[name], "corpus": "leis-mcp acervo",
            "created_at_utc": datetime.now(timezone.utc).isoformat(), "code_commit": code_commit(),
            "candidate_depth": DEPTH, "cutoffs": CUTOFFS, "tasks": tasks,
            "usage": {"ledger": LEDGER.snapshot(), "billed_usd": 0.0}, **extra})
        del system
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except ImportError:
            pass


if __name__ == "__main__":
    main()
