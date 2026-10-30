"""Central C2 benchmark report: the leis-mcp acervo is the benchmark; JurisTCU covers its gaps.

Reads reports/c2/leis/*/result.json (central), reports/c2/leis/engines (central engine track),
reports/c2/summary.json and reports/c2/engines (JurisTCU, auxiliary) and writes
reports/c2/BENCHMARK.md plus charts under reports/c2/charts/leis_*.png.

Usage: python -m lopsir_c2.results.benchmark
"""
import json

import numpy as np

from ..common import REPORTS
from ..harness import code_commit
from .charts import INK, INK2, SEQUENTIAL, SERIES, SURFACE, ABLATION, footnote, save, style
from .stats import paired_bootstrap, verdict

SYSTEMS = ["m0_leis", "m1_bm25", "m2_query2doc", "m3_splade", "m4_bgem3", "m5_hybrid", "m5_hybrid_cv", "m5_dense_reference", "m0_m5_hybrid", "m0_m5_hybrid_02"]
NAMES = {"m0_leis": "M0 leis-mcp", "m1_bm25": "M1 BM25", "m2_query2doc": "M2 Query2doc", "m3_splade": "M3 SPLADE-PT-BR",
         "m4_bgem3": "M4 BGE-M3", "m5_hybrid": "M5 Híbrido (α 0,2)", "m5_hybrid_cv": "M5 Híbrido (α 0,8, CV)",
         "m5_dense_reference": "M5r Nemotron denso", "m0_m5_hybrid": "M0 leis + Nemotron (α 0,8)",
         "m0_m5_hybrid_02": "M0 leis + Nemotron (α 0,2)"}
TASK_NAMES = {"dispositivo": "Dispositivo (artigo)", "norma": "Norma", "precedente": "Precedente"}
COLUMNS = [("ndcg_linear@10", "nDCG@10"), ("mrr@10", "MRR@10"), ("ap_at_k_minrel@10", "MAP@10"), ("recall@10", "R@10"),
           ("hit@1", "acerto@1"), ("hit@3", "acerto@3"), ("hit@10", "acerto@10"), ("recall@100", "R@100"),
           ("precision@10", "P@10")]

METRIC_SOURCES = [
    ("nDCG@10", "JUÁ (Tabela 2), BEIR", "leis (binário)", "TCU: relevância graduada 0–3"),
    ("MRR@10", "JUÁ (Figuras), leis METRICAS", "leis", "TCU"),
    ("MAP@10", "JUÁ (Figuras)", "leis", "TCU"),
    ("Recall@10", "JUÁ (Figuras)", "leis", "TCU"),
    ("acerto@1 / @3 / @10", "leis METRICAS", "leis", "TCU (Hit@1)"),
    ("Recall@100, P@10", "BEIR, SDD §2.2", "leis (R@100 dentro de 100 candidatos)", "TCU"),
    ("Judged@10", "SDD §2.2", "— (gabarito com 1–3 positivos)", "TCU"),
    ("IC95 pareado (bootstrap)", "SDD §13", "leis (53 consultas agregadas)", "TCU (70 consultas)"),
    ("Latência p50/p95/p99, QPS", "SDD §13, leis METRICAS", "leis", "TCU"),
    ("Tamanho da resposta (tokens)", "leis METRICAS", "leis (M0)", "—"),
    ("Consultas diretas (C1)", "leis METRICAS", "leis (M0)", "—"),
    ("Tempo de construção, bytes de índice, RAM", "SDD §5.3 (R06, R09)", "leis (Manticore × DuckDB)", "TCU (todos os motores)"),
    ("ANN-recall@k", "SDD §2.2", "— (sem denso no corpus inteiro)", "TCU (DuckDB HNSW × exato)"),
    ("Ajuste em dev / validação cruzada", "SDD §6.6, §9", "— (só teste)", "TCU (dev 30 + CV 100)"),
]


