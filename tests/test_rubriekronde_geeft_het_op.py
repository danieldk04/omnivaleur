"""De nachtelijke rubriekronde mag niet eeuwig dezelfde vraag blijven stellen.

19-09-2026, gemeten. De ronde in backend/services/categorie_herstel.py las elke
nacht de 200 nieuwste artikelen zonder rubriek en stelde daar 200 modelvragen
over. Van die 200 waren er die nacht 175 PlayStation- en PSP-spellen, plus
autobanden en sneeuwkettingen, bijna allemaal van één verkoper.

De taxonomie in api/imports._TAXONOMY kent 247 rubrieken, verdeeld over dames,
heren, kinderen, unisex, sieraden, wonen, antiek en muziek. Er zit geen enkele
rubriek voor spellen, consoles, media of auto-onderdelen tussen. Het model kan
die artikelen dus niet plaatsen, en de controle in _classify_with_claude gooit
een verzonnen rubriek terecht weg. Elke nacht opnieuw, met hetzelfde resultaat.

Gemeten door de echte ronde te draaien met een nepmodel: 200 modelvragen,
1.927.627 tekens aan prompt, ongeveer 551.000 invoertokens, zo'n 0,55 dollar per
nacht alleen aan invoer. Ruim 17 dollar per maand.

Deze proef legt vier dingen vast. De eerste faalt op de oude code, de andere
drie zijn de vangrails die ervoor zorgen dat de besparing niets kapotmaakt:

1. Een artikel dat drie keer niets opleverde wordt niet meer gevraagd.
2. Een artikel dat wél ingedeeld kan worden wordt gewoon ingedeeld.
3. Ligt het model plat, dan verliest niemand een kans. Zonder deze regel zou
   een leeg API-tegoed in drie nachten de hele voorraad afschrijven.
4. Staan de kolommen er nog niet, dan draait de ronde precies zoals hiervoor.
"""
import asyncio
from datetime import datetime, timezone

import pytest

from backend.services import categorie_herstel as ch


class _Antwoord:
    def __init__(self, data):
        self.data = data


