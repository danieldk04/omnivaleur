"""Een verkochte rij mag de nieuwe voorraad van hetzelfde artikel niet opslokken.

WAAROM DIT ER IS (18-09-2026, Daniels eigen account dkresellacademy@gmail.com).

Daniel: "Ik heb it publiceren maar die was al dubbel stond in dashboard. Toen zei
ik oh merge into one voor twee artikelen, maar nou is die helemaal weg." Het ging
om artikel 987 en om nog één.

Nagemeten op de echte database. Artikel (987) Blue Ralph Lauren Zip Vest is op
23-08-2026 op Vinted verkocht voor EUR 30,49. Op 18-09-2026 om 15:32:04 maakte
Daniel een nieuwe rij aan met datzelfde nummer — hetzelfde artikel, opnieuw
ingekocht, vijf eigen foto's. Tien seconden later drukte hij op Publish. Wat er
toen gebeurde, in deze volgorde:

  1. De verkoop-rem bij het uitdelen keek naar de hele FAMILIE (alle artikelen
     met hetzelfde nummer) en zag de verkoop van 23-08 op de oude rij. Alle drie
     de kanalen werden geannuleerd met "Item already sold on vinted".
  2. De drie advertentierijen die het publiceren net had klaargezet bleven
     eeuwig op 'pending' staan. Het dashboard zei "Publishing…" voor werk dat
     nooit meer zou komen.
  3. Het dashboard bood de twee rijen aan als dubbele rijen. Daniel drukte op
     "Merge into one". De samenvoeging houdt de OUDSTE rij aan — de verkochte —
     en verwijderde zijn nieuwe artikel. De verkochte advertentie stond geen
     samenvoeging in de weg: de botsingscontrole kijkt alleen naar 'active'.
  4. Het overgebleven artikel draagt een verkochte advertentie, dus het dashboard
     zet het onder "Sold". Uit "Live", uit "To list", en niet meer te publiceren.

Hetzelfde overkwam op 15-09-2026 een rij die hij zelf "1349 - 2" had genoemd —
hij schreef er letterlijk bij dat het het tweede exemplaar was.

Vastgelegd wordt hier:

  * SAMENVOEGEN weigert zodra de ene rij verkocht is en de andere niet. Twee
    verkochte of twee onverkochte rijen mogen gewoon samen.
  * HET DASHBOARD biedt zo'n groep niet meer aan, zodat de knop er niet staat.
  * DE VERKOOP-REM laat een artikel door dat pas ná de verkoop van zijn tweeling
    is aangemaakt. De eigen verkoop van een artikel blokkeert altijd.
  * EEN GEANNULEERDE publicatie laat geen wachtende advertentierij achter.
"""
import sys
import types
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORTEL))

from backend.api import items as items_api  # noqa: E402

KEEP = "11111111-1111-1111-1111-111111111111"
ANDER = "22222222-2222-2222-2222-222222222222"


# ───────────────────────── samenvoegen ──────────────────────────────────────

class _Query:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.soort = db, tabel, "select"
        self.filters, self.payload = {}, None

    def select(self, *_a, **_k):
        return self

    def update(self, payload):
        self.soort, self.payload = "update", payload
        return self

    def delete(self):
        self.soort = "delete"
        return self

    def eq(self, kolom, waarde):
        self.filters[kolom] = waarde
        return self

    def in_(self, kolom, waarden):
        self.filters[kolom] = list(waarden)
        return self

    def execute(self):
        if self.soort in ("update", "delete"):
            self.db.schrijfacties.append((self.tabel, self.soort, self.filters))
            return types.SimpleNamespace(data=[])
        return types.SimpleNamespace(data=self.db.tabellen.get(self.tabel, []))


class _NepDb:
    def __init__(self, items, listings):
        self.tabellen = {"items": items, "listings": listings, "jobs": []}
        self.schrijfacties = []

    def table(self, naam):
        return _Query(self, naam)


