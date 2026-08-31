"""Staat het project op slot, dan hoort Daniel dat van ons te horen.

WAAROM DIT ER IS (31-08-2026)
Supabase zette het hele project op slot omdat het gratis plan op was. Elk
verzoek kreeg een 402 met "Service for this project is restricted due to the
following violations: exceed_egress_quota…". Inloggen gaf 503, de blog 500, de
mailagent viel stil.

Wij hoorden dat niet van onze eigen server. We hoorden het van Ronald van
Zilverwebsite, die om 07:22 mailde dat inloggen niet lukte, met een
schermafbeelding erbij. Dat is de verkeerde volgorde: een klant hoort niet de
storingsmelder te zijn.

Twee dingen moeten daarom vastliggen:
  1. een blokkade is GEEN weggevallen verbinding — herhalen helpt niet en
     verbruikt juist nog meer van wat op is;
  2. er gaat één keer alarm uit, niet duizenden keren.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import database as db  # noqa: E402

BLOKKADE = (
    'Client error \'402 Payment Required\' for url \'https://x.supabase.co/rest/v1/items\'\n'
    '{"message":"Service for this project is restricted due to the following '
    'violations: exceed_cached_egress_quota, exceed_egress_quota, '
    'exceed_storage_size_quota. The project owner must upgrade their plan or '
    'remove spend caps to restore service."}'
)


@pytest.fixture(autouse=True)
def _schone_klok(monkeypatch):
    monkeypatch.setattr(db, "_QUOTA_GEMELD_OP", 0.0, raising=False)


def test_de_blokkade_wordt_herkend():
    assert db._is_quotastoring(RuntimeError(BLOKKADE))


def test_een_gewone_verbindingsfout_is_geen_blokkade():
    """Anders zou elke hik een alarmmail opleveren en kijkt niemand er nog naar."""
    assert db._is_quotastoring(RuntimeError("Server disconnected without sending a response")) == ""
    assert db._is_quotastoring(RuntimeError("Invalid login credentials")) == ""


def test_een_blokkade_wordt_niet_herhaald(monkeypatch):
    """DE KERN. Opnieuw proberen helpt niet bij een vol quotum — het verbruikt
    alleen nog meer van precies datgene wat op is."""
    monkeypatch.setattr(db, "meld_quotastoring", lambda e: None)
    assert db._is_herstelbaar(RuntimeError(BLOKKADE)) is False


def test_een_weggevallen_verbinding_wordt_nog_steeds_wel_herhaald():
    """De reparatie mag de bestaande herkansing niet meenemen in zijn val."""
    assert db._is_herstelbaar(RuntimeError("Server disconnected without sending a response")) is True


def test_de_blokkade_levert_precies_een_alarm_op(monkeypatch):
    """Bij duizenden verzoeken per uur zou een alarm per verzoek zelf de storing
    worden."""
    verstuurd = []
    import backend.services.email as mail
    monkeypatch.setattr(mail, "send_email",
                        lambda onderwerp, tekst, **kw: verstuurd.append(onderwerp))
    monkeypatch.setattr(db, "_QUOTA_GEMELD_OP", 0.0, raising=False)

    for _ in range(50):
        db.meld_quotastoring(RuntimeError(BLOKKADE))

    assert len(verstuurd) == 1, f"er gingen {len(verstuurd)} alarmen uit in plaats van 1"
    assert "Supabase" in verstuurd[0]


def test_het_alarm_zegt_wat_de_klant_merkt_en_wat_de_keuze_is(monkeypatch):
    """Daniel is geen programmeur. "402" zegt hem niets; "je klanten kunnen niet
    inloggen" wel, en daarna wil hij weten wat hem dat kost."""
    inhoud = []
    import backend.services.email as mail
    monkeypatch.setattr(mail, "send_email",
                        lambda onderwerp, tekst, **kw: inhoud.append(tekst))
    monkeypatch.setattr(db, "_QUOTA_GEMELD_OP", 0.0, raising=False)

    db.meld_quotastoring(RuntimeError(BLOKKADE))

    assert inhoud
    tekst = inhoud[0].lower()
    assert "inloggen" in tekst
    assert "factuurperiode" in tekst          # de gratis weg
    assert "opwaarderen" in tekst             # de betaalde weg


def test_een_mislukt_alarm_gooit_niets_om(monkeypatch):
    """Dit draait midden in een databaseaanroep. Zou het alarm zelf een fout
    opgooien, dan verandert een storing in een tweede storing."""
    import backend.services.email as mail

    def stuk(*a, **kw):
        raise RuntimeError("Resend weigert")

    monkeypatch.setattr(mail, "send_email", stuk)
    monkeypatch.setattr(db, "_QUOTA_GEMELD_OP", 0.0, raising=False)
    db.meld_quotastoring(RuntimeError(BLOKKADE))   # mag niet opgooien