class _Tabel:
    """Genoeg PostgREST om deze ronde na te bootsen, niet meer."""

    def __init__(self, db):
        self._db = db
        self._leeg_rubriek = False
        self._lt = None
        self._gte = None
        self._eq = {}
        self._in = None
        self._limit = None
        self._update = None

    def select(self, velden, *_a, **_k):
        # Een kolom opvragen die niet bestaat is precies wat PostgREST weigert.
        for veld in velden.split(","):
            if veld.strip() not in self._db.kolommen:
                raise RuntimeError(
                    f'column items.{veld.strip()} does not exist')
        return self

    def or_(self, expr):
        if "category" in expr:
            self._leeg_rubriek = True
        return self

    def lt(self, kolom, waarde):
        if kolom not in self._db.kolommen:
            raise RuntimeError(f"column items.{kolom} does not exist")
        self._lt = (kolom, waarde)
        return self

    def gte(self, kolom, waarde):
        if kolom not in self._db.kolommen:
            raise RuntimeError(f"column items.{kolom} does not exist")
        self._gte = (kolom, waarde)
        return self

    def eq(self, kolom, waarde):
        self._eq[kolom] = waarde
        return self

    def in_(self, kolom, waarden):
        self._in = (kolom, list(waarden))
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def update(self, patch):
        self._update = patch
        return self

    def _treffers(self):
        uit = []
        for rij in self._db.rijen:
            if self._leeg_rubriek and str(rij.get("category") or "").strip():
                continue
            if self._lt and not (int(rij.get(self._lt[0]) or 0) < self._lt[1]):
                continue
            if self._gte and not (int(rij.get(self._gte[0]) or 0) >= self._gte[1]):
                continue
            if any(rij.get(k) != v for k, v in self._eq.items()):
                continue
            if self._in and rij.get(self._in[0]) not in self._in[1]:
                continue
            uit.append(rij)
        return uit

    def execute(self):
        treffers = self._treffers()
        if self._update is not None:
            for rij in treffers:
                rij.update(self._update)
                # ZO DOET DE ECHTE DATABASE HET (19-09-2026, nagemeten).
                # items zet updated_at bij elke schrijfactie op de systeemtijd,
                # ook bij die van de rubriekteller zelf. De eerste versie van
                # deze nabootsing deed dat niet, en juist daardoor zag een
                # kapotte herkansregel er hier gezond uit.
                if "updated_at" in self._db.kolommen:
                    rij["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._db.schrijfacties.append((self._update, [r["id"] for r in treffers]))
            return _Antwoord(treffers)
        if self._limit is not None:
            treffers = treffers[:self._limit]
        return _Antwoord([dict(r) for r in treffers])


class _DB:
    def __init__(self, rijen, kolommen):
        self.rijen = rijen
        self.kolommen = set(kolommen)
        self.schrijfacties = []

    def table(self, _naam):
        return _Tabel(self)


BASISKOLOMMEN = ["id", "title", "description", "brand", "category", "gender",
                 "color", "user_id", "created_at", "updated_at"]
NIEUWE_KOLOMMEN = BASISKOLOMMEN + ["rubriek_pogingen", "rubriek_gepoogd_op",
                                   "rubriek_gevraagd_over"]


def _artikel(id_, titel, **extra):
    rij = {"id": id_, "title": titel, "description": "", "brand": None,
           "category": None, "gender": None, "color": None,
           "user_id": "verkoper", "created_at": "2026-09-01T00:00:00+00:00",
           "updated_at": "2026-09-01T00:00:00+00:00",
           "rubriek_pogingen": 0, "rubriek_gepoogd_op": None,
           "rubriek_gevraagd_over": None}
    rij.update(extra)
    return rij


def _draai(monkeypatch, db, antwoorden):
    """Draai de ronde met een nepmodel. `antwoorden` is titel -> uitkomst."""
    gevraagd = []

    async def _nep_model(titel, omschrijving, merk=None):
        gevraagd.append(titel)
        return antwoorden.get(titel) or {}

    import backend.api.imports as imports_mod
    monkeypatch.setattr(imports_mod, "_infer_attributes_smart", _nep_model)
    monkeypatch.setattr(ch, "get_db", lambda: db)
    uit = asyncio.run(ch.herstel_rubrieken())
    return gevraagd, uit


def test_na_drie_lege_nachten_wordt_er_niet_meer_gevraagd(monkeypatch):
    """DE KERN. Op de oude code wordt dit spel elke nacht opnieuw gevraagd."""
    db = _DB([
        _artikel("spel", "Gran Turismo Sony PSP FR", rubriek_pogingen=3,
                 rubriek_gepoogd_op="2026-09-18T03:00:00+00:00",
                 rubriek_gevraagd_over=ch._tekstvinger(
                     {"title": "Gran Turismo Sony PSP FR",
                      "description": "", "brand": None})),
        _artikel("jas", "Wollen winterjas dames maat M"),
    ], NIEUWE_KOLOMMEN)

    gevraagd, uit = _draai(monkeypatch, db, {
        "Wollen winterjas dames maat M": {"category": "dames jassen",
                                          "gender": "dames"},
    })

    assert "Gran Turismo Sony PSP FR" not in gevraagd, (
        "het uitgeputte spel werd tóch weer aan het model voorgelegd")
    assert gevraagd == ["Wollen winterjas dames maat M"]
    assert uit["gevuld"] == 1


def test_een_artikel_dat_wel_kan_wordt_gewoon_ingedeeld(monkeypatch):
    """De besparing mag geen enkele echte indeling kosten."""
    db = _DB([_artikel("jas", "Wollen winterjas dames maat M")], NIEUWE_KOLOMMEN)

    gevraagd, uit = _draai(monkeypatch, db, {
        "Wollen winterjas dames maat M": {"category": "dames jassen",
                                          "gender": "dames", "color": "zwart"},
    })

    assert gevraagd == ["Wollen winterjas dames maat M"]
    assert uit == {"gelezen": 1, "gevuld": 1, "leeg_gebleven": 0, "mislukt": 0}
    assert db.rijen[0]["category"] == "dames jassen"
    assert db.rijen[0]["rubriek_pogingen"] == 0, "een geslaagde indeling telt geen poging"


def test_drie_lege_nachten_kosten_precies_drie_kansen(monkeypatch):
    """Na drie nachten is het op, geen nacht eerder."""
    db = _DB([
        _artikel("spel", "Fifa 12 Playstation 3 PS3"),
        _artikel("jas", "Wollen winterjas dames maat M"),
    ], NIEUWE_KOLOMMEN)
    lukt = {"Wollen winterjas dames maat M": {"category": "dames jassen"}}

    for nacht in (1, 2, 3):
        # de jas is na nacht 1 ingedeeld, dus zet hem terug zodat er elke nacht
        # iets slaagt en de storingsrem niet aanslaat
        db.rijen[1]["category"] = None
        gevraagd, _ = _draai(monkeypatch, db, lukt)
        assert "Fifa 12 Playstation 3 PS3" in gevraagd, (
            f"nacht {nacht}: het spel verdient deze kans nog")
        assert db.rijen[0]["rubriek_pogingen"] == nacht

    db.rijen[1]["category"] = None
    gevraagd, _ = _draai(monkeypatch, db, lukt)
    assert "Fifa 12 Playstation 3 PS3" not in gevraagd, (
        "nacht 4: de kansen waren op")


def test_een_storing_kost_niemand_een_kans(monkeypatch):
    """DE BELANGRIJKSTE VANGRAIL.

    Op 19-09 was het API-tegoed op en kwam elke vraag leeg terug. Zonder deze
    regel zouden drie zulke nachten de hele voorraad definitief afschrijven,
    inclusief artikelen die prima in te delen zijn.
    """
    db = _DB([
        _artikel("jas", "Wollen winterjas dames maat M"),
        _artikel("broek", "Levi's 501 spijkerbroek heren W32"),
    ], NIEUWE_KOLOMMEN)

    for _ in range(3):
        gevraagd, uit = _draai(monkeypatch, db, {})       # model geeft niets terug
        assert len(gevraagd) == 2

    assert uit["gevuld"] == 0
    for rij in db.rijen:
        assert rij["rubriek_pogingen"] == 0, (
            "een storing werd als uitkomst geteld en kostte dit artikel zijn kansen")

    # en zodra het model weer werkt, wordt het gewoon ingedeeld
    gevraagd, uit = _draai(monkeypatch, db, {
        "Wollen winterjas dames maat M": {"category": "dames jassen"},
        "Levi's 501 spijkerbroek heren W32": {"category": "heren jeans"},
    })
    assert uit["gevuld"] == 2


def test_bewerkte_tekst_geeft_nieuwe_kansen(monkeypatch):
    """Vult de verkoper de titel aan, dan is het een andere vraag."""
    db = _DB([
        _artikel("kleed", "Vloerkleed perzisch 200x300 wol", rubriek_pogingen=3,
                 rubriek_gepoogd_op="2026-09-18T03:00:00+00:00",
                 updated_at="2026-09-19T10:00:00+00:00",
                 # hier vroegen we over, en dat is niet meer wat er nu staat
                 rubriek_gevraagd_over=ch._tekstvinger(
                     {"title": "Kleed", "description": "", "brand": None})),
        _artikel("jas", "Wollen winterjas dames maat M"),
    ], NIEUWE_KOLOMMEN)

    gevraagd, _ = _draai(monkeypatch, db, {
        "Wollen winterjas dames maat M": {"category": "dames jassen"},
    })

    assert "Vloerkleed perzisch 200x300 wol" in gevraagd, (
        "het artikel is na de laatste poging bewerkt en verdient een nieuwe beoordeling")


def test_een_aanraking_zonder_tekstwijziging_geeft_geen_nieuwe_kansen(monkeypatch):
    """DE VALSTRIK DIE DE HELE BESPARING BIJNA NUL MAAKTE (19-09-2026).

    De items-tabel zet updated_at bij elke schrijfactie op de systeemtijd, ook
    bij die van de rubriekteller zelf. Een regel die op updated_at afgaat ziet
    de ronde zijn eigen schrijfactie dus aan voor een bewerking door de verkoper
    en geeft de volgende nacht iedereen zijn kansen terug.

    Hetzelfde geldt voor een prijswijziging of een nieuwe foto: die raken het
    artikel aan, maar veranderen niets aan de vraag die het model krijgt.
    """
    tekst = {"title": "Need for Speed Playstation 2 PS2", "description": "",
             "brand": None}
    db = _DB([
        _artikel("spel", tekst["title"], rubriek_pogingen=3,
                 rubriek_gepoogd_op="2026-09-18T03:00:00+00:00",
                 # ruim na de laatste poging aangeraakt, maar de tekst is gelijk
                 updated_at="2026-09-19T11:30:00+00:00",
                 rubriek_gevraagd_over=ch._tekstvinger(tekst)),
        _artikel("jas", "Wollen winterjas dames maat M"),
    ], NIEUWE_KOLOMMEN)

    gevraagd, _ = _draai(monkeypatch, db, {
        "Wollen winterjas dames maat M": {"category": "dames jassen"},
    })

    assert tekst["title"] not in gevraagd, (
        "het artikel werd alleen aangeraakt, de vraag aan het model is "
        "letterlijk dezelfde en het antwoord dus ook")
    assert db.rijen[0]["rubriek_pogingen"] == 3


def test_de_besparing_houdt_nacht_na_nacht_stand(monkeypatch):
    """Tien nachten achter elkaar, precies zoals het in productie loopt.

    Deze proef valt om op de versie die op updated_at besliste: die gaf het spel
    elke nacht zijn kansen terug, omdat de tellerschrijfactie van de vorige nacht
    updated_at had verzet. Dan zijn het 10 modelvragen in plaats van 3.
    """
    db = _DB([
        _artikel("spel", "Gran Turismo 5 Playstation 3"),
        _artikel("jas", "Wollen winterjas dames maat M"),
    ], NIEUWE_KOLOMMEN)
    lukt = {"Wollen winterjas dames maat M": {"category": "dames jassen"}}

    gevraagd_over_het_spel = 0
    for _ in range(10):
        db.rijen[1]["category"] = None       # elke nacht slaagt er iets
        gevraagd, _ = _draai(monkeypatch, db, lukt)
        gevraagd_over_het_spel += gevraagd.count("Gran Turismo 5 Playstation 3")

    assert gevraagd_over_het_spel == 3, (
        f"het spel kostte {gevraagd_over_het_spel} modelvragen in tien nachten, "
        f"er waren er drie afgesproken")


def test_zonder_de_kolommen_verandert_er_niets(monkeypatch):
    """De code mag live staan vóór de migratie zonder iets te veranderen."""
    db = _DB([
        _artikel("spel", "Gran Turismo Sony PSP FR"),
        _artikel("jas", "Wollen winterjas dames maat M"),
    ], BASISKOLOMMEN)
    for rij in db.rijen:                      # de kolommen bestaan simpelweg niet
        rij.pop("rubriek_pogingen", None)
        rij.pop("rubriek_gepoogd_op", None)
        rij.pop("rubriek_gevraagd_over", None)

    gevraagd, uit = _draai(monkeypatch, db, {
        "Wollen winterjas dames maat M": {"category": "dames jassen"},
    })

    assert sorted(gevraagd) == ["Gran Turismo Sony PSP FR",
                                "Wollen winterjas dames maat M"]
    assert uit == {"gelezen": 2, "gevuld": 1, "leeg_gebleven": 1, "mislukt": 0}
    assert all("rubriek_pogingen" not in patch
               for patch, _ in db.schrijfacties), "er werd naar een kolom geschreven die niet bestaat"


def test_de_taxonomie_kent_geen_rubriek_voor_auto_onderdelen():
    """De aanname onder deze hele wijziging, vastgelegd zodat hij niet wegdrijft.

    Komt er ooit wél een rubriek voor auto-onderdelen of films bij, dan valt deze
    proef om en hoort iemand opnieuw te kijken of die artikelen nog moeten worden
    afgeschreven.

    24-09-2026: games, telefoons en audio/tv/foto zitten nu wél in de import.
    Nagekeken: op dat moment stond geen enkel artikel op 3 pogingen (0 van 370
    zonder rubriek), dus niemand was al afgeschreven; de 162 met 1 of 2 pogingen
    krijgen vanzelf de nieuwe takken voorgelegd.
    """
    from backend.api.imports import _TAXONOMY

    alle = [c.lower() for cats in _TAXONOMY.values() for c in cats]
    # Let op: "band" staat er niet bij, want "sieraden armbanden" en "muziek
    # orkestbanden" bevatten dat woord terwijl ze niets met autobanden te maken
    # hebben. Alleen woorden die eenduidig zijn.
    for woord in ("autoband", "sneeuwketting", "velgen", "dvd film", "blu-ray film"):
        assert not any(woord in c for c in alle), (
            f'er bestaat nu wél een rubriek met "{woord}" erin')
