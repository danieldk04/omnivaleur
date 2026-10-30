"""2dehands: een vast verzendbedrag voor elk artikel, en bieden toestaan op elke
advertentie (30-10-2026, Mieneke van Voordeelsieraden).

Haar prijzen zijn inclusief verzekerde verzending: op Marktplaats staat overal
"Zelf verzenden" voor EUR 0,01 (sinds 29-10), en ze wil hetzelfde op 2dehands, ook
voor wat niet op Marktplaats staat. Ze wil ook dat "Bieden toestaan" op elke
advertentie aan staat, met bieden vanaf 0.

Voor-en-na tegen cd5f3b2d, de laatste versie zonder deze wijziging (een vast
nummer: HEAD vergelijkt zichzelf na de commit).
"""
import asyncio
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VOOR = "cd5f3b2d"


def _laad(pad, naam):
    spec = importlib.util.spec_from_file_location(naam, ROOT / pad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = _laad("tests/test_verzending_2dh_keuze_en_ronde.py", "verzendproef_vast")
I, V, RO, J = T.I, T.V, T.RO, T.J
wereld = T.wereld   # dezelfde nagemaakte wereld (database, Marktplaats, 2dehands)


def _oud(pad, naam, bevat, mist):
    return T.R._oude_module(pad, VOOR, naam, moet_bevatten=bevat, moet_missen=mist)

VAST = {"modus": "vast", "woorden": [], "brief_onder": 0, "vast_cents": 1}
ZELF1 = {"soort": "zelf", "cents": 1}


# ── de instelling ────────────────────────────────────────────────────────────
def test_het_bedrag_wordt_bewaard_en_begrensd():
    s = I._schoon({I.VERZENDING_2DH_MODUS: "vast", I.VERZENDING_2DH_VAST: 1})
    assert s[I.VERZENDING_2DH_MODUS] == "vast" and s[I.VERZENDING_2DH_VAST] == 1
    assert I._schoon({I.VERZENDING_2DH_MODUS: "vast", I.VERZENDING_2DH_VAST: 0})[I.VERZENDING_2DH_VAST] == 1
    assert I._schoon({I.VERZENDING_2DH_MODUS: "vast", I.VERZENDING_2DH_VAST: 10**9})[
        I.VERZENDING_2DH_VAST] == I.VERZENDING_2DH_VAST_MAX
    assert I._schoon({I.VERZENDING_2DH_VAST: "abc"})[I.VERZENDING_2DH_VAST] is None
    assert I._schoon({})[I.VERZENDING_2DH_VAST] is None


def test_vast_zonder_bedrag_bestaat_niet():
    """Anders werd elke plaatsing stil Bpost terwijl de verkoper 'vast' koos."""
    for rommel in (None, "", "abc"):
        s = I._schoon({I.VERZENDING_2DH_MODUS: "vast", I.VERZENDING_2DH_VAST: rommel})
        assert s[I.VERZENDING_2DH_MODUS] == "standaard", rommel
    assert I._schoon({I.VERZENDING_2DH_MODUS: "vast"})[I.VERZENDING_2DH_MODUS] == "standaard"


def test_andere_keuzes_blijven_zoals_ze_waren():
    for modus in ("standaard", "regel", "alles"):
        assert I._schoon({I.VERZENDING_2DH_MODUS: modus})[I.VERZENDING_2DH_MODUS] == modus
    assert I._schoon({I.VERZENDING_2DH_WOORDEN: ["patch"]})[I.VERZENDING_2DH_MODUS] == "regel"


def test_de_regel_draagt_het_bedrag(monkeypatch):
    class DB:
        def table(self, _t):
            return self

        def __getattr__(self, _n):
            return lambda *_a, **_k: self

        def execute(self):
            return type("R", (), {"data": [{"extra_data": {
                I.VERZENDING_2DH_MODUS: "vast", I.VERZENDING_2DH_VAST: 1}}]})()
    regel = I.verzending_2dh_regel("u", DB())
    assert regel["modus"] == "vast" and regel["vast_cents"] == 1
    assert I.vast_bedrag(regel) == 1


@pytest.mark.parametrize("regel,verwacht", [
    ({"modus": "vast", "vast_cents": 1}, 1),
    ({"modus": "vast", "vast_cents": 295}, 295),
    ({"modus": "vast", "vast_cents": None}, None),
    ({"modus": "vast", "vast_cents": 0}, None),
    ({"modus": "alles", "vast_cents": 1}, None),       # een bewaard bedrag geldt alleen bij 'vast'
    ({"modus": "standaard", "vast_cents": 1}, None),
    ({"modus": "regel", "vast_cents": 1}, None),
])
def test_vast_bedrag(regel, verwacht):
    assert I.vast_bedrag(regel) == verwacht


# ── de beslissing ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("eigen,titel,mp,verwacht", [
    (None, "Gouden ring", None, ZELF1),                               # niet op Marktplaats of storing
    (None, "Gouden ring", {"soort": "platform"}, ZELF1),              # verzendt via PostNL op Marktplaats
    (None, "Gouden ring", {"soort": "zelf", "cents": 695}, ZELF1),    # het vaste bedrag wint
    (T.V.BPOST, "Gouden ring", None, V.STANDAARD),                    # eigen keuze per artikel gaat voor
    (300, "Gouden ring", None, {"soort": "zelf", "cents": 300}),
])
def test_doel_bij_vast(eigen, titel, mp, verwacht):
    assert V.doel(VAST, eigen, titel, mp) == verwacht


