"""Build in public: reacties onder Daniels posts en beloften met terugkomdatum (17-11-2026).

Draait de echte functies uit scripts/bip_reacties.py met een nagebouwde Bluesky-draad en
een echt stuk uit docs/build-in-public-ideeen.md. Op de vorige commit bestond het script niet.
"""
import importlib.util
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("bip", ROOT / "scripts" / "bip_reacties.py")
bip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bip)

ZELF = "did:plc:daniel"


def _post(rkey, did, handle, tekst, replies=None):
    return {"post": {"uri": f"at://{did}/app.bsky.feed.post/{rkey}", "cid": "c" + rkey,
                     "author": {"did": did, "handle": handle}, "indexedAt": "2026-11-17T08:00:00Z",
                     "record": {"text": tekst}}, "replies": replies or []}


def test_een_reactie_zonder_antwoord_wordt_gemeld():
    draad = {"thread": {**_post("p1", ZELF, "daniel", "dag 163"),
                        "replies": [_post("r1", "did:x", "anna", "Mooi werk, hoe lang duurde het?")]}}
    uit = bip.onbeantwoord(draad, ZELF)
    assert [r["sleutel"] for r in uit] == ["bsky:r1"]
    assert uit[0]["auteur"] == "anna" and "hoe lang" in uit[0]["tekst"]


def test_een_reactie_waar_daniel_al_op_antwoordde_wordt_niet_gemeld():
    antwoord = _post("a1", ZELF, "daniel", "Een paar uur!")
    draad = {"thread": {**_post("p1", ZELF, "daniel", "dag 163"),
                        "replies": [_post("r1", "did:x", "anna", "Hoe lang?", [antwoord])]}}
    assert bip.onbeantwoord(draad, ZELF) == []


def test_reacties_van_daniel_zelf_worden_nooit_gemeld():
    draad = {"thread": {**_post("p1", ZELF, "daniel", "dag 163"),
                        "replies": [_post("d1", ZELF, "daniel", "vervolg op mijn eigen post")]}}
    assert bip.onbeantwoord(draad, ZELF) == []


def test_een_diepere_reactie_van_een_ander_wordt_gevonden():
    diep = _post("r2", "did:y", "ben", "En wat kost het?")
    draad = {"thread": {**_post("p1", ZELF, "daniel", "dag 163"),
                        "replies": [_post("a1", ZELF, "daniel", "Een paar uur!", [diep])]}}
    assert [r["sleutel"] for r in bip.onbeantwoord(draad, ZELF)] == ["bsky:r2"]


def test_bluesky_slaat_al_geziene_reacties_over():
    feed = {"feed": [{"post": {**_post("p1", ZELF, "daniel", "dag 163")["post"]}}]}
    draad = {"thread": {**_post("p1", ZELF, "daniel", "dag 163"),
                        "replies": [_post("r1", "did:x", "anna", "Hoe lang?"),
                                    _post("r2", "did:y", "ben", "Mooi!")]}}

    def haal(pad, **_):
        return feed if pad.endswith("getAuthorFeed") else draad

    assert [r["sleutel"] for r in bip.bluesky(5, gezien={}, haal=haal)] == ["bsky:r1", "bsky:r2"]
    assert [r["sleutel"] for r in bip.bluesky(5, gezien={"bsky:r1": "2026-11-17"}, haal=haal)] == ["bsky:r2"]


def test_gezien_wordt_bewaard_en_dubbel_telt_niet(tmp_path):
    pad = tmp_path / "gezien.json"
    assert bip.zet_gezien(["x:1", "x:2"], pad, nu=date(2026, 11, 17)) == 2
    assert bip.zet_gezien(["x:2", "ih:abc"], pad, nu=date(2026, 11, 18)) == 1
    d = json.loads(pad.read_text())
    assert d == {"ih:abc": "2026-11-18", "x:1": "2026-11-17", "x:2": "2026-11-17"}
    assert bip.lees_gezien(tmp_path / "bestaat-niet.json") == {}


LIJST = """# Lijst
## Open beloften aan de lezers

| Datum | Post | Wat is beloofd | Meting die nodig is | Terugkom op | Status |
|---|---|---|---|---|---|
| 14-11-2026 | Dag 161 | Cijfers over de helpknop | Klikken per dag | 17-11-2026 | Open |
| 14-11-2026 | Dag 161 | Tijd tot eerste advertentie | Mediaan | 20-11-2026 | Open |
| 10-11-2026 | Dag 157 | Iets oud | x | 12-11-2026 | Gemeld op 13-11-2026 |
| 10-11-2026 | Dag 157 | Zonder datum | x |  | Open |

## Ideeën uit reacties

| Datum | Van | Idee | Terugkom op | Status |
|---|---|---|---|---|
| 16-11-2026 | iemand | iets | 01-01-2026 | Idee |
"""


def test_due_toont_alleen_aan_de_beurt_en_niet_gemelde_beloften():
    nu = date(2026, 11, 17)
    assert [b["belofte"] for b in bip.due(LIJST, nu)] == ["Cijfers over de helpknop"]
    assert [b["belofte"] for b in bip.due(LIJST, nu, dagen=3)] == [
        "Cijfers over de helpknop", "Tijd tot eerste advertentie"]


def test_de_echte_lijst_is_leesbaar_voor_het_script():
    tekst = (ROOT / "docs" / "build-in-public-ideeen.md").read_text()
    rijen = bip.beloften(tekst)
    assert rijen, "de tabel met open beloften is niet meer te lezen"
    assert all(r["terugkom"] for r in rijen), "elke open belofte hoort een terugkomdatum te hebben"