def load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def fmt(value, digits=3):
    return "—" if value is None else f"{value:.{digits}f}".replace(".", ",")


def pct(value):
    return "—" if value is None else f"{100 * value:.0f}%"


def central_results():
    return {s: r for s in SYSTEMS if (r := load(REPORTS / "leis" / s / "result.json"))}


def pooled(results, metric="ndcg_linear@10"):
    """Per-query values over the three tasks (53 queries), keyed task/query."""
    out = {}
    for system, result in results.items():
        values = {}
        for task in TASK_NAMES:
            for qid, row in result["tasks"][task]["evaluation"]["per_query"].items():
                if row["eligible"]:
                    values[qid] = row["metrics"][metric]
        out[system] = values
    return out


def central_table(results):
    lines = []
    for task, title in TASK_NAMES.items():
        n = len(next(iter(results.values()))["tasks"][task]["evaluation"]["per_query"])
        lines += [f"### {title} — {n} consultas", "",
                  "| Sistema | " + " | ".join(c for _, c in COLUMNS) + " | p50 ms | p95 ms |",
                  "|---|" + "---:|" * (len(COLUMNS) + 2)]
        order = sorted(results, key=lambda s: -results[s]["tasks"][task]["evaluation"]["aggregate"]["overall"]["metrics"]["ndcg_linear@10"])
        for system in order:
            t = results[system]["tasks"][task]
            m = t["evaluation"]["aggregate"]["overall"]["metrics"]
            lat = t["latency"]["total"]
            cells = [pct(m[k]) if k.startswith("hit") else fmt(m[k]) for k, _ in COLUMNS]
            name = f"**{NAMES[system]}**" if system == "m0_leis" else NAMES[system]
            lines.append(f"| {name} | " + " | ".join(cells) + f" | {lat['p50_ms']:.0f} | {lat['p95_ms']:.0f} |")
        lines.append("")
    return "\n".join(lines)


def pooled_table(results):
    values = pooled(results)
    base = values.get("m0_leis")
    rows = []
    for system in results:
        v = values[system]
        ci = paired_bootstrap(v)["ci95"]
        delta = paired_bootstrap(v, base) if base and system != "m0_leis" else None
        rows.append((system, float(np.mean(list(v.values()))), ci, delta))
    rows.sort(key=lambda r: -r[1])
    lines = ["| Sistema | nDCG@10 (53 consultas) | IC95 | Δ vs M0 leis [IC95] | Veredito |", "|---|---:|---|---|---|"]
    for system, mean, ci, delta in rows:
        d = "—" if not delta else f"{delta['mean']:+.3f} [{delta['ci95'][0]:+.3f}; {delta['ci95'][1]:+.3f}]".replace(".", ",")
        lines.append(f"| {NAMES[system]} | {fmt(mean)} | {fmt(ci[0])} a {fmt(ci[1])} | {d} | "
                     f"{'referência' if not delta else verdict(delta)} |")
    return "\n".join(lines), rows


def lookups_table(results):
    lookups = results.get("m0_leis", {}).get("direct_lookups_c1")
    if not lookups:
        return "—"
    lines = [f"Acerto@1: **{pct(lookups['hit@1'])}** em {lookups['n']} consultas diretas.", "",
             "| Tool | Argumentos | Acertou | ms (mediana de 3) |", "|---|---|---|---:|"]
    for r in lookups["rows"]:
        args = ", ".join(f"{k}={v}" for k, v in r["args"].items()).replace("|", "/")
        lines.append(f"| {r['tool']} | {args} | {'sim' if r['hit@1'] else 'não'} | {r['ms_median']:.1f} |")
    return "\n".join(lines)


