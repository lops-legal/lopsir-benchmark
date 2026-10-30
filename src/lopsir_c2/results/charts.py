"""Static PNG charts for the C2 report (light surface, reference palette of the dataviz method).

Identity rule: methods are named on the axis or by direct labels, so bar charts use one hue
for the five main methods and muted gray for ablations/references; multi-series charts use
the categorical slots in fixed order, always with a legend and direct labels.
"""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
ABLATION = "#b4b2a9"
POSITIVE, NEGATIVE = "#2a78d6", "#e34948"
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
METHOD_ORDER = ["m1_bm25", "m2_query2doc", "m3_splade", "m4_bgem3", "m5_hybrid", "m0_leis"]


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"], "font.size": 10,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.titlecolor": INK, "axes.titlelocation": "left", "legend.frameon": False,
    })


def footnote(fig, text):
    """Anchor the note by its top just below the lowest axis artist (tick labels, x label, colorbar)."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    to_figure = fig.transFigure.inverted()
    bottom = min(ax.get_tightbbox(renderer).transformed(to_figure).y0 for ax in fig.axes)
    fig.text(0.01, bottom - 0.02, text, color=INK2, fontsize=8.5, va="top", ha="left")


def save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def ranked(summary):
    rows = summary["methods"]
    return sorted(rows, key=lambda m: rows[m]["test"]["ndcg_linear@10"])


def ndcg_with_ci(summary, out):
    rows = summary["methods"]
    order = ranked(summary)
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(order) + 1.4))
    y = np.arange(len(order))
    values = [rows[m]["test"]["ndcg_linear@10"] for m in order]
    lows = [rows[m]["ndcg10_ci"]["ci95"][0] for m in order]
    highs = [rows[m]["ndcg10_ci"]["ci95"][1] for m in order]
    colors = [SERIES[0] if rows[m]["role"] == "main" else ABLATION for m in order]
    ax.barh(y, values, height=0.56, color=colors, edgecolor=SURFACE, linewidth=2)
    ax.errorbar(values, y, xerr=[np.subtract(values, lows), np.subtract(highs, values)], fmt="none",
                ecolor=INK2, elinewidth=1.2, capsize=3)
    for yi, value, high in zip(y, values, highs):
        ax.text(high + 0.008, yi, f"{value:.3f}", va="center", color=INK, fontsize=9)
    if "m1_bm25" in rows:
        ax.axvline(rows["m1_bm25"]["test"]["ndcg_linear@10"], color=MUTED, linestyle="--", linewidth=1)
    ax.set_yticks(y, [rows[m]["name"] for m in order])
    ax.set_xlim(0, max(highs) + 0.08)
    ax.set_xlabel("nDCG@10 no teste (70 consultas C2), barra = IC95% bootstrap por grupo")
    ax.grid(axis="y", visible=False)
    ax.set_title("C2 — qualidade de ranking por metodologia")
    footnote(fig, "Azul: as cinco metodologias. Cinza: ablação/referência. Tracejado: BM25 (M1).")
    return save(fig, out / "ndcg10_ci.png")


def delta_vs_bm25(summary, out):
    rows = {m: r for m, r in summary["methods"].items() if r["delta_vs_bm25"]}
    order = sorted(rows, key=lambda m: rows[m]["delta_vs_bm25"]["mean"])
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(order) + 1.4))
    y = np.arange(len(order))
    means = [rows[m]["delta_vs_bm25"]["mean"] for m in order]
    lows = [rows[m]["delta_vs_bm25"]["ci95"][0] for m in order]
    highs = [rows[m]["delta_vs_bm25"]["ci95"][1] for m in order]
    ax.axvline(0, color=AXIS, linewidth=1.2)
    for yi, mean, low, high, m in zip(y, means, lows, highs, order):
        color = POSITIVE if low > 0 else NEGATIVE if high < 0 else MUTED
        ax.plot([low, high], [yi, yi], color=color, linewidth=2.5, solid_capstyle="round")
        ax.plot(mean, yi, "o", color=color, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2)
        w, t, l = rows[m]["wins_ties_losses_vs_bm25"]
        ax.text(max(highs) + 0.01, yi, f"{mean:+.3f}  ({rows[m]['verdict_vs_bm25']}; {w}V/{t}E/{l}D)", va="center",
                color=INK, fontsize=8.5)
    ax.set_yticks(y, [rows[m]["name"] for m in order])
    ax.set_xlim(min(lows) - 0.02, max(highs) + 0.2)
    ax.set_xlabel("Diferença pareada de nDCG@10 contra o BM25 (IC95%)")
    ax.grid(axis="y", visible=False)
    ax.set_title("C2 — ganho sobre o baseline BM25")
    footnote(fig, "Azul: IC acima de zero. Vermelho: abaixo. Cinza: inclui zero (inconclusivo). "
                  "V/E/D = vitórias, empates, derrotas por consulta.")
    return save(fig, out / "delta_vs_bm25.png")


def quality_vs_latency(summary, out):
    rows = summary["methods"]
    fig, ax = plt.subplots(figsize=(8, 5))
    points = []
    for m, r in rows.items():
        latency = (r["latency_end_to_end_first_pass"] or {}).get("p50_ms")
        if latency:
            points.append((m, latency, r["test"]["ndcg_linear@10"]))
    for m, x, y in points:
        color = SERIES[0] if rows[m]["role"] == "main" else ABLATION
        ax.plot(x, y, "o", color=color, markersize=10, markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
        # ablations cluster near the main methods: short codes keep labels apart (names are in the bar chart)
        label = rows[m]["name"] if rows[m]["role"] == "main" else rows[m]["name"].split(" ")[0]
        ax.annotate(label, (x, y), xytext=(8, 4), textcoords="offset points", fontsize=9,
                    color=INK if rows[m]["role"] == "main" else INK2)
    frontier, best = [], -1
    for m, x, y in sorted(points, key=lambda p: p[1]):
        if y > best:
            frontier.append((x, y))
            best = y
    if len(frontier) > 1:
        ax.plot(*zip(*frontier), color=INK2, linewidth=1.2, linestyle="--", zorder=2, label="fronteira de Pareto")
        ax.legend(loc="lower right")
    ax.set_xscale("log")
    ax.set_xlabel("Latência p50 ponta a ponta por consulta (ms, escala log)")
    ax.set_ylabel("nDCG@10 (teste)")
    ax.set_title("C2 — qualidade × latência")
    footnote(fig, "Métodos com API: 1º passe, incluindo a chamada (embedding ou LLM). Métodos locais: rodadas aquecidas. "
                  "Máquina com GPU de 4 GB.")
    return save(fig, out / "quality_vs_latency.png")


def by_origin(summary, out):
    rows = summary["methods"]
    order = list(reversed(ranked(summary)))
    origins = [("real_keyword", "Consultas reais de usuários"), ("synthetic_keyword", "Consultas sintéticas")]
    fig, ax = plt.subplots(figsize=(8, 0.75 * len(order) + 1.4))
    y = np.arange(len(order))
    h = 0.36
    for k, (key, label) in enumerate(origins):
        vals = [rows[m]["by_origin"].get(key, {}).get("ndcg10", 0) for m in order]
        ax.barh(y + (k - 0.5) * h, vals, height=h, color=SERIES[k], edgecolor=SURFACE, linewidth=2, label=label)
    n = {key: rows[order[0]]["by_origin"].get(key, {}).get("n") for key, _ in origins}
    ax.set_yticks(y, [rows[m]["name"] for m in order])
    ax.invert_yaxis()
    ax.set_xlabel(f"nDCG@10 no teste (reais n={n['real_keyword']}, sintéticas n={n['synthetic_keyword']})")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    ax.set_title("C2 — consultas reais × sintéticas")
    return save(fig, out / "by_origin.png")


def recall_curve(summary, out):
    rows = summary["methods"]
    cutoffs = [1, 10, 20, 100]
    fig, ax = plt.subplots(figsize=(8, 5))
    methods = [m for m in METHOD_ORDER if m in rows]
    for i, m in enumerate(methods):
        ys = [rows[m]["test"][f"recall@{k}"] for k in cutoffs]
        ax.plot(cutoffs, ys, "-o", color=SERIES[i], linewidth=2, markersize=8, markeredgecolor=SURFACE,
                markeredgewidth=2, label=rows[m]["name"])
        ax.annotate(rows[m]["name"], (cutoffs[-1], ys[-1]), xytext=(8, 0), textcoords="offset points", va="center",
                    fontsize=8.5, color=INK)
    ax.set_xscale("log")
    ax.set_xticks(cutoffs, [f"@{k}" for k in cutoffs])
    ax.set_xlim(0.8, 600)
    ax.set_ylim(0, None)
    ax.set_ylabel("Recall sobre os positivos conhecidos (teste)")
    ax.set_title("C2 — cobertura dos positivos conhecidos")
    ax.legend(loc="upper left")
    return save(fig, out / "recall_curve.png")


def label_heatmap(summary, out):
    rows = summary["methods"]
    methods = [m for m in METHOD_ORDER if m in rows] + [m for m in rows if m not in METHOD_ORDER]
    keys = [("length_short", "curtas (≤2 termos)"), ("length_medium", "médias (3–5)"), ("length_long", "longas (≥6)"),
            ("multi_concept_e", "com conjunção 'e'"), ("unaccented_typing", "sem acento")]
    keys = [(k, l) for k, l in keys if any(k in rows[m]["by_label"] for m in methods)]
    data = np.array([[rows[m]["by_label"].get(k, {}).get("ndcg10", np.nan) for k, _ in keys] for m in methods])
    counts = [rows[methods[0]]["by_label"].get(k, {}).get("n", 0) for k, _ in keys]
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", SEQUENTIAL)
    fig, ax = plt.subplots(figsize=(1.5 * len(keys) + 3, 0.5 * len(methods) + 1.6))
    image = ax.imshow(data, cmap=cmap, vmin=0, vmax=max(0.6, np.nanmax(data)), aspect="auto")
    for i in range(len(methods)):
        for j in range(len(keys)):
            v = data[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=9, color="#ffffff" if v > 0.35 else INK)
    ax.set_xticks(range(len(keys)), [f"{l}\nn={c}" for (_, l), c in zip(keys, counts)], fontsize=8.5)
    ax.set_yticks(range(len(methods)), [rows[m]["name"] for m in methods])
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.colorbar(image, ax=ax, label="nDCG@10", shrink=0.8)
    ax.set_title("C2 — nDCG@10 por tipo de consulta (teste)")
    footnote(fig, "Grupos pequenos (n<10) são indicativos, não conclusivos.")
    return save(fig, out / "by_label.png")


def per_query_deltas(summary, results, out):
    from .stats import per_query
    rows = summary["methods"]
    base = per_query(results["m1_bm25"], "ndcg_linear@10")
    methods = [m for m in METHOD_ORDER if m in results and m != "m1_bm25"] or [m for m in results if m != "m1_bm25"]
    fig, axes = plt.subplots(len(methods), 1, figsize=(8, 1.7 * len(methods) + 0.8), sharex=True, sharey=True)
    axes = np.atleast_1d(axes)
    for ax, m in zip(axes, methods):
        vals = per_query(results[m], "ndcg_linear@10")
        deltas = np.sort([vals[q] - base[q] for q in base])[::-1]
        ax.bar(np.arange(len(deltas)), deltas, width=0.8, color=[POSITIVE if d > 0 else NEGATIVE for d in deltas])
        ax.axhline(0, color=AXIS, linewidth=1)
        ax.set_ylabel(rows[m]["name"].split(" ", 1)[0], rotation=0, ha="right", va="center", color=INK)
        ax.grid(axis="x", visible=False)
        ax.text(len(deltas) - 1, ax.get_ylim()[1] * 0.85 if ax.get_ylim()[1] > 0 else 0.1,
                rows[m]["name"], ha="right", fontsize=8.5, color=INK2)
    axes[-1].set_xlabel("Consultas de teste ordenadas pela diferença de nDCG@10 contra o BM25")
    axes[0].set_title("C2 — onde cada metodologia ganha ou perde do BM25, consulta a consulta")
    return save(fig, out / "per_query_delta.png")


def render_all(summary, results, out):
    style()
    made = [ndcg_with_ci(summary, out), quality_vs_latency(summary, out), by_origin(summary, out),
            recall_curve(summary, out), label_heatmap(summary, out)]
    if any(r["delta_vs_bm25"] for r in summary["methods"].values()):
        made += [delta_vs_bm25(summary, out), per_query_deltas(summary, results, out)]
    sensitivity = out.parent / "m5_hybrid" / "fusion_sensitivity.json"
    if sensitivity.exists():
        made.append(fusion_sensitivity(json.loads(sensitivity.read_text(encoding="utf-8")), out))
    return made


def fusion_sensitivity(payload, out):
    rows = payload["rows"]
    alphas = [r["alpha"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for k, (split, label) in enumerate((("dev", "dev (30 consultas)"), ("test", "teste (70 consultas)"))):
        values = [r[split] for r in rows]
        ax.plot(alphas, values, "-o", color=SERIES[k], linewidth=2, markersize=7, markeredgecolor=SURFACE,
                markeredgewidth=2, label=label)
        ax.annotate(label, (alphas[-1], values[-1]), xytext=(8, 0), textcoords="offset points", va="center", fontsize=8.5, color=INK)
    frozen = payload["frozen_config"]["param"]
    ax.axvline(frozen, color=MUTED, linestyle="--", linewidth=1)
    ax.text(frozen, ax.get_ylim()[1], f" α congelado no dev = {frozen}", va="top", fontsize=8.5, color=INK2)
    ax.set_xticks(alphas)
    ax.set_xlim(-0.03, 1.25)
    ax.set_xlabel("α = peso do ramo denso (0 = só BM25, 1 = só Nemotron denso)")
    ax.set_ylabel("nDCG@10")
    ax.set_title("C2 — sensibilidade da fusão convexa (diagnóstico pós-hoc)")
    ax.legend(loc="lower right")
    footnote(fig, "Não usado na seleção: o M5 fica congelado no α escolhido no dev. Mostra se o dev tinha sinal para escolher α.")
    return save(fig, out / "fusion_sensitivity.png")
