"""Een rubriek die geld vraagt stopt die rubriek, niet het hele kanaal.

WAT ER GEBEURDE (10-09-2026, Egbert Brouwer / Papa's Plectrums). Van zijn bulk
naar 2dehands mislukten er 24 met "Je hebt geen zoekertjesvorm gekozen". Dat
leest als een leeg veld op het formulier, maar dat was het niet. Gemeten in zijn
eigen opdrachten in de database:

  * alle 24 stonden in dezelfde drie gitaarrubrieken (/plaats/728/746, /747, /748);
  * de pagina meldde letterlijk "Dit is een betalende categorie";
  * de gratis keuze bestond daar niet ("Free option: knop niet gevonden");
  * de plaatsknop heette "Naar betalen" in plaats van "Plaats zoekertje";
  * en in diezelfde rubrieken lukten de eerste twee zoekertjes wél — elektrisch
    13:06 en 13:07, akoestisch 13:09 en 13:17, bas 13:10 en 13:56 — waarna het
    omsloeg. Het gratis tegoed van die rubriek was op.

Op datzelfde moment gingen zijn zoekertjes in Behuizingen en koffers, Standaards
en Toebehoren gewoon gratis online. Het kanaal werkt dus; alleen die drie
rubrieken kosten geld. Er stonden nog 274 opdrachten in die drie rubrieken te
wachten: 274 rode balken, één per twee minuten.

Deze proef gebruikt de LETTERLIJKE foutmelding van opdracht
4b77d41f-5ded-4ecd-895a-1b07785e8f5e uit zijn account, en draait die twee keer:
door de code zoals hij nu is, en door de code van vóór de reparatie.
"""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as jobs_api  # noqa: E402

# Vast commitnummer, geen HEAD: zodra dit gecommit is vergelijkt HEAD de
# reparatie met zichzelf en bewijst de voor-en-na niets meer.
VOOR_DE_REPARATIE = "af816f80"
USER_ID = "bcdf9aa4-314d-49a2-9573-8818ad61073d"

# Letterlijk uit de database, opdracht 4b77d41f-5ded-4ecd-895a-1b07785e8f5e.
ECHTE_FOUT = (
    'Error: Not published — complete the fields marked in red and click publish yourself. '
    'Je hebt geen zoekertjesvorm gekozen. | No field is marked invalid. | Real click: '
    'geklikt op 1367,444 (venster 1920x889, zichtbaarheid hidden+focus, daar ligt '
    'BUTTON.hz-Button = de knop) | Still on /plaats/728/748?title=, knop "Naar betalen" '
    '| Attribute fields: condition=Zo goed als nieuw, kind=LEEG, brand=LEEG | '
    "Form's own description length: 0 | Photos the form holds: 1 (0 thumbs) | "
    'Free option: knop niet gevonden | Price field: 12,95 | Page says: Help en info '
    'Voorwaarden Veiligheidscentrum Chat Meldingen 18 Papa\'s Plectrums FR Plaats '
    'zoekertje Gekozen categorie Muziek en Instrumenten Gitaren | Elektrisch Wijzigen '
    'Dit is een betalende categorie Gitaren | Elektrisc'
)

GITAREN = "muziek snaarinstrumenten gitaren elektrisch"
KOFFERS = "muziek behuizingen en koffers"


