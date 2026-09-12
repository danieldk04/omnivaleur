"""Twee artikelrijen voor één voorwerp mogen geen twee advertenties worden.

AANLEIDING (07-09-2026, De Juiste Toon): "Ook zie ik continue dubbele
advertenties verschijnen." Nagemeten op zijn openbare verkoperspagina, niet
aangenomen: elf titels stonden er dubbel, samen vijftien advertenties te veel,
waarvan er één diezelfde dag nog was bijgekomen en zes de dag ervoor.

OORZAAK. Twee imports van dezelfde Marktplaats-advertentie werden twee losse
artikelen. De bestaande dubbelcontrole (`tweelingen.familie_ids`) herkent
tweelingen aan het nummer dat de verkoper zelf voor de titel zet — "(1032) …" —
of aan een gedeelde sku. Zijn artikelen hebben geen van beide: elke import geeft
een eigen sku en zijn titels zijn kaal. De controle vond dus niets en allebei de
rijen werden gepubliceerd.

WAAROM TITEL ÉN FOTO. Op de titel alleen zou het misgaan: hij heeft acht
verschillende dameslederhosen die allemaal "Lederhosen dames" heten en die moeten
allemaal los te koop kunnen staan. Alle acht hebben eigen foto's. De echte
dubbelen delen een foto-adres letterlijk. Gemeten op zijn 1.319 artikelen:
45 paren met dezelfde titel én een gedeelde foto, geen van de acht lederhosen
erbij, en 12 paren die op dat moment allebei live op Marktplaats stonden.

De gegevens hieronder zijn zijn echte rijen (titels, prijzen, foto-adressen
ingekort).
"""
import pytest

from backend.services.crosslist import _zelfde_artikel_al_online
from backend.services.tweelingen import familie_ids