def response_table(results):
    m0 = results.get("m0_leis")
    if not m0:
        return ""
    lines = ["| Tarefa | Resposta média (caracteres) | ≈ tokens |", "|---|---:|---:|"]
    for task in ("dispositivo", "norma", "precedente", "norma_por_artigos"):
        t = m0["tasks"].get(task)
        if t and t.get("response_chars_mean"):
            lines.append(f"| {task} | {t['response_chars_mean']:,.0f} | {t['response_tokens_mean']:,.0f} |".replace(",", "."))
    return "\n".join(lines)


def engines_table(results):
    duck = load(REPORTS / "leis" / "engines" / "result.json")
    if not duck or "m1_bm25" not in results:
        return "Trilha de motores no leis ainda não executada."
    lines = ["| Tarefa | Manticore BM25 nDCG@10 | DuckDB FTS BM25 nDCG@10 | Manticore p50 ms | DuckDB p50 ms |", "|---|---:|---:|---:|---:|"]
    for task in TASK_NAMES:
        man = results["m1_bm25"]["tasks"][task]
        d = duck["tasks"][task]
        lines.append(f"| {TASK_NAMES[task]} | {fmt(man['evaluation']['aggregate']['overall']['metrics']['ndcg_linear@10'])} | "
                     f"{fmt(d['metrics']['ndcg_linear@10'])} | {man['latency']['total']['p50_ms']:.0f} | {d['latency']['total']['p50_ms']:.0f} |")
    b = duck["build"]
    lines += ["", f"DuckDB {duck.get('duckdb_version')}: base de {duck['database_bytes'] / 2**20:,.0f} MiB; carga "
              f"{b['dispositivos_load_seconds'] + b['precedentes_load_seconds']:.0f} s e índice FTS "
              f"{b['dispositivos_fts_seconds'] + b['precedentes_fts_seconds']:.0f} s para "
              f"{b['dispositivos_rows']:,} dispositivos e {b['precedentes_rows']:,} precedentes".replace(',', '.') + f". Manticore do leis: índice de 641 MB "
              "e ~150 MB de RAM (docs do leis-mcp)."]
    return "\n".join(lines)


def gap_section():
    summary = load(REPORTS / "summary.json")
    engines = load(REPORTS / "engines" / "result.json")
    crossval = load(REPORTS / "m5_hybrid" / "fusion_crossval.json")
    lines = ["| Lacuna do leis | O que o JurisTCU mede | Resultado |", "|---|---|---|"]
    if summary:
        rows = summary["methods"]
        best = max((m for m in rows if rows[m]["role"] == "main"), key=lambda m: rows[m]["test"]["ndcg_linear@10"])
        lines.append(f"| Relevância graduada (gabarito do leis é binário) | nDCG@10 com graus 0–3 em 70 consultas | melhor: "
                     f"{rows[best]['name']} {fmt(rows[best]['test']['ndcg_linear@10'])}; BM25 {fmt(rows['m1_bm25']['test']['ndcg_linear@10'])}; "
                     f"M0 leis {fmt(rows.get('m0_leis', {}).get('test', {}).get('ndcg_linear@10'))} |")
        lines.append(f"| Consultas reais de usuários | 35 palavras-chave reais × 35 sintéticas | M0 leis "
                     f"{fmt(rows.get('m0_leis', {}).get('by_origin', {}).get('real_keyword', {}).get('ndcg10'))} nas reais; "
                     f"BM25 {fmt(rows['m1_bm25']['by_origin']['real_keyword']['ndcg10'])} |")
        dense = rows.get("m5_dense_reference")
        if dense:
            lines.append(f"| Denso no corpus inteiro (no leis só reordena 100) | Nemotron 8B exato sobre 16.045 docs | "
                         f"{fmt(dense['test']['ndcg_linear@10'])} (BM25 {fmt(rows['m1_bm25']['test']['ndcg_linear@10'])}) |")
    if crossval:
        lines.append(f"| Split de ajuste (leis só tem teste) | dev de 30 + validação cruzada em 100 | α da fusão: 0,2 no dev, "
                     f"0,8 na CV (híbrido {fmt(crossval['cv_ndcg10_mean'])} × BM25 {fmt(crossval['bm25_ndcg10_all'])}) |")
    if engines:
        e = engines["engines"]
        hnsw = e.get("dense_duckdb_hnsw", {})
        lines.append(f"| Busca vetorial em banco (DuckDB VSS) | HNSW × exato com os mesmos vetores | ANN-recall@10 "
                     f"{fmt(hnsw.get('ann_recall_vs_exact', {}).get('@10'))}; nDCG@10 HNSW {fmt(hnsw.get('metrics', {}).get('ndcg_linear@10'))} × "
                     f"exato {fmt(e.get('dense_numpy_exact', {}).get('metrics', {}).get('ndcg_linear@10'))} |")
        hy = e.get("hybrid_duckdb_sql")
        if hy:
            lines.append(f"| Híbrido dentro do banco | BM25 FTS + cosseno + fusão numa consulta SQL | nDCG@10 {fmt(hy['metrics']['ndcg_linear@10'])}, "
                         f"p50 {hy['latency']['total']['p50_ms']:.0f} ms |")
    return "\n".join(lines)


