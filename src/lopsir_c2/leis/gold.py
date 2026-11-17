"""Convert the leis-mcp gold set into the canonical queries/qrels used by scripts/evaluate.py.

One dataset per task, because each ranks a different unit:
  leis-dispositivo  article of a norm      doc id "<chave_norma>#<artigo>"
  leis-norma        norm                   doc id "<chave_norma>"
  leis-precedente   qualified precedent    doc id "<TRIBUNAL>|<tipo>|<numero>"
Every gold item has relevance 1 (the gold set is binary). All queries are test queries: there is
no tuning on this corpus; methods arrive with the configuration frozen on JurisTCU dev.
"""
import json

from ..common import REPORTS, dataset_dir, sha256_file, write_json, write_jsonl
from . import LEIS_REFERENCE

TASKS = ("dispositivo", "norma", "precedente")


def dispositivo_key(chave_norma, artigo):
    return f"{chave_norma}#{artigo}"


def precedente_key(tribunal, tipo, numero):
    return f"{tribunal.upper()}|{tipo.lower()}|{numero}"


def gold_keys(task, esperado):
    if task == "dispositivo":
        return [dispositivo_key(n, a) for n, a in esperado]
    if task == "norma":
        return list(esperado)
    return [precedente_key(t, tipo, n) for t, tipo, n in esperado]


def build():
    reference = json.loads(LEIS_REFERENCE.read_text(encoding="utf-8"))
    counts = {}
    for task in TASKS:
        queries, qrels = [], []
        for n, item in enumerate(reference[task], 1):
            qid = f"{task}-{n:02d}"
            queries.append({"query_id": qid, "text": item["consulta"], "case_type": "C2", "origin": "leis_gold",
                            "language": "pt", "group_id": qid, "split": "test",
                            "tribunais": item.get("tribunais"), "labels": {}, "annotation_version": "leis-gold"})
            qrels += [(qid, key) for key in dict.fromkeys(gold_keys(task, item["esperado"]))]
        out = dataset_dir(f"leis-{task}")
        write_jsonl(out / "queries.jsonl", queries)
        (out / "qrels.tsv").write_text("query_id\tdoc_id\trelevance\n" + "".join(f"{q}\t{d}\t1\n" for q, d in qrels),
                                       encoding="utf-8", newline="\n")
        counts[task] = {"queries": len(queries), "qrels": len(qrels)}
    write_json(REPORTS / "leis" / "dataset-leis.json", {
        "kind": "leis_gold_manifest", "source": "github.com/lops-legal/leis-mcp tests/consultas_referencia.json",
        "reference_sha256": sha256_file(LEIS_REFERENCE), "relevance": "binary (gold items = 1)",
        "split": "test only; no tuning on this corpus", "tasks": counts,
        "direct_lookups": len(reference["consulta_direta"]),
        "note": "consulta_direta (8 identity lookups) is C1 and is scored only for the leis system itself"})
    return counts


if __name__ == "__main__":
    print(build())