class NepTabel:
    def __init__(self, db, naam):
        self.db, self.naam, self.filters = db, naam, []

    def select(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    def eq(self, kolom, waarde):
        self.filters.append(("eq", kolom, waarde))
        return self

    def in_(self, kolom, waarden):
        self.filters.append(("in", kolom, list(waarden)))
        return self

    def or_(self, *_a, **_k):
        # De familiecontrole gebruikt een or_-patroon op sku/titel. Toons rijen
        # dragen geen nummering, dus die vraag levert bij hem niets op.
        self.filters.append(("or", None, None))
        return self

    def execute(self):
        rijen = self.db.data[self.naam]
        for soort, kolom, waarde in self.filters:
            if soort == "eq":
                rijen = [r for r in rijen if r.get(kolom) == waarde]
            elif soort == "in":
                rijen = [r for r in rijen if r.get(kolom) in waarde]
            elif soort == "or":
                rijen = []
        return type("R", (), {"data": rijen})()


class NepDb:
    def __init__(self, **data):
        self.data = data

    def table(self, naam):
        return NepTabel(self, naam)


FOTO_TAPIJT = "https://img/9e-4bd6-8496-639bd127233f.jpg"
GEBRUIKER = "96e30080-ab81-47ac-8626-e8637f1e2a9e"


def _tapijten():
    """Vier importrijen van hetzelfde kleedje: zelfde titel, zelfde foto's.

    Nagemeten in zijn voorraad op 12-09-2026: van de zes artikelen die
    "Oosters tapijt klein 60/38 cm" heten dragen er vier LETTERLIJK dezelfde
    vijf foto-adressen (856414e9, 4ee0bcf8, dc3a75be, da553dc6, 232742b5). Dat
    zijn de dubbelen. De twee andere hebben elk zes eigen foto's en zijn twee
    andere kleedjes. Eerder stond hier één gedeelde foto van de twee; dat was
    ingekort en het gaf een verkeerd beeld van wat een dubbele is.
    """
    return [
        {"id": f"tap{i}", "user_id": GEBRUIKER, "sku": f"IMP-6CB890D{i}",
         "title": "Oosters tapijt klein 60/38 cm", "brand": None, "price": 20.0,
         "photo_urls": [FOTO_TAPIJT] + [f"https://img/tapijt-{n}.jpg" for n in range(4)]}
        for i in range(4)
    ]


def _lederhosen():
    """Acht ECHT verschillende dameslederhosen met dezelfde titel.

    Met zijn info-/maatplaatje erbij, want dat zet hij onder élke advertentie:
    het zit in 17 van zijn artikelen. Eén gedeeld plaatje van de tien maakt van
    acht broeken geen acht keer dezelfde broek.
    """
    return [
        {"id": f"led{i}", "user_id": GEBRUIKER, "sku": f"IMP-0170{i}F1D",
         "title": "Lederhosen dames", "brand": None, "price": prijs,
         "photo_urls": [FOTO_INFO] + [f"https://img/lederhosen-{i}-{n}.jpg"
                                      for n in range(9)]}
        for i, prijs in enumerate([40.0, 30.0, 25.0, 25.0, 35.0, 25.0, 30.0, 20.0])
    ]


def test_de_oude_controle_zag_toons_dubbelen_niet():
    """De voor-meting: zonder nummering in de titel en met eigen sku's vindt
    familie_ids alleen het artikel zelf, dus publiceren ging gewoon door."""
    tapijten = _tapijten()
    db = NepDb(items=tapijten, listings=[])
    familie = familie_ids(db, tapijten[0])
    assert familie == ["tap0"], familie


def test_dezelfde_titel_en_dezelfde_foto_telt_als_al_online():
    tapijten = _tapijten()
    db = NepDb(items=tapijten, listings=[
        {"item_id": "tap1", "platform": "marktplaats", "status": "active",
         "platform_listing_id": "m2406261856", "platform_listing_url": None},
    ])
    bezet = _zelfde_artikel_al_online(db, tapijten[0], ["marktplaats", "vinted"])
    assert list(bezet) == ["marktplaats"]
    assert bezet["marktplaats"]["platform_listing_id"] == "m2406261856"


def test_acht_verschillende_lederhosen_blijven_los_te_koop():
    leds = _lederhosen()
    db = NepDb(items=leds, listings=[
        {"item_id": f"led{i}", "platform": "marktplaats", "status": "active",
         "platform_listing_id": f"m{i}", "platform_listing_url": None}
        for i in range(1, 8)
    ])
    # Zeven van de acht staan al online. Toch mag de achtste gewoon geplaatst
    # worden: eigen foto's, dus een eigen voorwerp.
    assert _zelfde_artikel_al_online(db, leds[0], ["marktplaats"]) == {}


def test_een_verwijderde_advertentie_houdt_niets_tegen():
    tapijten = _tapijten()
    for status in ("delisted", "sold", "error"):
        db = NepDb(items=tapijten, listings=[
            {"item_id": "tap1", "platform": "marktplaats", "status": status,
             "platform_listing_id": "m1", "platform_listing_url": None},
        ])
        assert _zelfde_artikel_al_online(db, tapijten[0], ["marktplaats"]) == {}, status


def test_alleen_de_kanalen_waar_we_nu_naartoe_publiceren():
    tapijten = _tapijten()
    db = NepDb(items=tapijten, listings=[
        {"item_id": "tap1", "platform": "vinted", "status": "active",
         "platform_listing_id": "v1", "platform_listing_url": None},
    ])
    assert _zelfde_artikel_al_online(db, tapijten[0], ["marktplaats"]) == {}
    assert list(_zelfde_artikel_al_online(db, tapijten[0], ["vinted"])) == ["vinted"]


def test_een_artikel_zonder_fotos_blokkeert_nooit():
    # Zonder foto's is er niets te bewijzen, en dan is stilzwijgend blokkeren
    # erger dan een dubbele advertentie.
    tapijten = _tapijten()
    kaal = {**tapijten[0], "photo_urls": []}
    db = NepDb(items=tapijten, listings=[
        {"item_id": "tap1", "platform": "marktplaats", "status": "active",
         "platform_listing_id": "m1", "platform_listing_url": None},
    ])
    assert _zelfde_artikel_al_online(db, kaal, ["marktplaats"]) == {}


def test_het_artikel_zelf_telt_niet_mee():
    tapijt = _tapijten()[0]
    db = NepDb(items=[tapijt], listings=[
        {"item_id": tapijt["id"], "platform": "marktplaats", "status": "active",
         "platform_listing_id": "m1", "platform_listing_url": None},
    ])
    assert _zelfde_artikel_al_online(db, tapijt, ["marktplaats"]) == {}


def test_wat_de_familiecontrole_al_zag_wordt_niet_dubbel_geteld():
    tapijten = _tapijten()
    db = NepDb(items=tapijten, listings=[
        {"item_id": "tap1", "platform": "marktplaats", "status": "active",
         "platform_listing_id": "m1", "platform_listing_url": None},
    ])
    assert _zelfde_artikel_al_online(
        db, tapijten[0], ["marktplaats"], al_bekeken=["tap1"]) == {}


@pytest.mark.parametrize("kapot", ["items", "listings"])
def test_een_leesfout_laat_publiceren_gewoon_doorgaan(kapot):
    """De aanroeper vangt de fout af; hier bewaken we dat hij hem ook krijgt en
    dat er niet stilzwijgend 'geen dubbele' uit komt."""
    tapijten = _tapijten()

    class Stuk(NepDb):
        def table(self, naam):
            if naam == kapot:
                raise RuntimeError("verbinding weg")
            return super().table(naam)

    with pytest.raises(RuntimeError):
        Stuk(items=tapijten, listings=[]).table(kapot)
    db = Stuk(items=tapijten, listings=[])
    with pytest.raises(RuntimeError):
        _zelfde_artikel_al_online(db, tapijten[0], ["marktplaats"])


def test_de_controle_zit_echt_in_het_publicatiepad():
    """Een controle die niemand aanroept repareert niets."""
    from pathlib import Path
    bron = (Path(__file__).resolve().parents[1] / "backend" / "services"
            / "crosslist.py").read_text(encoding="utf-8")
    blok = bron.split("async def publish_to_platforms(")[1]
    blok = blok[:blok.index("api_platforms = ")]
    assert "_zelfde_artikel_al_online(" in blok
    # ... vóór het uitdelen van het werk, en de uitkomst gaat in dezelfde
    # `bezet`-lijst als de familiecontrole, zodat de verkoper één uitleg leest.
    assert "bezet.setdefault(p, rij)" in blok
