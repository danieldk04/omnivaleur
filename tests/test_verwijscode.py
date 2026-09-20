"""De persoonlijke verwijslink: wie krijgt welke code, en wat weigeren we.

Een code die stilletjes wordt opgeschoond koppelt een aanmelding aan de
verkeerde persoon, en dan gaat de gratis maand naar iemand anders. Daarom
weigeren we alles wat niet precies klopt in plaats van het te repareren.
"""
import pytest

from tests.test_verwijzing_gratis_maand import NepDb


@pytest.fixture()
def codes(monkeypatch):
    from backend.services import referral_codes as c
    return c


def _db():
    return NepDb(referral_codes=[], referrals=[], referral_clicks=[])


def test_wat_er_geweigerd_wordt(codes):
    assert codes.schoon_code("Daniel") == "daniel"        # hoofdletters mogen
    assert codes.schoon_code("  daniel  ") == "daniel"    # spaties eromheen ook
    assert codes.schoon_code("ab") is None                # te kort
    assert codes.schoon_code("x" * 41) is None            # te lang
    assert codes.schoon_code("daniel@x") is None          # rare tekens
    assert codes.schoon_code("mijn code") is None         # spatie erin
    assert codes.schoon_code("") is None
    assert codes.schoon_code(None) is None
    # Paden op de site: /r/login mag nooit iemands persoonlijke link worden.
    for verboden in ("login", "app", "api", "blog", "nl", "omnivaleur"):
        assert codes.schoon_code(verboden) is None, verboden


def test_eerste_code_is_de_voornaam(codes, monkeypatch):
    db = _db()
    monkeypatch.setattr(codes, "get_db", lambda: db)
    assert codes.zorg_voor_code("u1", "daniel.kuipers@gmail.com") == "daniel"
    rij = db.data["referral_codes"][0]
    assert rij["owner_user_id"] == "u1"
    assert rij["kind"] == "user"
    assert rij["bounty_cents"] == 0, "een klantcode kost een maand, geen geld"


def test_tweede_persoon_met_dezelfde_naam_krijgt_een_eigen_code(codes, monkeypatch):
    db = _db()
    monkeypatch.setattr(codes, "get_db", lambda: db)
    eerste = codes.zorg_voor_code("u1", "daniel@gmail.com")
    tweede = codes.zorg_voor_code("u2", "daniel@hotmail.com")
    assert eerste == "daniel"
    assert tweede != eerste and tweede.startswith("daniel-")


def test_dezelfde_persoon_houdt_zijn_code(codes, monkeypatch):
    db = _db()
    monkeypatch.setattr(codes, "get_db", lambda: db)
    eerste = codes.zorg_voor_code("u1", "daniel@gmail.com")
    assert codes.zorg_voor_code("u1", "daniel@gmail.com") == eerste
    assert len(db.data["referral_codes"]) == 1


def test_eigen_naam_kiezen_laat_de_oude_link_werken(codes, monkeypatch):
    """Een link die al in een appgroep of onder een video staat mag nooit
    doodlopen, dus de oude code blijft actief en blijft van dezelfde persoon."""
    db = _db()
    monkeypatch.setattr(codes, "get_db", lambda: db)
    oud = codes.zorg_voor_code("u1", "daniel@gmail.com")
    nieuw = codes.kies_eigen_code("u1", "DK-Resell")

    assert nieuw == "dk-resell"
    codes_van_u1 = {r["code"] for r in db.data["referral_codes"]}
    assert codes_van_u1 == {oud, nieuw}
    assert all(r["owner_user_id"] == "u1" for r in db.data["referral_codes"])
    # de app toont de nieuwste
    assert codes.codes_van("u1")[0]["code"] == nieuw


def test_bezette_naam_wordt_geweigerd(codes, monkeypatch):
    db = _db()
    monkeypatch.setattr(codes, "get_db", lambda: db)
    codes.zorg_voor_code("u1", "daniel@gmail.com")
    with pytest.raises(ValueError) as fout:
        codes.kies_eigen_code("u2", "daniel")
    assert "taken" in str(fout.value).lower()


def test_onbruikbare_naam_wordt_geweigerd(codes, monkeypatch):
    db = _db()
    monkeypatch.setattr(codes, "get_db", lambda: db)
    with pytest.raises(ValueError):
        codes.kies_eigen_code("u1", "login")
    with pytest.raises(ValueError):
        codes.kies_eigen_code("u1", "a b")
    assert db.data["referral_codes"] == []


def test_een_code_mag_nooit_op_ons_lijken(codes):
    """omnivaleur.com/r/omnivaleur-support leest als een officiële link van ons.
    Dat is precies wat iemand met slechte bedoelingen zou kiezen."""
    for naam in ("omnivaleur-support", "team-revaleur", "crosslist-team",
                 "support-nl", "officialshop", "admin2"):
        assert codes.schoon_code(naam) is None, naam
    assert codes.schoon_code("daniel-resell") == "daniel-resell"


def test_de_algemene_terugval_wordt_nooit_kaal_vergeven(codes, monkeypatch):
    """Uit info@bedrijf.nl valt geen naam te halen. Zou de eerste zo iemand de
    kale link /r/friend krijgen, dan is die voorgoed van hem."""
    db = _db()
    monkeypatch.setattr(codes, "get_db", lambda: db)
    eerste = codes.zorg_voor_code("u1", "info@bedrijf.nl")
    tweede = codes.zorg_voor_code("u2", "admin@winkel.be")
    assert eerste.startswith("friend-") and eerste != "friend"
    assert tweede.startswith("friend-") and tweede != eerste
