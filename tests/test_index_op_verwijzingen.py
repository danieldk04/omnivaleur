"""Elke kolom die naar items verwijst heeft een index in schema.sql.

12-10-2026: een artikel verwijderen liep in een statement timeout (57014), omdat
Postgres bij ON DELETE CASCADE / SET NULL de hele jobs- en import_candidates-tabel
las op zoek naar rijen van dat artikel. Een nieuwe verwijzing zonder index brengt
dat terug; deze proef faalt dan.
"""
import re
from pathlib import Path

SCHEMA = (Path(__file__).resolve().parent.parent / "schema.sql").read_text()


def _verwijzingen():
    """(tabel, kolom) voor elke kolom met REFERENCES items(id)."""
    paren = []
    for blok in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\n\);", SCHEMA, re.S | re.I):
        for kol in re.findall(r"^\s*(\w+)\s+UUID\s+REFERENCES\s+items\s*\(id\)", blok.group(2), re.M | re.I):
            paren.append((blok.group(1), kol))
    for tabel, kol in re.findall(
            r"ALTER TABLE\s+(\w+)\s+ADD COLUMN(?: IF NOT EXISTS)?\s+(\w+)\s+UUID\s+REFERENCES\s+items", SCHEMA, re.I):
        paren.append((tabel, kol))
    return paren


def _geindexeerd(tabel, kol):
    return re.search(rf"CREATE (?:UNIQUE )?INDEX[^;]*\bON\s+{tabel}\s*\(\s*{kol}\s*[,)]", SCHEMA, re.I)


def test_verwijzingen_gevonden():
    assert {"listings", "jobs", "import_candidates"} <= {t for t, _ in _verwijzingen()}


def test_elke_verwijzing_naar_items_heeft_een_index():
    zonder = [f"{t}.{k}" for t, k in _verwijzingen() if not _geindexeerd(t, k)]
    assert not zonder, f"Geen index op {zonder}: een artikel verwijderen leest dan de hele tabel"
