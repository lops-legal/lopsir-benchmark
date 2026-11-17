"""Build the canonical C2 dataset.

Source priority given by the user (2026-10-29): the project repository is the base;
JurisTCU is used because it is easily downloadable. The ~370k jurisprudence collection
has no locator in the repository yet (see reports/c1/repository-inventory.json); once it
exists, `--source canonical --path DIR` validates it into the same schema.

JurisTCU query formulations (dataset card): real keyword queries from user searches,
synthetic keyword queries and synthetic questions. Ids 1-50 / 51-100 / 101-150 follow
that order (101-150 are the question form of 51-100). Keyword queries are C2; questions
are C3 and are kept out of every C2 run.
"""
import argparse
import csv
import random
import re
from collections import Counter, defaultdict

from huggingface_hub import snapshot_download

from .common import (ROOT, Analyzer, REPORTS, dataset_dir, fold_accents, portuguese_stopwords, read_jsonl,
                     sha256_file, write_json, write_jsonl)

JURISTCU = {"repo_id": "ufca-llms/juris-tcu", "revision": "05f66e126f4375962a73cfd58db2c73a2945b9ef"}
RAW = ROOT / "data" / "raw" / "juris-tcu"
SEED = 42
DEV_FRACTION = 0.3
NEAR_DUPLICATE_JACCARD = 0.5
CITED_REFERENCE = re.compile(r"\b(lei|decreto|art\.?|artigo|s[uú]mula|ac[oó]rd[aã]o)\b|\d+[./]\d+", re.IGNORECASE)


def origin_of(qid):
    n = int(qid)
    if n <= 50:
        return "real_keyword"
    if n <= 100:
        return "synthetic_keyword"
    return "synthetic_question"


def topic_of(qid):
    """Synthetic keyword query k+50 and question k+100 were generated from the same summary."""
    n = int(qid)
    return f"topic-{n - 50}" if 51 <= n <= 100 else f"topic-{n - 100}" if n > 100 else f"real-{n}"


def accented_vocabulary(corpus, max_plain_share=0.05):
    """Folded words that the corpus almost always spells with diacritics ("licitacao" ->
    "licitação"). Words that are also common without accents ("e"/"é") are excluded."""
    plain, marked = Counter(), Counter()
    for doc in corpus:
        for word in re.findall(r"[^\W\d_]+", doc["text"].lower()):
            folded = fold_accents(word)
            (plain if folded == word else marked)[folded] += 1
    return {w for w, n in marked.items() if plain[w] < max_plain_share * (plain[w] + n)}


def labels_for(text, accented):
    stop = portuguese_stopwords()
    words = [w for w in re.findall(r"[^\W\d_]+", text.lower()) if w not in stop]
    content = Analyzer(fold=True, stem=False, stopwords=True)(text)
    n = len(content)
    return {
        "cited_reference": bool(CITED_REFERENCE.search(text)),
        "multi_concept_e": " e " in f" {text.lower()} ",
        "unaccented_typing": any(w == fold_accents(w) and w in accented for w in words),
        "length": "short" if n <= 2 else "medium" if n <= 5 else "long",
        "content_terms": n,
    }


def near_duplicate_groups(queries):
    analyzer = Analyzer(fold=True, stem=True, stopwords=True)
    tokens = {q["query_id"]: set(analyzer(q["text"])) for q in queries}
    parent = {qid: qid for qid in tokens}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    ids = list(tokens)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            union = tokens[a] | tokens[b]
            if union and len(tokens[a] & tokens[b]) / len(union) >= NEAR_DUPLICATE_JACCARD:
                parent[find(b)] = find(a)
    return {qid: f"g{find(qid)}" for qid in ids}


def grouped_split(queries):
    """Stratified by origin, whole near-duplicate groups on one side, frozen by SEED."""
    rng = random.Random(SEED)
    split = {}
    for origin in sorted({q["origin"] for q in queries}):
        groups = defaultdict(list)
        for q in queries:
            if q["origin"] == origin:
                groups[q["group_id"]].append(q["query_id"])
        keys = sorted(groups)
        rng.shuffle(keys)
        target = round(DEV_FRACTION * sum(len(v) for v in groups.values()))
        taken = 0
        for key in keys:
            side = "dev" if taken < target else "test"
            taken += len(groups[key]) if side == "dev" else 0
            for qid in groups[key]:
                split[qid] = side
    return split