def test_vast_vraagt_marktplaats_niets():
    assert I.heeft_marktplaats_nodig(VAST, "Gouden ring") is False


def test_oude_code_kende_vast_niet():
    oud = _oud("backend/services/instellingen.py", "oude_instellingen_vast",
                 ("verzending_2dh_modus",), ("vast_bedrag",))
    assert "vast" not in oud.VERZENDING_2DH_MODI
    assert oud._schoon({"verzending_2dh_modus": "vast", "verzending_2dh_vast_cents": 1})[
        "verzending_2dh_modus"] == "standaard", "vroeger: Bpost, het bedrag werd genegeerd"


# ── de uitgifte van een nieuw zoekertje ──────────────────────────────────────
def test_nieuw_zoekertje_krijgt_het_vaste_bedrag_zonder_marktplaats(monkeypatch):
    nu, vragen = T._uitgifte(monkeypatch, "Gouden ring", None, VAST, op_mp=False)
    assert nu == ZELF1
    assert vragen == [], "Marktplaats hoeft niet gevraagd"


def test_ook_als_marktplaats_iets_anders_toont(monkeypatch):
    nu, vragen = T._uitgifte(monkeypatch, "Gouden ring", {"soort": "zelf", "cents": 695}, VAST)
    assert nu == ZELF1 and vragen == []


def test_een_storing_bij_marktplaats_maakt_er_geen_bpost_van(monkeypatch):
    nu, vragen = T._uitgifte(monkeypatch, "Gouden ring", None, VAST)
    assert nu == ZELF1 and vragen == []


def test_eigen_keuze_per_artikel_gaat_voor_het_vaste_bedrag(monkeypatch):
    nu, _ = T._uitgifte(monkeypatch, "Gouden ring", None, VAST, eigen="bpost", op_mp=False)
    assert nu == {"soort": "standaard"}
    nu, _ = T._uitgifte(monkeypatch, "Gouden ring", None, VAST, eigen=250, op_mp=False)
    assert nu == {"soort": "zelf", "cents": 250}


def test_eigen_keuzes_niet_te_lezen_legt_niets_vast(monkeypatch):
    nu, _ = T._uitgifte(monkeypatch, "Gouden ring", None, VAST, eigen_fout=True, op_mp=False)
    assert nu is None, "een storing is geen antwoord"


def test_oude_uitgifte_gaf_bpost(monkeypatch):
    """VOOR: met dezelfde instelling (vast 1 cent) werd het Bpost 7,10."""
    oud = _oud("backend/api/jobs.py", "oude_jobs_vast",
                 ("verzending_2dh_regel",), ("vast_bedrag",))
    nu, _ = T._uitgifte(monkeypatch, "Gouden ring", None, VAST, op_mp=False, module=oud)
    assert nu != ZELF1, "de oude code legde het vaste bedrag niet vast"


