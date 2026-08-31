"""Samenvoegen mag niet klappen op twee advertenties op hetzelfde kanaal.

WAAROM DIT ER IS (31-08-2026, Daniel)
Daniel drukte op "Merge all 13" en kreeg foutcode na foutcode terug —
269E80, 0A2143, 07F3A8, 9D7E67, DFD460, 2C75C5 en verder, allemaal binnen
dezelfde minuut op POST /api/items/merge. Op zijn scherm stond alleen
"Something went wrong on our side"; de 33 dubbele rijen bleven staan.

De oorzaak lag in de database, niet in de merge-logica: `listings` heeft een
unieke sleutel op (item_id, platform). Acht kopieën van dezelfde trui met elk
een eigen Marktplaats-advertentie kunnen dus niet onder één item hangen. De
oude code verhuisde alle advertenties in bulk en liet Postgres de botsing
melden, wat als 500 bij de klant terechtkwam.

Wat deze proef vastlegt:
  * een botsing levert een nette weigering op, geen exceptie;
  * de rij die botst blijft compleet bestaan — niets weggegooid;
  * groepen zonder botsing gaan in dezelfde aanroep gewoon door;
  * twee losers die allebei hetzelfde kanaal meebrengen kunnen niet allebei
    naar binnen glippen.
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
            return type("R", (), {"data": []})()
        return type("R", (), {"data": self.db.tabellen.get(self.tabel, [])})()


class _NepDb:
    def __init__(self, items, listings):
        self.tabellen = {"items": items, "listings": listings, "jobs": []}
        self.schrijfacties = []

    def table(self, naam):
        return _Query(self, naam, "select")


KEEP = "11111111-1111-1111-1111-111111111111"
BOTST = "22222222-2222-2222-2222-222222222222"
VRIJ = "33333333-3333-3333-3333-333333333333"


def _items():
    trui = {"title": "Navy Profuomo Half Zip - Men M", "sku": "1308",
            "brand": "Profuomo", "price": 34.99}
    return [dict(trui, id=KEEP), dict(trui, id=BOTST), dict(trui, id=VRIJ)]


def _draai(listings, losers, monkeypatch):
    db = _NepDb(_items(), listings)
    monkeypatch.setattr(api, "get_db", lambda: db)
    monkeypatch.setattr(api, "zelfde_artikel", lambda *_a, **_k: True)
    monkeypatch.setattr(api, "bekende_merken_van", lambda *_a, **_k: set())
    uitslag = api.merge_items({"keep": KEEP, "merge": losers}, user_id="u1")
    return uitslag, db


def test_botsing_wordt_geweigerd_in_plaats_van_een_serverfout(monkeypatch):
    """DE KERN. Dit is precies wat Daniel elf keer op zijn scherm kreeg."""
    listings = [{"item_id": KEEP, "platform": "marktplaats"},
                {"item_id": BOTST, "platform": "marktplaats"}]

    uitslag, _ = _draai(listings, [BOTST], monkeypatch)

    assert uitslag["merged"] == [], "een botsende rij mag niet samengevoegd worden"
    assert len(uitslag["refused"]) == 1
    assert uitslag["refused"][0]["reason"] == "advert_on_same_platform"
    assert uitslag["refused"][0]["platforms"] == ["marktplaats"], (
        "de app moet kunnen zeggen om welk kanaal het gaat")


def test_de_botsende_rij_wordt_niet_weggegooid(monkeypatch):
    """Erger dan een foutmelding: een advertentie die online doorloopt terwijl
    wij hem uit de administratie hebben laten vallen."""
    listings = [{"item_id": KEEP, "platform": "marktplaats"},
                {"item_id": BOTST, "platform": "marktplaats"}]

    _, db = _draai(listings, [BOTST], monkeypatch)

    verwijderd = [a for a in db.schrijfacties if a[1] == "delete"]
    assert verwijderd == [], f"er is toch iets verwijderd: {verwijderd}"
    assert db.schrijfacties == [], "er mag helemaal niets geschreven zijn"


def test_een_rij_zonder_botsing_gaat_gewoon_door(monkeypatch):
    """De rem mag niet zo breed zijn dat samenvoegen nooit meer werkt."""
    listings = [{"item_id": KEEP, "platform": "marktplaats"},
                {"item_id": VRIJ, "platform": "vinted"}]

    uitslag, db = _draai(listings, [VRIJ], monkeypatch)

    assert uitslag["merged"] == [VRIJ]
    assert uitslag["refused"] == []
    tabellen = [(a[0], a[1]) for a in db.schrijfacties]
    assert ("listings", "update") in tabellen
    assert ("items", "delete") in tabellen


def test_botsende_en_vrije_rij_in_een_aanroep(monkeypatch):
    """Bij "Merge all" zit alles door elkaar; één botsing mag de rest niet
    meeslepen."""
    listings = [{"item_id": KEEP, "platform": "marktplaats"},
                {"item_id": BOTST, "platform": "marktplaats"},
                {"item_id": VRIJ, "platform": "vinted"}]

    uitslag, _ = _draai(listings, [BOTST, VRIJ], monkeypatch)

    assert uitslag["merged"] == [VRIJ]
    assert [r["id"] for r in uitslag["refused"]] == [BOTST]


def test_twee_losers_met_hetzelfde_kanaal_glippen_er_niet_allebei_in(monkeypatch):
    """De tweede loser botst niet met keep zoals die begon, maar wél met het
    kanaal dat de eerste loser er net in heeft gebracht. Zonder bijwerken van
    de bezette kanalen levert dat alsnog de oude serverfout op."""
    listings = [{"item_id": BOTST, "platform": "vinted"},
                {"item_id": VRIJ, "platform": "vinted"}]

    uitslag, _ = _draai(listings, [BOTST, VRIJ], monkeypatch)

    assert uitslag["merged"] == [BOTST], "de eerste mag naar binnen"
    assert [r["id"] for r in uitslag["refused"]] == [VRIJ], (
        "de tweede brengt hetzelfde kanaal mee en moet nu geweigerd worden")
