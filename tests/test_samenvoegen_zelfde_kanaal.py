"""Samenvoegen mag niet klappen op advertenties op hetzelfde kanaal.

WAAROM DIT ER IS (31-08-2026, Daniel)
Daniel drukte op "Merge all 13" en kreeg foutcode na foutcode terug —
269E80, 0A2143, 07F3A8, 9D7E67, DFD460, 2C75C5 en verder, allemaal binnen
dezelfde minuut op POST /api/items/merge. Op zijn scherm stond alleen
"Something went wrong on our side"; de 33 dubbele rijen bleven staan.

De oorzaak lag in de database, niet in de merge-logica. Nagemeten in Supabase:

    CREATE UNIQUE INDEX listings_item_platform_unique
      ON public.listings USING btree (item_id, platform)
      WHERE ((status)::text = 'active'::text);

Eén item mag dus hoogstens één LOPENDE advertentie per kanaal hebben. Acht
kopieën van dezelfde trui met elk een eigen Marktplaats-advertentie kunnen
daardoor niet onder één item hangen. De oude code verhuisde alle advertenties
in bulk en liet Postgres de botsing melden, wat als 500 bij de klant belandde.

Twee dingen worden hier vastgelegd, en ze horen bij elkaar:

  * De CONTROLE VOORAF volgt de index zoals die er ná
    `scripts/fix_listings_unique.sql` uitziet: botsen doet alleen wat dezelfde
    advertentie zóu worden — zelfde kanaal én zelfde advertentienummer, met een
    ontbrekend nummer als één waarde (`NULLS NOT DISTINCT`).
  * Het VANGNET eronder vangt de weigering van de database op zolang die
    wijziging nog niet gedraaid is. Zonder dat zou de klant tussen nu en dat
    moment nog steeds een serverfout zien.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import items as api  # noqa: E402


class _Query:
    """Onthoudt wat er gevraagd werd en geeft terug wat de nep-db klaarzette."""

    def __init__(self, db, tabel, soort):
        self.db, self.tabel, self.soort = db, tabel, soort
        self.filters = {}
        self.payload = None

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
            if self.tabel == "listings" and self.db.oude_index:
                raise RuntimeError(
                    "{'code': '23505', 'message': 'duplicate key value violates "
                    "unique constraint \"listings_item_platform_unique\"'}")
            return type("R", (), {"data": []})()
        return type("R", (), {"data": self.db.tabellen.get(self.tabel, [])})()


class _NepDb:
    def __init__(self, items, listings, oude_index=False):
        self.tabellen = {"items": items, "listings": listings, "jobs": []}
        self.schrijfacties = []
        # De striktere index die er staat zolang fix_listings_unique.sql niet
        # gedraaid is: elke verhuizing naar een bezet kanaal wordt geweigerd.
        self.oude_index = oude_index

    def table(self, naam):
        return _Query(self, naam, "select")


KEEP = "11111111-1111-1111-1111-111111111111"
ANDER = "22222222-2222-2222-2222-222222222222"
DERDE = "33333333-3333-3333-3333-333333333333"


def _items():
    trui = {"title": "Navy Profuomo Half Zip - Men M", "sku": "1308",
            "brand": "Profuomo", "price": 34.99}
    return [dict(trui, id=KEEP), dict(trui, id=ANDER), dict(trui, id=DERDE)]


def _advert(item, kanaal, nummer="m1", status="active"):
    return {"item_id": item, "platform": kanaal,
            "platform_listing_id": nummer, "status": status}


def _draai(listings, losers, monkeypatch, oude_index=False):
    db = _NepDb(_items(), listings, oude_index)
    monkeypatch.setattr(api, "get_db", lambda: db)
    monkeypatch.setattr(api, "zelfde_artikel", lambda *_a, **_k: True)
    monkeypatch.setattr(api, "bekende_merken_van", lambda *_a, **_k: set())
    uitslag = api.merge_items({"keep": KEEP, "merge": losers}, user_id="u1")
    return uitslag, db


# ── het vangnet: zolang de oude index er nog staat ───────────────────────────

def test_de_database_mag_weigeren_zonder_dat_de_klant_een_foutcode_ziet(monkeypatch):
    """DE KERN. Dit is letterlijk wat Daniel elf keer op zijn scherm kreeg."""
    listings = [_advert(KEEP, "marktplaats", "m100"),
                _advert(ANDER, "marktplaats", "m200")]

    uitslag, _ = _draai(listings, [ANDER], monkeypatch, oude_index=True)

    assert uitslag["merged"] == []
    assert uitslag["refused"][0]["reason"] == "advert_on_same_platform"
    assert uitslag["refused"][0]["platforms"] == ["marktplaats"]


def test_bij_een_weigering_wordt_er_niets_weggegooid(monkeypatch):
    """Erger dan een foutmelding: een advertentie die online doorloopt terwijl
    wij hem uit de administratie hebben laten vallen."""
    listings = [_advert(KEEP, "marktplaats", "m100"),
                _advert(ANDER, "marktplaats", "m200")]

    _, db = _draai(listings, [ANDER], monkeypatch, oude_index=True)

    assert [a for a in db.schrijfacties if a[1] == "delete"] == [], (
        "het item is verwijderd terwijl zijn advertenties niet mee konden")
    assert [a for a in db.schrijfacties if a[0] == "jobs"] == [], (
        "de opdrachten zijn verhuisd terwijl de advertenties bleven staan")


def test_een_andere_databasefout_wordt_niet_stilletjes_ingeslikt(monkeypatch):
    """Het vangnet is er voor één specifieke botsing. Alles daarbuiten moet
    gewoon omhoog blijven vliegen, anders verdwijnt de volgende storing net zo
    geruisloos als deze."""
    class _Stuk(_NepDb):
        def table(self, naam):
            q = _Query(self, naam, "select")
            if naam == "listings":
                origineel = q.execute

                def kapot():
                    if q.soort == "update":
                        raise RuntimeError("connection reset by peer")
                    return origineel()
                q.execute = kapot
            return q

    db = _Stuk(_items(), [_advert(KEEP, "vinted", "v1"), _advert(ANDER, "ebay", "e1")])
    monkeypatch.setattr(api, "get_db", lambda: db)
    monkeypatch.setattr(api, "zelfde_artikel", lambda *_a, **_k: True)
    monkeypatch.setattr(api, "bekende_merken_van", lambda *_a, **_k: set())

    try:
        api.merge_items({"keep": KEEP, "merge": [ANDER]}, user_id="u1")
    except RuntimeError as e:
        assert "connection reset" in str(e)
    else:
        raise AssertionError("een verbindingsfout hoort niet als weigering te eindigen")


# ── de controle vooraf: zoals het ná de schemawijziging hoort te werken ──────

def test_twee_echte_advertenties_op_hetzelfde_kanaal_mogen_samen(monkeypatch):
    """Waar het Daniel om gaat: acht kopieën van dezelfde trui, elk met een
    eigen Marktplaats-advertentie. Dat is precies het normale geval."""
    listings = [_advert(KEEP, "marktplaats", "m100"),
                _advert(ANDER, "marktplaats", "m200")]

    uitslag, db = _draai(listings, [ANDER], monkeypatch)

    assert uitslag["merged"] == [ANDER], (
        "twee verschillende advertenties zijn geen botsing")
    assert ("items", "delete") in [(a[0], a[1]) for a in db.schrijfacties]


def test_dezelfde_advertentie_twee_keer_blijft_wel_een_botsing(monkeypatch):
    """Hetzelfde advertentienummer op hetzelfde kanaal is geen tweede
    advertentie maar dezelfde, en die kan er maar één keer zijn."""
    listings = [_advert(KEEP, "marktplaats", "m100"),
                _advert(ANDER, "marktplaats", "m100")]

    uitslag, _ = _draai(listings, [ANDER], monkeypatch)

    assert uitslag["merged"] == []
    assert uitslag["refused"][0]["reason"] == "advert_on_same_platform"


def test_twee_lopende_advertenties_zonder_nummer_botsen_ook(monkeypatch):
    """NULLS NOT DISTINCT in de index, en hier dezelfde regel: zonder dit kan
    één item onbeperkt lopende advertenties zonder nummer verzamelen, en zo
    ziet dubbel publiceren eruit. 101 van de 11.102 advertenties in de database
    hebben geen nummer, dus dit geval is echt."""
    listings = [_advert(KEEP, "marktplaats", None),
                _advert(ANDER, "marktplaats", None)]

    uitslag, _ = _draai(listings, [ANDER], monkeypatch)

    assert uitslag["merged"] == []
    assert uitslag["refused"][0]["reason"] == "advert_on_same_platform"


def test_een_verkochte_advertentie_blokkeert_niets(monkeypatch):
    """De index draagt `WHERE status = 'active'`. Een verkochte of ingetrokken
    advertentie hoort dus niets in de weg te staan — de oude controle weigerde
    die groepen onnodig."""
    listings = [_advert(KEEP, "marktplaats", "m100", status="sold"),
                _advert(ANDER, "marktplaats", "m100", status="delisted")]

    uitslag, _ = _draai(listings, [ANDER], monkeypatch)

    assert uitslag["merged"] == [ANDER], (
        "niet-lopende advertenties vallen buiten de index en mogen samen")


def test_verschillende_kanalen_gaan_gewoon_door(monkeypatch):
    listings = [_advert(KEEP, "marktplaats", "m100"),
                _advert(DERDE, "vinted", "v100")]

    uitslag, _ = _draai(listings, [DERDE], monkeypatch)

    assert uitslag["merged"] == [DERDE]
    assert uitslag["refused"] == []


def test_botsende_en_vrije_rij_in_een_aanroep(monkeypatch):
    """Bij "Merge all" zit alles door elkaar; één botsing mag de rest niet
    meeslepen."""
    listings = [_advert(KEEP, "marktplaats", "m100"),
                _advert(ANDER, "marktplaats", "m100"),
                _advert(DERDE, "vinted", "v100")]

    uitslag, _ = _draai(listings, [ANDER, DERDE], monkeypatch)

    assert uitslag["merged"] == [DERDE]
    assert [r["id"] for r in uitslag["refused"]] == [ANDER]


def test_twee_losers_met_dezelfde_advertentie_glippen_er_niet_allebei_in(monkeypatch):
    """De tweede loser botst niet met keep zoals die begon, maar wél met wat de
    eerste loser er net in heeft gebracht. Zonder bijwerken van de bezette
    advertenties levert dat alsnog de oude serverfout op."""
    listings = [_advert(ANDER, "vinted", "v1"),
                _advert(DERDE, "vinted", "v1")]

    uitslag, _ = _draai(listings, [ANDER, DERDE], monkeypatch)

    assert uitslag["merged"] == [ANDER], "de eerste mag naar binnen"
    assert [r["id"] for r in uitslag["refused"]] == [DERDE], (
        "de tweede brengt dezelfde advertentie mee en moet geweigerd worden")