def engines_tcu_table():
    engines = load(REPORTS / "engines" / "result.json")
    if not engines:
        return "—"
    lines = ["| Motor | nDCG@10 | p50 ms | p95 ms | Construção | Observação |", "|---|---:|---:|---:|---|---|"]
    for name, row in engines["engines"].items():
        build = row.get("build", {})
        secs = build.get("build_seconds") or build.get("load_seconds")
        note = ""
        if "ann_recall_vs_exact" in row:
            note = f"ANN-recall@10 {fmt(row['ann_recall_vs_exact']['@10'])}"
        for key in ("agreement_top10_vs_bm25s", "agreement_top10_vs_numpy"):
            if key in row:
                note = f"top-10 igual ao de referência em {pct(row[key])}"
        lines.append(f"| {build.get('engine', name)} | {fmt(row['metrics']['ndcg_linear@10'])} | {row['latency']['total']['p50_ms']:.1f} | "
                     f"{row['latency']['total']['p95_ms']:.1f} | {'—' if secs is None else f'{secs:.0f} s'} | {note} |")
    return "\n".join(lines)


def charts(results, pooled_rows):
    style()
    out = REPORTS / "charts"
    systems = sorted(results, key=lambda s: -np.mean([results[s]["tasks"][t]["evaluation"]["aggregate"]["overall"]["metrics"]["ndcg_linear@10"] for t in TASK_NAMES]))
    data = np.array([[results[s]["tasks"][t]["evaluation"]["aggregate"]["overall"]["metrics"]["ndcg_linear@10"] for t in TASK_NAMES] for s in systems])
    from matplotlib.colors import LinearSegmentedColormap
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 0.55 * len(systems) + 1.6))
    image = ax.imshow(data, cmap=LinearSegmentedColormap.from_list("blue", SEQUENTIAL), vmin=0, vmax=1, aspect="auto")
    for i in range(len(systems)):
        for j in range(len(TASK_NAMES)):
            ax.text(j, i, f"{data[i, j]:.2f}", ha="center", va="center", fontsize=10, color="#ffffff" if data[i, j] > 0.55 else INK)
    ax.set_xticks(range(len(TASK_NAMES)), list(TASK_NAMES.values()))
    ax.set_yticks(range(len(systems)), [NAMES[s] for s in systems])
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.colorbar(image, ax=ax, label="nDCG@10", shrink=0.8)
    ax.set_title("Benchmark central — acervo leis-mcp, nDCG@10 por tarefa")
    footnote(fig, "Gabarito do leis-mcp (53 consultas). M3–M5 reordenam os 100 primeiros do BM25; “M0 leis + Nemotron” reordena os "
                  "100 primeiros do próprio leis. Configurações congeladas no JurisTCU.")
    save(fig, out / "leis_ndcg_heatmap.png")

    fig, ax = plt.subplots(figsize=(8, 0.5 * len(pooled_rows) + 1.4))
    order = list(reversed(pooled_rows))
    y = np.arange(len(order))
    means = [r[1] for r in order]
    ax.barh(y, means, height=0.56, color=[SERIES[0] if r[0] == "m0_leis" else ABLATION if r[3] and verdict(r[3]) != "superior" else SERIES[2] for r in order],
            edgecolor=SURFACE, linewidth=2)
    ax.errorbar(means, y, xerr=[[m - r[2][0] for m, r in zip(means, order)], [r[2][1] - m for m, r in zip(means, order)]],
                fmt="none", ecolor=INK2, elinewidth=1.2, capsize=3)
    for yi, r in zip(y, order):
        ax.text(r[2][1] + 0.01, yi, f"{r[1]:.3f}", va="center", fontsize=9, color=INK)
    ax.set_yticks(y, [NAMES[r[0]] for r in order])
    ax.set_xlim(0, 1.08)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("nDCG@10 nas 53 consultas do gabarito, IC95 bootstrap")
    ax.set_title("Benchmark central — todas as tarefas do leis")
    footnote(fig, "Azul: M0 leis-mcp (referência). Verde: superior ao M0 com IC fora de zero. Cinza: não superior.")
    save(fig, out / "leis_pooled_ndcg.png")


