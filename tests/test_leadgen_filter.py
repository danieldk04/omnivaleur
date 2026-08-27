"""Het leadfilter mag alleen verkopers doorlaten die wij ook echt kunnen bedienen.

Aanleiding (27-08-2026): twee leads op één dag kregen een enthousiaste mail en
daarna een afwijzing. Borstelbeer verkoopt refurbished elektrische tandenborstels
— daar bestaat geen categorie voor, dus publiceren zou vastlopen. Vianen Telecom
wilde telefoonaccessoires kwijt; ook geen categorie. In beide gevallen was dat
vooraf te zien.

Deze test bewaakt twee dingen: dat het filter de échte categorielijst gebruikt in
plaats van een kopie die uit de pas loopt, en dat de twee afwijsregels werken.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import leadgen_marktplaats as mp  # noqa: E402


@pytest.fixture(scope="module")
def groepen():
    return mp._publiceerbare_groepen()


def test_de_groepen_komen_uit_het_echte_dashboard(groepen):
    # Niet uit een lijst in dit script: die loopt binnen een maand achter op de
    # werkelijkheid en filtert dan precies verkeerd om.
    assert set(groepen) >= {"dames", "heren", "kinderen", "unisex", "sieraden",
                            "games", "electronics", "antiek", "muziek", "wonen"}
    assert all(sleutels for sleutels in groepen.values())


def test_electronics_is_alleen_telefoons(groepen):
    """De val waar Vianen Telecom in liep: 'elektronica' klinkt breed, maar de hele
    tak bestaat uit telefoonmerken. Accessoires, computers en audio horen er niet
    in en mogen er ook niet stilletjes bij komen zonder dat iemand dit ziet."""
    tak = " ".join(groepen["electronics"]).lower()
    assert "telefoon" in tak
    for verboden in ("hoesje", "oplader", "oordopjes", "laptop", "computer", "tv"):
        assert verboden not in tak, f"{verboden} zit nu in electronics — pas het filter aan"


def test_hele_productgebieden_ontbreken_nog_steeds(groepen):
    """Zolang dit klopt, moet het filter zulke leads afwijzen. Komt er ooit wél een
    tak bij, dan valt deze test om en is dat het sein om het filter te verruimen.

    Alleen woorden die in GEEN ENKELE tak voorkomen. Boeken, gereedschap en
    speelgoed staan bewust niet in deze lijst: die bestaan wél, maar uitsluitend
    onder 'antiek'. Dat onderscheid staat in de prompt zelf."""
    alles = " ".join(s for sleutels in groepen.values() for s in sleutels).lower()
    for ontbreekt in ("tandenborstel", "verzorging", "witgoed", "wasmachine",
                      "koelkast", "laptop", "toetsenbord", "fiets", "huisdier"):
        assert ontbreekt not in alles, f"'{ontbreekt}' bestaat nu wel — verruim het filter"


def test_de_audiotak_bestaat_en_is_compleet(groepen):
    """Toegevoegd op 27-08-2026 voor de 51 leads in audio/tv/foto die we niet
    konden bedienen. Alle 68 Marktplaats-subcategorieën van l1=31 horen erin;
    een half afgemaakte tak is precies het probleem dat we wilden oplossen."""
    audio = groepen["audio"]
    assert len(audio) == 68, f"{len(audio)} in plaats van 68 — is er een categorie weggevallen?"
    tekst = " ".join(audio)
    for verwacht in ("luidsprekers", "koptelefoons", "televisies",
                     "fotocamera s digitaal", "lenzen en objectieven",
                     "verrekijkers", "platenspelers"):
        assert verwacht in tekst


def test_boeken_en_gereedschap_bestaan_alleen_als_antiek(groepen):
    """De nuance die de prompt moet maken. Een antiquaar is een prima lead, een
    boekhandel met nieuwe romans niet."""
    antiek = " ".join(groepen["antiek"]).lower()
    assert "boeken" in antiek and "gereedschap" in antiek
    anders = " ".join(s for g, v in groepen.items() if g != "antiek" for s in v).lower()
    assert "boeken" not in anders


def test_de_prompt_bevat_de_hele_lijst():
    """Het model mag niet uit eigen kennis aanvullen; het moet de lijst voor zich
    hebben. Een steekproef uit drie takken."""
    prompt = mp._fill({"name": "Test", "ads": 40})
    for sleutel in ("tuinstoelen", "iphone", "kettingen"):
        assert sleutel in prompt
    assert "geen persoonlijke\n    verzorging" in prompt or "verzorging" in prompt


def _oordeel(**overschrijf):
    basis = {"is_lead": True, "confidence": 90, "verkopertype": "handelaar",
             "verzendbaar": True, "commercieel": True,
             "categorie_fit": "heren", "retail_varianten": False}
    basis.update(overschrijf)
    return basis


def test_een_gewone_kledinghandelaar_blijft_erdoor():
    assert mp._keep(_oordeel(), 70)
    assert mp._afwijsreden(_oordeel(), 70) == ""


@pytest.mark.parametrize("fit", ["geen", "", "persoonlijke verzorging", "boeken"])
def test_zonder_passende_categorie_valt_hij_af(fit):
    """Borstelbeer. Ook een verzonnen groepsnaam telt als 'past niet' — het model
    mag zich er niet uitkletsen met een categorie die niet bestaat."""
    assert not mp._keep(_oordeel(categorie_fit=fit), 70)
    assert mp._afwijsreden(_oordeel(categorie_fit=fit), 70) == "geen categorie"


def test_een_webshop_met_varianten_valt_af():
    """Eén jas in vijf maten en drie kleuren. Bij ons is een artikel één stuk met
    één prijs, dus daar is niets zinnigs mee te doen."""
    verdict = _oordeel(retail_varianten=True)
    assert not mp._keep(verdict, 70)
    assert mp._afwijsreden(verdict, 70) == "varianten"


def test_de_oude_afwijsregels_werken_nog():
    assert mp._afwijsreden(_oordeel(is_lead=False), 70) == "geen lead"
    assert mp._afwijsreden(_oordeel(confidence=40), 70) == "twijfel"
    assert mp._afwijsreden(_oordeel(verkopertype="verhuur"), 70) == "verhuur"
    assert mp._afwijsreden(_oordeel(verzendbaar=False), 70) == "onverzendbaar"
    assert mp._afwijsreden(_oordeel(commercieel=False), 70) == "particulier"


def test_een_oud_oordeel_telt_niet_meer_mee():
    """Zonder versiestempel verandert een strenger filter niets aan de stapel waar
    de mails uit komen — precies de stapel waar het misging."""
    assert mp.PROMPT_VERSIE >= 2


# ── Een leesfout mag geen advertentie onzichtbaar maken ─────────────────────

def test_bij_een_leesfout_wordt_geen_advertentienummer_overschreven():
    """`_tweede_advertentie` bewaakt de verkoper die hetzelfde artikel meerdere
    keren los te koop zet: tien identieke blikjes plectrums zijn tien
    advertenties. Zei die functie ten onrechte "nee", dan werd het nummer van de
    bestaande regel overschreven en kende het dashboard negen advertenties niet
    meer — dus kon het ze ook niet weghalen bij verkoop.

    Tot 27-08-2026 gaf hij bij een databasefout False terug, precies die kant op.
    En leesfouten zijn hier geen theorie: parallelle Supabase-leesacties vielen
    gemeten 45 van de 55 keer om.
    """
    from backend.api import imports

    class _Stuk:
        def table(self, *a, **k): raise RuntimeError("Supabase deed het even niet")

    assert imports._tweede_advertentie(_Stuk(), "item-1", "marktplaats", "123") is True

    class _Werkt:
        def table(self, *a, **k): return self
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def execute(self): return type("R", (), {"data": [{"platform_listing_id": "123"}]})()

    # Alleen dezelfde advertentie bekend → geen tweede, koppelen mag.
    assert imports._tweede_advertentie(_Werkt(), "item-1", "marktplaats", "123") is False
    # Een ander nummer bekend → er staat er al een, dus niet overschrijven.
    assert imports._tweede_advertentie(_Werkt(), "item-1", "marktplaats", "999") is True
