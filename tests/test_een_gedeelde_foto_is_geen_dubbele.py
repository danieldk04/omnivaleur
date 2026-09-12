"""Vier verschillende lederhosen zijn geen vier keer dezelfde lederhose.

WAAROM DIT ER IS (12-09-2026, De Juiste Toon)
"Ben dit hele weekend al de Lederhosen aan het plaatsen, belangrijk voor
oktober, zie alleen ze nog niet snel op mp komen." Bij elke poging kwam:
"Already listed here under a duplicate copy of this item. Merge them first,
otherwise you get two adverts for one article."

Ze waren geen dubbelen. Vier artikelen die allemaal "Lederhosen Dames" heten
zijn vier verschillende broeken: 40 cm, 35 cm, 47 cm en een groene suède, elk
met eigen prijs, eigen tekst en negen tot elf eigen foto's. Ze delen één
plaatje: zijn eigen info-/maatfoto, die in 17 van zijn artikelen zit. Op de oude
regel ("dezelfde titel én minstens één gedeelde foto") gold dat als bewijs, en
de melding stuurde hem naar samenvoegen — wat twee echte broeken tot één zou
hebben geplakt.

GEMETEN op zijn 1.318 artikelen, alle 43 paren met dezelfde titel én een
gedeelde foto. De scheiding is scherp, zonder twijfelgevallen ertussen: 26 echte
dubbelen delen de hele kleinere fotoset (4 van 4, 5 van 5, 9 van 9, 10 van 10,
11 van 11, en twee paren van 1 van 1), 17 valse delen precies één foto van zeven
tot elf. Over alle verkopers samen geeft de nieuwe regel 32 artikelen vrij en
blokkeert er geen enkele bij.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.crosslist import _zelfde_artikel_al_online, _zelfde_fotos  # noqa: E402

INFO = "https://img.omnivaleur.com/toon/a13db2d0d574470e35573e5f.jpg"


def broek(n: int, aantal: int = 9) -> set:
    """Een lederhose met eigen foto's plus zijn vaste info-plaatje."""
    return {f"https://img.omnivaleur.com/toon/broek{n}-{i}.jpg" for i in range(aantal)} | {INFO}


def test_alleen_het_infoplaatje_gedeeld_is_geen_dubbele():
    assert not _zelfde_fotos(broek(1), broek(2))
    assert not _zelfde_fotos(broek(1, 10), broek(3, 6))


def test_twee_imports_van_dezelfde_advertentie_blijven_een_dubbele():
    zelfde = broek(1)
    assert _zelfde_fotos(zelfde, set(zelfde))


def test_import_die_een_foto_meer_ophaalde_telt_nog_steeds_als_dubbele():
    groot = broek(1, 10)
    klein = set(list(groot)[:9])
    assert _zelfde_fotos(groot, klein)


def test_twee_artikelen_met_dezelfde_enige_foto_zijn_een_dubbele():
    # Zijn twee grand foulards: allebei één foto, en dat is dezelfde.
    een = {"https://img.omnivaleur.com/toon/94c2faf1c9.jpg"}
    assert _zelfde_fotos(een, set(een))


def test_lege_fotoset_blokkeert_nooit():
    assert not _zelfde_fotos(set(), broek(1))
    assert not _zelfde_fotos(broek(1), set())


# ── En hetzelfde nog een keer via de controle die publiceren écht tegenhoudt ──

class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.f, self.inf = db, tabel, {}, {}

    def select(self, *_a, **_k): return self
    def eq(self, k, v): self.f[k] = v; return self
    def in_(self, k, v): self.inf[k] = list(v); return self
    def limit(self, _n): return self

    def execute(self):
        bron = self.db.items if self.tabel == "items" else self.db.listings
        rijen = [r for r in bron
                 if all(r.get(k) == v for k, v in self.f.items())
                 and all(r.get(k) in vals for k, vals in self.inf.items())]
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, items, listings): self.items, self.listings = items, listings
    def table(self, naam): return _Q(self, naam)


def _toons_kast():
    """Zijn vier lederhosen, waarvan er één al op Marktplaats staat."""
    items = [{"id": f"broek-{n}", "user_id": "toon", "title": "Lederhosen Dames",
              "photo_urls": sorted(broek(n))} for n in (1, 2, 3, 4)]
    listings = [{"item_id": "broek-4", "platform": "marktplaats", "status": "active",
                 "platform_listing_id": "m2439167847", "platform_listing_url": ""}]
    return _DB(items, listings)


def test_publiceren_wordt_niet_geweigerd_om_het_infoplaatje():
    db = _toons_kast()
    bezet = _zelfde_artikel_al_online(db, db.items[0], ["marktplaats"], [])
    assert bezet == {}, f"broek 1 werd geweigerd om broek 4: {bezet}"


def test_een_echte_dubbele_wordt_nog_steeds_geweigerd():
    db = _toons_kast()
    # Twee imports van dezelfde advertentie: zelfde titel, zelfde foto's.
    db.items[0]["photo_urls"] = list(db.items[3]["photo_urls"])
    bezet = _zelfde_artikel_al_online(db, db.items[0], ["marktplaats"], [])
    assert "marktplaats" in bezet, "een echte dubbele moet geweigerd blijven"
