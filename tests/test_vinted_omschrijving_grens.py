"""Vinted weigert een omschrijving boven de 2000 tekens.

GEMETEN 17-09-2026, Johan Kist: "Gebruik niet meer dan 2000 tekens voor je
beschrijving". 11 van zijn 24 omschrijvingen komen van Marktplaats en zijn langer,
tot 4219 tekens. De opdracht gaat nu ingekort de deur uit (zie
_vinted_tekst_binnen_grens in backend/api/jobs.py); het artikel zelf blijft heel.
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as J  # noqa: E402

GRENS = J.VINTED_MAX_OMSCHRIJVING


def _lang(zinnen=60):
    alinea = " ".join(f"Dit is zin {i} over de klank en de staat van deze gitaar." for i in range(12))
    return "\n\n".join(alinea for _ in range(zinnen // 12 + 1))


def test_korte_tekst_blijft_precies_gelijk():
    t = "Mooie gitaar.\n\nOphalen in Fochteloo."
    assert J.vinted_omschrijving(t) is t


def test_lange_tekst_past_en_is_netjes_afgebroken():
    t = _lang(120)
    assert J._vinted_lengte(t) > GRENS
    kort = J.vinted_omschrijving(t)
    assert J._vinted_lengte(kort) <= GRENS
    assert t.startswith(kort)                           # niets herschreven, alleen ingekort
    assert kort.endswith(".")                           # op een zin of alinea, niet midden in een woord
    assert J._vinted_lengte(kort) > GRENS * 0.7         # en niet onnodig veel weg


def test_regeleinde_en_emoji_tellen_zoals_het_formulier():
    t = ("🎸 a\n" * 500)
    kort = J.vinted_omschrijving(t)
    assert len(kort.encode("utf-16-le")) // 2 + kort.count("\n") <= GRENS


def test_slottekst_van_de_verkoper_blijft_staan():
    slot = "Blackbird Guitars, Stienekamp 16, Fochteloo. Bezichtigen op afspraak."
    t = _lang(120) + "\n\n" + slot
    kort = J.vinted_omschrijving(t, slot)
    assert kort.endswith(slot)
    assert J._vinted_lengte(kort) <= GRENS


def test_html_wordt_eerst_platte_tekst():
    t = "<p>Mooie gitaar</p>" * 150                      # 2700 tekens ruw, 2100 tekens plat
    kort = J.vinted_omschrijving(t)
    assert "<" not in kort and J._vinted_lengte(kort) <= GRENS


class _DB:
    def __init__(self):
        self.updates = []

    def table(self, _naam):
        db = self

        class Q:
            def update(self, velden):
                self.velden = velden; return self

            def eq(self, _k, v):
                db.updates.append((v, self.velden)); return self

            def execute(self):
                return types.SimpleNamespace(data=[])
        return Q()


def test_alleen_vinted_opdrachten_worden_ingekort_en_opgeslagen(monkeypatch):
    import backend.services.crosslist as C
    monkeypatch.setattr(C, "slottekst_van", lambda _u: "")
    lang = _lang(120)
    jobs = [{"id": "v", "platform": "vinted", "action": "create", "user_id": "u", "payload": {"description": lang}},
            {"id": "m", "platform": "marktplaats", "action": "create", "user_id": "u", "payload": {"description": lang}}]
    db = _DB()
    assert J._vinted_tekst_binnen_grens(db, jobs) == 1
    assert J._vinted_lengte(jobs[0]["payload"]["description"]) <= GRENS
    assert jobs[1]["payload"]["description"] == lang
    assert [u[0] for u in db.updates] == ["v"]
