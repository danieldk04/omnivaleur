"""Publiceren mag niet stukgaan doordat een artikel meerdere advertenties heeft.

WAAROM DIT ER IS (31-08-2026)
Nadat de unieke index op `listings` was vervangen (scripts/fix_listings_unique.sql)
kon Daniel eindelijk zijn dubbele rijen samenvoegen. Direct daarna kwam er een
nieuwe serverfout binnen, code A1C211:

    duplicate key value violates unique constraint
    "listings_item_platform_advert_unique"
    Key (item_id, platform, platform_listing_id)=(1d9b3e99…, marktplaats,
    m2437307079) already exists.

De oorzaak stond in `complete_job`: bij het afronden van een publicatie werd de
advertentierij gezocht met `.eq(item_id).eq(platform)` en dan BIJGEWERKT. Dat
raakte alle rijen tegelijk. Eén artikel dat na het samenvoegen acht
Marktplaats-advertenties draagt, kreeg er dus acht met hetzelfde nummer.

Het venijn: dit was vóór de indexwijziging net zo fout, alleen onzichtbaar. De
oude index verbood meerdere lopende advertenties per kanaal, dus het geval kwam
niet voor. Zodra het wél voorkwam, overschreven zeven echte advertentienummers
elkaar — en daarmee waren zeven advertenties niet meer terug te vinden. De
database weigert het nu, en dat is maar goed ook.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class _Query:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.soort = "select"
        self.filters = {}
        self.payload = None

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
        if self.soort == "select":
            rijen = self.db.listings
            for kolom, waarde in self.filters.items():
                if waarde is None:
                    rijen = [r for r in rijen if not r.get(kolom)]
                else:
                    rijen = [r for r in rijen if r.get(kolom) == waarde]
            return type("R", (), {"data": rijen})()
        self.db.schrijfacties.append((self.soort, dict(self.filters), self.payload))
        if self.soort == "update":
            geraakt = [r for r in self.db.listings
                       if all(r.get(k) == v for k, v in self.filters.items())]
            for r in geraakt:
                r.update(self.payload)
            # DE ECHTE DATABASE. Twee lopende advertenties met hetzelfde nummer
            # op hetzelfde artikel en kanaal worden geweigerd — dat is precies
            # `listings_item_platform_advert_unique`.
            actief = [(r["item_id"], r["platform"], r.get("platform_listing_id"))
                      for r in self.db.listings if r.get("status") == "active"]
            if len(actief) != len(set(actief)):
                raise RuntimeError(
                    "{'code': '23505', 'message': 'duplicate key value violates "
                    "unique constraint \"listings_item_platform_advert_unique\"'}")
        else:
            self.db.listings.append(dict(self.payload))
        return type("R", (), {"data": []})()


class _NepDb:
    def __init__(self, listings):
        self.listings = listings
        self.schrijfacties = []

    def table(self, naam):
        return _Query(self, naam)


ITEM = "1d9b3e99-c8f2-40e0-ad44-6ac7a4d4f7b1"


def _advert(nummer, status="active"):
    return {"id": f"rij-{nummer or 'leeg'}", "item_id": ITEM,
            "platform": "marktplaats", "platform_listing_id": nummer,
            "status": status}


async def _rond_af(db, nieuw_nummer):
    """Speelt het create-deel van complete_job na."""
    from backend.api import jobs as api
    job = {"action": "create", "item_id": ITEM, "platform": "marktplaats"}
    body = {"platform_listing_id": nieuw_nummer,
            "platform_listing_url": f"https://mp.nl/{nieuw_nummer}"}
    await api._rond_publicatie_af(db, job, body)


def test_acht_advertenties_onder_een_artikel_botsen_niet(monkeypatch):
    """DE KERN. Dit is foutcode A1C211: het artikel draagt na het samenvoegen
    al drie lopende Marktplaats-advertenties, en er komt een vierde bij."""
    import asyncio
    db = _NepDb([_advert("m2437307079"), _advert("m2421148232"), _advert("m2409769119")])

    asyncio.run(_rond_af(db, "m9999999999"))

    nummers = sorted(r.get("platform_listing_id") for r in db.listings)
    assert nummers == ["m2409769119", "m2421148232", "m2437307079", "m9999999999"], (
        f"de bestaande advertenties zijn aangetast: {nummers}")
    assert len(db.listings) == 4, "de nieuwe advertentie moet erbij komen"


def test_bestaande_nummers_worden_nooit_overschreven(monkeypatch):
    """Het echte gevaar, ook vóór de index het weigerde: zeven advertenties die
    stilletjes hetzelfde nummer krijgen zijn zeven advertenties die we online
    niet meer terugvinden."""
    import asyncio
    db = _NepDb([_advert("m111"), _advert("m222")])

    asyncio.run(_rond_af(db, "m333"))

    assert {r["platform_listing_id"] for r in db.listings} == {"m111", "m222", "m333"}


def test_de_rij_die_op_een_nummer_wacht_wordt_ingevuld(monkeypatch):
    """Het normale geval: publiceren maakt een rij zonder nummer aan en de
    afronding vult hem in. Er mag dan géén tweede rij bij komen."""
    import asyncio
    db = _NepDb([_advert("m111"), _advert(None, status="pending")])

    asyncio.run(_rond_af(db, "m444"))

    assert len(db.listings) == 2, "er is een rij bij gekomen in plaats van ingevuld"
    ingevuld = [r for r in db.listings if r["platform_listing_id"] == "m444"]
    assert ingevuld and ingevuld[0]["status"] == "active"


def test_dezelfde_afronding_twee_keer_verandert_niets(monkeypatch):
    """De extensie kan een afronding laat of dubbel sturen. Dat moet op dezelfde
    rij landen en niet op een tweede."""
    import asyncio
    db = _NepDb([_advert("m555")])

    asyncio.run(_rond_af(db, "m555"))

    assert len(db.listings) == 1, "een herhaalde afronding maakte een tweede rij"
    assert db.listings[0]["platform_listing_id"] == "m555"


def test_een_mislukte_publicatie_markeert_niet_alles_als_kapot(monkeypatch):
    """Zonder advertentienummer ging vroeger élke rij van dit kanaal op 'error'.
    Zeven lopende advertenties als kapot markeren omdat de achtste faalde is
    erger dan de storing zelf."""
    import asyncio
    from backend.api import jobs as api
    db = _NepDb([_advert("m111"), _advert("m222"), _advert(None, status="pending")])
    job = {"action": "create", "item_id": ITEM, "platform": "marktplaats"}

    asyncio.run(api._rond_publicatie_af(db, job, {}))

    kapot = [r for r in db.listings if r.get("status") == "error"]
    assert len(kapot) == 1, f"{len(kapot)} rijen op error gezet in plaats van 1"
    assert not kapot[0].get("platform_listing_id"), (
        "een lopende advertentie is als kapot gemarkeerd")
