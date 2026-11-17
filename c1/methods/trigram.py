from ..model import Hit, SearchResult, reference


class Trigram:
    method_id = "C1-M3"
    name = "PostgreSQL pg_trgm GiST KNN"

    def __init__(self, conn, **kwargs):
        self.conn = conn

    def prepare(self):
        self.conn.execute("CREATE INDEX IF NOT EXISTS c1_trigram_gist ON c1.entities USING gist(reference gist_trgm_ops(siglen=64))")
        self.conn.execute("ANALYZE c1.entities")
        return {"engine": "pg_trgm GiST", "siglen": 64, "ranking": "reference <-> query_reference", "similarity_cutoff": None}

    def search(self, query, k=20):
        ref = reference(query.fields)
        rows = self.conn.execute("""SELECT entity_id, 1-(reference <-> %s) AS score
            FROM c1.entities WHERE collection=%s
            ORDER BY reference <-> %s, entity_id LIMIT %s""",
            (ref, query.fields["collection"], ref, k)).fetchall()
        return SearchResult([Hit(r["entity_id"],float(r["score"])) for r in rows], len(rows))