# ── de ronde over wat al online staat ────────────────────────────────────────
def test_ronde_zet_elk_zoekertje_op_het_vaste_bedrag(wereld, monkeypatch):
    monkeypatch.setattr(I, "verzending_2dh_regel", lambda user_id, db=None: dict(VAST))
    w, u = wereld, "mieneke"
    w.artikel(u, "a", "Gouden ring", {"soort": "zelf", "cents": 695}, dh={"soort": "platform"})
    w.artikel(u, "b", "Zilveren ketting", dh={"soort": "platform"}, mp_nummer=False)
    w.artikel(u, "c", "Oorbellen", {"soort": "platform"}, dh={"soort": "zelf", "cents": 1})
    w.artikel(u, "d", "Armband", dh={"soort": "geen"}, mp_nummer=False)
    RO.start(u, db=w)
    T._draai(w)
    nieuw = {j["item_id"]: j["payload"]["verzending"] for j in w.jobs if "payload" in j}
    assert nieuw == {"a": ZELF1, "b": ZELF1}
    assert w.mp_vragen == [], "bij een vast bedrag hoeft Marktplaats niet gelezen"
    st = T._stand(w, u)
    assert st["status"] == "klaar" and st["tel"]["al_goed"] == 1 and st["tel"]["ophalen"] == 1


def test_een_ander_bedrag_stopt_de_oude_ronde(wereld, monkeypatch):
    w, u = wereld, "mieneke"
    w.artikel(u, "a", "Gouden ring", dh={"soort": "platform"}, mp_nummer=False)
    monkeypatch.setattr(I, "verzending_2dh_regel", lambda user_id, db=None: dict(VAST))
    RO.start(u, db=w)
    anders = {**VAST, "vast_cents": 295}
    assert RO.stop_als_verouderd(u, anders, w) is True


# ── bieden toestaan, vanuit de instellingen naar de opdracht ─────────────────
def _lees_als(monkeypatch, inst):
    monkeypatch.setattr(I, "lees", lambda user_id: I._schoon(inst))


def test_bieden_standaard_gaat_alleen_mee_als_gekozen(monkeypatch):
    _lees_als(monkeypatch, {})
    assert I.BIEDEN_STANDAARD not in I.verzendkeuzes("u", 100)
    _lees_als(monkeypatch, {I.BIEDEN_STANDAARD: "volg"})
    assert I.BIEDEN_STANDAARD not in I.verzendkeuzes("u", 100)
    _lees_als(monkeypatch, {I.BIEDEN_STANDAARD: "aan"})
    assert I.verzendkeuzes("u", 100)[I.BIEDEN_STANDAARD] == "aan"


def test_bieden_standaard_vangt_rommel_op():
    assert I._schoon({})[I.BIEDEN_STANDAARD] == "volg"
    assert I._schoon({I.BIEDEN_STANDAARD: "iets"})[I.BIEDEN_STANDAARD] == "volg"
    assert I._schoon({I.BIEDEN_STANDAARD: "aan"})[I.BIEDEN_STANDAARD] == "aan"


def test_andere_verzendkeuzes_blijven_ongemoeid(monkeypatch):
    _lees_als(monkeypatch, {I.BIEDEN_STANDAARD: "aan", "levering": "verzenden", "pakket_grens": 50,
                            I.MP_ZELF_VERZENDEN: 1})
    uit = I.verzendkeuzes("u", 10)
    assert uit["levering"] == "verzenden" and uit["pakket"] == I.PAKKET_KLEIN
    assert uit[I.MP_ZELF_VERZENDEN] == 1 and uit[I.BIEDEN_STANDAARD] == "aan"


def test_de_instellingen_api_geeft_beide_terug():
    s = I._schoon({I.BIEDEN_STANDAARD: "aan", I.VERZENDING_2DH_MODUS: "vast",
                   I.VERZENDING_2DH_VAST: 1})
    assert (s["bieden_standaard"], s["verzending_2dh_modus"], s["verzending_2dh_vast_cents"]) == ("aan", "vast", 1)
