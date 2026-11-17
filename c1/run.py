"""Execute one C1 method at a time against the imported real PostgreSQL corpus."""
import argparse
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import traceback
import psutil
from psycopg.types.json import Jsonb
from .db import connect, stats
from .queries import load
from .results.metrics import ranking_metrics,summarize

METHODS={"m1":("exact","Exact"),"m2":("bm25","BM25"),"m3":("trigram","Trigram"),"m4":("edit_distance","EditDistance"),"m5":("linkage","Linkage")}


def execute(args):
    all_queries=load(args.queries)
    training=[q for q in all_queries if q.split=="train"]
    selected=[q for q in all_queries if q.split==args.split and (args.origin=="all" or q.origin==args.origin)]
    if args.limit:selected=selected[:args.limit]
    if not selected:raise ValueError("No real queries selected")
    if any(q.origin.startswith("synthetic") or q.query_id.startswith("demo-") for q in all_queries):
        raise ValueError("Synthetic/legacy fixtures are not allowed in this experiment")
    root=Path(args.output)/args.method;root.mkdir(parents=True,exist_ok=True)
    stop=threading.Event();proc=psutil.Process();peak=[proc.memory_info().rss]
    def sample():
        while not stop.wait(0.05):peak[0]=max(peak[0],proc.memory_info().rss)
    monitor=threading.Thread(target=sample,daemon=True);monitor.start()
    experiment_id=f"{args.method}-{args.split}-{args.origin}"
    start=time.perf_counter(); rows=[]
    try:
        with connect() as conn:
            count=conn.execute("SELECT count(*) AS n FROM c1.entities").fetchone()["n"]
            if not count:raise ValueError("Real database has no entities")
            module,classname=METHODS[args.method]
            cls=getattr(importlib.import_module(f"c1.methods.{module}"),classname)
            method=cls(conn,training_queries=training,work_dir=f"work/c1-{args.method}")
            t=time.perf_counter();parameters=method.prepare();prepare_seconds=time.perf_counter()-t
            for i,q in enumerate(selected):
                times=[];answer=None;error=None
                for repetition in range(args.repetitions):
                    t=time.perf_counter()
                    try:
                        answer=method.search(q,k=args.top_k);status="ok"
                    except Exception as exc:
                        status="error";error=f"{type(exc).__name__}: {exc}";answer=None
                    elapsed=(time.perf_counter()-t)*1000
                    if status=="ok":times.append(elapsed)
                    conn.execute("""INSERT INTO c1.query_audit VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(experiment_id,method,query_id,repetition) DO UPDATE SET
                        returned=excluded.returned,total_ms=excluded.total_ms,status=excluded.status""",
                        (experiment_id,method.method_id,q.query_id,repetition,q.text,Jsonb(q.fields),len(answer.hits) if answer else 0,elapsed,status))
                    if error:break
                hits=answer.hits if answer else []
                row={"query_id":q.query_id,"text":q.text,"fields":q.fields,"origin":q.origin,"collection":q.fields["collection"],
                     "gold":q.gold,"status":"error" if error else "ok","error":error,"query_ms":times,
                     "candidate_count":answer.candidate_count if answer else None,
                     "ranking":[h.__dict__ for h in hits],"metrics":ranking_metrics(q.gold,[h.entity_id for h in hits])}
                rows.append(row)
                with (root/"per-query.jsonl").open("a" if i else "w",encoding="utf-8") as h:h.write(json.dumps(row,ensure_ascii=False)+"\n")
                if (i+1)%25==0 or i==len(selected)-1:print(json.dumps({"method":method.method_id,"completed":i+1,"total":len(selected),"last_error":error}),flush=True)
            grouped={}
            for key in sorted({(r["origin"],r["collection"]) for r in rows}):
                grouped["/".join(key)]=summarize([r for r in rows if (r["origin"],r["collection"])==key])
            summary={"kind":"real_c1_retrieval_measurement","method_id":method.method_id,"name":method.name,
                     "input_mode":"structured_identity_reference","query_parsing_included":False,
                     "split":args.split,"origin_filter":args.origin,"top_k":args.top_k,"repetitions":args.repetitions,
                     "prepare_seconds":prepare_seconds,"elapsed_seconds":time.perf_counter()-start,
                     "peak_python_rss_bytes":peak[0],"database":stats(conn),"parameters":parameters,
                     "overall":summarize(rows),"groups":grouped,"api_calls":0,"api_cost_usd":0,
                     "local_monetary_cost":None,"absent_queries":0,"artificial_typo_queries":0,
                     "limitations":["Existing reference tests plus explicitly labeled clean real-identity lookups, not user search logs.",
                                    "No absent-target or typo robustness claims; corpus is legislation plus precedents, not general case law.",
                                    "Latency is in-process lookup including database calls; structured query preparation is excluded.",
                                    "Python RSS excludes PostgreSQL server and operating-system caches."]}
            try:summary["code_commit"]=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
            except subprocess.CalledProcessError:summary["code_commit"]=None
            summary["versions"]={p:importlib.metadata.version(p) for p in ("psycopg","bm25s","rapidfuzz","splink","duckdb","pyarrow","numpy")}
            (root/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            print(json.dumps(summary["overall"],ensure_ascii=True),flush=True)
            return summary
    finally:
        stop.set();monitor.join(timeout=1)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--method",choices=METHODS,required=True)
    p.add_argument("--queries",type=Path,default=Path("artifacts/c1/queries.jsonl"))
    p.add_argument("--output",type=Path,default=Path("reports/c1/real"))
    p.add_argument("--split",choices=["train","dev","test"],default="test")
    p.add_argument("--origin",default="all")
    p.add_argument("--repetitions",type=int,default=3)
    p.add_argument("--top-k",type=int,default=100)
    p.add_argument("--limit",type=int)
    a=p.parse_args()
    if a.repetitions<1 or a.top_k<1:p.error("repetitions and top-k must be positive")
    execute(a)