def main():
    results = central_results()
    if not results:
        raise SystemExit("no central results under reports/c2/leis")
    pooled_md, pooled_rows = pooled_table(results)
    charts(results, pooled_rows)
    text = f"""# Benchmark C2 — central no acervo leis-mcp, JurisTCU nas lacunas (gerado)

Commit `{(code_commit() or '')[:10]}`. **Benchmark central:** o acervo do leis-mcp (347.195 dispositivos de legislação federal e
11.253 precedentes qualificados), com o gabarito conferido do próprio leis-mcp (`tests/consultas_referencia.json`):
53 consultas C2 em três tarefas, mais 8 consultas diretas (C1). **Auxiliar:** o JurisTCU entra só onde o leis não
consegue medir (relevância graduada, consultas reais, denso no corpus inteiro, ajuste em dev, busca vetorial em banco).

Protocolo no leis: nenhum ajuste (o gabarito inteiro é teste); M1–M5 chegam com a configuração congelada no dev do JurisTCU;
M3, M4 e M5 reordenam os 100 primeiros do M1 (protocolo "rerank" do JUÁ), porque codificar os 358 mil documentos não cabe
na máquina. O M0 é o leis-mcp como servido, e reproduz as métricas publicadas no próprio repositório.

## Métricas e de onde vêm

| Métrica | Origem | Medida no leis (central) | Medida no JurisTCU (lacuna) |
|---|---|---|---|
""" + "\n".join(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in METRIC_SOURCES) + f"""

## Resultado central — todas as tarefas juntas

{pooled_md}

![nDCG@10 agregado](charts/leis_pooled_ndcg.png)

![nDCG@10 por tarefa](charts/leis_ndcg_heatmap.png)

## Resultado central por tarefa

{central_table(results)}
## Consultas diretas (C1) — só o leis

{lookups_table(results)}

## Tamanho da resposta do leis (uso normal, limite=10)

{response_table(results)}

## Motores no acervo central — o mesmo BM25 em Manticore e DuckDB

{engines_table(results)}

## Lacunas do leis cobertas pelo JurisTCU

{gap_section()}

### Motores no JurisTCU (BM25 em três bancos, denso exato × HNSW, híbrido em SQL)

{engines_tcu_table()}

Detalhes do JurisTCU: [RESULTS.md](RESULTS.md) e [ERRORS.md](ERRORS.md).
"""
    (REPORTS / "BENCHMARK.md").write_text(text, encoding="utf-8", newline="\n")
    print(pooled_md)


if __name__ == "__main__":
    main()
