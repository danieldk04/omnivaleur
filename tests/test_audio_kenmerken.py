"""Type en Wattage bij audio, tv en foto.

Deze velden zijn niet verplicht — een advertentie komt zonder ook online — maar
wie in de zoekfilters op "Type" filtert, ziet een advertentie zonder type niet
staan. Dat is stille onzichtbaarheid, dezelfde fout als ooit bij sportkleding.

De keuzelijsten in marktplaats.js zijn woordelijk opgehaald uit de facetten van
Marktplaats' eigen zoek-API. Een zelfbedachte waarde wordt door het formulier
genegeerd en is dan niet van "niet ingevuld" te onderscheiden — vandaar dat deze
test vooral bewaakt dát er niets zelfbedacht in staat.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MP_JS = ROOT / "extension" / "content" / "marktplaats.js"


def _blok() -> str:
    """Het stuk marktplaats.js dat op zichzelf kan draaien: de tabellen en de
    twee keuzefuncties, tot aan fillForm (die de pagina nodig heeft)."""
    src = MP_JS.read_text(encoding="utf-8")
    return src[src.index("  const MP_AUDIO_TYPE = {"):src.index("  async function fillForm(item) {")]


def _tabel(naam: str) -> dict:
    src = MP_JS.read_text(encoding="utf-8")
    start = src.index(f"  const {naam} = {{")
    eind = src.index("\n  };", start)
    body = src[start + len(f"  const {naam} = {{"):eind]
    return json.loads("{" + body.rstrip().rstrip(",") + "}")


@pytest.fixture(scope="module")
def typen():
    return _tabel("MP_AUDIO_TYPE")


@pytest.fixture(scope="module")
def wattage():
    return _tabel("MP_AUDIO_WATT")


def test_de_type_lijsten_zijn_er_nog(typen):
    assert len(typen) == 39, f"{len(typen)} in plaats van 39 categorieën met een Type"
    for cat, opties in typen.items():
        assert opties, cat
        assert len(set(opties)) == len(opties), f"dubbele optie in {cat}"
        assert all(isinstance(o, str) and o.strip() for o in opties), cat


def test_elke_categorie_bestaat_ook_in_het_dashboard(typen, wattage):
    """Een keuzelijst voor een categorie die niemand kan kiezen is dood gewicht,
    en wijst er meestal op dat een sleutel hernoemd is."""
    app = (ROOT / "frontend" / "app.html").read_text(encoding="utf-8")
    start = app.index("  audio: [")
    blok = app[start:app.index("\n  ],", start)]
    bekend = {k[len("audio "):] for k in re.findall(r'\["(audio [^"]+)"', blok)}
    for cat in list(typen) + list(wattage):
        assert cat in bekend, f"'{cat}' staat niet in de audio-lijst van het dashboard"


def test_de_wattagevakken_sluiten_op_elkaar_aan(wattage):
    """De indeling verschilt per categorie — luidsprekers kent 120-150, versterkers
    niet. Een gat of overlap zou artikelen in het verkeerde vak zetten."""
    assert set(wattage) == {"luidsprekers", "versterkers en receivers"}
    for cat, vakken in wattage.items():
        assert vakken[0][0] == 0, cat
        assert vakken[-1][1] is None, f"{cat} heeft geen open bovenvak"
        for (_, boven, _), (onder_v, _, _) in zip(vakken, vakken[1:]):
            assert boven == onder_v, f"gat of overlap in {cat}"


# titel, categorie, verwacht type, verwacht wattage
GEVALLEN = [
    ("JBL Charge 5 draagbare speaker bluetooth 150 watt", "audio luidsprekers",
     "Draagbare speaker", "150 watt of meer"),
    # Meervoud: het label is enkelvoud, de verkoper schrijft meervoud.
    ("Bowers & Wilkins 603 vloerstaande luidsprekers 30W", "audio luidsprekers",
     "Vloerstaande luidspreker", "Minder dan 60 watt"),
    ("KEF LS50 bookshelf speakers 100W", "audio luidsprekers",
     "Boekenplank luidspreker", "60 tot 120 watt"),
    # Geen herkenbaar type → het vangnet van Marktplaats zelf, nooit een gok.
    ("Onbekend merk speaker", "audio luidsprekers", "Overige typen", None),
    # Versterkers hebben wél wattage maar géén type-lijst.
    ("Marantz PM6007 versterker 130 watt", "audio versterkers en receivers",
     None, "120 watt of meer"),
    ("Sony WH-1000XM5 over-ear koptelefoon", "audio koptelefoons", "Over-ear", None),
    ("Apple AirPods Pro oordopjes", "audio koptelefoons", "In-ear", None),
    ("Canon EOS 90D DSLR body", "audio fotocamera s digitaal", "Spiegelreflex", None),
    ("Sony A7 III mirrorless", "audio fotocamera s digitaal", "Systeemcamera", None),
    # s→z-meervoud: "lens" wordt "lenzen".
    ("Canon 70-200 telelenzen", "audio lenzen en objectieven", "Telelens", None),
    ("Sigma 14mm groothoek objectief", "audio lenzen en objectieven", "Groothoeklens", None),
    # Langste label wint, anders pakt "SD" het van "MicroSDXC".
    ("SanDisk 128GB microSDXC kaart", "audio geheugenkaarten", "MicroSDXC", None),
    ("Samsung 55 inch QLED televisie", "audio televisies", "QLED", None),
    # Categorie zonder Type-lijst: niets invullen.
    ("Universele oplader", "audio opladers", None, None),
    # Buiten de audio-tak mag dit nooit aanslaan.
    ("Levi 501 spijkerbroek", "dames jeans", None, None),
    # Geen getal met watt = geen wattage. Raden is hier net zo schadelijk als
    # een verkeerd type: de koper filtert de advertentie er juist mee weg.
    ("Losse speaker zonder specificaties", "audio luidsprekers", "Overige typen", None),
]


@pytest.mark.skipif(not shutil.which("node"), reason="node niet beschikbaar")
def test_de_keuze_klopt_voor_echte_advertentieteksten(tmp_path):
    script = tmp_path / "proef.js"
    script.write_text(
        _blok()
        + "\nconst gevallen = " + json.dumps(GEVALLEN, ensure_ascii=False) + ";\n"
        + """
        const uit = gevallen.map(([titel, cat]) => {
          const item = { category: cat, title: titel, description: "" };
          return [mpAudioType(item), mpAudioWattage(item)];
        });
        console.log(JSON.stringify(uit));
        """,
        encoding="utf-8",
    )
    r = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    gekregen = json.loads(r.stdout)

    fouten = []
    for (titel, cat, v_type, v_watt), (g_type, g_watt) in zip(GEVALLEN, gekregen):
        if [g_type, g_watt] != [v_type, v_watt]:
            fouten.append(f"{titel!r} ({cat}): kreeg {g_type!r}/{g_watt!r}, "
                          f"verwacht {v_type!r}/{v_watt!r}")
    assert not fouten, "\n".join(fouten)


@pytest.mark.skipif(not shutil.which("node"), reason="node niet beschikbaar")
def test_er_wordt_nooit_een_waarde_verzonnen(tmp_path, typen, wattage):
    """De harde eis: wat de functie teruggeeft moet lettelijk in de lijst van
    Marktplaats staan, of null zijn. Een waarde die er niet in staat wordt door
    het formulier genegeerd en lijkt dan op 'niet ingevuld'."""
    script = tmp_path / "alles.js"
    proeven = [
        [f"{woord} te koop, 250 watt, in nette staat", f"audio {cat}"]
        for cat in list(typen) + list(wattage)
        for woord in ("willekeurige tekst zonder aanwijzing", "set compleet")
    ]
    script.write_text(
        _blok()
        + "\nconst p = " + json.dumps(proeven, ensure_ascii=False) + ";\n"
        + """
        console.log(JSON.stringify(p.map(([t, c]) => {
          const item = { category: c, title: t, description: "" };
          return [c, mpAudioType(item), mpAudioWattage(item)];
        })));
        """,
        encoding="utf-8",
    )
    r = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr

    for cat, t, w in json.loads(r.stdout):
        kaal = cat[len("audio "):]
        assert t is None or t in typen.get(kaal, []), f"verzonnen type {t!r} bij {cat}"
        assert w is None or w in [v[2] for v in wattage.get(kaal, [])], \
            f"verzonnen wattage {w!r} bij {cat}"
