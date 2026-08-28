"""Een advertentie mag nooit worden weggehaald als hij niet terug kan komen.

WAT ER GEBEURDE (28-08-2026, Jaap van zilverwebsite.nl)
Herplaatsen is twee stappen: eerst weg bij Marktplaats, dan opnieuw plaatsen.
Van zijn 1.222 items hadden er 532 geen omschrijving — die waren geïmporteerd
uit de zoeklijst van Marktplaats, en die geeft alleen titel, prijs en het
omslagplaatje. Het plaatsformulier van Marktplaats WEIGERT een advertentie
zonder tekst, dus de tweede stap brak af nog voor de foto's.

Gemeten op één dag: 60 verwijderopdrachten geslaagd, 61 plaatsingen mislukt,
58 daarvan met "This item has no description". Marktplaats zet een verwijderde
advertentie meteen op 410, dus ook de tekst zelf was weg.

Daarnaast: de handmatige verversknop meldde de hele dag "3 per dag bereikt",
omdat de dagteller élke verwijderopdracht meetelde — ook de tientallen uit de
nachtelijke ronde, die een eigen, veel ruimere grens heeft.
"""
import re
from pathlib import Path

from backend.services.relist import ontbreekt_voor_herplaatsen

ROOT = Path(__file__).resolve().parents[1]
RELIST = (ROOT / "backend/services/relist.py").read_text(encoding="utf-8")
MP = (ROOT / "extension/content/marktplaats.js").read_text(encoding="utf-8")
DH = (ROOT / "extension/content/tweedehands.js").read_text(encoding="utf-8")
SHARED = (ROOT / "extension/content/shared.js").read_text(encoding="utf-8")


# ── 1. De rem zelf ───────────────────────────────────────────────────────────

def test_item_zonder_tekst_wordt_niet_herplaatst():
    reden = ontbreekt_voor_herplaatsen(
        {"description": "", "photo_urls": ["https://x/1.jpg"]})
    assert reden and "description" in reden


def test_item_met_alleen_witruimte_telt_ook_als_leeg():
    assert ontbreekt_voor_herplaatsen(
        {"description": "   \n ", "photo_urls": ["https://x/1.jpg"]})


def test_item_zonder_fotos_wordt_niet_herplaatst():
    reden = ontbreekt_voor_herplaatsen({"description": "Zilveren lepel", "photo_urls": []})
    assert reden and "photo" in reden


def test_compleet_item_mag_gewoon():
    assert ontbreekt_voor_herplaatsen(
        {"description": "Zilveren lepel, 1802", "photo_urls": ["https://x/1.jpg"]}) is None


def test_de_rem_staat_voor_de_verwijderopdracht():
    """Volgorde is hier alles: controleren ná het verwijderen helpt niemand."""
    rem = RELIST.index('if strategy == "relist" and ontbreekt_voor_herplaatsen(item)')
    verwijder = RELIST.index('"action": "delete"')
    assert rem < verwijder


def test_er_wordt_eerst_geprobeerd_aan_te_vullen():
    """De advertentie staat op dat moment nog online; daar staat de tekst."""
    blok = RELIST.split("if strategy == \"relist\" and ontbreekt_voor_herplaatsen(item)")[1][:900]
    assert "vul_item_aan_uit_advertentie" in blok
    assert "platform_listing_url" in blok


def test_aanvullen_overschrijft_nooit_wat_de_verkoper_zelf_invulde():
    """Aanvullen mag, overschrijven niet.

    Sinds 28-08-2026 vervangen we een opgeslagen omschrijving wél, maar alleen
    als die letterlijk het begin is van wat er op de advertentiepagina staat —
    dus een afgekapte versie van dezelfde tekst. Dat was nodig omdat onze eigen
    4000-tekengrens de onderkant van elke lange advertentietekst wegsneed
    (Jaap, Zilverwebsite). Een tekst die de verkoper zelf heeft aangepast wijkt
    af en blijft staan.
    """
    src = (ROOT / "backend/services/mp_enrich.py").read_text(encoding="utf-8")
    fn = src.split("async def vul_item_aan_uit_advertentie(")[1].split("\nasync def ")[0]
    assert 'not huidig' in fn
    assert '_is_afgekapt(huidig, tekst)' in fn


