"""Vinted-woontextiel zonder kleur krijgt een kleur mee (Daniel, 15-11-2026).

Vinted eist een kleur bij dekens en kleden. Toon (dejuistetoon) kwam in een maand
met 14 artikelen niet op Vinted: "colour (empty, no colour on this item and
nothing usable in the title)". Daarna zette hij ze zelf op Meerkleurig en kwamen
ze wel online (gemeten 09-11 en 10-11). De server doet dat nu zelf in de
uitgaande opdracht: eerst een kleur uit de titel, anders "Various".

De titels en rubrieken hieronder komen uit Toons echte mislukte opdrachten.
De laatste proef draait de ECHTE parseColours uit extension/content/vinted.js op
de opdracht zoals de server hem verstuurt, en op de opdracht zonder vangnet.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.api.jobs import _vinted_meerkleurig_vangnet  # noqa: E402


def _job(title, category, color=None, platform="vinted", action="create"):
    return {"id": "x", "platform": platform, "action": action,
            "payload": {"title": title, "category": category, "color": color}}


ECHT_MISLUKT = [
    ("Klassieke grand foulard met franjes 210/70 cm", "wonen plaids en woondekens", "Various"),
    ("Kelim kleed traditioneel patroon en kleurstelling 134/70", "wonen tapijten en kleden", "Various"),
    ("Perzisch handgeknoopt tapijt koper kleurig 172/105", "antiek kleden en textiel", None),
    ("Grand foulard woonkleed gekleurde banen 262/147", "wonen plaids en woondekens", "Various"),
    ("Kelim poefkussen 55/55 cm", "wonen tapijten en kleden", "Various"),
    ("Tapijt Perzisch dessin roodbruin 158/90", "wonen tapijten en kleden", "Brown"),
]


def test_echte_mislukte_artikelen_krijgen_een_kleur():
    for titel, rubriek, verwacht in ECHT_MISLUKT:
        jobs = [_job(titel, rubriek)]
        assert _vinted_meerkleurig_vangnet(jobs) == 1, titel
        kleur = jobs[0]["payload"]["color"]
        assert kleur, titel
        if verwacht:
            assert kleur == verwacht, (titel, kleur)


def test_titel_met_twee_kleuren():
    jobs = [_job("Klassiek getint beddensprei kleed lindegroen roomwit 190/134",
                 "wonen plaids en woondekens")]
    _vinted_meerkleurig_vangnet(jobs)
    assert jobs[0]["payload"]["color"] == "Green, White"


def test_blijft_af_van_wat_niet_mag():
    jobs = [
        _job("Grand foulard", "wonen plaids en woondekens", color="blauw"),   # heeft kleur
        _job("Zwarte jas", "dames jassen"),                                   # geen woontextiel
        _job("Grand foulard", "wonen plaids en woondekens", platform="marktplaats"),
        _job("Grand foulard", "wonen plaids en woondekens", action="delete"),
        _job("Babykleding setje", "babykleding"),
    ]
    assert _vinted_meerkleurig_vangnet(jobs) == 0
    assert jobs[0]["payload"]["color"] == "blauw"
    assert all(not j["payload"]["color"] for j in jobs[1:])


def _extensie_kleuren(payloads):
    """parseColours uit de echte vinted.js, op een lijst payloads."""
    js = r"""
const fs = require("fs"), vm = require("vm");
const bron = fs.readFileSync(process.argv[1], "utf8");
const kaart = bron.match(/const COLOUR_MAP = \{[\s\S]*?\n  \};/)[0];
const functie = bron.match(/function parseColours\(item\) \{[\s\S]*?\n  \}\n/)[0];
const hulp = (bron.match(/function kaartKleur\(w\) \{[\s\S]*?\n  \}\n/) || [""])[0];
const ctx = {};
vm.runInNewContext(`${kaart}\n${hulp}\n${functie}\nthis.parseColours = parseColours;`, ctx);
const items = JSON.parse(process.argv[2]);
console.log(JSON.stringify(items.map((i) => ctx.parseColours(i))));
"""
    uit = subprocess.run(
        ["node", "-e", js, str(ROOT / "extension/content/vinted.js"), json.dumps(payloads)],
        capture_output=True, text=True, check=True)
    return json.loads(uit.stdout)


def test_echte_extensie_voor_en_na():
    zonder = [_job(t, r)["payload"] for t, r, _ in ECHT_MISLUKT]
    met = [dict(p) for p in zonder]
    _vinted_meerkleurig_vangnet([{"platform": "vinted", "action": "create", "payload": p} for p in met])
    voor = _extensie_kleuren(zonder)
    na = _extensie_kleuren(met)
    # Zonder vangnet vindt de extensie bij deze titels niets: precies de fout van Toon.
    assert sum(1 for k in voor if not k) >= 5, voor
    assert all(na), na


# Mieke (brocantedepot, 25-11-2026): vazen, kandelaars en schaaltjes zonder kleur,
# 49 van 51 Vinted-plaatsingen "colour (empty ...)". Titels uit haar echte opdrachten.
BROCANTE = [
    ("Vaas West Germany 521-14", "antiek woonaccessoires", "Various"),
    ("Koperen kandelaar", "antiek woonaccessoires", "Various"),
    ("Koehoorn", "antiek woonaccessoires", "Various"),
    ("Aardewerk kruik", "antiek woonaccessoires", "Various"),
    ("Koperen kandelaar", "antiek curiosa en brocante", "Various"),
]


def test_brocante_zonder_kleur_krijgt_een_kleur():
    for titel, rubriek, verwacht in BROCANTE:
        jobs = [_job(titel, rubriek)]
        assert _vinted_meerkleurig_vangnet(jobs) == 1, titel
        assert jobs[0]["payload"]["color"] == verwacht, titel


def test_brocante_met_eigen_kleur_of_ander_kanaal_blijft_staan():
    jobs = [
        _job("Vintage messing uiltjes", "antiek woonaccessoires", color="Gold"),
        _job("Koperen kandelaar", "antiek woonaccessoires", platform="marktplaats"),
        _job("Koperen kandelaar", "antiek woonaccessoires", action="delete"),
    ]
    assert _vinted_meerkleurig_vangnet(jobs) == 0
    assert jobs[0]["payload"]["color"] == "Gold"
    assert not jobs[1]["payload"]["color"] and not jobs[2]["payload"]["color"]


def test_brocante_opdracht_geeft_de_extensie_een_kleur():
    jobs = [_job("Koperen kandelaar", "antiek woonaccessoires")]
    _vinted_meerkleurig_vangnet(jobs)
    assert _extensie_kleuren([jobs[0]["payload"]]) == [["Various"]]