def _advert(item, kanaal, nummer="m1", status="active"):
    return {"item_id": item, "platform": kanaal,
            "platform_listing_id": nummer, "status": status}


def _samenvoegen(listings, monkeypatch):
    trui = {"title": "(987) Blue Ralph Lauren Zip Vest - Boys XL", "sku": "987",
            "brand": "Ralph Lauren", "price": 29.99}
    db = _NepDb([dict(trui, id=KEEP), dict(trui, id=ANDER)], listings)
    monkeypatch.setattr(items_api, "get_db", lambda: db)
    monkeypatch.setattr(items_api, "zelfde_artikel", lambda *_a, **_k: True)
    monkeypatch.setattr(items_api, "bekende_merken_van", lambda *_a, **_k: set())
    return items_api.merge_items({"keep": KEEP, "merge": [ANDER]}, user_id="u1"), db


def test_de_verkochte_rij_slokt_de_nieuwe_voorraad_niet_op(monkeypatch):
    """DE KERN. Dit is letterlijk wat er met artikel 987 gebeurde."""
    listings = [_advert(KEEP, "vinted", "8675466688", status="sold")]

    uitslag, db = _samenvoegen(listings, monkeypatch)

    assert uitslag["merged"] == [], "de nieuwe rij is opgeslokt door de verkochte"
    assert uitslag["refused"][0]["reason"] == "one_copy_is_sold"
    assert uitslag["refused"][0]["platforms"] == ["vinted"]
    assert [a for a in db.schrijfacties if a[1] == "delete"] == [], (
        "er is een artikel verwijderd dat nog gewoon te koop staat")


def test_ook_andersom_verkocht_en_niet_verkocht_blijven_los(monkeypatch):
    """Nu draagt de LOSER de verkoop. Samenvoegen zou die verkochte advertentie
    naar het levende artikel verhuizen, en dan verdwijnt dát onder "Sold"."""
    listings = [_advert(ANDER, "vinted", "8675466688", status="sold")]

    uitslag, db = _samenvoegen(listings, monkeypatch)

    assert uitslag["merged"] == []
    assert uitslag["refused"][0]["reason"] == "one_copy_is_sold"
    assert [a for a in db.schrijfacties if a[1] == "delete"] == []


def test_twee_verkochte_rijen_mogen_wel_samen(monkeypatch):
    """Allebei geschiedenis: samenvoegen is dan gewoon opruimen."""
    listings = [_advert(KEEP, "vinted", "v1", status="sold"),
                _advert(ANDER, "marktplaats", "m1", status="sold")]

    uitslag, _ = _samenvoegen(listings, monkeypatch)

    assert uitslag["merged"] == [ANDER]


def test_twee_onverkochte_rijen_mogen_gewoon_samen(monkeypatch):
    """De echte tweeling — twee importrijen van één trui — blijft werken."""
    listings = [_advert(KEEP, "vinted", "v1"),
                _advert(ANDER, "marktplaats", "m1", status="delisted")]

    uitslag, _ = _samenvoegen(listings, monkeypatch)

    assert uitslag["merged"] == [ANDER]


# ───────────────────────── de dubbel-balk ───────────────────────────────────

def test_het_dashboard_biedt_zon_groep_niet_meer_aan(monkeypatch):
    """De knop mag er niet eens staan: samenvoegen is niet terug te draaien."""
    items = [{"id": KEEP, "title": "(987) Blue Ralph Lauren Zip Vest",
              "sku": "987", "brand": "Ralph Lauren", "price": 29.99,
              "photo_urls": [], "created_at": "2026-07-03T09:26:42+00:00"},
             {"id": ANDER, "title": "(987) Blue Ralph Lauren Zip Vest",
              "sku": "987", "brand": "Ralph Lauren", "price": 29.99,
              "photo_urls": [], "created_at": "2026-09-18T15:32:04+00:00"}]
    listings = [_advert(KEEP, "vinted", "8675466688", status="sold")]

    db = _NepDb(items, listings)
    monkeypatch.setattr(items_api, "get_db", lambda: db)
    monkeypatch.setattr(items_api, "fetch_all", lambda maak: maak().execute().data)
    monkeypatch.setattr(items_api, "groepeer", lambda _i: [items])

    uit = items_api.list_duplicates(user_id="u1")

    assert uit["groups"] == [], (
        "een verkochte en een onverkochte rij zijn twee verschillende voorwerpen")


