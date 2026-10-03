"""Plaatsingen die op hun rubriek wachten mogen de kop van de rij niet vullen (03-10-2026).

Egbert Brouwer (bcdf9aa4), 09:30 UTC. Chrome stond aan, maar sinds 08:48 ging er
niets meer uit: 107 plaatsingen en 935 verzendkost-bijwerkingen op 2dehands. De
oudste 25 plaatsingen wachtten op hun Marktplaats-rubriek; de opzoeking vanaf de
server faalde elke drie minuten opnieuw. De uitgifte leest maar de kop van de rij
(WACHTRIJ_KOP = 25) volledig in, en die kop bestond precies uit die 25. Elke
poll werden ze alle vijf bekeken, alle vijf teruggehouden, en kwam er niets uit.

Elke proef draait de echte functies en laat eerst de versie van vóór deze
reparatie falen op dezelfde gegevens.
"""
from datetime import datetime, timedelta, timezone

import backend.api.jobs as J
from tests.test_2dehands_verzendkosten_bijwerken import (
    _bijwerking, _db, _plaatsing_in_de_rij, _tijd, _uitgifte)
from tests.test_2dehands_volgt_de_marktplaats_rubriek import _oude_module

VOOR_DE_REPARATIE = "744ee9fe"   # vast nummer: HEAD vergelijkt zichzelf na de commit


def _oude_jobs():
    return _oude_module("backend/api/jobs.py", VOOR_DE_REPARATIE, "oude_jobs_rubriekkop",
                        moet_bevatten=("_is_2dh_bijwerking",),
                        moet_missen=("_LICHTE_VELDEN",))


NU = datetime(2026, 10, 3, 9, 30, tzinfo=timezone.utc)


def _licht(jid, actie, gemaakt, rubriek_sinds=None):
    return {"id": jid, "action": actie, "platform": "2dehands", "item_id": jid,
            "created_at": gemaakt.isoformat(), "scheduled_for": None,
            "rubriek_sinds": rubriek_sinds.isoformat() if rubriek_sinds else None}


def _egbert_om_half_tien():
    """Zo stond zijn 2dehands-rij er gemeten bij: bijwerkingen van 30-09, daarna
    25 wachtende patches van 08:29 en 82 nieuwe van 08:30-08:44."""
    dertig = datetime(2026, 9, 30, 9, 45, tzinfo=timezone.utc)
    rij = [_licht(f"b{i:03}", "content_refresh", dertig + timedelta(seconds=40 * i))
           for i in range(300)]
    wacht = datetime(2026, 10, 3, 8, 29, tzinfo=timezone.utc)
    rij += [_licht(f"w{i:02}", "create", wacht + timedelta(seconds=i),
                   rubriek_sinds=datetime(2026, 10, 3, 8, 36, 51, tzinfo=timezone.utc))
            for i in range(25)]
    vers = datetime(2026, 10, 3, 8, 30, tzinfo=timezone.utc)
    rij += [_licht(f"p{i:02}", "create", vers + timedelta(seconds=10 * i)) for i in range(82)]
    return rij


def test_de_kop_bestaat_niet_meer_alleen_uit_wachters():
    rij = _egbert_om_half_tien()
    kop = J._wachtrij_volgorde(rij, NU)[:J.WACHTRIJ_KOP]
    assert all(j["id"].startswith("p") for j in kop), [j["id"] for j in kop]
    oud = _oude_jobs()._wachtrij_volgorde(rij, NU)[:J.WACHTRIJ_KOP]
    assert all(j["id"].startswith("w") for j in oud), "zo stond het live om 09:30"


def test_staan_er_alleen_nog_wachters_en_bijwerkingen_dan_gaan_de_bijwerkingen():
    rij = [r for r in _egbert_om_half_tien() if not r["id"].startswith("p")]
    kop = J._wachtrij_volgorde(rij, NU)[:J.WACHTRIJ_KOP]
    assert all(j["action"] == "content_refresh" for j in kop)


def test_ook_oudere_wachters_gaan_achter_jongere_bijwerkingen_en_scans():
    wacht = NU - timedelta(hours=1)
    rij = [_licht(f"w{i:02}", "create", wacht + timedelta(seconds=i), rubriek_sinds=wacht)
           for i in range(25)]
    rij += [_licht("b-jong", "content_refresh", NU - timedelta(minutes=5)),
            _licht("scan", "scan", NU - timedelta(minutes=2))]
    kop = J._wachtrij_volgorde(rij, NU)[:J.WACHTRIJ_KOP]
    assert [j["id"] for j in kop[:2]] == ["b-jong", "scan"]


def test_wachters_komen_weer_aan_de_beurt_als_de_rij_voor_hen_leeg_is():
    rij = [r for r in _egbert_om_half_tien() if r["id"].startswith("w")]
    assert len(J._wachtrij_volgorde(rij, NU)[:J.WACHTRIJ_KOP]) == 25


