"""Een kanaal op inlogpauze krijgt geen werk, langs welke weg dan ook.

WAT ER GEBEURDE (11-11-2026, De Juiste Toon). Toon zette 's avonds op een
Windows-computer 29 artikelen klaar. Daar was hij niet ingelogd op 2dehands. De
extensie meldde dat netjes, de server zette 2dehands op pauze, en toch kreeg de
extensie het zoekertje 245 keer opnieuw: na elke Marktplaats-opdracht gaf de
server "de beurt" door aan 2dehands, langs de pauze heen. Elke keer pakken,
"niet ingelogd", terug in de rij. De pauze op Marktplaats ging zelfs helemaal
nooit in: drie oude geannuleerde rijen zonder done_at stonden bij aflopend
sorteren vooraan (Postgres zet NULL voorop) en het pauzestempel viel buiten de
drie die gelezen werden. En de melding die hij kreeg zei "u was de hele tijd
ingelogd, dit ligt aan ons", terwijl zijn extensie (1.0.420) de kopbalk van
2dehands zelf had gelezen en die "uitgelogd" zei.

Deze proeven draaien de echte code; elk faalt op de versie van vóór 12-11-2026.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import backend.api.jobs as J  # noqa: E402
from test_kanalen_om_de_beurt import _bouw_db, _lynn_wachtrij, _uitgifte  # noqa: E402

NU = datetime.now(timezone.utc)
VERWIJT = (
    "You are not signed in to 2dehands (2dehands.be) in this browser, so nothing was "
    "published. We checked twice: once in the background and once in a tab on "
    "2dehands (2dehands.be) itself, and the site refused both times (HTTP 401)."
)


def test_een_kanaal_op_inlogpauze_krijgt_ook_via_de_beurt_geen_werk(monkeypatch):
    """Toons avond: Marktplaats deed de vorige, 2dehands staat op pauze."""
    db = _bouw_db(_lynn_wachtrij(), laatst_bediend="marktplaats")
    monkeypatch.setattr(J, "_inlog_pauze_actief",
                        lambda _db, _u, platform, _nu: platform == "2dehands")
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit, "Marktplaats heeft zelf werk en moet gewoon doorgaan"
    assert all(j["platform"] == "marktplaats" for j in uit), (
        f"2dehands staat op inlogpauze en mag niets krijgen; gekregen: "
        f"{[(j['platform'], j['id']) for j in uit]}")


def test_zonder_pauze_blijft_de_beurt_gewoon_bestaan(monkeypatch):
    """De reparatie mag het om-de-beurt-delen niet slopen."""
    db = _bouw_db(_lynn_wachtrij(), laatst_bediend="marktplaats")
    monkeypatch.setattr(J, "_inlog_pauze_actief", lambda *a: False)
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit and uit[0]["platform"] == "2dehands"


class _PostgresVraag:
    """Sorteert zoals Postgres: bij aflopend sorteren staat NULL vooraan."""

    def __init__(self, rijen):
        self.rijen, self.zonder_null, self.max = rijen, None, None

    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def order(self, *a, **k): return self

    @property
    def not_(self):
        buiten = self

        class _Niet:
            def is_(self, kolom, _w):
                buiten.zonder_null = kolom
                return buiten
        return _Niet()

    def limit(self, n):
        self.max = n
        return self

    def execute(self):
        rijen = [r for r in self.rijen
                 if not (self.zonder_null and r.get(self.zonder_null) is None)]
        rijen.sort(key=lambda r: (r["done_at"] is not None, r["done_at"] or ""), reverse=False)
        leeg = [r for r in rijen if r["done_at"] is None]
        gevuld = sorted([r for r in rijen if r["done_at"] is not None],
                        key=lambda r: r["done_at"], reverse=True)
        return type("R", (), {"data": (leeg + gevuld)[: self.max]})()


def test_de_pauze_ziet_het_stempel_achter_oude_rijen_zonder_done_at():
    """Toons Marktplaats-rij: drie 'item sold elsewhere' zonder done_at, dan het stempel."""
    rijen = [{"done_at": None, "result": {"cancelled": "item sold elsewhere"}} for _ in range(3)]
    rijen.append({"done_at": (NU - timedelta(minutes=2)).isoformat(),
                  "result": {"cancelled": J._PAUZE_STEMPEL}})
    db = type("Db", (), {"table": lambda self, _n: _PostgresVraag(rijen)})()
    assert J._inlog_pauze_actief(db, "u1", "marktplaats", NU), (
        "het pauzestempel van twee minuten geleden moet gezien worden")


def test_een_verwijt_na_de_kopbalkmeting_wordt_geen_zakelijk_excuus(monkeypatch):
    """1.0.420 las de kopbalk: 'uitgelogd' is dan waar, ook voor een zakelijke verkoper."""
    monkeypatch.setattr(J, "get_db", lambda: object())
    monkeypatch.setattr(J, "_verkoper_soort", lambda *a: "TRADER")
    monkeypatch.setattr(J, "_reden_zonder_vals_verwijt", lambda _d, _u, _p, r, *a: r)
    gekregen = {}
    monkeypatch.setattr(J, "_pauzeer_op_inlogverwijt",
                        lambda _d, _u, _p, reden: gekregen.setdefault("reden", reden) and 0)
    verzoek = type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.420"}})()
    uit = J.stop_platform({"platform": "2dehands", "reason": VERWIJT}, verzoek, "u1")
    assert not uit.get("zakelijk"), uit
    assert "business account" not in gekregen["reden"], gekregen["reden"]
    assert "not signed in" in gekregen["reden"]


def test_een_oude_kopie_zonder_kopbalkmeting_krijgt_nog_wel_het_zakelijk_excuus(monkeypatch):
    """Vóór 1.0.332 kon de extensie zakelijk niet van uitgelogd onderscheiden."""
    monkeypatch.setattr(J, "get_db", lambda: object())
    monkeypatch.setattr(J, "_verkoper_soort", lambda *a: "TRADER")
    monkeypatch.setattr(J, "_pauzeer_op_inlogverwijt", lambda *a: 0)
    verzoek = type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.327"}})()
    uit = J.stop_platform({"platform": "2dehands", "reason": VERWIJT}, verzoek, "u1")
    assert uit.get("zakelijk") is True


def test_de_foutmelding_van_een_nieuwe_kopie_blijft_de_inlogmelding():
    """Het /error-pad: dezelfde grens, afgelezen aan het versiestempel in de tekst."""
    nieuw = VERWIJT + " [extensie 1.0.420]"
    oud = VERWIJT + " [extensie 1.0.327]"
    assert J._kopbalk_heeft_gesproken(J._extensie_versie(nieuw), nieuw)
    assert not J._kopbalk_heeft_gesproken(J._extensie_versie(oud), oud)
    assert not J._kopbalk_heeft_gesproken(None, VERWIJT)
    assert not J._kopbalk_heeft_gesproken((1, 0, 420), "Timeout: input[name=title]")
