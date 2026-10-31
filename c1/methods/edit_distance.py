from rapidfuzz import process
from rapidfuzz.distance import Levenshtein
from ..db import entity_rows
from ..model import Hit, SearchResult, reference


class EditDistance:
    method_id = "C1-M4"
    name = "RapidFuzz Levenshtein exhaustive reference matching"

    def __init__(self, conn, **kwargs):
        self.conn = conn
        self.groups = {}

    def prepare(self):
        for row in entity_rows(self.conn,"entity_id,collection,reference"):
            group = self.groups.setdefault(row["collection"], {"ids": [], "references": []})
            group["ids"].append(row["entity_id"])
            group["references"].append(row["reference"])
        return {"engine":"RapidFuzz", "scorer":"Levenshtein.normalized_similarity", "blocking":"collection_only", "weights":[1,1,1]}

    def search(self, query, k=20):
        group=self.groups[query.fields["collection"]]
        ranked=process.extract(reference(query.fields),group["references"],scorer=Levenshtein.normalized_similarity,limit=k)
        return SearchResult([Hit(group["ids"][index],float(score)) for _,score,index in ranked],len(group["ids"]))
