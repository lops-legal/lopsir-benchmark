import math
import statistics


def ranking_metrics(gold, ranked):
    positives=set(gold)
    if not positives:return None
    ranks=[i for i,d in enumerate(ranked,1) if d in positives]
    result={"hit@1":float(bool(ranks) and ranks[0]==1),"mrr@10":1/ranks[0] if ranks and ranks[0]<=10 else 0.0}
    for k in (10,20,100):
        count=sum(i<=k for i in ranks)
        result[f"recall@{k}"]=count/len(positives)
        result[f"precision@{k}"]=count/k
    dcg=sum(1/math.log2(i+1) for i in ranks if i<=10)
    ideal=sum(1/math.log2(i+1) for i in range(1,min(len(positives),10)+1))
    result["ndcg@10"]=dcg/ideal
    return result


def summarize(rows):
    good=[r for r in rows if r["status"]=="ok"]
    quality={key:statistics.mean(r["metrics"][key] for r in rows) for key in rows[0]["metrics"]} if rows else {}
    timings=[t for r in good for t in r["query_ms"]]
    def percentile(p):
        if not timings:return None
        s=sorted(timings);pos=(len(s)-1)*p/100;lo=int(pos);hi=min(lo+1,len(s)-1)
        return s[lo]+(s[hi]-s[lo])*(pos-lo)
    return {"queries":len(rows),"failures":len(rows)-len(good),"quality":quality,
            "latency_ms":{f"p{p}":percentile(p) for p in (50,95,99)},
            "measured_successful_calls":len(timings),
            "serial_lookup_qps":1000*len(timings)/sum(timings) if timings and sum(timings)>0 else None}
