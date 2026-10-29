"""Fellegi-Sunter linkage using Splink, fitted only from real training lookups."""
import hashlib
from pathlib import Path
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from splink import DuckDBAPI, Linker, SettingsCreator
import splink.comparison_library as cl
from ..model import Hit, SearchResult

FIELDS=("collection","authority","kind","number","year","article")
ARROW_SCHEMA=pa.schema([(c,pa.string()) for c in ("entity_id",)+FIELDS+("known_identity",)])


def to_record(identifier,fields,known=None):
    return {"entity_id":identifier,**{k:(str(fields[k]) if fields.get(k) not in (None,"") else None) for k in FIELDS},"known_identity":known}


class Linkage:
    method_id="C1-M5"
    name="Splink Fellegi-Sunter with training-only linked pairs"

    def __init__(self,conn,training_queries=None,work_dir="work/c1-linkage",**kwargs):
        self.conn=conn;self.training_queries=[q for q in (training_queries or []) if len(q.gold)==1]
        self.root=Path(work_dir);self.root.mkdir(parents=True,exist_ok=True)

    def prepare(self):
        if not self.training_queries:raise ValueError("No real training identity lookups; refusing fabricated weights")
        path=self.root/"corpus.parquet"
        with pq.ParquetWriter(path,ARROW_SCHEMA,compression="zstd") as writer,self.conn.transaction():
            with self.conn.cursor(name="c1_linkage_export") as cur:
                cur.execute("SELECT entity_id,collection,authority,kind,number,year,article FROM c1.entities ORDER BY entity_id")
                while batch:=cur.fetchmany(5000):
                    writer.write_table(pa.Table.from_pylist([to_record(r["entity_id"],r,r["entity_id"]) for r in batch],schema=ARROW_SCHEMA))
        self.duck=duckdb.connect(str(self.root/"linkage.duckdb"))
        self.duck.execute("SET memory_limit='256MB'")
        self.duck.execute("SET threads=2")
        self.duck.execute("CREATE OR REPLACE TABLE corpus AS SELECT * FROM read_parquet(?)",[str(path)])
        self.api=DuckDBAPI(self.duck)
        self.corpus=self.api.register("corpus",dataset_display_name="corpus")
        training=pa.Table.from_pylist([to_record("training:"+q.query_id,q.fields,q.gold[0]) for q in self.training_queries],schema=ARROW_SCHEMA)
        train=self.api.register(training,table_name="training_queries",dataset_display_name="training_queries")
        comparisons=[cl.ExactMatch(c) for c in FIELDS if c!="number"]+[cl.LevenshteinAtThresholds("number",[1,2])]
        settings=SettingsCreator(link_type="link_only",unique_id_column_name="entity_id",comparisons=comparisons,
            blocking_rules_to_generate_predictions=["l.collection=r.collection AND l.number=r.number"],
            retain_matching_columns=False,retain_intermediate_calculation_columns=False)
        self.linker=Linker([self.corpus,train],settings)
        self.linker.training.estimate_probability_two_random_records_match(["l.known_identity=r.known_identity"],recall=1.0)
        self.linker.training.estimate_u_using_random_sampling(max_pairs=100000,seed=42,min_count_per_level=1,num_chunks=3)
        self.linker.training.estimate_m_from_label_column("known_identity")
        self.linker.misc.save_model_to_json(str(self.root/"trained-model.json"),overwrite=True)
        return {"engine":"Splink/DuckDB","training_queries":len(self.training_queries),"test_labels_used":False,
                "blocking":"same collection and exact reference number", "u_max_pairs":100000,
                "m_source":"linked training identity pairs", "calibration_claimed":False,
                "limitations":"Training lookups are clean. Unobserved disagreement levels may retain library defaults; inspect trained model."}

    def search(self,query,k=20):
        name="query_"+hashlib.sha256(query.query_id.encode()).hexdigest()[:16]
        table=self.api.register(pa.Table.from_pylist([to_record("query:"+query.query_id,query.fields)],schema=ARROW_SCHEMA),table_name=name,dataset_display_name=name)
        predictions=self.linker.inference.predict_between(self.corpus,table,warning_mode="auto")
        # Use SQL LIMIT before materializing Python records; include linkage time in search.
        rows=self.duck.execute(f'''SELECT entity_id_l,entity_id_r,match_probability
            FROM "{predictions.physical_name}" ORDER BY match_probability DESC,entity_id_l,entity_id_r LIMIT ?''',[k]).fetchall()
        total=self.duck.execute(f'SELECT count(*) FROM "{predictions.physical_name}"').fetchone()[0]
        hits=[]
        for left,right,score in rows:
            target=right if str(left).startswith("query:") else left
            hits.append(Hit(target,float(score)))
        predictions.drop_table_from_database_and_remove_from_cache()
        table.drop_table_from_database_and_remove_from_cache()
        return SearchResult(hits,total)
