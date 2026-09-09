"""Een webadres in de advertentietekst kost EUR 9,00 op Marktplaats en 2dehands.

WAAROM DIT ER IS (09-09-2026, Egbert Brouwer / papas-plectrums). Onder elk van
zijn 5.533 artikelen staat `https://www.papas-plectrums.nl` en
`info@papas-plectrums.nl`. Marktplaats en 2dehands publiceren zo'n zoekertje
niet: ze zetten hem klaar als bestelregel "Websitevermelding" van EUR 9,00.
Winkelmandje: 17 regels, EUR 153,00, nul advertenties online.

De filter `_zonder_links` is toen op het publicatiepad gezet, in `_pick`. Deze
proef gaat over wat daar NIET langskwam, en dat is de reden dat dit bestand
bestaat:

  1. De reddingsronde in `relist.py` bouwt haar eigen 'create'-payload. Dat pad
     had exact hetzelfde lek al eens eerder (04-09-2026: Engelse advertenties op
     Marktplaats, "(1357) Lilac Profuomo Shirt"), dus het is geen theorie.
  2. `captured_listing` in `jobs.py` vult een lege omschrijving aan met de tekst
     die letterlijk van de advertentiepagina komt — bij hem dus mét link.
  3. `_zet_taal_goed` laat de tekst door een vertaling gaan en levert een NIEUWE
     tekst op. Wat daaruit komt is nooit door `_pick` geweest.

Daarom staat `_haal_links_eruit` op dezelfde plek als `_zet_taal_goed`: de enige
plek waar élke opdracht langskomt, vlak voor hij naar de extensie gaat.

Draaien: python3 -m pytest tests/test_geen_link_in_advertentie.py
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as api  # noqa: E402
from backend.services.crosslist import _zonder_links, _met_slot  # noqa: E402
from tests.test_kansloze_wachtrij import _DB  # noqa: E402

# Letterlijk zijn slottekst, niet verzonnen.
SLOT = ("Kijk voor meer plectrums op https://www.papas-plectrums.nl\n"
        "Vragen? Mail info@papas-plectrums.nl")

TEKST = ("Zeldzaam plectrum uit 1978, nauwelijks bespeeld.\n"
         "Verzenden kan, ophalen in Zwolle mag ook.")


def _job(desc, titel="Fender plectrum 1978", platform="2dehands", jid="j1"):
    return {"id": jid, "user_id": "u", "platform": platform, "action": "create",
            "status": "pending", "item_id": "i1",
            "payload": {"title": titel, "description": desc, "price": 9.5}}


# ── 1. Het geval zelf ────────────────────────────────────────────────────────

def test_zijn_eigen_tekst_gaat_schoon_de_deur_uit():
    db = _DB(jobs=[])
    job = _job(_met_slot(TEKST, SLOT))
    # VOOR: precies wat de reddingsronde in de opdracht zette.
    assert "papas-plectrums.nl" in job["payload"]["description"]

    aangepast = api._haal_links_eruit(db, [job])

    # NA: geen enkel adres meer, en dat is het verschil tussen een advertentie
    # en een bestelregel van EUR 9,00.
    assert aangepast == 1
    schoon = job["payload"]["description"]
    assert "papas-plectrums.nl" not in schoon
    assert "https://" not in schoon
    assert "info@" not in schoon
    # En de advertentie zelf staat er nog gewoon.
    assert "Zeldzaam plectrum uit 1978" in schoon
    assert "ophalen in Zwolle" in schoon


def test_ook_een_adres_in_de_titel():
    db = _DB(jobs=[])
    job = _job(TEKST, titel="Plectrum — papas-plectrums.nl")
    api._haal_links_eruit(db, [job])
    assert "papas-plectrums.nl" not in job["payload"]["title"]
    assert "Plectrum" in job["payload"]["title"]


# ── 2. VOOR-EN-NA op het pad dat het lek wás ─────────────────────────────────

def test_de_reddingsronde_bouwde_de_link_er_zelf_weer_in():
    """De payload zoals relist.py hem samenstelde vóór 09-09: slottekst eronder,
    geen linkfilter. Dit is het bewijs dat het lek echt bestond en niet alleen
    denkbaar was."""
    zoals_relist_het_bouwde = _met_slot(TEKST, SLOT)
    assert "https://www.papas-plectrums.nl" in zoals_relist_het_bouwde
    # Precies deze tekst zou zonder deze zeef ongewijzigd de extensie in gaan.
    db = _DB(jobs=[])
    job = _job(zoals_relist_het_bouwde)
    api._haal_links_eruit(db, [job])
    assert "papas-plectrums.nl" not in job["payload"]["description"]


def test_relist_haalt_de_link_er_nu_ook_bij_de_bron_al_uit():
    """Twee sloten op dezelfde deur. Zonder dit staat er in het dashboard en in
    de geschiedenis een andere tekst dan er naar de site is gegaan."""
    bron = (ROOT / "backend" / "services" / "relist.py").read_text()
    assert "_zonder_links" in bron, "relist.py bouwt zijn payload nog zonder linkfilter"


def test_de_zeef_staat_na_de_vertaling_en_niet_ervoor():
    """Een vertaling levert een NIEUWE tekst op. Staat de linkfilter ervoor, dan
    filtert hij een tekst die daarna weer vervangen wordt."""
    bron = (ROOT / "backend" / "api" / "jobs.py").read_text()
    na_taal = bron.index("uit = _zet_taal_goed(db, [kandidaat])")
    zeef = bron.index("_haal_links_eruit(db, uit)")
    assert zeef > na_taal


# ── 3. Geen collateral damage: 46 andere accounts ───────────────────────────

def test_een_tekst_zonder_adres_blijft_letterlijk_zoals_hij_is():
    """De vorige versie van deze filter raakte 55% van alle advertenties aan om
    er bij één klant een link uit te halen. Dat mag niet terugkomen."""
    db = _DB(jobs=[])
    job = _job(TEKST)
    voor = dict(job["payload"])
    aangepast = api._haal_links_eruit(db, [job])
    assert aangepast == 0
    assert job["payload"] == voor


def test_vinted_en_shopify_blijven_er_helemaal_buiten():
    """Daar mag een webadres gewoon in staan, en de verkoper wil dat ook."""
    for platform in ("vinted", "shopify", "ebay"):
        db = _DB(jobs=[])
        job = _job(_met_slot(TEKST, SLOT), platform=platform)
        voor = dict(job["payload"])
        assert api._haal_links_eruit(db, [job]) == 0
        assert job["payload"] == voor


def test_marktplaats_telt_net_zo_goed_mee_als_2dehands():
    db = _DB(jobs=[])
    job = _job(_met_slot(TEKST, SLOT), platform="marktplaats")
    assert api._haal_links_eruit(db, [job]) == 1


# ── 4. Wat er uitgaat, staat ook in de geschiedenis ─────────────────────────

def test_de_schone_tekst_wordt_teruggeschreven_in_de_opdracht():
    """Anders zegt het dashboard iets anders dan wat er naar 2dehands ging, en
    dan zoekt de volgende sessie zich weer scheel."""
    rij = _job(_met_slot(TEKST, SLOT))
    db = _DB(jobs=[rij])
    api._haal_links_eruit(db, [rij])
    opgeslagen = next(j for j in db.jobs if j["id"] == "j1")
    assert "papas-plectrums.nl" not in (opgeslagen["payload"]["description"])


def test_een_kapotte_database_houdt_de_opdracht_niet_tegen():
    """De opdracht die uitgaat is al schoon; opslaan is een nette bijkomstigheid.
    Een storing daarin mag geen publicatie kosten."""
    class _Stuk:
        def table(self, naam): raise RuntimeError("database plat")

    job = _job(_met_slot(TEKST, SLOT))
    assert api._haal_links_eruit(_Stuk(), [job]) == 1
    assert "papas-plectrums.nl" not in job["payload"]["description"]


# ── 5. De filter zelf, op zijn randen ───────────────────────────────────────

def test_een_tekst_die_bijna_alleen_link_is_blijft_staan():
    """ZONDER RUINE. Een lege omschrijving laat het formulier hangen; dan is een
    betaalpagina die de extensie herkent het kleinere kwaad."""
    over = _zonder_links("https://www.papas-plectrums.nl")
    assert over.strip() != ""


def test_geen_lege_opdracht_of_rare_payload_laat_dit_omvallen():
    db = _DB(jobs=[])
    assert api._haal_links_eruit(db, []) == 0
    assert api._haal_links_eruit(db, None) == 0
    assert api._haal_links_eruit(db, [{"id": "x", "platform": "2dehands", "payload": None}]) == 0
    assert api._haal_links_eruit(db, [{"id": "y", "platform": "2dehands",
                                       "payload": {"title": None, "description": ""}}]) == 0


# ── 6. De ECHTE uitgifte, van wachtrij tot wat de extensie in handen krijgt ──
#
# Alles hierboven roept de zeef zelf aan. Deze twee draaien `get_pending_jobs`,
# dus precies de weg die zijn opdracht aflegt, met de zeef als enige verschil.

from tests.test_kanalen_om_de_beurt import _bouw_db, _job as _rij, _uitgifte  # noqa: E402


def _egbert_wachtrij():
    rij = _rij("td0", "2dehands", 30)
    # `_taal` staat er al op, zoals bij elke gelokaliseerde payload — dan laat de
    # taalzeef hem met rust en gaat er geen vertaaldienst aan te pas.
    rij["payload"] = {"price": 9.5, "_taal": "nl",
                      "title": "Fender plectrum 1978",
                      "description": _met_slot(TEKST, SLOT)}
    return [rij]


def test_wat_de_extensie_krijgt_bevat_geen_webadres(monkeypatch):
    uit = _uitgifte(monkeypatch, _bouw_db(_egbert_wachtrij(), laatst_bediend="marktplaats"),
                    "2dehands")
    assert uit, "er moet werk uitgedeeld worden"
    tekst = uit[0]["payload"]["description"]
    assert "papas-plectrums.nl" not in tekst, f"dit gaat EUR 9,00 kosten: {tekst!r}"
    assert "Zeldzaam plectrum uit 1978" in tekst


def test_zonder_de_zeef_ging_datzelfde_webadres_er_gewoon_doorheen(monkeypatch):
    """VOOR-EN-NA in de echte uitgifte: zet de zeef uit en het lek is er weer.
    Zo weten we dat het de zeef is die dit tegenhoudt en niets anders."""
    monkeypatch.setattr(api, "_haal_links_eruit", lambda db, jobs: 0)
    uit = _uitgifte(monkeypatch, _bouw_db(_egbert_wachtrij(), laatst_bediend="marktplaats"),
                    "2dehands")
    assert uit and "papas-plectrums.nl" in uit[0]["payload"]["description"], (
        "deze proef bewijst niets meer: zonder zeef zou de link er nog in moeten staan")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
