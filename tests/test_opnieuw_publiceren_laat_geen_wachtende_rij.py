"""Opnieuw publiceren laat de oude rij niet eeuwig op 'pending' staan.

WAAROM DIT ER IS (01-10-2026, Vagif). Twee ringen stonden eerder op 2dehands,
de advertenties waren weggehaald (rij 'delisted', oud nummer erop). Opnieuw
publiceren zette die oude rij op 'pending'; de afronding vond geen rij met het
nieuwe nummer en geen rij zonder nummer, en zette er een nieuwe naast. De oude
bleef op 'pending' met een dood nummer. Gemeten: 79 zulke rijen bij 6 klanten.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.services.crosslist as cl  # noqa: E402
from backend.api import jobs as api  # noqa: E402


class _Query:
    def __init__(self, db):
        self.db, self.soort, self.filters, self.payload = db, "select", {}, None

    def select(self, *_a, **_k):
        return self

    def update(self, payload):
        self.soort, self.payload = "update", payload
        return self

    def insert(self, payload):
        self.soort, self.payload = "insert", payload
        return self

    def eq(self, kolom, waarde):
        self.filters[kolom] = waarde
        return self

    def is_(self, kolom, _waarde):
        self.filters[kolom] = None
        return self

    def execute(self):
        rijen = [r for r in self.db.listings
                 if all((not r.get(k)) if v is None else r.get(k) == v
                        for k, v in self.filters.items())]
        if self.soort == "update":
            for r in rijen:
                r.update(self.payload)
        elif self.soort == "insert":
            self.db.listings.append({"id": f"nieuw-{len(self.db.listings)}", **self.payload})
        return type("R", (), {"data": rijen})()


class _NepDb:
    def __init__(self, listings):
        self.listings = listings

    def table(self, _naam):
        return _Query(self)


def _publiceer_opnieuw(db, nieuw_nummer):
    rijen = [dict(r) for r in db.listings]
    asyncio.run(cl._wachtrij_klaarzetten(db, "ring", "2dehands", rijen))
    job = {"action": "create", "item_id": "ring", "platform": "2dehands", "payload": {}}
    asyncio.run(api._rond_publicatie_af(db, job, {"platform_listing_id": nieuw_nummer}))


def _oud(status="delisted"):
    return {"id": "oud", "item_id": "ring", "platform": "2dehands",
            "platform_listing_id": "m2438711902", "status": status}


def test_oude_rij_blijft_niet_op_pending_hangen(monkeypatch):
    async def geen_verwijdering(_db, _job):
        return None
    monkeypatch.setattr(api, "_rij_van_de_gepaarde_verwijdering", geen_verwijdering)
    db = _NepDb([_oud()])

    _publiceer_opnieuw(db, "m2448540349")

    hangend = [r for r in db.listings if r["status"] == "pending"]
    assert not hangend, f"rij blijft op pending hangen: {hangend}"
    oud = next(r for r in db.listings if r["id"] == "oud")
    assert oud["status"] == "delisted" and oud["platform_listing_id"] == "m2438711902"
    nieuw = [r for r in db.listings if r.get("platform_listing_id") == "m2448540349"]
    assert len(nieuw) == 1 and nieuw[0]["status"] == "active"


def test_mislukte_herpublicatie_wordt_zichtbaar_rood(monkeypatch):
    """Faalt het opnieuw plaatsen, dan hoort de verkoper rood te zien, niet een
    rij die eeuwig 'wordt geplaatst' zegt."""
    db = _NepDb([_oud("error")])
    asyncio.run(cl._wachtrij_klaarzetten(db, "ring", "2dehands", [dict(r) for r in db.listings]))
    job = {"action": "create", "item_id": "ring", "platform": "2dehands", "payload": {}}

    asyncio.run(api._rond_publicatie_af(db, job, {}))

    assert not [r for r in db.listings if r["status"] == "pending"]
    assert [r for r in db.listings if r["status"] == "error" and not r.get("platform_listing_id")]


def test_rij_zonder_nummer_wordt_hergebruikt():
    """Tweede klik terwijl er al een wachtende rij is: geen tweede rij erbij."""
    db = _NepDb([{"id": "w", "item_id": "ring", "platform": "2dehands",
                  "platform_listing_id": None, "status": "error"}])

    asyncio.run(cl._wachtrij_klaarzetten(db, "ring", "2dehands", [dict(r) for r in db.listings]))

    assert len(db.listings) == 1 and db.listings[0]["status"] == "pending"


# ── Lege fabrikantvelden: een zin die naar Preferences wijst (01-10-2026) ──

_RUW = ("Error: Not published — complete the fields marked in red and click publish "
        "yourself. Dit veld is verplicht. | Error: Dit veld is verplicht. | Fields "
        "marked invalid: textAttribute[manufacturerTradename]=LEEG, "
        "textAttribute[manufacturerAddress]=LEEG, textAttribute[manufacturerEmail]=LEEG")


def test_lege_fabrikantvelden_wijzen_naar_preferences():
    uit = api._rechtgezette_foutmelding({"platform": "marktplaats", "action": "create"},
                                        {"error": _RUW}, None)
    assert "Preferences" in uit["error"] and "textAttribute" not in uit["error"]
    assert uit["error_oorspronkelijk"] == _RUW


def test_betaalmuur_blijft_voorgaan():
    tekst = ('Marktplaats (marktplaats.nl) charges for adverts in "Modelauto\'s": the site '
             "says this is a paid category. textAttribute[manufacturerTradename]=LEEG")
    uit = api._rechtgezette_foutmelding({"platform": "marktplaats", "action": "create"},
                                        {"error": tekst}, None)
    assert uit["error"] == tekst


def test_ingevuld_fabrikantveld_telt_niet():
    tekst = "Fields marked invalid: textAttribute[manufacturerTradename]=JP MiniWheels"
    uit = api._rechtgezette_foutmelding({"platform": "marktplaats", "action": "create"},
                                        {"error": tekst}, None)
    assert uit.get("error") == tekst
