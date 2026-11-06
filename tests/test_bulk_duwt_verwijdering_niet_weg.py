"""Een grote bulk mag verkochte artikelen niet online houden (06-11-2026).

Goudlief (5aae4954): 1.786 wachtende Marktplaats-opdrachten. De uitgifte las de
oudste 500, en dat waren 500 plaatsingen van 31-10. Sinds 20-10 lukte er geen enkele
Marktplaats-verwijdering meer, de scan werd na drie dagen afgeblazen, en drie op
Shopify verkochte artikelen stonden nog actief op Marktplaats.

De proef draait de echte functies en laat de versie van vóór de reparatie falen.
"""
from datetime import datetime, timedelta, timezone

import backend.api.jobs as J
from tests.test_2dehands_volgt_de_marktplaats_rubriek import _oude_module

VOOR_DE_REPARATIE = "13cce855"   # vast nummer: HEAD vergelijkt zichzelf na de commit
NU = datetime(2026, 11, 6, 8, 0, tzinfo=timezone.utc)
BULK = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
USER = "gebruiker"


def _rij(jid, actie, gemaakt, gepland=None):
    return {"id": jid, "user_id": USER, "status": "pending", "platform": "marktplaats",
            "action": actie, "item_id": jid, "created_at": gemaakt.isoformat(),
            "scheduled_for": gepland.isoformat() if gepland else None}


class _Vraag:
    """Houdt zich aan order, limit en or_, want daar zat de fout."""

    def __init__(self, rijen):
        self.rijen, self.ofs, self.max = rijen, [], None

    def select(self, *_):
        return self

    def eq(self, k, v):
        self.rijen = [r for r in self.rijen if r[k] == v]
        return self

    def or_(self, filter_):
        self.ofs.append(filter_)
        return self

    def order(self, k):
        self.rijen = sorted(self.rijen, key=lambda r: r[k])
        return self

    def limit(self, n):
        self.max = n
        return self

    @staticmethod
    def _klopt(rij, filter_):
        for deel in filter_.split(","):
            kolom, op, waarde = deel.split(".", 2)
            if op == "neq" and rij[kolom] != waarde:
                return True
            if op == "not" and rij[kolom] is not None:
                return True
        return False

    def execute(self):
        rijen = [r for r in self.rijen if all(self._klopt(r, f) for f in self.ofs)]
        return type("U", (), {"data": rijen[:self.max]})()


class _Db:
    def __init__(self, rijen):
        self.rijen = rijen

    def table(self, _):
        return _Vraag(list(self.rijen))


def _goudlief():
    rij = [_rij(f"p{i:04}", "create", BULK + timedelta(seconds=i)) for i in range(854)]
    rij.append(_rij("verkocht", "delete", datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc)))
    rij.append(_rij("scan", "scan", datetime(2026, 11, 5, 5, 0, tzinfo=timezone.utc)))
    nacht = datetime(2026, 11, 6, 1, 0, tzinfo=timezone.utc)
    rij.append(_rij("herplaats", "delete", nacht))
    rij.append(_rij("herplaats", "create", nacht, gepland=nacht + timedelta(minutes=5)))
    rij[-1]["id"] = "herplaats-c"
    return rij


def _nieuwe_kop(module=J):
    licht = module._lees_wachtrij(_Db(_goudlief()), USER, "marktplaats")
    return licht, [j["id"] for j in module._wachtrij_volgorde(licht, NU)[:module.WACHTRIJ_KOP]]


def test_verkochte_verwijdering_staat_vooraan_in_de_kop():
    _, kop = _nieuwe_kop()
    assert "verkocht" in kop[:2]   # alleen een achterstallige scan mag ervoor


def test_oude_versie_zag_verwijdering_en_scan_niet():
    oud = _oude_module("backend/api/jobs.py", VOOR_DE_REPARATIE, "oude_jobs_bulk",
                       moet_bevatten=("WACHTRIJ_MAX",), moet_missen=("_lees_wachtrij",))
    licht = sorted(_goudlief(), key=lambda r: r["created_at"])[:oud.WACHTRIJ_MAX]
    kop = [j["id"] for j in oud._wachtrij_volgorde(licht, NU)[:oud.WACHTRIJ_KOP]]
    assert {j["action"] for j in licht} == {"create"}
    assert "verkocht" not in kop


def test_oude_volgorde_zette_hem_achter_de_bulk_ook_als_hij_gelezen_was():
    oud = _oude_module("backend/api/jobs.py", VOOR_DE_REPARATIE, "oude_jobs_bulk",
                       moet_bevatten=("WACHTRIJ_MAX",), moet_missen=("_lees_wachtrij",))
    kop = [j["id"] for j in oud._wachtrij_volgorde(_goudlief(), NU)[:oud.WACHTRIJ_KOP]]
    assert "verkocht" not in kop


def test_herplaatsing_blijft_achter_de_plaatsingen():
    """Het paar wordt mee gelezen, dus zijn verwijdering telt niet als losse."""
    licht, kop = _nieuwe_kop()
    assert {"herplaats", "herplaats-c", "scan"} <= {j["id"] for j in licht}
    assert "herplaats" not in kop


def test_een_kort_rijtje_leest_maar_een_keer():
    class Teller(_Db):
        keer = 0

        def table(self, t):
            Teller.keer += 1
            return super().table(t)

    J._lees_wachtrij(Teller([_rij("a", "create", BULK)]), USER, "marktplaats")
    assert Teller.keer == 1