def test_na_zes_uur_wachten_telt_een_plaatsing_weer_als_gewoon_werk():
    lang = _licht("w-lang", "create", NU - timedelta(hours=7),
                  rubriek_sinds=NU - timedelta(hours=7))
    bijwerking = _licht("b", "content_refresh", NU - timedelta(days=3))
    assert [j["id"] for j in J._wachtrij_volgorde([bijwerking, lang], NU)] == ["w-lang", "b"]


def test_de_uitgifte_geeft_weer_werk_als_de_rubriek_niet_op_te_vragen_is(monkeypatch):
    """Door de echte get_pending_jobs. De rubriekopzoeking faalt, zoals op de server."""
    def rij():
        wachters = [{**_plaatsing_in_de_rij(f"w{i:02}", minuten=60 - i),
                     "rubriek_sinds": _tijd(55)} for i in range(25)]
        for w in wachters:
            w["payload"] = {**w["payload"], "_rubriek_zoeken_sinds": _tijd(55)}
        verse = [{**_plaatsing_in_de_rij(f"p{i:02}", minuten=30 - i), "rubriek_sinds": None}
                 for i in range(10)]
        return wachters + verse + [_bijwerking("b1")]

    def houd_wachters_vast(db, user_id, job):
        return not job["payload"].get("_rubriek_zoeken_sinds")

    oude = _oude_jobs()
    for module in (J, oude):
        monkeypatch.setattr(module, "_zet_rubriek_van_marktplaats", houd_wachters_vast)
        monkeypatch.setattr(module, "_stuur_naar_eigenaar", lambda *a: None, raising=False)
    nu = _uitgifte(monkeypatch, _db(rij()), "1.0.364")
    assert [j["id"] for j in nu] == ["p00"]
    oud = _uitgifte(monkeypatch, _db(rij()), "1.0.364", module=oude)
    assert oud == [], "zo kreeg zijn extensie een uur lang niets"


# ── Eén onvindbare rubriek vooraan hield de hele rij tegen (03-10-2026, 15:44 UTC) ──
# Egbert: 25 plaatsingen van 15:05 wachtten nog steeds terwijl zijn extensie online
# was. De oudste had 13 mislukte opzoekingen (13 x 3 minuten = 39 minuten); de
# andere 24 waren nooit geprobeerd. Lokaal gedraaid vonden twee van de drie hun
# rubriek wel.
VOOR_DEZE_REPARATIE = "c2157f7b"


def _oude_jobs_poison():
    return _oude_module("backend/api/jobs.py", VOOR_DEZE_REPARATIE, "oude_jobs_poison",
                        moet_bevatten=("_is_2dh_bijwerking",),
                        moet_missen=("_rubriek_mislukt",))


def test_een_onvindbare_rubriek_vooraan_houdt_de_rest_niet_meer_tegen(monkeypatch):
    def rij():
        wachters = []
        for i in range(25):
            w = {**_plaatsing_in_de_rij(f"w{i:02}", minuten=40 - i),
                 "rubriek_sinds": _tijd(35),
                 "rubriek_pogingen": "13" if i == 0 else None}
            w["payload"] = {**w["payload"], "_rubriek_zoeken_sinds": _tijd(35),
                            **({"_rubriek_pogingen": 13, "_onvindbaar": True} if i == 0 else {})}
            wachters.append(w)
        return wachters

    def maak_fake():
        rust = {"aan": False}

        def fake(db, user_id, job):
            # Dezelfde regels als _zet_rubriek_van_marktplaats: een mislukking zet de
            # rust aan voor de hele gebruiker, een succes haalt hem weg.
            if job["payload"].get("_onvindbaar"):
                rust["aan"] = True
                return False
            if rust["aan"]:
                return False
            job["payload"] = {k: v for k, v in job["payload"].items()
                              if k != "_rubriek_zoeken_sinds"}
            return True
        return fake

    oude = _oude_jobs_poison()
    for module in (J, oude):
        monkeypatch.setattr(module, "_zet_rubriek_van_marktplaats", maak_fake())
        monkeypatch.setattr(module, "_stuur_naar_eigenaar", lambda *a: None, raising=False)
    nu = _uitgifte(monkeypatch, _db(rij()), "1.0.364")
    assert nu and nu[0]["id"] != "w00", [j["id"] for j in nu]
    oud = _uitgifte(monkeypatch, _db(rij()), "1.0.364", module=oude)
    assert oud == [], "zo kreeg zijn extensie 38 minuten niets"


def test_wie_het_meest_mislukte_staat_achteraan_bij_de_wachters():
    wacht = NU - timedelta(hours=1)
    rij = [{**_licht("oud", "create", wacht, rubriek_sinds=wacht), "rubriek_pogingen": "13"},
           _licht("nieuw", "create", wacht + timedelta(minutes=1), rubriek_sinds=wacht)]
    assert [j["id"] for j in J._wachtrij_volgorde(rij, NU)] == ["nieuw", "oud"]