def test_een_echte_tweeling_blijft_wel_in_de_balk_staan(monkeypatch):
    items = [{"id": KEEP, "title": "(1032) Grijs Ralph Lauren Zip Vest",
              "sku": "1032", "brand": "Ralph Lauren", "price": 39.99,
              "photo_urls": [], "created_at": "2026-07-03T09:26:42+00:00"},
             {"id": ANDER, "title": "(1032) Grey Ralph Lauren Zip Vest",
              "sku": "1032", "brand": "Ralph Lauren", "price": 39.99,
              "photo_urls": [], "created_at": "2026-08-25T10:38:27+00:00"}]
    listings = [_advert(KEEP, "marktplaats", "m1")]

    db = _NepDb(items, listings)
    monkeypatch.setattr(items_api, "get_db", lambda: db)
    monkeypatch.setattr(items_api, "fetch_all", lambda maak: maak().execute().data)
    monkeypatch.setattr(items_api, "groepeer", lambda _i: [items])

    uit = items_api.list_duplicates(user_id="u1")

    assert len(uit["groups"]) == 1
    assert [i["id"] for i in uit["groups"][0]["items"]] == [KEEP, ANDER]


# ───────────────────────── de verkoop-rem ───────────────────────────────────

class _JobsDb:
    """Net genoeg database om get_pending_jobs één publicatie te laten wegen."""

    def __init__(self, item, listings, job):
        self.item, self.listings, self.job = item, listings, job
        self.updates = []

    def table(self, naam):
        db = self

        class T:
            def __init__(self):
                self.naam, self.filters, self.patch = naam, {}, None

            def select(self, *a, **kw): return self
            def order(self, *a, **kw): return self
            def limit(self, *a, **kw): return self
            def lte(self, *a, **kw): return self
            def is_(self, kolom, waarde):
                self.filters[kolom] = waarde
                return self

            def update(self, patch):
                self.patch = patch
                return self

            def eq(self, kolom, waarde):
                self.filters[kolom] = waarde
                return self

            def in_(self, kolom, waarden):
                self.filters[kolom] = list(waarden)
                return self

            def execute(self):
                if self.patch is not None:
                    db.updates.append((self.naam, dict(self.filters), self.patch))
                    return types.SimpleNamespace(data=[])
                if self.naam == "items":
                    return types.SimpleNamespace(data=[db.item])
                if self.naam == "listings":
                    rijen = [r for r in db.listings
                             if r["item_id"] in self.filters.get("item_id", [])
                             and r["status"] == self.filters.get("status", r["status"])]
                    return types.SimpleNamespace(data=rijen)
                if self.naam == "jobs":
                    if self.filters.get("status") == "pending":
                        return types.SimpleNamespace(data=[db.job])
                    return types.SimpleNamespace(data=[])
                return types.SimpleNamespace(data=[])

        return T()


