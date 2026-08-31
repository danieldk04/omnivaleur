"""De verkoopcontrole werkt een wachtrij af in plaats van elke ronde alles.

WAAROM DIT ER IS (31-08-2026)
Op 31-08-2026 zette Supabase het hele project op slot: 402 Payment Required,
verkeer 437% van het gratis plan. Inloggen gaf 503, de blog 500 — de app lag
eruit voor iedereen. Bij 24 actieve gebruikers komt dat verkeer niet van
bezoekers; het kwam van onze eigen lussen.

De duurste was deze. `poll_platform_statuses` haalde ELKE ronde alle actieve
advertenties op (gemeten 27-08: 4.751) en liep ze daarna één voor één langs met
een netwerkaanroep per stuk. Elke vijf minuten, 288 keer per dag. Dat is niet
alleen duur, het werkte ook niet: 4.751 aanroepen achter elkaar duren veel
langer dan vijf minuten, dus wat achteraan de lijst stond werd nooit bereikt.

Deze proef draait de echte functie tegen een nagemaakte database en legt drie
dingen vast die, als ze wegvallen, het project opnieuw op slot zetten:

  1. er wordt alleen opgehaald wat aan de beurt is, met een dak erop;
  2. een advertentie die niet nagekeken kón worden krijgt tóch een stempel —
     anders staat hij morgen weer vooraan en komt de rest nooit aan bod;
  3. hetzelfde geldt voor een advertentie waarvan de eigenaar geen koppeling
     heeft: die wordt overgeslagen, maar niet vergeten.
"""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import polling  # noqa: E402


# ── een nagemaakte Supabase-client ───────────────────────────────────────────
# Genoeg om de kettingen te volgen die polling.py bouwt, en om achteraf te
# kunnen zien wát er gevraagd en geschreven is.

class _Antwoord:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters: dict = {}
        self.kolommen = ""
        self.limiet = None
        self.volgorde = None
        self.update_velden = None

    # bouwstenen
    def select(self, kolommen):
        self.kolommen = kolommen
        return self

    def eq(self, kolom, waarde):
        self.filters[f"eq:{kolom}"] = waarde
        return self

    def in_(self, kolom, waarden):
        self.filters[f"in:{kolom}"] = list(waarden)
        return self

    def or_(self, uitdrukking):
        self.filters["or"] = uitdrukking
        return self

    def order(self, kolom, desc=False, nullsfirst=False):
        self.volgorde = (kolom, desc, nullsfirst)
        return self

    def limit(self, n):
        self.limiet = n
        return self

    def update(self, velden):
        self.update_velden = dict(velden)
        return self

    # uitvoeren
    def execute(self):
        self.db.gevraagd.append(self)
        if self.update_velden is not None:
            self.db.geschreven.append(self)
            for rij in self.db.tabellen.get(self.tabel, []):
                if self._raakt(rij):
                    rij.update(self.update_velden)
            return _Antwoord([])
        rijen = [r for r in self.db.tabellen.get(self.tabel, []) if self._raakt(r)]
        if self.limiet is not None:
            rijen = rijen[:self.limiet]
        return _Antwoord([dict(r) for r in rijen])

    def _raakt(self, rij) -> bool:
        for sleutel, waarde in self.filters.items():
            soort, _, kolom = sleutel.partition(":")
            if soort == "eq" and rij.get(kolom) != waarde:
                return False
            if soort == "in" and rij.get(kolom) not in waarde:
                return False
            if soort == "or":
                # alleen de vorm die polling.py gebruikt: nog nooit nagekeken,
                # of langer geleden dan de grens.
                grens = waarde.split("last_checked.lt.", 1)[1]
                gezien = rij.get("last_checked")
                if gezien is not None and str(gezien) >= grens:
                    return False
        return True


class _Db:
    def __init__(self, tabellen):
        self.tabellen = tabellen
        self.gevraagd: list = []
        self.geschreven: list = []

    def table(self, naam):
        return _Query(self, naam)


def _opzet(listings, koppelingen=("gebruiker-1",)):
    return _Db({
        "listings": listings,
        "items": [{"id": l["item_id"], "user_id": l.get("_eigenaar", "gebruiker-1")}
                  for l in listings],
        "platform_credentials": [
            {"user_id": u, "platform": "marktplaats", "token": "x" * 50}
            for u in koppelingen
        ],
    })


def _listing(nr, last_checked, eigenaar="gebruiker-1"):
    return {"id": f"l{nr}", "item_id": f"i{nr}", "platform": "marktplaats",
            "platform_listing_id": f"mp{nr}", "not_found_count": 0,
            "status": "active", "last_checked": last_checked,
            "_eigenaar": eigenaar}


class _NepPlatform:
    def __init__(self, uitkomst="active"):
        self.uitkomst, self.gevraagd = uitkomst, []

    async def get_listing_status(self, listing_id, credentials):
        self.gevraagd.append(listing_id)
        if isinstance(self.uitkomst, Exception):
            raise self.uitkomst
        return self.uitkomst


@pytest.fixture
def omgeving(monkeypatch):
    def zet(db, platform):
        monkeypatch.setattr(polling, "get_db", lambda: db)
        monkeypatch.setattr(polling, "get_platform", lambda naam: platform)

        async def _niets(*a, **k):
            return None
        monkeypatch.setattr(polling, "handle_item_sold", _niets)
    return zet


# ── 1. alleen wat aan de beurt is ────────────────────────────────────────────

