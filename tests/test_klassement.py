"""Rekenregels van het klassement, de niveaus en de Founding Circle
(services/klassement.py). Zuivere rekenfuncties, dus met rijen te bewijzen."""
from datetime import datetime, timedelta, timezone

from backend.services import klassement as k

NU = datetime(2026, 12, 20, 12, 0, tzinfo=timezone.utc)


def _vriend(uid, dagen_geleden, plan="pro", status="active", code="anna"):
    eerste = NU - timedelta(days=dagen_geleden)
    verw = {"user_id": uid, "code": code, "first_paid_at": eerste.isoformat()}
    abo = {"status": status, "plan": plan, "stripe_subscription_id": "sub_" + uid}
    return verw, abo


def _stel(vrienden, namen=None, eigenaar=None):
    verw, abos = [], {}
    for v, a in vrienden:
        verw.append(v)
        abos[v["user_id"]] = a
    return k.bereken(verw, eigenaar or {"anna": "A", "bob": "B"}, abos, namen or {}, NU)


def test_niveaus_en_volgend():
    assert [k.niveau(n) for n in (0, 1, 2, 3, 4, 5, 9, 10, 40)] == [
        None, "bronze", "bronze", "silver", "silver", "gold", "gold", "platinum", "platinum"]
    assert k.volgend_niveau(0) == ("bronze", 1)
    assert k.volgend_niveau(4) == ("gold", 1)
    assert k.volgend_niveau(10) is None


def test_light_en_creatorcode_en_eigen_account_tellen_niet():
    u = _stel([
        _vriend("f1", 40, plan="light"),
        _vriend("f2", 40, code="creator"),          # code zonder klant als eigenaar
        _vriend("A", 40),                           # eigen code zelf gebruikt
        _vriend("f3", 40, status="canceled"),
        _vriend("f4", 40, plan=None),
    ])
    assert u["per_user"] == {}


def test_vriend_telt_pas_na_30_dagen_voor_de_maand():
    # f1 betaalt 29 dagen: nog niet rijp. f2 betaalt 31 dagen: de 30 dagen werden
    # vol op 19-12, dus telt hij in december. f3 betaalt 60 dagen: rijp sinds
    # 20-11, dus telt in november en niet meer in december.
    u = _stel([_vriend("f1", 29), _vriend("f2", 31), _vriend("f3", 60)], namen={"A": "anna"})
    assert u["per_user"]["A"]["telt"] == 3          # alle betalende vrienden voor het niveau
    assert u["per_user"]["A"]["maand_telt"] == 1    # alleen f2 voor het bord van december
    assert [r["count"] for r in u["board"]] == [1]


def test_bord_alleen_met_naam_en_gerangschikt():
    # Anna: drie vrienden van 30 dagen die in december rijp werden. Bob: een.
    a = [_vriend("a1", 30), _vriend("a2", 32), _vriend("a3", 31)]
    b = [_vriend("b1", 30 + 1, code="bob")]
    u = _stel(a + b, namen={"A": "anna", "B": "bob"})
    assert [r["name"] for r in u["board"]] == ["anna", "bob"]
    assert u["board"][0]["count"] == 3 and u["board"][0]["qualifies"] is True
    assert u["board"][1]["count"] == 1 and u["board"][1]["qualifies"] is False
    assert [r["rank"] for r in u["board"]] == [1, 2]
    # zonder naam onzichtbaar
    z = _stel(a + b, namen={"A": "anna"})
    assert [r["name"] for r in z["board"]] == ["anna"]


def test_founding_circle_eerste_tien_op_datum_vijfde_vriend():
    # Twaalf klanten, elk met vijf betalende vrienden; klant n haalde de vijfde vriend later.
    codes, vr = {}, []
    for n in range(12):
        code = f"c{n}"
        codes[code] = f"U{n}"
        for j in range(5):
            vr.append(_vriend(f"v{n}_{j}", 100 - n, code=code))
    u = _stel(vr, eigenaar=codes)
    leden = sorted(uid for uid, p in u["per_user"].items() if p["founding"])
    # klant 0 betaalde het vroegst (100 dagen geleden), klant 11 het laatst: 10 plekken
    assert len(leden) == 10
    assert "U0" in leden and "U9" in leden and "U10" not in leden and "U11" not in leden
    assert u["founding_taken"] == 10


def test_voor_gebruiker_geeft_nooit_user_ids_en_toont_eigen_plek():
    a = [_vriend("a1", 31), _vriend("a2", 32), _vriend("a3", 33)]
    u = _stel(a, namen={"A": "anna"})
    uit = k.voor_gebruiker(u, "A", "anna")
    assert "user_id" not in str(uit["board"])
    assert uit["board"][0]["me"] is True
    assert uit["me"]["rank"] == 1 and uit["me"]["level"] == "silver"
    assert uit["me"]["next_level"] == {"level": "gold", "to_go": 2}
    leeg = k.voor_gebruiker(u, "ZZZ", None)
    assert leeg["me"]["joined"] is False and leeg["me"]["level"] is None


def test_klassementsnaam_in_instellingen_volgt_codeopmaak():
    from backend.services.instellingen import KLASSEMENT_NAAM, _schoon
    assert _schoon({KLASSEMENT_NAAM: " Anna "})[KLASSEMENT_NAAM] == "anna"
    assert _schoon({KLASSEMENT_NAAM: "omnivaleur-support"})[KLASSEMENT_NAAM] is None
    assert _schoon({KLASSEMENT_NAAM: "api"})[KLASSEMENT_NAAM] is None
    assert _schoon({})[KLASSEMENT_NAAM] is None
    # leegmaken kan: None blijft None
    assert _schoon({KLASSEMENT_NAAM: None})[KLASSEMENT_NAAM] is None
