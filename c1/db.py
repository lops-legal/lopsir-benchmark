import os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

DEFAULT_DSN = "host=127.0.0.1 port=55431 user=lopsir dbname=postgres connect_timeout=10"


def connect():
    return psycopg.connect(os.environ.get("LOPSIR_C1_DSN", DEFAULT_DSN), row_factory=dict_row, autocommit=True)


def create_schema(conn):
    conn.execute((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))


def entity_rows(conn, columns="entity_id,collection,authority,kind,number,year,article,norm_key,reference"):
    # Column selection is internal code, never user-supplied SQL.
    return conn.execute(f"SELECT {columns} FROM c1.entities ORDER BY entity_id").fetchall()


def stats(conn):
    return {
        "server": conn.execute("SELECT version() AS version").fetchone()["version"],
        "records_by_collection": conn.execute("SELECT collection,count(*) AS rows FROM c1.records GROUP BY collection ORDER BY collection").fetchall(),
        "entities_by_collection": conn.execute("SELECT collection,count(*) AS rows FROM c1.entities GROUP BY collection ORDER BY collection").fetchall(),
        "database_bytes": conn.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"],
        "entities_bytes": conn.execute("SELECT pg_total_relation_size('c1.entities') AS bytes").fetchone()["bytes"],
    }