def _deel_uit(item_gemaakt_op, listings, monkeypatch):
    import backend.api.jobs as jobs
    from backend.services import tweelingen

    item = {"id": "nieuw", "user_id": "u1", "title": "(987) Blue Ralph Lauren Zip Vest",
            "sku": "987", "brand": "Ralph Lauren", "created_at": item_gemaakt_op}
    job = {"id": "j1", "item_id": "nieuw", "platform": "marktplaats",
           "action": "create", "status": "pending",
           "created_at": "2026-09-18T15:32:21+00:00", "payload": {}}
    db = _JobsDb(item, listings, job)
    monkeypatch.setattr(jobs, "get_db", lambda: db)
    monkeypatch.setattr(jobs, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(jobs, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(tweelingen, "familie_ids", lambda _db, _r: ["nieuw", "oud"])

    uit = jobs.get_pending_jobs(
        request=type("R", (), {"headers": {}})(), platform="marktplaats", user_id="u1")
    return uit, db


def test_een_nieuw_exemplaar_mag_wel_online(monkeypatch):
    """DE KERN AAN DE PUBLICEERKANT. Het nieuwe artikel is van 18-09, de verkoop
    van zijn tweeling van 23-08. Dat is een ander voorwerp."""
    listings = [{"item_id": "oud", "platform": "vinted", "status": "sold",
                 "sold_at": "2026-08-23T16:12:21+00:00"}]

    uit, db = _deel_uit("2026-09-18T15:32:04+00:00", listings, monkeypatch)

    assert [j["id"] for j in uit] == ["j1"], (
        "een tweede exemplaar is geen tweede verkoop van hetzelfde voorwerp")
    assert [u for u in db.updates if u[2].get("status") == "cancelled"] == []


def test_een_echte_tweeling_wordt_nog_steeds_tegengehouden(monkeypatch):
    """De tweelingrij bestond al lang vóór de verkoop: één trui, twee rijen."""
    listings = [{"item_id": "oud", "platform": "vinted", "status": "sold",
                 "sold_at": "2026-08-23T16:12:21+00:00"}]

    uit, db = _deel_uit("2026-07-03T09:26:42+00:00", listings, monkeypatch)

    assert uit == [], "dit zou een tweede koper voor één trui opleveren"
    geannuleerd = [u for u in db.updates
                   if u[0] == "jobs" and u[2].get("status") == "cancelled"]
    assert geannuleerd and "sold on vinted" in geannuleerd[0][2]["result"]["cancelled"].lower()


def test_de_eigen_verkoop_blokkeert_altijd(monkeypatch):
    """Ook al is het artikel later aangemaakt dan zijn eigen verkoopdatum —
    dit exemplaar is zelf weg en gaat nergens meer heen."""
    listings = [{"item_id": "nieuw", "platform": "vinted", "status": "sold",
                 "sold_at": "2026-08-23T16:12:21+00:00"}]

    uit, _ = _deel_uit("2026-09-18T15:32:04+00:00", listings, monkeypatch)

    assert uit == []


def test_zonder_verkoopdatum_remmen_we(monkeypatch):
    """Bij twijfel geen publicatie: een dubbel verkocht artikel is erger dan een
    opdracht die blijft wachten."""
    listings = [{"item_id": "oud", "platform": "vinted", "status": "sold",
                 "sold_at": None}]

    uit, _ = _deel_uit("2026-09-18T15:32:04+00:00", listings, monkeypatch)

    assert uit == []


def test_de_geannuleerde_publicatie_laat_geen_wachtende_rij_achter(monkeypatch):
    """Anders staat er "Publishing…" voor werk dat nooit meer komt. Gemeten:
    vier van zulke rijen in Daniels account, de oudste van 29-07."""
    listings = [{"item_id": "oud", "platform": "vinted", "status": "sold",
                 "sold_at": "2026-08-23T16:12:21+00:00"}]

    _, db = _deel_uit("2026-07-03T09:26:42+00:00", listings, monkeypatch)

    opgeruimd = [u for u in db.updates
                 if u[0] == "listings" and u[2].get("status") == "error"]
    assert opgeruimd, "de wachtende advertentierij blijft eeuwig op 'pending' staan"
    filters = opgeruimd[0][1]
    assert filters["item_id"] == "nieuw" and filters["platform"] == "marktplaats"
    assert filters["status"] == "pending", "alleen wachtende rijen mogen mee"
    assert filters["platform_listing_id"] == "null", (
        "een rij met advertentienummer hoort bij een echte advertentie en blijft")
