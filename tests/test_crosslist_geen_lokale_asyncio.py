"""Een `import asyncio` binnen een functie maakt asyncio daar een lokale naam.

Op 23-11 zette commit c79f2d69 er een in publish_to_platforms; elke plaatsing gaf daarna
UnboundLocalError (HTTP 500, o.a. code 207C6E bij Esther). Deze proef houdt dat tegen.
"""
import ast
from pathlib import Path

BESTAND = Path(__file__).resolve().parent.parent / "backend" / "services" / "crosslist.py"


def test_geen_lokale_import_van_asyncio():
    boom = ast.parse(BESTAND.read_text(encoding="utf-8"))
    fout = []
    for functie in ast.walk(boom):
        if isinstance(functie, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(functie):
                if isinstance(n, ast.Import) and any(a.name == "asyncio" for a in n.names):
                    fout.append(f"{functie.name} regel {n.lineno}")
    assert not fout, f"lokale import asyncio in: {fout}"
