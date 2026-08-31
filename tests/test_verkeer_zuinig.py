"""Onze eigen lussen mogen de database niet leegtrekken.

WAAROM DIT ER IS (31-08-2026)
Supabase zette het project op slot: 402 Payment Required, verkeer op 437% van
het gratis plan (21,8 GB tegen een limiet van 5 GB). Inloggen gaf 503, de blog
500 — de app lag eruit voor iedere klant, en de mailagent viel stil.

Met 24 actieve gebruikers kwam dat verkeer niet van bezoekers. Het kwam van
achtergrondtaken die elke paar minuten dezelfde tabellen opnieuw ophaalden, en
van kolommen die werden meegenomen zonder dat iemand ze las.

Deze proef bewaakt de twee plekken waar dat het ergst was. Ze staan er niet om
netheid: valt een van deze regels weg, dan loopt de meter opnieuw vol en gaat de
site opnieuw plat.
"""
import pathlib
import re

WORTEL = pathlib.Path(__file__).resolve().parents[1]
POLLING = (WORTEL / "backend" / "services" / "polling.py").read_text(encoding="utf-8")
ENRICH = (WORTEL / "backend" / "services" / "mp_enrich.py").read_text(encoding="utf-8")


# ── de verkoopcontrole ───────────────────────────────────────────────────────

def test_de_verkoopcontrole_haalt_niet_meer_alles_op():
    """Dit was de duurste: elke vijf minuten alle 4.751 actieve advertenties,
    288 keer per dag."""
    ronde = POLLING.split("async def poll_platform_statuses(", 1)[1].split("\nasync def ", 1)[0]
    assert "fetch_all" not in ronde, \
        "de verkoopcontrole haalt weer de hele tabel op"
    assert ".limit(PER_RONDE)" in ronde
    assert "last_checked.lt." in ronde


def test_de_koppelingen_worden_niet_meer_allemaal_opgehaald():
    """`platform_credentials` bevat tokens en cookies — de dikste rijen die we
    hebben. Die hoorden nooit in hun geheel opgehaald te worden."""
    ronde = POLLING.split("async def poll_platform_statuses(", 1)[1].split("\nasync def ", 1)[0]
    creds = ronde.split('db.table("platform_credentials")', 1)[1][:300]
    assert '.in_("user_id"' in creds, \
        "alle koppelingen van alle verkopers worden weer opgehaald"


# ── het aanvullen van teksten ────────────────────────────────────────────────

def test_de_tekstronde_haalt_niet_van_alles_de_volledige_omschrijving_op():
    """`description` is de dikste kolom die we hebben, en er werd maar één ding
    aan gevraagd: ben je leeg? Bij een verkoper met 2.135 items betekende dat
    elk kwartier megabytes ophalen voor een vinkje."""
    blok = ENRICH.split("    rijen = await naast_de_lus(lambda: fetch_all(", 1)[1][:400]
    kolommen = re.search(r'\.select\("([^"]+)"\)', blok).group(1)
    assert "description" not in kolommen, \
        "de bulkvraag haalt weer van elke advertentie de volledige tekst op"
    # De losse vraag "wie mist er tekst" mag natuurlijk wel; die geeft id's terug.
    assert 'or_("description.is.null,description.eq.")' in ENRICH


def test_de_echte_teksten_komen_alleen_voor_wat_we_aanpakken():
    """Voor `_is_afgekapt` is de inhoud wél nodig — maar alleen van de handvol
    advertenties die deze ronde aan de beurt is, niet van de hele voorraad."""
    assert 'db.table("items").select("id,description")' in ENRICH
    blok = ENRICH.split('db.table("items").select("id,description")', 1)[1][:200]
    assert '.in_("id"' in blok


def test_de_leegcontrole_leest_geen_tekst_meer():
    """Zou ergens nog `str(r.get("description"))` staan om te kijken of hij leeg
    is, dan is de bulkvraag stiekem weer nodig en komt de kolom terug."""
    ronde = ENRICH.split("async def vul_ontbrekende_teksten_aan(", 1)[1] \
        if "async def vul_ontbrekende_teksten_aan(" in ENRICH else ENRICH
    assert 'r.get("heeft_tekst")' in ENRICH, \
        "de leegcontrole gebruikt niet meer het lichte vinkje"
