import bm25s
from ..db import entity_rows
from ..model import Hit, SearchResult, reference


class BM25:
    method_id="C1-M2"
    name="BM25S Lucene variant over real identity references"

    def __init__(self,conn,k1=1.2,b=0.75,**kwargs):
        self.conn=conn;self.k1=k1;self.b=b;self.groups={}

    def prepare(self):
        for row in entity_rows(self.conn,"entity_id,collection,reference"):
            group=self.groups.setdefault(row["collection"],{"ids":[],"references":[]})
            group["ids"].append(row["entity_id"]);group["references"].append(row["reference"])
        for group in self.groups.values():
            group["model"]=bm25s.BM25(k1=self.k1,b=self.b,method="lucene",backend="numpy")
            tokens=bm25s.tokenize(group.pop("references"),stopwords=[],token_pattern=r"(?u)\b\w+\b",show_progress=False)
            group["model"].index(tokens,show_progress=False)
        return {"engine":"bm25s","variant":"lucene","k1":self.k1,"b":self.b,"stemming":False,"stopwords":[],
                "implementation_paper":"https://arxiv.org/abs/2407.03618","code":"https://github.com/xhluca/bm25s"}

    def search(self,query,k=20):
        group=self.groups[query.fields["collection"]]
        tokens=bm25s.tokenize([reference(query.fields)],stopwords=[],token_pattern=r"(?u)\b\w+\b",show_progress=False)
        indices,scores=group["model"].retrieve(tokens,k=min(k,len(group["ids"])),show_progress=False,n_threads=1)
        hits=[Hit(group["ids"][int(i)],float(s)) for i,s in zip(indices[0],scores[0]) if s>0]
        return SearchResult(hits,len(group["ids"]))