def test_alleen_een_afgekapte_tekst_wordt_vervangen():
    from backend.services.mp_enrich import _is_afgekapt
    vol = "Zilveren lepel, 1802.\n\nGewicht: 15,8 gram.\n\nArtikelnummer 4711. Verzendkosten 6,95."
    assert _is_afgekapt("Zilveren lepel, 1802.\n\nGewicht: 15,8 gram.", vol)
    assert _is_afgekapt("Zilveren lepel, 1802. Gewicht: 15,8 gram...", vol)
    assert _is_afgekapt("", vol)
    assert not _is_afgekapt("Mijn eigen tekst over deze lepel", vol)


def test_de_tekstgrens_knipt_geen_advertenties_meer_af():
    """2000 tekens was een zelfverzonnen grens die de onderkant wegsneed."""
    shared = (ROOT / "extension/content/shared.js").read_text(encoding="utf-8")
    assert "slice(0, 2000)" not in shared
    assert "MAX_BESCHRIJVING = 20000" in shared
    enrich = (ROOT / "backend/services/mp_enrich.py").read_text(encoding="utf-8")
    assert "DESC_MAX = 20000" in enrich


def test_de_afsluitvraag_gaat_uit_voor_de_plaatsklik():
    """"Site verlaten?" bevroor het publiceren tot de verkoper zelf klikte."""
    shared = (ROOT / "extension/content/shared.js").read_text(encoding="utf-8")
    blok = shared.split('type: "SUBMIT_CLICKED"')[1].split("btn.click()")[0]
    assert "ONTWAPEN_AFSLUITVRAAG" in blok
    bg = (ROOT / "extension/background.js").read_text(encoding="utf-8")
    assert 'msg.type === "ONTWAPEN_AFSLUITVRAAG"' in bg


def test_publiceren_vult_een_item_met_een_enkele_foto_eerst_aan():
    src = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")
    blok = src.split("_fill_inferred_gaps(db, item)")[1][:1600]
    assert 'len(item.get("photo_urls") or []) <= 1' in blok
    assert "vul_item_aan_uit_advertentie" in blok


# ── 2. De dagteller telt alleen de knop die hij bewaakt ──────────────────────

def test_dagteller_telt_alleen_handmatige_verversingen():
    blok = RELIST.split("if platform in COOLDOWN_DAYS_PER_PLATFORM:")[1].split("if row.data:")[0]
    assert '.eq("payload->>_handmatige_verversing", "true")' in blok, \
        "anders telt de nachtelijke ronde de handmatige knop vol"
    assert '.neq("status", "error")' in blok, \
        "een mislukte verwijdering heeft niets ververst en hoort niet mee te tellen"


def test_alleen_de_handmatige_weg_zet_het_merkteken():
    blok = RELIST.split("delete_payload = {")[1].split("}")[0]
    assert '"_handmatige_verversing": not eigen_quotum' in blok


# ── 3. De extensie maakt het formulier af voordat hij klaagt ─────────────────

def test_tekstprobleem_wist_niet_de_rest_van_het_formulier():
    for naam, src in (("marktplaats", MP), ("2dehands", DH)):
        vul = src.split("async function fillForm(item) {")[1]
        assert "let descError = null;" in vul, f"{naam}: tekstfout brak het hele formulier af"
        assert "if (descError) throw descError;" in vul, f"{naam}: de reden moet alsnog gemeld"
        # de klacht komt ná het invullen van foto's en kenmerken
        assert vul.index("uploadPhotos") < vul.index("if (descError) throw descError;")
        assert vul.index('step("brand"') < vul.index("if (descError) throw descError;")


def test_er_wordt_gewacht_op_de_tekst_editor():
    fn = SHARED.split("async function fillDescription(")[1].split("\n  }")[0]
    assert re.search(r"for \(let poging = 0; poging < \d+ && !selector", fn), \
        "de editor wordt later bijgeladen dan het titelveld"
    assert "The description field could not be found" in fn


def test_extensieversie_is_opgehoogd():
    manifest = (ROOT / "extension/manifest.json").read_text(encoding="utf-8")
    versie = re.search(r'"version":\s*"1\.0\.(\d+)"', manifest)
    assert versie and int(versie.group(1)) >= 257
