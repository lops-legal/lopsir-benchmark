"""Compile existing C1 reference tests and transparent real-identity lookups."""
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from .db import connect
from .model import Query, normalize, number, reference


def read_aliases(source_root):
    tree=ast.parse((Path(source_root)/"src/leis_mcp/apelidos.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id=="APELIDOS":
            return ast.literal_eval(node.value)
    raise ValueError("Source alias dictionary not found")


def resolve_norm(text, aliases):
    folded=normalize(text)
    for key, values in aliases.items():
        if folded in [normalize(v) for v in values]: return key
    if folded.startswith(("constituicao", "cf")): return "constituicao:1988"
    match=re.search(r"(lei complementar|decreto lei|lei delegada|medida provisoria|emenda constitucional|lei|lc|mp|ec)\s*(?:n[ou]?\s*)?(\d[\d.]*)",text,flags=re.I)
    if not match:
        match=re.search(r"(lei complementar|decreto lei|lei|lc|mp|ec)\s+(\d+)",folded)
    if not match: raise ValueError(f"Unresolved source norm reference: {text}")
    types={"lei complementar":"lei.complementar","lc":"lei.complementar","decreto lei":"decreto.lei","lei delegada":"lei.delegada","medida provisoria":"medida.provisoria","mp":"medida.provisoria","emenda constitucional":"emenda.constitucional","ec":"emenda.constitucional","lei":"lei"}
    return types[normalize(match[1])]+":"+number(match[2])


def article(text):
    folded=normalize(text.replace(".", ""))
    if folded.startswith("adct"): return "adct "+re.search(r"\d+",folded)[0]
    return re.sub(r"\s*[º°]\s*", "",folded)


def provision_fields(norm, art, aliases, conn):
    key=resolve_norm(norm,aliases)
    rows=conn.execute("SELECT DISTINCT authority,kind,number,year FROM c1.entities WHERE norm_key=%s ORDER BY year",(key,)).fetchall()
    if not rows: raise ValueError(f"No real corpus identity for {norm}")
    fields={"collection":"dispositivos","norm_key":key,"article":article(art)}
    for col in ("authority","kind","number","year"):
        values={r[col] for r in rows}
        if len(values)==1: fields[col]=next(iter(values))
    return fields


def precedent_fields(args,conn):
    fields={"collection":"precedentes","authority":normalize(args["tribunal"]),"number":number(args["numero"])}
    if args.get("tipo"):
        kinds=conn.execute("SELECT DISTINCT kind FROM c1.entities WHERE collection='precedentes' AND authority=%s",(fields["authority"],)).fetchall()
        matches=[r["kind"] for r in kinds if normalize(args["tipo"]) in r["kind"]]
        if len(matches)!=1: raise ValueError("Source kind abbreviation is ambiguous")
        fields["kind"]=matches[0]
    return fields


def gold_ids(fields,conn):
    clauses=[];values=[]
    for key,value in fields.items():
        if key not in {"collection","authority","kind","number","year","article","norm_key"}:raise ValueError(key)
        if value not in (None,""):
            clauses.append(f"{key}=%s");values.append(value)
    return [r["entity_id"] for r in conn.execute("SELECT entity_id FROM c1.entities WHERE "+" AND ".join(clauses)+" ORDER BY entity_id",values).fetchall()]


def build(source_root,output,known_per_collection=250):
    root=Path(source_root);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    aliases=read_aliases(root)
    source=json.loads((root/"tests/consultas_referencia.json").read_text(encoding="utf-8"))
    queries=[]
    with connect() as conn:
        for index,item in enumerate(source["consulta_direta"]):
            args=item["args"]
            if item["tool"]=="obter_dispositivo":
                fields=provision_fields(args["norma"],args["artigo"],aliases,conn)
                text=f"{args['norma']} artigo {args['artigo']}"
            elif item["tool"]=="obter_precedente":
                fields=precedent_fields(args,conn)
                text=" ".join(str(args[k]) for k in ("tribunal","tipo","numero") if args.get(k))
            else:
                # Citation verification mixes several items and a separate contract;
                # retain the seven single-target reference calls in this first study.
                continue
            gold=gold_ids(fields,conn)
            if not gold: raise ValueError(f"Existing reference test has no corpus positive: {text}")
            queries.append(Query(f"source-direct-{index+1}",text,fields,gold,"existing_reference_test","test",gold[0]))
        for collection in ("precedentes","dispositivos"):
            rows=conn.execute("""SELECT entity_id,collection,authority,kind,number,year,article,norm_key,reference
                FROM c1.entities WHERE collection=%s AND number<>'' AND (collection='precedentes' OR article<>'')
                ORDER BY md5(entity_id || 'lopsir-c1-v1') LIMIT %s""",(collection,known_per_collection)).fetchall()
            for row in rows:
                identity=row.pop("entity_id");text=row.pop("reference")
                fields={k:v for k,v in row.items() if v not in (None,"")}
                digest=hashlib.sha256(identity.encode()).hexdigest()
                bucket=int(digest[:8],16)%10
                split="train" if bucket<2 else "dev" if bucket<4 else "test"
                queries.append(Query("known-"+digest[:16],text,fields,[identity],"derived_real_identity_lookup",split,identity))
    payload=[q.__dict__ for q in queries]
    output.write_text("\n".join(json.dumps(q,ensure_ascii=False) for q in payload)+"\n",encoding="utf-8")
    return {"queries":len(queries),"existing_reference_calls":sum(q.origin=="existing_reference_test" for q in queries),
            "derived_real_identity_lookups":sum(q.origin!="existing_reference_test" for q in queries),
            "note":"Existing structured references and clean known-item lookups; not user logs, no invented cases or artificial typos."}


def load(path):
    return [Query(**json.loads(line)) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root",required=True,type=Path)
    p.add_argument("--output",default="artifacts/c1/queries.jsonl",type=Path)
    p.add_argument("--known-per-collection",type=int,default=250)
    a=p.parse_args();print(json.dumps(build(a.source_root,a.output,a.known_per_collection),ensure_ascii=True))
