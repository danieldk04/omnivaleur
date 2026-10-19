"""Na de Vinted-plaatsklik kijkt de achtergrond zelf in de kast.

WAAROM DIT ER IS (18/19-10-2026, Janneke 31d28378)
"Ik ben er achter gekomen dat er pas een nieuw tabblad opent als ik de vorige
handmatig gesloten heb." Gemeten in haar opdrachten: na "plaatsen: op de knop
geklikt" meldt het invulscript nooit meer iets. Van haar 110 geslaagde
Vinted-plaatsingen sinds 12-10 werden er 88 pas na 170 s of later afgemeld, door
de bewaker die na drie minuten in de kast kijkt. Zolang staat het tabblad stil en
geeft de server geen volgende Vinted-opdracht uit. Sloot zij het tabblad, dan
kwam de volgende binnen een halve minuut.

Nu kijkt de achtergrond vanaf de klik elke paar seconden zelf, met het hoogwater
van vlak voor de klik, en sluit het tabblad zodra de advertentie er staat.
De proef draait de echte functies uit background.js in node, met een nagemaakte
kast waarin de advertentie 30 s na de klik verschijnt (tijd 100x versneld).
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
VOOR = "206f955e"   # extensie 1.0.397, de versie van 18-10
TITEL = "Winterjas Noppies maat 140"


def _bron(commit=None):
    if commit is None:
        return (ROOT / "extension/background.js").read_text(encoding="utf-8")
    return subprocess.run(["git", "show", f"{commit}:extension/background.js"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout


def _stuk(bron, kop, eind="\n}\n"):
    start = bron.index(kop)
    return bron[start:bron.index(eind, start) + len(eind)]


def _draai(meta, kast_voor, nieuw, verschijnt_na_s, ook_bewaker_al_klaar=False):
    if NODE is None:
        pytest.skip("node is niet geïnstalleerd")
    bron = _bron()
    blok = bron[bron.index("const NA_KLIK_INTERVAL_MS"):]
    blok = _stuk(blok, "const NA_KLIK_INTERVAL_MS")   # tot het einde van vintedNaKlikZoeken
    blok = (blok.replace("6000;", "60;").replace("150000;", "1500;")
            .replace("await sleep(4000);", "await sleep(40);"))
    js = f"""
const T0 = Date.now(), SCHAAL = 100;
const VINTED_ORIGINS = ["https://www.vinted.nl"];
let opslag = {{ jobtab_7: {json.dumps(meta)} }};
const chrome = {{ storage: {{ local: {{
  get: async (k) => ({{ [k]: opslag[k] }}),
  remove: async (ks) => {{ for (const k of [].concat(ks)) delete opslag[k]; }},
}} }} }};
const kastVoor = {json.dumps(kast_voor)}, nieuw = {json.dumps(nieuw)};
const fetch = async (url) => ({{ ok: true, json: async () => {{
  if (String(url).includes("/users/current")) return {{ user: {{ id: 1 }} }};
  const s = (Date.now() - T0) * SCHAAL / 1000;
  return {{ items: (s >= {verschijnt_na_s} ? [nieuw] : []).concat(kastVoor) }};
}} }});
const uit = {{ afgemeld: [], gesloten: [], wakerUit: [] }};
const finaliseJob = async (_s, jobId, soort, body) => {{
  uit.afgemeld.push({{ jobId, soort, id: body.platform_listing_id,
                       na_s: Math.round((Date.now() - T0) * SCHAAL / 1000) }});
}};
const sluitWerkTabblad = (t) => uit.gesloten.push(t);
const clearJobWatchdog = (t) => uit.wakerUit.push(t);
{_stuk(bron, "function _vintedTitelSleutel(")}
{_stuk(bron, "function _vintedTitelZonderSku(")}
{_stuk(bron, "function _vintedPrijsKlopt(")}
{_stuk(bron, "async function bgVindVintedAdvertentie(")}
{blok}
{"setTimeout(() => { delete opslag.jobtab_7; }, 100);" if ook_bewaker_al_klaar else ""}
vintedNaKlikZoeken(7).then(() => console.log(JSON.stringify(uit)));
"""
    r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _adv(i, prijs):
    return {"id": i, "title": TITEL, "price": {"amount": f"{prijs:.2f}", "currency_code": "EUR"},
            "is_closed": False, "is_draft": False}


META = {"jobId": "j1", "platform": "vinted", "action": "create", "submitClicked": True,
        "vintedNaId": 10419166038, "serverUrl": "s",
        "payload": {"title": TITEL, "price": 48.5, "_vinted_titelgenoten": 2,
                    "_vinted_bezet": ["10419166038"]}}
# Haar kast op 18-10 09:10: het andere meisjesstuk (50 euro) stond er al.
KAST = [_adv(10419166038, 50.0)]
NIEUW = _adv(10422879568, 48.5)


def test_nieuw_afgemeld_en_tabblad_dicht_zodra_hij_online_staat():
    uit = _draai(META, KAST, NIEUW, verschijnt_na_s=30)
    assert [a["id"] for a in uit["afgemeld"]] == ["10422879568"]
    assert uit["afgemeld"][0]["soort"] == "complete"
    assert uit["afgemeld"][0]["na_s"] < 60          # was 180 s of meer
    assert uit["gesloten"] == [7] and uit["wakerUit"] == [7]


def test_nieuw_zonder_hoogwater_doet_het_niets():
    uit = _draai({**META, "vintedNaId": None}, KAST, NIEUW, verschijnt_na_s=10)
    assert uit["afgemeld"] == [] and uit["gesloten"] == []


def test_nieuw_alleen_een_oudere_titelgenoot_is_geen_treffer():
    # De klik leverde niets op: de bewaker beslist zoals vroeger.
    uit = _draai(META, KAST, _adv(10419036363, 48.5), verschijnt_na_s=0)
    assert uit["afgemeld"] == []


def test_nieuw_niet_dubbel_afmelden_als_een_ander_al_afmeldde():
    uit = _draai(META, KAST, NIEUW, verschijnt_na_s=60, ook_bewaker_al_klaar=True)
    assert uit["afgemeld"] == []


def test_oud_keek_na_de_klik_niet_in_de_kast():
    oud = _bron(VOOR)
    handler = _stuk(oud, 'if (msg.type === "SUBMIT_CLICKED") {', "\n  }\n")
    assert "bgVindVintedAdvertentie" not in handler and "vintedNaKlikZoeken" not in oud
    assert re.search(r"const JOB_TAB_TIMEOUT_MIN = 3;", oud)
    nieuw = _stuk(_bron(), 'if (msg.type === "SUBMIT_CLICKED") {', "\n  }\n")
    assert "vintedNaKlikZoeken(sender.tab.id)" in nieuw
