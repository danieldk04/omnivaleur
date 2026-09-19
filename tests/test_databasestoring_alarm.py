"""Krijgt Daniel bericht als de database wegvalt?

WAT ER GEBEURDE (19-09-2026). Tussen 15:10 en 16:57 gaf Supabase geen antwoord
meer: PostgREST 503 met PGRST002 ("Could not query the database for the schema
cache"), de opslag 544 DatabaseTimeout, auth helemaal niets. De site zelf bleef
overeind — /health gaf 200 in 0,3 seconde, want dat kijkt niet in de database —
en alles wat wél gegevens nodig heeft gaf 500. Bijna twee uur lang leeg
dashboard en geen publicaties, en er ging geen enkel bericht uit. Het bestaande
alarm dekt maar één manier waarop de database wegvalt: het project dat op slot
gaat wegens verbruik (402).

Deze proef draait de ECHTE meldfunctie uit backend/database.py met een
nagebootste klok, en gebruikt de letterlijke fouttekst van die middag.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.database as D  # noqa: E402

# Letterlijk wat de database die middag teruggaf.
PGRST002 = ('{"code":"PGRST002","details":null,"hint":null,'
            '"message":"Could not query the database for the schema cache. Retrying."}')
OPSLAG = '{"statusCode":"544","error":"DatabaseTimeout","message":"The connection to the database timed out"}'


class _Klok:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def verder(self, seconden):
        self.t += seconden


@pytest.fixture
def opstelling(monkeypatch):
    """Verse tellers, een klok die wij bedienen en een postbus in plaats van mail."""
    klok = _Klok()
    monkeypatch.setattr(D.time, "monotonic", klok)
    monkeypatch.setattr(D, "_DB_EERSTE_FOUT", 0.0)
    monkeypatch.setattr(D, "_DB_GEMELD_OP", 0.0)
    postbus = []

    import backend.services.email as E
    monkeypatch.setattr(E, "send_email",
                        lambda onderwerp, tekst, **kw: postbus.append((onderwerp, tekst)) or True)
    return klok, postbus


def test_een_storing_van_drie_minuten_levert_een_mail_op(opstelling):
    klok, postbus = opstelling
    fout = Exception(PGRST002)

    D._databasefout_gezien(fout)          # eerste mislukking: alleen onthouden
    assert postbus == [], "één mislukking is nog geen storing"

    klok.verder(60)
    D._databasefout_gezien(fout)
    assert postbus == [], "een minuut hik is nog steeds geen storing"

    klok.verder(150)                       # nu 3,5 minuut onafgebroken stuk
    D._databasefout_gezien(fout)
    assert len(postbus) == 1, "hier hoort de mail te komen"
    onderwerp, tekst = postbus[0]
    assert "database" in onderwerp.lower()
    assert "supabase.com/dashboard" in tekst, "de mail moet zeggen wat hij moet doen"
    assert "PGRST002" in tekst, "en wat de database zelf teruggaf"


def test_een_korte_hik_mailt_niets(opstelling):
    """De verbinding valt geregeld even weg; dat wordt gewoon herhaald."""
    klok, postbus = opstelling
    D._databasefout_gezien(Exception(PGRST002))
    klok.verder(30)
    D._databasefout_gezien(Exception(PGRST002))
    D.database_deed_het()                  # en hij doet het weer
    klok.verder(600)
    D._databasefout_gezien(Exception(PGRST002))
    assert postbus == [], f"niets te melden, maar er ging post uit: {postbus}"


def test_een_gewone_fout_in_een_query_is_geen_storing(opstelling):
    """Anders mailt hij bij elke programmeerfout en wordt het alarm genegeerd."""
    klok, postbus = opstelling
    for tekst in ('{"code":"42703","message":"column listings.updated_at does not exist"}',
                  '{"code":"23505","message":"duplicate key value violates unique constraint"}',
                  "JSON object requested, multiple (or no) rows returned"):
        D._databasefout_gezien(Exception(tekst))
        klok.verder(300)
        D._databasefout_gezien(Exception(tekst))
    assert postbus == [], f"dit zijn fouten in een vraag, geen storing: {postbus}"


def test_de_opslagfout_van_die_middag_telt_ook_mee(opstelling):
    klok, postbus = opstelling
    D._databasefout_gezien(Exception(OPSLAG))
    klok.verder(200)
    D._databasefout_gezien(Exception(OPSLAG))
    assert len(postbus) == 1, "544 DatabaseTimeout hoort net zo goed een storing te zijn"


def test_een_weggevallen_verbinding_telt_mee(opstelling):
    """ReadTimeout is precies wat er die middag als eerste langskwam."""
    import httpx
    klok, postbus = opstelling
    D._databasefout_gezien(httpx.ReadTimeout("The read operation timed out"))
    klok.verder(200)
    D._databasefout_gezien(httpx.ReadTimeout("The read operation timed out"))
    assert len(postbus) == 1


def test_na_herstel_komt_er_bericht_en_begint_de_telling_opnieuw(opstelling):
    klok, postbus = opstelling
    D._databasefout_gezien(Exception(PGRST002))
    klok.verder(200)
    D._databasefout_gezien(Exception(PGRST002))
    assert len(postbus) == 1

    klok.verder(4000)
    D.database_deed_het()
    assert len(postbus) == 2, "het herstel hoort ook gemeld te worden"
    onderwerp, tekst = postbus[1]
    assert "doet het weer" in onderwerp
    assert "70 minuten" in tekst, f"de duur hoort in de mail te staan: {tekst}"

    # En daarna begint alles opnieuw: geen tweede herstelmail zonder storing.
    D.database_deed_het()
    assert len(postbus) == 2


def test_binnen_de_stilte_geen_tweede_mail_maar_daarna_wel(opstelling):
    klok, postbus = opstelling
    D._databasefout_gezien(Exception(PGRST002))
    klok.verder(200)
    D._databasefout_gezien(Exception(PGRST002))
    assert len(postbus) == 1

    klok.verder(3600)                      # een uur later, storing duurt voort
    D._databasefout_gezien(Exception(PGRST002))
    assert len(postbus) == 1, "binnen twee uur hoort er geen herinnering te komen"

    klok.verder(3700)                      # nu ruim twee uur na de eerste mail
    D._databasefout_gezien(Exception(PGRST002))
    assert len(postbus) == 2, "na de stilteperiode mag hij het opnieuw zeggen"


# ── Voor-en-na ───────────────────────────────────────────────────────────────
VOOR_HET_ALARM = "defcd54d"


def test_de_oude_versie_zweeg_bij_precies_deze_storing(monkeypatch):
    """Zonder deze reparatie ging er geen enkel bericht uit, en dat is hoe de
    storing van 19-09 bijna twee uur onopgemerkt bleef."""
    import importlib.util
    import subprocess
    import tempfile

    bron = subprocess.run(["git", "show", f"{VOOR_HET_ALARM}:backend/database.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_databasefout_gezien" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_database.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_database", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)

    postbus = []
    import backend.services.email as E
    monkeypatch.setattr(E, "send_email",
                        lambda onderwerp, tekst, **kw: postbus.append(onderwerp) or True)

    # De oude code kende maar één alarm: het project dat op slot gaat.
    oud.meld_quotastoring(Exception(PGRST002))
    assert postbus == [], "de oude versie had hier juist niets voor"
    assert not oud._is_herstelbaar(Exception(PGRST002)), (
        "en zag PGRST002 niet eens als iets om opnieuw te proberen")

    # Ter vergelijking: waar hij wél op reageerde.
    oud.meld_quotastoring(Exception(
        "Service for this project is restricted due to the following violations: quota"))
    assert len(postbus) == 1, "het bestaande alarm blijft gewoon werken"


def test_een_echte_mislukte_leesactie_komt_bij_het_alarm_terecht(opstelling):
    """Niet de meldfunctie los aanroepen maar de echte weg: een echte
    Supabase-client die een echte leesactie doet op een adres dat niet antwoordt.

    Dit is de aansluiting die telt. De meldfunctie kan perfect werken en tóch
    nooit afgaan als hij niet in de foutafhandeling van de client hangt."""
    from supabase import create_client

    klok, postbus = opstelling
    db = create_client("http://127.0.0.1:1", "nep-sleutel-voor-deze-proef")

    for ronde in range(2):
        with pytest.raises(Exception):
            db.table("items").select("id").limit(1).execute()
        klok.verder(200)

    assert postbus, "een database die niet antwoordt hoort een alarm te geven"
    onderwerp, tekst = postbus[0]
    assert "database" in onderwerp.lower()
    assert "supabase.com/dashboard" in tekst
