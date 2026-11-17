"""Second corpus for C2: the user's leis-mcp acervo (federal legislation and precedents).

The leis-mcp repository (github.com/lops-legal/leis-mcp) ships a checked gold set,
tests/consultas_referencia.json, which becomes binary qrels here. The leis system itself
(Manticore BM25F with its weights, analyzer, query syntax and relaxation) is benchmarked as M0
next to the five C2 methods, on the same metrics used for JurisTCU.
"""
import os
import sys
from pathlib import Path

LEIS_SRC = Path(os.environ.get("LEIS_MCP_SRC", Path.home() / "leis-mcp" / "src"))
LEIS_REFERENCE = LEIS_SRC.parent / "tests" / "consultas_referencia.json"
os.environ.setdefault("MANTICORE_URL", "http://127.0.0.1:9308")


def leis_modules():
    """Import the leis-mcp package from its checkout (pure standard library)."""
    if str(LEIS_SRC) not in sys.path:
        sys.path.insert(0, str(LEIS_SRC))
    from leis_mcp import apelidos, busca, consulta, manticore, schema  # noqa: F401
    return busca, consulta, manticore, apelidos
