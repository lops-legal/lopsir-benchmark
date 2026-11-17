"""C2-M0 - the user's leis-mcp search system on JurisTCU.

Same engine and configuration as leis-mcp (github.com/lops-legal/leis-mcp, commit 732bb6f): Manticore
with the libstemmer_pt analyzer, accents folded (non_cjk), exact words and prefixes indexed; ranker
10000*bm25f(1.2, 0.3) + 1000*sum(lcs*user_weight); the leis query syntax translator (consulta.traduzir,
with its legal vocabulary expansion); and its relaxed search (quorum 60% when the strict AND finds
fewer than 3 documents). JurisTCU has no norm-specific fields, so the per-field weights become
titulo=1, texto=1 and the code/alteradora bonuses do not apply. Nothing is tuned: the system is
measured as configured. Runs in a separate Manticore instance (MANTICORE_URL, default port 9318),
never in the leis production index.

Usage: python -m lopsir_c2.m0_leis --dataset juristcu
"""
import argparse
import os
import time

os.environ.setdefault("MANTICORE_URL", "http://127.0.0.1:9318")

from ..common import load_corpus  # noqa: E402
from ..harness import finalize  # noqa: E402
from ..leis import LEIS_SRC, leis_modules  # noqa: E402

busca, consulta_mod, manticore, _ = leis_modules()
from leis_mcp.schema import _OPCOES  # noqa: E402

METHOD_ID = "m0_leis"
TABLE = "bench_juristcu"
RANKER = "expr('10000*bm25f(1.2, 0.3) + 1000*sum(lcs*user_weight)')"
CARD = {
    "method_name": "M0 leis-mcp: Manticore BM25F + proximidade, sintaxe e busca relaxada do leis",
    "advantage_hypothesis": "o sistema de busca já em produção do usuário, medido no mesmo protocolo dos cinco métodos",
    "paper": "https://doi.org/10.1561/1500000019",
    "code": "https://github.com/lops-legal/leis-mcp",
    "implementation": "Manticore 9.3.2 (Windows nativo), configuração e tradutor de consulta do leis-mcp 732bb6f",
    "models": None, "api": None, "gpu": False,
    "deviation_from_reference": "Corpus do TCU sem campos de norma: pesos titulo=1, texto=1 e sem bônus de código, MP ou "
                                "lei alteradora. Instância Manticore separada da de produção.",
}


def create_index(corpus):
    manticore.sql(f"DROP TABLE IF EXISTS {TABLE}")
    manticore.sql(f"CREATE TABLE {TABLE} (titulo text, texto text, doc string) {_OPCOES}")
    started = time.perf_counter()
    for start in range(0, len(corpus), 500):
        manticore.bulk_replace(TABLE, [{"id": int(d["doc_id"]), "titulo": d["title"] or "", "texto": d["text"],
                                        "doc": d["doc_id"]} for d in corpus[start:start + 500]])
    manticore.sql(f"FLUSH RAMCHUNK {TABLE}")
    return time.perf_counter() - started


class LeisSearch:
    def __call__(self, text, timer):
        with timer.stage("translate"):
            expressao = consulta_mod.traduzir(text)
            sem_expansao = consulta_mod.traduzir(text, expandir=False)

        def executar(expr):
            return manticore.busca_com_total(
                f"SELECT id, doc, WEIGHT() AS relevancia FROM {TABLE} WHERE MATCH({manticore.quote(expr)}) LIMIT 100 "
                f"OPTION ranker={RANKER}, field_weights=(titulo=1, texto=1), max_matches=1000")

        with timer.stage("search"):
            linhas, _, _ = busca._com_relaxamento(expressao, executar, sem_expansao)
        seen, hits = set(), []
        for linha in linhas:
            if linha["doc"] not in seen:
                seen.add(linha["doc"])
                hits.append((linha["doc"], float(linha["relevancia"])))
        return hits


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="juristcu")
    args = parser.parse_args()
    corpus = load_corpus(args.dataset)
    build_seconds = create_index(corpus)
    status = {row["Variable_name"]: row["Value"] for row in manticore.sql(f"SHOW TABLE {TABLE} STATUS")}
    build_info = {"index_build_seconds": build_seconds, "index_bytes": int(status.get("disk_bytes", 0)),
                  "index_ram_bytes": int(status.get("ram_bytes", 0)), "documents": len(corpus),
                  "leis_src": str(LEIS_SRC), "manticore_url": os.environ["MANTICORE_URL"]}
    del corpus
    config = {"ranker": RANKER, "field_weights": "titulo=1, texto=1", "relaxed_quorum": busca.FRACAO_QUORUM,
              "min_strict_results": busca.MIN_RESULTADOS_ESTRITOS, "vocabulary_expansion": True}
    finalize(METHOD_ID, CARD, args.dataset, LeisSearch(), config, dev_grid=None, build_info=build_info,
             latency_rounds=5, usage={"api_requests": 0, "billed_usd": 0.0})


if __name__ == "__main__":
    main()
