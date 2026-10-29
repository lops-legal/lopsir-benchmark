from dataclasses import dataclass, field
import re
import unicodedata


def normalize(value):
    value = "" if value is None else str(value)
    value = "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", value, flags=re.UNICODE))


def number(value):
    return str(value or "").replace(".", "").strip()


def reference(fields):
    order = ("authority", "kind", "number", "year", "article")
    return " ".join(normalize(fields[k]) for k in order if fields.get(k) not in (None, "", 0))


@dataclass
class Query:
    query_id: str
    text: str
    fields: dict
    gold: list[str] = field(default_factory=list)
    origin: str = "existing_reference_test"
    split: str = "test"
    group: str = ""


@dataclass
class Hit:
    entity_id: str
    score: float


@dataclass
class SearchResult:
    hits: list[Hit]
    candidate_count: int
    stages_ms: dict = field(default_factory=dict)