def test_een_advertentie_die_net_is_nagekeken_blijft_deze_ronde_liggen(omgeving):
    """De kern van de reparatie. Wie net is nagekeken kost deze ronde niets —
    geen rij uit de database en geen netwerkaanroep."""
    net_gezien = "2026-08-31T12:00:00+00:00"        # ver binnen het uur
    lang_geleden = "2026-08-01T00:00:00+00:00"
    db = _opzet([_listing(1, net_gezien), _listing(2, lang_geleden),
                 _listing(3, None)])
    platform = _NepPlatform()
    omgeving(db, platform)

    asyncio.run(polling.poll_platform_statuses())

    # nummer 1 is met rust gelaten; 2 (oud) en 3 (nooit) zijn nagekeken.
    assert sorted(platform.gevraagd) == ["mp2", "mp3"]


def test_er_komen_er_nooit_meer_dan_het_dak_in_een_ronde(omgeving):
    """Zonder dak loopt een ronde alsnog tientallen minuten en begint de
    volgende overnieuw met dezelfde lijst."""
    db = _opzet([_listing(n, None) for n in range(polling.PER_RONDE + 25)])
    platform = _NepPlatform()
    omgeving(db, platform)

    asyncio.run(polling.poll_platform_statuses())

    assert len(platform.gevraagd) == polling.PER_RONDE


def test_de_oudste_gaat_voor_en_wie_nog_nooit_is_gezien_gaat_daar_weer_voor():
    """De wachtrij moet eerlijk zijn, anders verhongert de staart alsnog."""
    bron = (ROOT / "backend" / "services" / "polling.py").read_text(encoding="utf-8")
    assert '.order("last_checked", desc=False, nullsfirst=True)' in bron
    assert f".limit(PER_RONDE)" in bron


# ── 2. een mislukte controle blokkeert de rij niet ───────────────────────────

def test_een_advertentie_die_niet_bereikbaar_is_krijgt_toch_een_stempel(omgeving):
    """DE VALKUIL. Zou het stempel alleen bij een geslaagde controle gezet
    worden, dan blijft een kapotte advertentie eeuwig bovenaan de wachtrij
    staan en komt de rest van de voorraad nooit meer aan de beurt."""
    db = _opzet([_listing(1, None)])
    platform = _NepPlatform(RuntimeError("platform ligt eruit"))
    omgeving(db, platform)

    asyncio.run(polling.poll_platform_statuses())

    assert db.tabellen["listings"][0]["last_checked"] is not None, \
        "een mislukte controle liet geen stempel achter — de wachtrij loopt vast"


def test_de_verkoopcontrole_schrijft_hooguit_een_keer_per_advertentie(omgeving):
    """Drie losse updates per advertentie was drie keer zoveel verkeer als
    nodig, elke ronde opnieuw."""
    db = _opzet([_listing(1, None)])
    platform = _NepPlatform("not_found")
    omgeving(db, platform)

    asyncio.run(polling.poll_platform_statuses())

    op_listings = [q for q in db.geschreven if q.tabel == "listings"]
    assert len(op_listings) == 1
    assert op_listings[0].update_velden["not_found_count"] == 1
    assert "last_checked" in op_listings[0].update_velden


def test_twee_keer_niet_gevonden_is_pas_afgemeld(omgeving):
    """Deze drempel bestond al en moet blijven: één 404 is vaak een verlopen
    sessie, en daarop afmelden haalde eerder levende advertenties offline."""
    db = _opzet([_listing(1, None)])
    db.tabellen["listings"][0]["not_found_count"] = 1
    platform = _NepPlatform("not_found")
    omgeving(db, platform)

    asyncio.run(polling.poll_platform_statuses())

    assert db.tabellen["listings"][0]["status"] == "delisted"


# ── 3. overgeslagen is niet vergeten ─────────────────────────────────────────

def test_een_advertentie_zonder_koppeling_wordt_gestempeld_en_niet_bevraagd(omgeving):
    """Zonder stempel staat deze elke ronde opnieuw vooraan en duwt hij de
    advertenties weg die wél te controleren zijn — met een dak op de ronde is
    dat genoeg om de verkoopcontrole helemaal stil te leggen."""
    db = _opzet([_listing(1, None, eigenaar="gebruiker-zonder-koppeling"),
                 _listing(2, None)],
                koppelingen=("gebruiker-1",))
    platform = _NepPlatform()
    omgeving(db, platform)

    asyncio.run(polling.poll_platform_statuses())

    assert platform.gevraagd == ["mp2"]
    zonder = [r for r in db.tabellen["listings"] if r["id"] == "l1"][0]
    assert zonder["last_checked"] is not None, \
        "de overgeslagen advertentie blijft eeuwig aan de beurt"


def test_koppelingen_worden_alleen_voor_de_eigenaren_van_deze_ronde_gehaald(omgeving):
    """`platform_credentials` bevat tokens en cookies en is de dikste tabel die
    we hebben. Die in zijn geheel ophalen terwijl er één eigenaar meedoet is
    precies het verkeer dat we kwijt wilden."""
    db = _opzet([_listing(1, None)], koppelingen=("gebruiker-1", "gebruiker-2",
                                                  "gebruiker-3"))
    platform = _NepPlatform()
    omgeving(db, platform)

    asyncio.run(polling.poll_platform_statuses())

    creds = [q for q in db.gevraagd if q.tabel == "platform_credentials"]
    assert creds, "er is niet naar koppelingen gevraagd"
    assert creds[0].filters.get("in:user_id") == ["gebruiker-1"]
