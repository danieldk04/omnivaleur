"""Een lange titel komt netjes op Marktplaats en 2dehands, zonder los eind.

WAAROM DIT ER IS (07-10-2026, Goudlief)
155 van zijn 672 Shopify-titels zijn langer dan de 60 tekens van Marktplaats. De
extensie kapte ze af op het laatste hele woord en dan stond er "Armbanden van
roestvrij staal, geometrisch, casual," of "... sieraden uit de" op de site. De
server kort nu zelf in vlak voor de opdracht uitgaat (_mp_titel_binnen_grens).

De proef rekent met de echte smartTrunc uit extension/content/shared.js: wat de
extensie typt is smartTrunc(titel uit de opdracht). Met JOBS_BRON=<pad> draait hij
tegen een oude backend/api/jobs.py; die heeft geen zeef en faalt.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _laad():
    bron = os.environ.get("JOBS_BRON")
    if not bron:
        from backend.api import jobs
        return jobs
    spec = importlib.util.spec_from_file_location("jobs_titel_onder_proef", bron)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


api = _laad()
_zeef = getattr(api, "_mp_titel_binnen_grens", lambda db, jobs: 0)

# Letterlijk uit zijn voorraad.
GOUDLIEF = [
    "Acryl kralenkettingen, cirkelvormig, eenvoudig, dagelijks gebruik, eenvoudige serie, damessieraden",
    "Acryl armbanden display set hartvormige eenvoudige, romantische armbanden serie voor dagelijks",
    "Armbanden met bedels van roestvrij staal, bloemen, casual, dagelijks, eenvoudig, serie",
    "Acryl kralenarmbanden, eenvoudige dagelijkse sieraden uit de Simple Series voor dames.",
    "14K vergulde roestvrijstalen oorbellen met hartjesmotief, eenvoudige dagelijkse serie, damessieraden",
    "Broches van roestvrij staal met vlindermotief, eenvoudige dagelijkse sieraden uit de Simple-serie",
    "Acryl kralenkettingen, ronde, casual, dagelijkse, eenvoudige serie, dames sieraden",
    "Armbanden van roestvrij staal, geometrisch, casual, dagelijks, eenvoudig, serie, damessieraden",
    "Acryl kralen armbanden hart retro dagelijkse klassieke serie dames sieraden",
    "Armbanden met strass steentjes, druppelvormig, eenvoudig, dagelijks gebruik, eenvoudige serie, dames",
    "Cetabever Dekkende Buitenbeits - 0,75 liter - Bentheimer Geel",
    "Armbanden met touwbedeltjes, hartjes, zoete, romantische serie voor dagelijks gebruik, damessieraden",
]
LOS_EIND = {"de", "het", "een", "en", "of", "met", "van", "voor", "uit", "in", "op", "aan"}


class _DB:
    def __init__(self):
        self.opgeslagen = []

    def table(self, _naam):
        return self

    def update(self, data):
        self.opgeslagen.append(data)
        return self

    def eq(self, *_a):
        return self

    def execute(self):
        return self


def _smart_trunc(titels: list[str]) -> list[str]:
    """De echte smartTrunc van de extensie, in node gedraaid."""
    if not shutil.which("node"):
        pytest.skip("node ontbreekt")
    bron = (ROOT / "extension/content/shared.js").read_text()
    functie = re.search(r"function smartTrunc\(str, maxLen\) \{.*?\n  \}\n", bron, re.S).group(0)
    script = functie + "const t=JSON.parse(require('fs').readFileSync(0,'utf8'));" \
                       "process.stdout.write(JSON.stringify(t.map(s=>smartTrunc(s,60))));"
    uit = subprocess.run(["node", "-e", script], input=json.dumps(titels),
                         capture_output=True, text=True, check=True)
    return json.loads(uit.stdout)


def _uitgaand(titel, platform="marktplaats", actie="create"):
    job = {"id": "j1", "platform": platform, "action": actie, "payload": {"title": titel}}
    _zeef(_DB(), [job])
    return job["payload"]["title"]


def test_wat_op_marktplaats_komt_heeft_geen_los_eind():
    getypt = _smart_trunc([_uitgaand(t) for t in GOUDLIEF])
    for orig, t in zip(GOUDLIEF, getypt):
        assert len(t) <= 60, t
        assert not t.endswith((",", ";", ":", "-", ".")), f"{t!r} (uit {orig!r})"
        assert t.rsplit(" ", 1)[-1].lower() not in LOS_EIND, f"{t!r} (uit {orig!r})"
        assert orig.startswith(t), "inkorten, nooit herschrijven"
        assert len(t) >= 30, f"te veel weggehaald: {t!r}"


def test_extensie_typt_letterlijk_wat_in_de_opdracht_staat():
    uit = [_uitgaand(t) for t in GOUDLIEF]
    assert _smart_trunc(uit) == uit


def test_2dehands_en_bijwerken_ook():
    lang = GOUDLIEF[7]
    assert len(_uitgaand(lang, "2dehands")) <= 60
    assert len(_uitgaand(lang, "marktplaats", "content_refresh")) <= 60


def test_verwijderen_vinted_en_korte_titel_blijven_ongemoeid():
    lang = GOUDLIEF[7]
    assert _uitgaand(lang, "marktplaats", "delete") == lang
    assert _uitgaand(lang, "vinted") == lang
    kort = "Acryl kralenarmbanden met hartje"
    assert _uitgaand(kort) == kort


def test_ingekorte_titel_wordt_in_de_opdracht_bewaard():
    db = _DB()
    job = {"id": "j1", "platform": "marktplaats", "action": "create",
           "payload": {"title": GOUDLIEF[0], "price": 12.5}}
    assert _zeef(db, [job]) == 1
    assert db.opgeslagen == [{"payload": job["payload"]}]
    assert job["payload"]["price"] == 12.5


def test_emoji_telt_zoals_de_browser_telt():
    titel = "Gouden ring 💍 " + "met zirkonia steentjes en hartjesmotief voor dames"
    uit = _uitgaand(titel)
    assert len(uit.encode("utf-16-le")) // 2 <= 60


def test_hoofdletter_aan_het_eind_blijft():
    titel = "Tabletten voor volwassenen met extra Vitamine A " + "x" * 20
    assert api._mp_titel(titel).endswith("Vitamine A")
