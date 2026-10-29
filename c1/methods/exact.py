from ..model import Hit, SearchResult


class Exact:
    method_id = "C1-M1"
    name = "PostgreSQL exact composite-key lookup"

    def __init__(self, conn, **kwargs):
        self.conn = conn

    def prepare(self):
        return {"engine": "PostgreSQL B-tree", "learned_parameters": False}

    def search(self, query, k=20):
        clauses, values = [], []
        allowed = ("collection", "authority", "kind", "number", "year", "article", "norm_key")
        for field in allowed:
            if query.fields.get(field) not in (None, ""):
                clauses.append(f"{field} = %s")
                values.append(query.fields[field])
        if len(clauses) < 2:
            return SearchResult([], 0)
        where = " AND ".join(clauses)
        rows = self.conn.execute(f"SELECT entity_id FROM c1.entities WHERE {where} ORDER BY entity_id LIMIT %s", values+[k]).fetchall()
        total = self.conn.execute(f"SELECT count(*) AS n FROM c1.entities WHERE {where}", values).fetchone()["n"]
        return SearchResult([Hit(r["entity_id"], 1.0) for r in rows], total)
