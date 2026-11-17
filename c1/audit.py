"""Audit the actual corpus, identity split, persisted queries and query plans."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import psutil
from .db import connect, stats
from .model import reference
from .queries import load, gold_ids


def audit(queries_path, output):
    queries=load(queries_path); memberships=defaultdict(set)
    for q in queries:
        for identity in q.gold:memberships[identity].add(q.split)
    leakage={k:sorted(v) for k,v in memberships.items() if len(v)>1}
    if leakage:raise ValueError(f"Identity leakage: {leakage}")
    with connect() as conn:
        mismatches=[q.query_id for q in queries if not set(q.gold).issubset(set(gold_ids(q.fields,conn)))]
        if mismatches:raise ValueError(f"Ungrounded positive identities: {mismatches}")
        plans={}
        for collection in ('precedentes','dispositivos'):
            q=next(q for q in queries if q.split=='test' and q.fields['collection']==collection)
            plans[collection]=conn.execute('''EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON)
                SELECT entity_id,1-(reference <-> %s) AS score FROM c1.entities
                WHERE collection=%s ORDER BY reference <-> %s,entity_id LIMIT 100''',
                (reference(q.fields),collection,reference(q.fields))).fetchone()['QUERY PLAN']
        result={'kind':'actual_database_and_query_audit','utc':datetime.now(timezone.utc).isoformat(),
            'database':stats(conn),'queries':len(queries),'splits':dict(Counter(q.split for q in queries)),
            'identity_leakage':leakage,'ungrounded_gold_queries':mismatches,
            'source_snapshots':conn.execute('SELECT filename,sha256,rows FROM c1.source_snapshots ORDER BY filename').fetchall(),
            'sql_audit':conn.execute('''SELECT method,status,count(*) AS calls FROM c1.query_audit
                GROUP BY method,status ORDER BY method,status''').fetchall(),
            'indexes':conn.execute('''SELECT indexrelname,pg_relation_size(indexrelid) AS bytes
                FROM pg_stat_user_indexes WHERE schemaname='c1' ORDER BY indexrelname''').fetchall(),
            'trigram_query_plans':plans,
            'hardware':{'os':platform.platform(),'cpu':platform.processor(),'logical_cpus':psutil.cpu_count(),
                'physical_cpus':psutil.cpu_count(logical=False),'ram_bytes':psutil.virtual_memory().total},
            'unmeasured':{'concurrent_capacity':'No load generator or isolated machine.',
                'production_update_sla':'No production ingestion workload.',
                'absent_target_false_acceptance':'No real absent-target labeled queries.',
                'typo_robustness':'No real typo queries; no fabricated perturbations.'}}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'queries':len(queries),'leaks':len(leakage),'ungrounded':len(mismatches)}))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--queries',default='artifacts/c1/queries.jsonl')
    p.add_argument('--output',default='reports/c1/real/audit.json')
    a=p.parse_args();audit(a.queries,a.output)