def build_juristcu():
    snapshot_download(JURISTCU["repo_id"], repo_type="dataset", revision=JURISTCU["revision"], local_dir=RAW)
    out = dataset_dir("juristcu")
    corpus = [{"doc_id": d["_id"], "title": d.get("title") or None, "text": d["text"]} for d in read_jsonl(RAW / "corpus.jsonl")]
    if len({d["doc_id"] for d in corpus}) != len(corpus):
        raise ValueError("Duplicate corpus ids")
    doc_ids = {d["doc_id"] for d in corpus}

    accented = accented_vocabulary(corpus)
    queries = []
    for raw in read_jsonl(RAW / "queries.jsonl"):
        qid, origin = raw["_id"], origin_of(raw["_id"])
        queries.append({"query_id": qid, "text": raw["text"].strip(),
                        "case_type": "C3" if origin == "synthetic_question" else "C2",
                        "origin": origin, "language": "pt", "topic_id": topic_of(qid),
                        "labels": labels_for(raw["text"], accented), "annotation_version": "c2-rules-v1"})

    c2 = [q for q in queries if q["case_type"] == "C2"]
    groups = near_duplicate_groups(c2)
    for q in queries:
        q["group_id"] = groups.get(q["query_id"], q["topic_id"])
    split = grouped_split(c2)
    for q in queries:
        q["split"] = split.get(q["query_id"], "reserved_for_c3")

    qrels = []
    with (RAW / "qrels" / "test.tsv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["corpus-id"] not in doc_ids:
                raise ValueError(f"qrel points outside corpus: {row}")
            qrels.append((row["query-id"], row["corpus-id"], row["score"].split(".")[0]))

    write_jsonl(out / "corpus.jsonl", corpus)
    write_jsonl(out / "queries.jsonl", queries)
    with (out / "qrels.tsv").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("query_id\tdoc_id\trelevance\n")
        for row in qrels:
            handle.write("\t".join(row) + "\n")
    write_manifest("juristcu", corpus, queries, qrels)
    return out


def write_manifest(name, corpus, queries, qrels):
    out = dataset_dir(name)
    grades = defaultdict(int)
    for _, _, rel in qrels:
        grades[rel] += 1
    c2 = [q for q in queries if q["case_type"] == "C2"]
    count = lambda key, items: dict(sorted(defaultdict(int, {k: sum(1 for q in items if key(q) == k) for k in {key(q) for q in items}}).items()))
    lengths = [len(d["text"]) for d in corpus]
    write_json(REPORTS / f"dataset-{name}.json", {
        "kind": "c2_dataset_manifest",
        "dataset": name,
        "source": JURISTCU if name == "juristcu" else None,
        "authorization": "User instruction 2026-10-29: base = lops-legal/lopsir-benchmark repository, then JurisTCU if easily downloadable. Repository holds no corpus yet (370k collection locator unresolved).",
        "document_view": "EXCERTO only, as published in the JUA adaptation",
        "files": {f: {"sha256": sha256_file(out / f), "bytes": (out / f).stat().st_size}
                  for f in ("corpus.jsonl", "queries.jsonl", "qrels.tsv")},
        "counts": {"documents": len(corpus), "queries": len(queries), "c2_queries": len(c2),
                   "qrels": len(qrels), "qrels_by_grade": dict(sorted(grades.items())),
                   "c2_by_origin": count(lambda q: q["origin"], c2),
                   "c2_by_split": count(lambda q: q["split"], c2),
                   "c2_by_origin_split": count(lambda q: f"{q['origin']}/{q['split']}", c2),
                   "c2_near_duplicate_groups": len({q["group_id"] for q in c2}),
                   "c2_labels": {k: sum(1 for q in c2 if q["labels"][k] is True) for k in ("cited_reference", "multi_concept_e", "unaccented_typing")},
                   "c2_length": count(lambda q: q["labels"]["length"], c2)},
        "document_chars": {"mean": sum(lengths) / len(lengths), "min": min(lengths), "max": max(lengths)},
        "split_policy": {"seed": SEED, "dev_fraction": DEV_FRACTION, "stratify": "origin",
                         "groups": f"near-duplicate queries (stemmed token Jaccard >= {NEAR_DUPLICATE_JACCARD})",
                         "note": "Positive-document overlap forms one 59-query component, so doc-overlap grouping is infeasible; only global hyperparameters are tuned on dev."},
        "relevance": {"scale": "0-3 original JurisTCU grades preserved", "binary_threshold": 1},
    })
    with (REPORTS / f"queries-{name}.tsv").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("query_id\tcase_type\torigin\tsplit\tgroup_id\tcited_reference\tmulti_concept_e\tunaccented_typing\tlength\n")
        for q in queries:
            lab = q["labels"]
            handle.write(f"{q['query_id']}\t{q['case_type']}\t{q['origin']}\t{q['split']}\t{q['group_id']}\t"
                         f"{int(lab['cited_reference'])}\t{int(lab['multi_concept_e'])}\t{int(lab['unaccented_typing'])}\t{lab['length']}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["juristcu"], default="juristcu")
    args = parser.parse_args()
    print(build_juristcu())


if __name__ == "__main__":
    main()