def _oude_module():
    bron = subprocess.run(["git", "show", f"{VOOR_DE_REPARATIE}:backend/api/jobs.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_BETAALDE_RUBRIEK" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


# ── Een database die zich gedraagt als de echte wachtrij van Egbert ────────
class _Vraag:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters = {}
        self.wijziging = None

    def select(self, *_a, **_kw):
        return self

    def update(self, waarden):
        self.wijziging = waarden
        return self

    def eq(self, veld, waarde):
        self.filters[veld] = waarde
        return self

    def in_(self, veld, waarden):
        self.filters[f"in:{veld}"] = list(waarden)
        return self

    def __getattr__(self, _naam):
        def bouw(*_a, **_kw):
            return self
        return bouw

    def execute(self):
        class Antwoord:
            data = []
        if self.tabel == "jobs" and self.wijziging is None:
            Antwoord.data = [j for j in self.db.jobs
                             if j["status"] == self.filters.get("status", j["status"])
                             and j["platform"] == self.filters.get("platform", j["platform"])]
        if self.tabel == "jobs" and self.wijziging is not None:
            for jid in self.filters.get("in:id", []):
                self.db.geannuleerd.append(jid)
        return Antwoord()


class _DB:
    def __init__(self, jobs):
        self.jobs = jobs
        self.geannuleerd = []

    def table(self, naam):
        return _Vraag(self, naam)


def _wachtrij():
    """Zijn echte wachtrij in het klein: gitaren én een rubriek die gratis is."""
    return ([{"id": f"g{i}", "item_id": f"i{i}", "action": "create", "status": "pending",
              "platform": "2dehands", "payload": {"category": GITAREN}} for i in range(5)]
            + [{"id": f"k{i}", "item_id": f"j{i}", "action": "create", "status": "pending",
                "platform": "2dehands", "payload": {"category": KOFFERS}} for i in range(3)])


def _ontwapen(module, monkeypatch, db):
    monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(module, "execute_with_retry",
                        lambda bouwer, *_a, **_kw: bouwer.execute())
    monkeypatch.setattr(module, "fetch_all", lambda *_a, **_kw: [])


def test_de_melding_wordt_herkend_als_betalende_rubriek():
    assert jobs_api._BETAALDE_RUBRIEK.search(ECHTE_FOUT), (
        "de echte foutmelding van Egbert wordt niet herkend")
    # En hij mag NIET als betaalmuur op het hele kanaal gelden: dat zou ook zijn
    # gratis rubrieken dichtzetten.
    assert not jobs_api._BETAALMUUR.search(ECHTE_FOUT)


def test_ook_de_melding_van_de_nieuwe_extensie_wordt_herkend():
    """De extensie stopt vanaf 1.0.317 zelf vóór de klik. Haar melding moet hier
    net zo goed aankomen als de oude, anders werkt de rem alleen op oude kopieen.

    De zin komt letterlijk uit betaalrubriekBezwaar in
    extension/content/shared.js; tests/betalende-rubriek-test.js bewaakt dat hij
    daar ook echt zo staat.
    """
    van_de_extensie = (
        '2dehands (2dehands.be) charges for an advert in this category '
        '(Muziek en Instrumenten Gitaren | Elektrisch): there is no free option left '
        'and the publish button now reads "Naar betalen". Nothing was published and '
        'nothing was ordered — we never click a payment button for you.'
    )
    assert jobs_api._BETAALDE_RUBRIEK.search(van_de_extensie)
    assert not jobs_api._BETAALMUUR.search(van_de_extensie)
    bron = (ROOT / "extension" / "content" / "shared.js").read_text(encoding="utf-8")
    assert "charges for an advert in this category" in bron, (
        "de extensie stuurt een andere zin dan waar de server op wacht")


def test_een_gewone_mislukking_is_geen_betalende_rubriek():
    for onschuldig in [
        "Error: Not published — complete the fields marked in red. | Fields marked invalid: color",
        'Still on /plaats/621/636?title=, knop "Plaats zoekertje"',
        "Uploading the photos took too long",
    ]:
        assert not jobs_api._BETAALDE_RUBRIEK.search(onschuldig), onschuldig


def test_alleen_die_ene_rubriek_wordt_teruggenomen(monkeypatch):
    db = _DB(_wachtrij())
    _ontwapen(jobs_api, monkeypatch, db)
    aantal = jobs_api._stop_wachtrij(db, USER_ID, "2dehands", "reden", rubriek=GITAREN)
    assert aantal == 5, f"{aantal} teruggenomen in plaats van 5"
    assert sorted(db.geannuleerd) == ["g0", "g1", "g2", "g3", "g4"], db.geannuleerd
    assert not [x for x in db.geannuleerd if x.startswith("k")], (
        "de gratis rubriek is óók teruggenomen — precies wat niet mag")


def test_zonder_rubriek_gaat_nog_steeds_het_hele_kanaal_dicht(monkeypatch):
    """De bestaande betaalmuur op het hele kanaal moet ongewijzigd blijven werken."""
    db = _DB(_wachtrij())
    _ontwapen(jobs_api, monkeypatch, db)
    assert jobs_api._stop_wachtrij(db, USER_ID, "2dehands", "reden") == 8


def test_de_melding_legt_uit_dat_de_rest_gewoon_doorgaat():
    tekst = jobs_api._melding_rubriek_vraagt_geld("2dehands", GITAREN)
    assert GITAREN in tekst
    assert "other categories" in tekst, "de verkoper moet lezen dat de rest doorloopt"
    assert "nothing was ordered" in tekst.lower()
    # Niet de tekst van de kanaalbrede betaalmuur: die zegt dat het kanaal uit
    # staat, en dat is hier onjuist.
    assert "does not let your account place adverts for free" not in tekst


def test_de_verkoper_leest_de_naam_die_2dehands_zelf_gebruikt():
    """Onze eigen sleutel leest als een foutcode; het formulier zet zijn eigen
    naam boven aan de pagina, en die staat al in de melding van de extensie."""
    assert jobs_api._rubrieknaam(ECHTE_FOUT, GITAREN) == "Muziek en Instrumenten Gitaren | Elektrisch"
    # Staat hij er niet in, dan onze eigen naam, maar dan wel leesbaar.
    assert jobs_api._rubrieknaam("iets anders", GITAREN) == (
        "Muziek snaarinstrumenten gitaren elektrisch")
    assert jobs_api._rubrieknaam("", None) == ""


def test_deze_mislukking_telt_niet_mee_als_kansloos_kanaal(monkeypatch):
    """Anders zou een verkoper die in één betalende rubriek begint zijn hele
    kanaal dicht zien gaan, terwijl elke gratis rubriek het gewoon doet."""
    class _KansloosDB:
        def table(self, _naam):
            return _KansloosVraag()

    class _KansloosVraag:
        def __getattr__(self, _n):
            return lambda *_a, **_kw: self

        def execute(self):
            class A:
                data = [{"status": "error", "result": {"error": ECHTE_FOUT}}
                        for _ in range(20)]
            return A()

    monkeypatch.setattr(jobs_api, "_kanaal_hard_dicht", lambda *_a, **_kw: False)
    monkeypatch.setattr(jobs_api, "_nooit_gelukt_op", lambda *_a, **_kw: True)
    monkeypatch.setattr(jobs_api, "_kansloze_reeks", lambda *_a, **_kw: False)
    assert jobs_api._kanaal_kansloos(_KansloosDB(), USER_ID, "2dehands") is False


def test_de_vorige_versie_liet_de_hele_rij_doorlopen(monkeypatch):
    """Voor-en-na. Zonder dit weten we alleen dat de nieuwe code werkt."""
    oud = _oude_module()
    assert not hasattr(oud, "_BETAALDE_RUBRIEK")
    # De oude code herkende deze melding niet, dus bleven alle 274 wachtende
    # opdrachten staan om één voor één te mislukken.
    assert not oud._BETAALMUUR.search(ECHTE_FOUT), (
        "de oude betaalmuur ving dit al af — dan verklaart de reparatie niets")
    # En _stop_wachtrij kon er niet gericht op filteren: hij nam alles of niets.
    db = _DB(_wachtrij())
    _ontwapen(oud, monkeypatch, db)
    assert oud._stop_wachtrij(db, USER_ID, "2dehands", "reden") == 8, (
        "de oude versie kon alleen het hele kanaal terugnemen")
    import inspect
    assert "rubriek" not in inspect.signature(oud._stop_wachtrij).parameters
