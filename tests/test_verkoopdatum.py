"""De verkoopdatum moet de ECHTE datum zijn, niet de dag waarop wij het merkten.

WAT ER MISGING (30-08-2026)
Twaalf verkopen van weken kregen alle twaalf een tijdstempel tussen 07:36:54 en
07:37:06 op 30 augustus. De oorzaak: verkopen op Vinted worden ontdekt door elke
tien minuten de eigen bestellingenpagina te lezen, en die pagina is een
geschiedenis. Elke bestelling die we voor het eerst konden koppelen werd geboekt
met de klok van dat moment. Na een stille periode — de extensie lag stil, of een
verbetering herkende ineens oude bestellingen — landde de omzet van weken op één
dag en was elke grafiek onbruikbaar.

Deze test bewaakt de twee regels die dat voorkomen:
1. De datum wordt gelezen uit wat het platform toont; een onduidelijke datum
   levert None op en dan verandert er niets (dezelfde regel als mp_datums.py).
2. Een datum mag alleen naar VOREN in de tijd worden bijgesteld. Ontdekken kan
   nooit eerder dan verkopen, dus een lagere datum is per definitie de betere —
   en zo repareert een latere ronde vanzelf een te late stempel.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.verkoopdatum import als_datum, lees_verkoopdatum  # noqa: E402

NU = datetime(2026, 8, 30, 7, 37, tzinfo=timezone.utc)


def test_machineleesbare_datum_wint():
    """Het datetime-attribuut van de pagina is exact — inclusief het tijdstip."""
    d = lees_verkoopdatum("2026-08-17T10:22:00Z", NU)
    assert d == datetime(2026, 8, 17, 10, 22, tzinfo=timezone.utc)


def test_kale_datum_wordt_middag():
    """Middag, niet middernacht: anders schuift een tijdzoneverschil de verkoop
    naar de dag ervoor of erna, en de grafiek telt per dag."""
    assert lees_verkoopdatum("2026-08-17", NU) == datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def test_nederlandse_en_engelse_vormen():
    assert lees_verkoopdatum("gisteren", NU).date() == datetime(2026, 8, 29).date()
    assert lees_verkoopdatum("eergisteren", NU).date() == datetime(2026, 8, 28).date()
    assert lees_verkoopdatum("yesterday", NU).date() == datetime(2026, 8, 29).date()
    assert lees_verkoopdatum("3 dagen geleden", NU).date() == datetime(2026, 8, 27).date()
    assert lees_verkoopdatum("2 days ago", NU).date() == datetime(2026, 8, 28).date()
    assert lees_verkoopdatum("17 aug", NU).date() == datetime(2026, 8, 17).date()
    assert lees_verkoopdatum("17 augustus 2026", NU).date() == datetime(2026, 8, 17).date()
    assert lees_verkoopdatum("Aug 17, 2026", NU).date() == datetime(2026, 8, 17).date()
    assert lees_verkoopdatum("17-08-2026", NU).date() == datetime(2026, 8, 17).date()


def test_vandaag_krijgt_nooit_een_tijd_in_de_toekomst():
    """"Vandaag" om 07:37 mag geen stempel van 12:00 opleveren."""
    assert lees_verkoopdatum("vandaag", NU) == NU


def test_onduidelijk_is_geen_datum():
    """Een gegokte datum is erger dan geen datum: dan blijft de bestaande staan."""
    for rommel in (None, "", "   ", "Maat 40 - Zeer Goed", "Verzendlabel klaar",
                   "€ 20,19", "(1304) Brown Suitsupply Jumper"):
        assert lees_verkoopdatum(rommel, NU) is None


def test_toekomst_en_grijs_verleden_worden_geweigerd():
    """Een verkoop in de toekomst bestaat niet, en iets van jaren terug is een
    leesfout — bijvoorbeeld een artikelnummer dat op een jaartal lijkt."""
    assert lees_verkoopdatum("2030-01-01", NU) is None
    assert lees_verkoopdatum("2026-08-30T23:00:00Z", NU) is None
    assert lees_verkoopdatum("1999-01-01", NU) is None


def test_datum_uit_een_hele_orderregel():
    """De regeltekst is het laatste vangnet als de pagina geen datumveld heeft."""
    regel = "(1304) Brown Suitsupply Jumper - Men M € 20,19 12 aug"
    assert lees_verkoopdatum(regel, NU).date() == datetime(2026, 8, 12).date()


def test_als_datum_leest_opgeslagen_stempels():
    assert als_datum("2026-08-17T10:22:00+00:00") == datetime(2026, 8, 17, 10, 22, tzinfo=timezone.utc)
    # Zonder tijdzone: als UTC lezen, niet als lokale tijd — anders verspringt
    # de dag en staat de verkoop op de verkeerde datum in de grafiek.
    assert als_datum("2026-08-17T10:22:00").tzinfo is not None


def test_datum_wordt_alleen_naar_voren_bijgesteld():
    """De kernregel. Een herdetectie mag een verkoop nooit naar vandaag schuiven,
    maar een echte, eerdere datum moet een te late stempel wél repareren."""
    gestempeld = als_datum("2026-08-30T07:37:06+00:00")   # de te late stempel
    later_op_de_dag = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)

    echt = lees_verkoopdatum("17 aug", later_op_de_dag)
    assert echt < gestempeld                     # de correctie wordt doorgevoerd

    opnieuw_gezien = lees_verkoopdatum("vandaag", later_op_de_dag)
    assert not (opnieuw_gezien < gestempeld)     # en de terugval blijft liggen


def test_extensie_stuurt_de_besteldatum_mee():
    """Zonder deze velden in de extensie heeft de server niets om te lezen en
    valt alles terug op de dag van ontdekken — precies de storing van 30-08."""
    src = (ROOT / "extension" / "background.js").read_text(encoding="utf-8")
    assert "datumKandidaten" in src, "de bestellingen-scraper leest geen datum meer uit"
    assert "time[datetime]" in src, "het machineleesbare datumveld wordt niet meer gelezen"
    assert "date: datumKandidaten(row)" in src, "de datum wordt niet meegestuurd naar de server"


def test_verkoopbronnen_geven_hun_eigen_datum_door():
    """eBay en Shopify weten precies wanneer er verkocht is. Gooien we dat weg,
    dan krijgt elke ingehaalde bestelling alsnog de datum van vandaag."""
    webhooks = (ROOT / "backend" / "api" / "webhooks.py").read_text(encoding="utf-8")
    assert "sold_at=_ebay_sale_time(payload, item_data)" in webhooks
    assert "sold_at=besteld_op" in webhooks
    sweep = (ROOT / "backend" / "services" / "shopify_orders.py").read_text(encoding="utf-8")
    assert "sold_at=besteld_op" in sweep
