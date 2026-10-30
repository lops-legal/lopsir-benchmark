"""Error analysis for C2 on the test split: lexical/dense disagreement (as in JUA section 5.5),
largest gains and losses against BM25, and the full query x method table.

Only query ids, short keyword texts and labels are written; no document text is reproduced.
"""
from .stats import MAIN, SHORT, load_results, per_query, query_table

FAIL, SUCCEED = 0.1, 0.5  # nDCG@10 thresholds for "both fail" / "both succeed"


def disagreement(lexical, dense, margin=0.1):
    buckets = {"lexical_wins": [], "dense_wins": [], "both_fail": [], "both_succeed": [], "similar": []}
    for qid in lexical:
        a, b = lexical[qid], dense[qid]
        if a < FAIL and b < FAIL:
            buckets["both_fail"].append(qid)
        elif a >= SUCCEED and b >= SUCCEED:
            buckets["both_succeed"].append(qid)
        elif a - b >= margin:
            buckets["lexical_wins"].append(qid)
        elif b - a >= margin:
            buckets["dense_wins"].append(qid)
        else:
            buckets["similar"].append(qid)
    return buckets


def label_text(q):
    lab = q["labels"]
    tags = [{"short": "curta", "medium": "média", "long": "longa"}[lab["length"]]]
    tags += [name for key, name in (("multi_concept_e", "conjunção"), ("unaccented_typing", "sem acento"),
                                    ("cited_reference", "referência")) if lab[key]]
    return f"{'real' if q['origin'] == 'real_keyword' else 'sintética'}; " + ", ".join(tags)


def write_errors(dataset, out):
    results = load_results(dataset)
    if "m1_bm25" not in results:
        return None
    queries = query_table(dataset)
    scores = {m: per_query(r, "ndcg_linear@10") for m, r in results.items()}
    base = scores["m1_bm25"]
    order = sorted(base, key=int)
    lines = ["# C2 — análise de erros (teste, gerado)", "",
             "nDCG@10 por consulta de teste. Textos das consultas vêm do JurisTCU (palavras-chave curtas); nenhum trecho de documento é reproduzido.", ""]

    dense_key = next((m for m in ("m5_dense_reference", "m4_bgem3") if m in scores), None)
    if dense_key:
        b = disagreement(base, scores[dense_key])
        lines += [f"## Lexical (M1 BM25) × denso ({SHORT[dense_key]})", "",
                  f"Critério: ambos falham se os dois < {FAIL}; ambos acertam se os dois ≥ {SUCCEED}; vence quem supera o outro por ≥ 0,1.", "",
                  "| Situação | Consultas | % | Ids |", "|---|---|---|---|"]
        names = {"lexical_wins": "BM25 vence", "dense_wins": "denso vence", "both_fail": "ambos falham",
                 "both_succeed": "ambos acertam", "similar": "parecidos"}
        for key, ids in b.items():
            lines.append(f"| {names[key]} | {len(ids)} | {100 * len(ids) / len(base):.0f}% | {', '.join(sorted(ids, key=int))} |")
        for key in ("lexical_wins", "dense_wins", "both_fail"):
            if b[key]:
                lines += ["", f"**{names[key]}:** " + "; ".join(f"`{queries[q]['text']}` ({label_text(queries[q])})"
                                                               for q in sorted(b[key], key=int))]
        lines.append("")

    for m in [x for x in MAIN + ["m2_rm3_ablation", "m5_dense_reference"] if x in scores and x != "m1_bm25"]:
        deltas = sorted(((scores[m][q] - base[q], q) for q in base), reverse=True)
        lines += [f"## {SHORT[m]} contra o BM25", "", "| | Consulta | Tipo | BM25 | Método | Δ |", "|---|---|---|---|---|---|"]
        for tag, chunk in (("ganho", deltas[:5]), ("perda", list(reversed(deltas[-5:])))):
            for d, q in chunk:
                if (tag == "ganho" and d > 0) or (tag == "perda" and d < 0):
                    lines.append(f"| {tag} | `{queries[q]['text']}` | {label_text(queries[q])} | {base[q]:.2f} | {scores[m][q]:.2f} | {d:+.2f} |")
        lines.append("")

    methods = [m for m in MAIN + ["m2_rm3_ablation", "m5_dense_reference"] if m in scores]
    lines += ["## Tabela completa (nDCG@10)", "",
              "| Id | Consulta | Tipo | " + " | ".join(SHORT[m].split(" ")[0] for m in methods) + " | Melhor |",
              "|---|---|---|" + "---|" * len(methods) + "---|"]
    for q in order:
        row = [scores[m][q] for m in methods]
        best = max(row)
        winners = "/".join(SHORT[m].split(" ")[0] for m, v in zip(methods, row) if v == best and best > 0) or "nenhum"
        lines.append(f"| {q} | `{queries[q]['text']}` | {label_text(queries[q])} | " +
                     " | ".join(f"**{v:.2f}**" if v == best and best > 0 else f"{v:.2f}" for v in row) + f" | {winners} |")
    path = out / "ERRORS.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path
