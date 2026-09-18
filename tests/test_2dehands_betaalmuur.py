"""2dehands vraagt dit account geld per advertentie, en dat is iets anders.

WAAROM DIT ER IS (09-09-2026, Egbert Brouwer / papas-plectrums)
  "Ik probeer nu listings op 2eHands te krijgen, ineens zie ik 3 nieuwe tabs
   geopend van 2eHands, met allemaal factuurtjes die betaald moeten worden."

GEMETEN in zijn eigen opdrachten, drie stuks (18:59, 19:08, 19:13 UTC):

  [tab op https://www.2dehands.be/payments/orderOverview/index.html,
   4 invulveld(en), invulscript geladen: nee]
  [laatste stap: "plaatsen: op de knop geklikt, wachten op de advertentie"]

Het formulier ging dus open, werd ingevuld en er werd op plaatsen geklikt.
2dehands publiceerde alleen niet: het zette de advertentie als bestelregel van
EUR 9,00 klaar. 806 opdrachten voor 2dehands, nul geslaagde plaatsingen, ooit.

Twee dingen deden wij daarna fout, en allebei kostten ze hem iets:

1. We herschreven die gemeten waarneming tot "het formulier ging nooit open,
   controleer of je bent ingelogd". Hij was ingelogd; zijn scan van diezelfde
   minuut gaf HTTP 200 op het afgeschermde overzicht. Dat kostte hem een week
   zoeken op de verkeerde plek.
2. De rem zette het kanaal op pauze maar liet bewust één proefadvertentie per
   ronde door, omdat een pauze zonder uitweg een muur is. Bij een betaalmuur is
   die proef juist het probleem: elke proef is EUR 9,00. Zijn winkelmandje:
   17 regels, EUR 153,00.

Draaien: python3 -m pytest tests/test_2dehands_betaalmuur.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as api  # noqa: E402
from tests.test_kansloze_wachtrij import _DB  # noqa: E402

# Letterlijk het adres uit zijn opdrachten. Niet verzonnen: overgenomen.
BETAALADRES = "https://www.2dehands.be/payments/orderOverview/index.html"

# De melding zoals de extensie hem nu schrijft, ingekort tot wat ertoe doet.
BETAALMUUR = (
    "2dehands (2dehands.be) does not let this account place adverts for free. The form was "
    "filled in and published, but instead of going online the advert was added to an unpaid "
    "2dehands (2dehands.be) order. Nothing went online, and nothing has been paid. "
    f"[tabblad kwam uit op {BETAALADRES}] [extensie 1.0.315]"
)

# De oude melding: precies wat hij dagenlang terugkreeg.
OUDE_TIMEOUT = (
    "Extension timed out waiting for this 2dehands job to finish (no response after 3 minutes). "
    "The page may have changed, needs a manual step, or the extension lost track of the tab. "
    f"[tab op {BETAALADRES}, 4 invulveld(en), invulscript geladen: nee] "
    '[laatste stap: "plaatsen: op de knop geklikt, wachten op de advertentie", 190s geleden] '
    "[extensie 1.0.314]"
)


@pytest.fixture(autouse=True)
def _geen_echte_database(monkeypatch):
    monkeypatch.setattr(api, "execute_with_retry", lambda q, *a, **k: q.execute())


def _job(i, result, status="error", platform="2dehands", action="create"):
    return {"id": f"b{i}", "user_id": "u", "platform": platform, "action": action,
            "status": status, "item_id": f"i{i}", "result": result}


# ── 1. Herkennen we het uberhaupt ───────────────────────────────────────────

def test_de_betaalpagina_wordt_herkend_in_de_melding_van_de_extensie():
    db = _DB(jobs=[_job(1, {"error": BETAALMUUR})])
    assert api._kanaal_hard_dicht(db, "u", "2dehands") is True


def test_ook_als_de_melding_alleen_nog_als_oorspronkelijke_tekst_bestaat():
    """Een door de server herschreven melding bewaart de echte tekst apart.

    Zonder dit zou een oude, al herschreven rij de betaalmuur verbergen.
    """
    db = _DB(jobs=[_job(1, {"error": "iets anders", "error_oorspronkelijk": OUDE_TIMEOUT})])
    assert api._kanaal_hard_dicht(db, "u", "2dehands") is True


def test_een_gewone_mislukking_is_geen_betaalmuur():
    db = _DB(jobs=[_job(i, {"error": "Photos could not be uploaded"}) for i in range(5)])
    assert api._kanaal_hard_dicht(db, "u", "2dehands") is False


def test_een_leeg_logboek_sluit_niets_af():
    """Wantrouw je eigen lege uitkomst: niets weten is geen reden om dicht te gaan."""
    assert api._kanaal_hard_dicht(_DB(jobs=[]), "u", "2dehands") is False


def test_een_ander_kanaal_wordt_er_niet_in_meegesleept():
    db = _DB(jobs=[_job(1, {"error": BETAALMUUR})])
    assert api._kanaal_hard_dicht(db, "u", "marktplaats") is False


# ── 2. Een keer is genoeg ───────────────────────────────────────────────────

def test_een_enkele_betaalpagina_sluit_het_kanaal_al():
    """VOOR-EN-NA. Dit is het hele verschil, en het is in geld te tellen.

    VOOR: één zo'n mislukking was ver onder elke drempel (drie op rij, of tien
    ondoorgronde bij elkaar), dus bleef het kanaal gewoon openstaan en ging de
    volgende advertentie er meteen achteraan. Elke advertentie EUR 9,00.
    NA: één waarneming is genoeg.
    """
    db = _DB(jobs=[_job(1, {"error": BETAALMUUR})])
    # VOOR: de twee oude ingangen zeggen allebei nee bij één mislukking.
    assert api._kansloze_reeks(db, "u", "2dehands") is False
    # NA: het kanaal gaat toch dicht.
    assert api._kanaal_kansloos(db, "u", "2dehands") is True


def test_de_oude_rem_had_dit_bij_een_enkele_poging_laten_lopen():
    """Zonder de betaalmuur-ingang is één mislukking gewoon pech, en gaat het door."""
    db = _DB(jobs=[_job(1, {"error": OUDE_TIMEOUT.replace(BETAALADRES, "https://www.2dehands.be/plaats/728/748")})])
    assert api._kanaal_kansloos(db, "u", "2dehands") is False


# ── 3. Een nieuwere extensie is hier geen argument ──────────────────────────

def test_een_nieuwere_kopie_opent_de_deur_niet_opnieuw():
    """De uitweg voor een gewone pauze mag hier niet gelden.

    _verdient_nieuwe_kans geeft een kanaal een schone start zodra er een
    nieuwere kopie van de extensie draait dan die de mislukkingen maakte. Dat
    klopt voor onze eigen fouten. Maar geen enkele versie van ons verandert iets
    aan wat 2dehands voor een advertentie rekent, en bij Egbert zou die uitweg
    het kanaal telkens opnieuw openzetten voor weer EUR 9,00.
    """
    jobs = [_job(i, {"error": BETAALMUUR}) for i in range(3)]
    db = _DB(jobs=jobs, heartbeat=[{"user_id": "u", "ext_version": "1.0.320"}])
    # De uitweg zegt hier inderdaad "geef hem een nieuwe kans".
    assert api._verdient_nieuwe_kans(db, "u", "2dehands") is True
    # En toch blijft het kanaal dicht, want de betaalmuur gaat voor.
    assert api._kanaal_kansloos(db, "u", "2dehands") is True


# ── 4. Deze melding wordt niet meer overschreven ────────────────────────────

def test_de_gemeten_melding_blijft_staan_zoals_hij_is():
    """VOOR-EN-NA op de tekst die hem een week de verkeerde kant op stuurde."""
    body = {"error": BETAALMUUR}
    uit = api._rechtgezette_foutmelding(
        {"platform": "2dehands", "action": "create"}, body, versie=(1, 0, 315), kansloos=True)
    assert uit["error"] == BETAALMUUR
    assert "never opened" not in uit["error"]
    assert "signed in" not in uit["error"]


def test_de_oude_melding_werd_wel_degelijk_herschreven():
    """VOOR-EN-NA op precies de tekst die hij drie keer op het scherm kreeg.

    VOOR: die tekst voldoet aan de voorwaarde die de herschrijving aanzette
    (_ONDOORGROND matcht op "timed out waiting for this ... job to finish"), en
    dan werd er onvoorwaardelijk "het formulier ging nooit open, misschien ben je
    niet ingelogd" van gemaakt. Dat is aantoonbaar wat hij las.
    NA: de betaalmuur-uitzondering staat ervoor, dus de waarneming blijft staan.
    """
    zonder_marker = OUDE_TIMEOUT.replace(
        BETAALADRES, "https://www.2dehands.be/plaats/728/748")
    # VOOR: dezelfde tekst zonder het betaaladres wordt nog steeds herschreven.
    assert api._ONDOORGROND.search(zonder_marker)
    oud = api._rechtgezette_foutmelding(
        {"platform": "2dehands", "action": "create"},
        {"error": zonder_marker}, versie=(1, 0, 314), kansloos=True)
    assert "never opened" in oud["error"]
    assert "not signed in" in oud["error"]
    assert "728/748" in oud["error_oorspronkelijk"]

    # NA: met het gemeten betaaladres erin blijft hij onaangeroerd.
    nieuw = api._rechtgezette_foutmelding(
        {"platform": "2dehands", "action": "create"},
        {"error": OUDE_TIMEOUT}, versie=(1, 0, 314), kansloos=True)
    assert nieuw["error"] == OUDE_TIMEOUT
    assert "not signed in" not in nieuw["error"]


def test_ook_een_verouderde_kopie_verandert_de_betaalmelding_niet():
    """Een stale-versie-verwijt bovenop een betaalmuur is weer de verkeerde kant op."""
    uit = api._rechtgezette_foutmelding(
        {"platform": "2dehands", "action": "create"},
        {"error": BETAALMUUR}, versie=(1, 0, 100), kansloos=False)
    assert uit["error"] == BETAALMUUR
    assert "verouderde kopie" not in uit["error"]


# ── 5. Wat hij te lezen krijgt als hij opnieuw op publiceren klikt ─────────

def test_de_pauzetekst_wordt_vervangen_door_de_echte_reden():
    tekst = api._melding_kanaal_vraagt_geld("2dehands")
    assert "does not let your account place adverts for free" in tekst
    assert BETAALADRES in tekst
    assert "nothing has been paid" in tekst
    assert "other channels keep working" in tekst
    # En niet meer de belofte die het duur maakte.
    assert "test listing" not in tekst
    assert "One test listing IS being sent" not in tekst


def test_de_gewone_pauzetekst_belooft_die_proef_nog_wel():
    """VOOR-EN-NA: bij een gewone pauze is die proef juist goed, en blijft hij."""
    assert "One test listing IS being sent" in api._melding_kanaal_op_pauze("2dehands")


# ── 6. En de proefadvertentie die het duur maakte ──────────────────────────

def test_bij_een_betaalmuur_gaat_er_geen_proefadvertentie_meer_doorheen():
    """Dit is waar de EUR 153,00 vandaan kwam.

    De gewone rem laat per ronde bewust één advertentie door, want een pauze
    zonder uitweg is een muur. Dat klopt zolang een mislukte poging alleen tijd
    kost. Bij een betaalmuur is elke proef EUR 9,00, dus daar moet de deur wel
    helemaal dicht.
    """
    from backend.services import crosslist as cl

    db = _DB(jobs=[_job(i, {"error": BETAALMUUR}) for i in range(3)])
    cl._KANSLOOS_CACHE.clear()
    cl._HARD_DICHT_CACHE.clear()

    # VOOR: de gewone rem laat de eerste vraag van een ronde altijd door.
    assert cl._kanaal_kansloos_gecached(db, "u", "2dehands") is False
    # (en pas de tweede vraag van diezelfde ronde wordt geblokkeerd)
    assert cl._kanaal_kansloos_gecached(db, "u", "2dehands") is True

    # NA: de betaalmuur kent die uitzondering niet, ook niet de eerste keer.
    cl._HARD_DICHT_CACHE.clear()
    assert cl._kanaal_hard_dicht_gecached(db, "u", "2dehands") is True
    assert cl._kanaal_hard_dicht_gecached(db, "u", "2dehands") is True


def test_zonder_betaalmuur_blijft_de_proefadvertentie_gewoon_bestaan():
    """Die uitweg is er niet voor niets: zonder haar is een pauze een muur."""
    from backend.services import crosslist as cl

    db = _DB(jobs=[_job(i, {"error": OUDE_TIMEOUT.replace(
        BETAALADRES, "https://www.2dehands.be/plaats/728/748")}) for i in range(12)])
    cl._KANSLOOS_CACHE.clear()
    cl._HARD_DICHT_CACHE.clear()
    assert cl._kanaal_hard_dicht_gecached(db, "u", "2dehands") is False
    assert cl._kanaal_kansloos_gecached(db, "u", "2dehands") is False   # de proef
    assert cl._kanaal_kansloos_gecached(db, "u", "2dehands") is True    # de rest


# ── 7. De echte oorzaak: het webadres in de advertentietekst ───────────────
#
# 2dehands rekent EUR 9,00 voor een zoekertje met een webadres erin ("Websitevermelding").
# Zet je de link in de omschrijving in plaats van in het URL-veld, dan meldt de
# site "er is een URL gevonden" en wil ze alsnog betaald worden. Egberts tekst
# draagt onder elk artikel https://www.papas-plectrums.nl en info@papas-plectrums.nl.

# Zijn tekst, letterlijk overgenomen uit de laatste plaatsopdracht (ingekort).
EGBERT_TEKST = (
    "Je miniatuur Gibson ES 355 gitaar koop je natuurlijk bij Papa's Plectrums.\n"
    "Elk exemplaar wordt met de hand gemaakt in Indonesie en is gemaakt van hout.\n"
    "- Leuk om te verzamelen of cadeau te geven\n"
    "Als je meer advertenties van Papa's Plectrums wilt zien klik dan rechts boven "
    "op \"Bekijk alle advertenties\"\n"
    "https://www.papas-plectrums.nl\n"
    "info@papas-plectrums.nl\n"
    "\n"
    "Hof van Batuwe 22\n"
    "3412 JC Lopikerkapel\n"
    "+31 6 41214478\n"
    "\n"
    "KVK Utrecht: 30273991\n"
    "BTW: NL177553947B01\n"
    "Gratis verzending bij bestellingen vanaf €35,00\n"
    "De miniatuur gitaar kan je met onderstaande link bestellen en veilig betalen met Wero:"
)


def test_het_webadres_gaat_eruit_en_de_rest_blijft_staan():
    """VOOR-EN-NA op de tekst die zijn advertenties EUR 9,00 per stuk kostte."""
    from backend.services.crosslist import _zonder_links
    import re as _re

    # VOOR: dit is wat er naar 2dehands ging, en dit is waar het geld op zat.
    assert "https://www.papas-plectrums.nl" in EGBERT_TEKST
    assert "info@papas-plectrums.nl" in EGBERT_TEKST

    uit = _zonder_links(EGBERT_TEKST)

    # NA: geen webadres en geen e-mailadres meer, in geen enkele vorm.
    assert not _re.search(r"https?://|www\.|papas-plectrums", uit, _re.I), uit
    # En de advertentie is nog steeds een advertentie.
    assert "Papa's Plectrums" in uit           # de winkelnaam mag blijven
    assert "Leuk om te verzamelen" in uit
    assert "Hof van Batuwe 22" in uit          # adres en KVK zijn geen link
    assert "KVK Utrecht: 30273991" in uit
    assert "+31 6 41214478" in uit
    assert len(uit) > 0.7 * len(EGBERT_TEKST)  # er is geknipt, niet gesloopt


def test_de_zin_die_naar_de_weggehaalde_link_wees_gaat_mee():
    """Anders eindigt de advertentie met 'bestellen met onderstaande link:' en niets."""
    from backend.services.crosslist import _zonder_links
    assert "onderstaande link" not in _zonder_links(EGBERT_TEKST)


@pytest.mark.parametrize("tekst", [
    "Mooie gitaar, z.o.z. voor de maten. Nieuwprijs t.w.v. € 129,00.",
    # GEMETEN false positive (09-09-2026): een zin zonder spatie na de punt,
    # waarin het volgende woord toevallig ook een landcode is. Kwam echt voor.
    "Wordt binnen een week verstuurd.De maat staat op het label.",
    "Nog een paar dagen te gaan.Nu met korting.",
    "Handgemaakt in Duitsland.Fr. vanaf 5 euro.",
    "Verzenden kost 6,95. Ophalen kan ook, bel gerust.",
    "Set van 3 stuks. Zie foto's. Gemaakt in Indonesie, handwerk.",
    "Maat 42. Merk: Mr. Big. Kleur: zwart.",
])
def test_gewone_advertentietekst_blijft_letterlijk_heel(tekst):
    """Een filter dat te veel pakt is erger dan geen filter: dan verminkt hij
    elke advertentie van elke klant."""
    from backend.services.crosslist import _zonder_links
    assert _zonder_links(tekst) == tekst


def test_een_tekst_die_alleen_uit_een_link_bestaat_wordt_niet_leeggehaald():
    """Een lege omschrijving laat het formulier hangen; dat is erger.

    Zo'n geval loopt dan alsnog tegen de betaalmuur aan, en die wordt nu
    herkend en gestopt.
    """
    from backend.services.crosslist import _zonder_links
    assert _zonder_links("https://www.papas-plectrums.nl") == "https://www.papas-plectrums.nl"


def test_alleen_marktplaats_en_2dehands_krijgen_de_gefilterde_tekst():
    """Op Vinted, eBay en Shopify hoort de tekst gewoon heel te blijven."""
    bron = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")
    pick = bron.split("def _pick(platform: str) -> dict:")[1].split("\n    # Eerst de extensieplatforms")[0]
    assert 'if platform in ("marktplaats", "2dehands"):' in pick
    assert "beschrijving = _zonder_links(beschrijving)" in pick
    assert "titel = _zonder_links(titel)" in pick


def test_een_mislukking_van_voor_de_filter_houdt_het_kanaal_niet_dicht():
    """Een rem mag geen muur worden om een oorzaak die is weggenomen.

    Al zijn betaalmuur-mislukkingen komen van advertenties MET een webadres
    erin. Nu we dat webadres eruit halen zeggen die mislukkingen niets meer over
    wat we zouden versturen, dus gaat het kanaal weer open. Blijft de betaalmuur
    staan bij een advertentie die al schoon was, dan telt hij wél.
    """
    vuil = {"id": "v", "user_id": "u", "platform": "2dehands", "action": "create",
            "status": "error", "item_id": "i1",
            "result": {"error": BETAALMUUR}, "payload": {"description": EGBERT_TEKST}}
    schoon = {**vuil, "id": "s", "item_id": "i2",
              "payload": {"description": "Mooie miniatuurgitaar, handgemaakt."}}

    assert api._kanaal_hard_dicht(_DB(jobs=[vuil]), "u", "2dehands") is False
    assert api._kanaal_hard_dicht(_DB(jobs=[schoon]), "u", "2dehands") is True


def test_de_server_neemt_de_hele_rij_terug_bij_de_eerste_betaalpagina():
    """En dat moet vanaf de SERVER, niet uit de extensie.

    Zijn kopie is 1.0.314 en de Chrome Web Store deed er eerder drie weken over.
    Tot die tijd is dit de enige plek die de betaalpagina kan zien, en zijn
    huidige kopie zet het adres van het tabblad al in haar foutmelding.
    """
    bron = (ROOT / "backend/api/jobs.py").read_text(encoding="utf-8")
    fail = bron.split("def fail_job(")[1].split("\ndef ")[0]
    assert "_BETAALMUUR.search" in fail
    assert "_stop_wachtrij(db, user_id, job[\"platform\"], reden)" in fail
    assert "_melding_kanaal_vraagt_geld" in fail
    # En vóór de opdracht wordt weggeschreven, zodat de melding op de rij klopt.
    assert fail.index("_BETAALMUUR.search") < fail.index('"status": "error"')


# ── 8. EEN BETAALPAGINA OP EEN KANAAL DAT AANTOONBAAR GRATIS PLAATST ────────
#
# GEMETEN 18-09-2026 bij De Juiste Toon. Om 06:41 UTC kwam één advertentie
# ("Wandkleed geborduurd 89/69 cm", rubriek wonen wanddecoraties) op de
# betaalpagina uit. Om 06:29, twaalf minuten eerder, ging er nog een advertentie
# van hem gratis online; de dag ervoor 200, in totaal 219. Toch ging het hele
# kanaal dicht, werden zijn 36 wachtende opdrachten teruggenomen en las hij
# "That is why nothing has ever gone online there".
#
# Dat is de duurste soort onwaar: een dicht kanaal maakt geen opdrachten meer
# aan, dus komt er nooit een nieuwe rij die het oordeel kan herzien. Zonder
# ingreep met de hand was hij 2dehands kwijt.

GEPLAATST_OM = "2026-09-18T06:29:06+00:00"
MUUR_OM = "2026-09-18T06:41:45+00:00"


def _geplaatst(i, wanneer=GEPLAATST_OM, platform="2dehands"):
    return {"id": f"ok{i}", "user_id": "u", "platform": platform, "action": "create",
            "status": "done", "item_id": f"g{i}", "result": {},
            "created_at": wanneer, "done_at": wanneer}


def _muur(i, wanneer=MUUR_OM, status="error", result=None):
    return {"id": f"m{i}", "user_id": "u", "platform": "2dehands", "action": "create",
            "status": status, "item_id": f"m{i}",
            "result": result if result is not None else {"error": BETAALMUUR},
            "created_at": wanneer, "done_at": wanneer}


def test_een_kanaal_dat_aantoonbaar_gratis_plaatst_gaat_niet_dicht():
    """VOOR-EN-NA, met dezelfde waarneming en één verschil ernaast.

    VOOR: één betaalpagina sloot het kanaal, ongeacht wat er die dag online was
    gegaan. NA: staat er een geslaagde plaatsing, dan is "dit account plaatst
    hier niet gratis" aantoonbaar onwaar en gaat het over deze advertentie.
    """
    muur = _muur(1)
    assert api._kanaal_hard_dicht(_DB(jobs=[muur]), "u", "2dehands") is True
    met_bewijs = _DB(jobs=[_geplaatst(i) for i in range(3)] + [muur])
    assert api._kanaal_hard_dicht(met_bewijs, "u", "2dehands") is False


def test_zesendertig_teruggenomen_opdrachten_zijn_samen_een_waarneming():
    """De wachtrij-stop schrijft dezelfde tekst op alles wat nog wachtte.

    Telden die mee, dan maakte één advertentie op de betaalpagina zichzelf tot
    zevenendertig en haalde elke drempel zichzelf.
    """
    kopieen = [_muur(i, status="cancelled",
                     result={"cancelled": "queue stopped", "error": BETAALMUUR})
               for i in range(36)]
    db = _DB(jobs=[_geplaatst(0)] + kopieen + [_muur(99)])
    assert len(api._betaalmuur_waarnemingen(db, "u", "2dehands")) == 1
    assert api._kanaal_hard_dicht(db, "u", "2dehands") is False


def test_drie_betaalpaginas_na_de_laatste_plaatsing_sluiten_het_kanaal_alsnog():
    """Wat als 2dehands een account echt omzet naar betaald? Dan blijkt dat.

    Twee is nog geen bewijs: dat kunnen twee betalende rubrieken zijn. Bij drie
    op rij, zonder dat er tussendoor nog iets gratis online gaat, ligt het niet
    meer aan de rubriek. Dat kost hem drie onbetaalde bestelregels in plaats van
    een kanaal dat het aantoonbaar deed.
    """
    geplaatst = [_geplaatst(0)]
    muren = [_muur(i, wanneer=f"2026-09-18T07:0{i}:00+00:00") for i in (1, 2, 3)]
    assert api._kanaal_hard_dicht(_DB(jobs=geplaatst + muren), "u", "2dehands") is True
    assert api._kanaal_hard_dicht(_DB(jobs=geplaatst + muren[:2]), "u", "2dehands") is False


def test_een_betaalpagina_van_voor_de_laatste_plaatsing_telt_niet_meer():
    """Gaat er daarna weer iets gratis online, dan is de muur weg."""
    muren = [_muur(i, wanneer=f"2026-09-17T20:0{i}:00+00:00") for i in (1, 2, 3)]
    db = _DB(jobs=muren + [_geplaatst(9)])
    assert api._kanaal_hard_dicht(db, "u", "2dehands") is False


def test_de_melding_zegt_alleen_nooit_online_als_dat_klopt():
    from datetime import datetime, timezone
    nooit = api._melding_kanaal_vraagt_geld("2dehands")
    assert "nothing has ever gone online there" in nooit
    wel = api._melding_kanaal_vraagt_geld(
        "2dehands", datetime(2026, 9, 18, tzinfo=timezone.utc))
    assert "nothing has ever gone online there" not in wel
    assert "did go online there for free until 18-09-2026" in wel


def test_de_melding_op_die_ene_advertentie_wijst_de_rubriek_aan():
    tekst = api._melding_advertentie_op_de_rekening("2dehands", "wonen wanddecoraties")
    assert "nothing has ever gone online" not in tekst
    assert "switched off for your account" not in tekst
    assert '"wonen wanddecoraties"' in tekst
    assert BETAALADRES in tekst
    # En hij wordt herkend als "deze rubriek kost geld", zodat de volgende
    # advertentie in diezelfde rubriek er niet opnieuw op stukloopt.
    assert api._BETAALDE_RUBRIEK.search(tekst)


def test_de_wachtrij_blijft_staan_als_het_kanaal_aantoonbaar_gratis_plaatst():
    """De extensie in het veld stopt de rij; de server laat dat niet meer toe.

    Een nieuwe extensie is bij een verkoper pas weken later binnen, dus moet de
    server deze aanroep kunnen weigeren op wat hij zelf kan zien.
    """
    bron = (ROOT / "backend/api/jobs.py").read_text(encoding="utf-8")
    stop = bron.split("def stop_platform(")[1].split("\ndef ")[0]
    assert "_BETAALMUUR.search(ruw) and not _kanaal_hard_dicht(" in stop
    fail = bron.split("def fail_job(")[1].split("\ndef ")[0]
    assert "_melding_advertentie_op_de_rekening(" in fail
    assert "rubriek=rubriek" in fail


# ── 9. EEN VOORTGANGSBERICHT MAG DE FOUT NIET WISSEN ────────────────────────
#
# GEMETEN (18-09-2026, De Juiste Toon). Vijf tapijten liepen tussen 10:47 en
# 11:46 vast op de betaalpagina van 2dehands. Om 11:52:26 kregen alle vijf
# hetzelfde voortgangsbericht van de extensie, en daarna stond er in `result`
# alleen nog {"_progress": ...}: geen fouttekst meer. Sinds 1 september
# overkwam dat 98 mislukte opdrachten, 57 daarvan op 2dehands.
#
# Elke rem leest die fouttekst. Zonder tekst weet de machine niet meer dat die
# rubriek geld kost en zet ze het volgende tapijt gewoon weer klaar, en op
# 2dehands is dat elke keer een bestelregel van EUR 9,00.

_NU = datetime.now(timezone.utc)
_KLOK = {"aangemaakt": (_NU - timedelta(hours=3)).isoformat(),
         "vroeg": (_NU - timedelta(hours=2)).isoformat(),
         "laat": (_NU - timedelta(hours=1)).isoformat(),
         "laatst": _NU.isoformat()}

RUBRIEK_KOST_GELD = api._melding_rubriek_vraagt_geld(
    "2dehands", "Huis en Inrichting Stoffering | Tapijten en Kleden")


def _opdracht(status, result):
    return _DB(jobs=[{"id": "j1", "user_id": "u", "platform": "2dehands", "action": "create",
                      "status": status, "item_id": "i1", "result": result}])


def test_een_late_voortgangsping_wist_de_fout_van_een_afgeronde_opdracht_niet(monkeypatch):
    monkeypatch.setattr(api, "_record_extension_heartbeat", lambda *a, **k: None)
    klaar = _opdracht("error", {"error": RUBRIEK_KOST_GELD})
    monkeypatch.setattr(api, "get_db", lambda: klaar)
    api.report_job_progress("j1", {"stap": "klokstand: 0.0/s"}, user_id="u")
    assert klaar.jobs[0]["result"] == {"error": RUBRIEK_KOST_GELD}

    # VOOR-EN-NA: op een opdracht die nog loopt hoort dezelfde ping wel te landen,
    # anders zou het dashboard niets meer laten zien tijdens een scan.
    loopt = _opdracht("claimed", {})
    monkeypatch.setattr(api, "get_db", lambda: loopt)
    api.report_job_progress("j1", {"stap": "klokstand: 0.0/s"}, user_id="u")
    assert loopt.jobs[0]["result"]["_progress"]["stap"] == "klokstand: 0.0/s"


def test_een_gewiste_fout_maakt_de_rubriekrem_blind():
    """Waarom het wissen duur was: precies dit gebeurde met zijn tapijten."""
    gewist = _DB(jobs=[{"id": "j1", "user_id": "u", "platform": "2dehands", "action": "create",
                        "status": "error", "item_id": "i1", "category": "tapijten",
                        "created_at": _KLOK["aangemaakt"], "done_at": _KLOK["laat"],
                        "result": {"_progress": {"stap": "klokstand: 0.0/s"}}}])
    assert api._betaalde_rubriek_bekend(gewist, "u", "2dehands", "tapijten") is False


def test_de_rubriekrem_kijkt_naar_wanneer_de_opdracht_afliep():
    """Vier tapijten werden in dezelfde seconde klaargezet en liepen uren later af.

    Op aanmaaktijd is hun volgorde willekeurig; alleen het moment van afronden
    zegt wat 2dehands het laatst tegen deze verkoper zei.
    """
    muur = {"id": "muur", "user_id": "u", "platform": "2dehands", "action": "create",
            "status": "error", "item_id": "i1", "category": "tapijten",
            "created_at": _KLOK["aangemaakt"], "done_at": _KLOK["laat"],
            "result": {"error": RUBRIEK_KOST_GELD}}
    gelukt = {"id": "ok", "user_id": "u", "platform": "2dehands", "action": "create",
              "status": "done", "item_id": "i2", "category": "tapijten",
              "created_at": _KLOK["aangemaakt"], "done_at": _KLOK["vroeg"], "result": {}}
    assert api._betaalde_rubriek_bekend(_DB(jobs=[muur, gelukt]), "u", "2dehands",
                                        "tapijten") is True
    # En andersom: is de geslaagde plaatsing de laatste, dan is de rubriek weer vrij.
    gelukt_laatst = dict(gelukt, done_at=_KLOK["laatst"])
    assert api._betaalde_rubriek_bekend(_DB(jobs=[muur, gelukt_laatst]), "u", "2dehands",
                                        "tapijten") is False
