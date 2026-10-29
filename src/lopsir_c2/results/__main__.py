"""Build the C2 comparison: summary.json, charts and RESULTS.md from every method's result.json.

Usage: python -m lopsir_c2.results --dataset juristcu
"""
import argparse
from datetime import datetime, timezone

from ..common import REPORTS, write_json
from ..harness import code_commit
from .charts import render_all
from .errors import write_errors
from .stats import MAIN, load_results, summarize

ADVANTAGE = {"m1_bm25": "mais barata", "m2_query2doc": "expansão por LLM", "m2_rm3_ablation": "expansão sem LLM",
             "m3_splade": "esparso aprendido", "m4_bgem3": "modelo único multilíngue", "m5_hybrid": "junta tudo",
             "m5_dense_reference": "ramo denso isolado"}


def fmt(value, digits=3):
    return "—" if value is None else f"{value:.{digits}f}"


def mib(value):
    return "—" if not value else f"{value / 2**20:,.0f}"


def table(summary):
    rows = summary["methods"]
    order = sorted(rows, key=lambda m: -rows[m]["test"]["ndcg_linear@10"])
    lines = ["| Metodologia | Vantagem testada | nDCG@10 [IC95] | Δ vs BM25 [IC95] | Veredito | P@10 | R@20 | R@100 | MRR@10 | p50 ponta a ponta (ms) | RAM pico (MiB) | Tokens API |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in order:
        r = rows[m]
        t = r["test"]
        ci = r["ndcg10_ci"]["ci95"]
        delta = r["delta_vs_bm25"]
        dtext = "—" if not delta else f"{delta['mean']:+.3f} [{delta['ci95'][0]:+.3f}, {delta['ci95'][1]:+.3f}]"
        latency = (r["latency_end_to_end_first_pass"] or {}).get("p50_ms")
        name = r["name"] if r["role"] == "main" else f"*{r['name']}*"
        lines.append(f"| {name} | {ADVANTAGE[m]} | {fmt(t['ndcg_linear@10'])} [{fmt(ci[0])}, {fmt(ci[1])}] | {dtext} | "
                     f"{r['verdict_vs_bm25'] or 'baseline'} | {fmt(t['precision@10'])} | {fmt(t['recall@20'])} | "
                     f"{fmt(t['recall@100'])} | {fmt(t['mrr@10'])} | {fmt(latency, 1)} | "
                     f"{mib((r['resources'] or {}).get('peak_rss_bytes'))} | {r['api_prompt_tokens']:,} |")
    return "\n".join(lines)


def origin_table(summary):
    rows = summary["methods"]
    order = sorted(rows, key=lambda m: -rows[m]["test"]["ndcg_linear@10"])
    lines = ["| Metodologia | Reais (n) | Sintéticas (n) |", "|---|---|---|"]
    for m in order:
        o = rows[m]["by_origin"]
        real, syn = o.get("real_keyword", {}), o.get("synthetic_keyword", {})
        lines.append(f"| {rows[m]['name']} | {fmt(real.get('ndcg10'))} ({real.get('n', 0)}) | {fmt(syn.get('ndcg10'))} ({syn.get('n', 0)}) |")
    return "\n".join(lines)


def cards(summary):
    rows = summary["methods"]
    parts = []
    for m in [x for x in MAIN if x in rows] + [x for x in rows if x not in MAIN]:
        r = rows[m]
        res = r["resources"] or {}
        stages = ", ".join(f"{k} {fmt(v.get('p50_ms'), 1)}" for k, v in (r["latency_stages_first_pass"] or {}).items())
        parts.append(f"### {r['name']}\n\n"
                     f"- **Método:** {r['method_name']}\n"
                     f"- **Hipótese de vantagem:** {r['advantage_hypothesis']}\n"
                     f"- **Artigo:** {r['paper']} · **Código:** {r['code'] or 'sem repositório oficial (ver ficha)'}\n"
                     f"- **Configuração congelada no dev:** `{r['config']}` ({r['configs_tried']} configurações testadas; dev nDCG@10 {fmt(r['dev_ndcg10'])})\n"
                     f"- **Teste:** nDCG@10 {fmt(r['test']['ndcg_linear@10'])}, nDCG@20 {fmt(r['test']['ndcg_linear@20'])}, "
                     f"P@20 {fmt(r['test']['precision@20'])}, Hit@1 {fmt(r['test']['hit@1'])}, Judged@10 {fmt(r['test']['judged_fraction@10'])}\n"
                     f"- **Latência p50 por etapa (1º passe, ms):** {stages or '—'}\n"
                     f"- **Recursos:** pico RAM {mib(res.get('peak_rss_bytes'))} MiB; índice {mib(res.get('index_bytes'))} MiB; "
                     f"VRAM {mib(res.get('peak_vram_bytes'))} MiB; requisições API {r['api_requests']}; custo faturado US$ {fmt(r['billed_usd'], 2)}\n")
    return "\n".join(parts)


def write_report(summary, charts, out):
    n = next(iter(summary["methods"].values()))["test_queries"]
    text = f"""# C2 — resultados comparativos (gerado)

Gerado em {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} a partir de `reports/c2/*/result.json`, commit `{(code_commit() or '')[:10]}`.
Conjunto: JurisTCU (EXCERTO, 16.045 documentos), **{n} consultas C2 de teste** (35 reais + 35 sintéticas), qrels 0–3 originais.
Configurações escolhidas só no dev (30 consultas) pela nDCG@10 e avaliadas uma vez no teste.
IC95%: bootstrap pareado, {summary['bootstrap']['resamples']:,} reamostragens de grupos de consulta, semente {summary['bootstrap']['seed']}.
Veredito contra o BM25: *superior/inferior* só quando o IC95% da diferença exclui zero; caso contrário *inconclusivo*.
Itálico = ablação ou referência, não conta entre as cinco metodologias.

## Quadro principal

{table(summary)}

![nDCG@10 com IC95%](charts/ndcg10_ci.png)

![Diferença contra o BM25](charts/delta_vs_bm25.png)

## Qualidade × latência

![Qualidade × latência](charts/quality_vs_latency.png)

## Cobertura

![Recall por corte](charts/recall_curve.png)

## Consultas reais × sintéticas

{origin_table(summary)}

![Por origem](charts/by_origin.png)

## Por tipo de consulta

![Por etiqueta](charts/by_label.png)

## Consulta a consulta

![Deltas por consulta](charts/per_query_delta.png)

## Análise de erros

Desacordo lexical × denso, maiores ganhos e perdas contra o BM25 e a tabela consulta × método: [ERRORS.md](ERRORS.md).

## Fichas resumidas

{cards(summary)}
"""
    (out / "RESULTS.md").write_text(text, encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="juristcu")
    args = parser.parse_args()
    summary = summarize(args.dataset)
    write_json(REPORTS / "summary.json", summary)
    charts = render_all(summary, load_results(args.dataset), REPORTS / "charts")
    write_report(summary, charts, REPORTS)
    write_errors(args.dataset, REPORTS)
    for _, r in sorted(summary["methods"].items(), key=lambda x: -x[1]["test"]["ndcg_linear@10"]):
        line = f"{r['name']:<28} nDCG@10 {r['test']['ndcg_linear@10']:.4f}"
        if r["delta_vs_bm25"]:
            d = r["delta_vs_bm25"]
            line += f"  delta {d['mean']:+.4f} [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}] {r['verdict_vs_bm25']}"
        print(line)


if __name__ == "__main__":
    main()
