"""Read the existing leis-mcp normalized corpus, without modifying its checkout."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from .db import connect, create_schema, stats
from .model import normalize, number, reference


def convert(record, collection):
    if collection == "precedentes":
        entity_id = "precedent:" + record["chave"]
        fields = {"authority": normalize(record["tribunal"]), "kind": normalize(record["tipo"]),
                  "number": number(record["numero"]), "year": record.get("ano") or None, "article": None}
        norm_key = None
    else:
        entity_id = "provision:" + record["urn"] + "#" + str(record.get("artigo", ""))
        fields = {"authority": normalize(record.get("esfera")),
                  "kind": normalize(record["chave_norma"].split(":")[0]),
                  "number": number(record["numero"]), "year": record.get("ano") or None,
                  "article": normalize(record.get("artigo"))}
        norm_key = record["chave_norma"]
    return (
        collection + ":" + str(record["id"]), entity_id, collection,
        fields["authority"], fields["kind"], fields["number"], fields["year"],
        fields["article"], norm_key, reference(fields), record.get("titulo", ""),
        record.get("texto", ""), record.get("link", ""), record.get("caminho", "")
    )


def import_corpus(source_root, output):
    source_root = Path(source_root)
    inputs = [source_root / ".local/normalizado" / (name + ".jsonl") for name in ("precedentes", "dispositivos")]
    if not all(p.is_file() for p in inputs):
        raise ValueError("Expected real normalized leis-mcp corpus files are missing")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    snapshots = []
    with connect() as conn:
        create_schema(conn)
        # This namespace belongs exclusively to C1; never touches the source database.
        with conn.transaction():
            conn.execute("TRUNCATE c1.records,c1.entities,c1.source_snapshots")
            for path in inputs:
                digest, count = hashlib.sha256(), 0
                with conn.cursor().copy("COPY c1.records FROM STDIN") as copy, path.open("rb") as lines:
                    for raw in lines:
                        digest.update(raw)
                        copy.write_row(convert(json.loads(raw), path.stem))
                        count += 1
                item = {"filename": path.name, "sha256": digest.hexdigest(), "rows": count, "bytes": path.stat().st_size}
                snapshots.append(item)
                conn.execute("INSERT INTO c1.source_snapshots(filename,sha256,rows) VALUES (%s,%s,%s)", (path.name,item["sha256"],count))
                print(json.dumps({"imported": path.name, "rows": count}), flush=True)
            conn.execute("""INSERT INTO c1.entities
                SELECT DISTINCT ON(entity_id) entity_id,collection,authority,kind,number,year,article,norm_key,reference,title,source_link
                FROM c1.records ORDER BY entity_id, record_id""")
        conn.execute("CREATE INDEX IF NOT EXISTS c1_identity_exact ON c1.entities(collection,authority,kind,number,year,article)")
        conn.execute("CREATE INDEX IF NOT EXISTS c1_norm_article ON c1.entities(norm_key,article)")
        conn.execute("CREATE INDEX IF NOT EXISTS c1_number ON c1.entities(number)")
        conn.execute("ANALYZE c1.entities")
        report = {"kind":"real_corpus_import", "source_repository":"https://github.com/lops-legal/leis-mcp",
                  "source_modified":False,"snapshots":snapshots,"elapsed_seconds":time.perf_counter()-start,
                  "database":stats(conn)}
    (output / "corpus-manifest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"import_seconds":round(report["elapsed_seconds"],2),"database":report["database"]},ensure_ascii=True),flush=True)
    return report


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root",required=True,type=Path)
    p.add_argument("--output",default="reports/c1/real",type=Path)
    args=p.parse_args()
    import_corpus(args.source_root,args.output)
