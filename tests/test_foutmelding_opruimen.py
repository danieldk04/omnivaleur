"""Een rode balk moet weg kunnen.

WAAROM DIT ER IS (03-09-2026, Egbert Brouwer / papas-plectrums)

Zijn wachtrij voor 2dehands werd terecht teruggenomen: 279 opdrachten van elk
drie en een halve minuut zijn zestien uur waarin hij verder niets kan. Maar elke
teruggenomen opdracht liet een rode balk achter op de artikelrij, en zo'n balk
verdween alleen door alsnog met succes te publiceren — precies wat er niet
lukte. Hij keek dus tegen zes bladzijden rood aan zonder één knop die ergens
heen leidde: "Ik kom niet verder."

Een advertentie die nooit is aangemaakt is geen mislukte advertentie maar een
niet-geplaatste. Dus verdwijnt zo'n rij hier echt, en gaat het artikel gewoon
terug naar "nog plaatsen".
"""
import re
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import listings as api  # noqa: E402


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters, self.join_filters = {}, {}, {}
        self.op, self.velden = None, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, velden): self.op, self.velden = "update", velden; return self
    def delete(self): self.op = "delete"; return self

    def eq(self, k, v):
        # "items.user_id" is de gekoppelde vraag: geef de advertenties wáár het
        # artikel van deze verkoper is. Postgres kent die band zelf.
        (self.join_filters if "." in k else self.filters)[k] = v
        return self

    def in_(self, k, v): self.in_filters[k] = list(v); return self
    def order(self, *_a, **_k): return self
    def range(self, *_a, **_k): return self
    def limit(self, *_a, **_k): return self

    def _raak(self):
        bron = self.db.tabellen[self.tabel]
        rijen = [r for r in bron
                 if all(r.get(k) == v for k, v in self.filters.items())
                 and all(r.get(k) in v for k, v in self.in_filters.items())]
        for sleutel, waarde in self.join_filters.items():
            tabel, kolom = sleutel.split(".", 1)
            per_id = {r["id"]: r for r in self.db.tabellen[tabel]}
            rijen = [r for r in rijen
                     if (per_id.get(r.get("item_id")) or {}).get(kolom) == waarde]
        return rijen

    def execute(self):
        self.db.vragen += 1
        if self.op == "delete" and self.db.hik:
            self.db.hik = False
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        rijen = self._raak()
        if self.op == "delete" and self.tabel == "listings":
            # Zoals de echte database: `sync_events.listing_id` wijst met een
            # sleutel naar `listings` en heeft geen "on delete cascade". Staat
            # daar nog een regel, dan weigert Postgres de rij weg te gooien.
            geraakt = {r["id"] for r in rijen}
            if [g for g in self.db.tabellen.get("sync_events", [])
                    if g.get("listing_id") in geraakt]:
                raise RuntimeError('update or delete on table "listings" violates '
                                   'foreign key constraint "sync_events_listing_id_fkey"')
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        elif self.op == "delete":
            self.db.tabellen[self.tabel] = [r for r in self.db.tabellen[self.tabel] if r not in rijen]
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, **tabellen):
        self.tabellen = tabellen
        self.vragen = 0      # hoeveel keer de database is aangesproken
        self.hik = False     # laat de eerstvolgende delete de verbinding verliezen

    def table(self, naam): return _Q(self, naam)


def _opzet(monkeypatch, listings, aantal_items=5, echte_herkansing=False,
           gebeurtenissen=None):
    db = _DB(
        items=[{"id": f"i{i}", "user_id": "u"} for i in range(aantal_items)]
              + [{"id": "vreemd", "user_id": "ander"}],
        listings=listings,
        sync_events=list(gebeurtenissen or []),
    )
    monkeypatch.setattr(api, "get_db", lambda: db)
    monkeypatch.setattr(api, "fetch_all", lambda maak, *a, **k: maak().execute().data)
    if not echte_herkansing:
        monkeypatch.setattr(api, "execute_with_retry", lambda q, **k: q.execute())
    return db


def _mislukt(n, platform="2dehands", met_nummer=False):
    return [{"id": f"l{platform[:2]}{i}", "item_id": f"i{i}", "platform": platform, "status": "error",
             "error_message": "form never opened",
             "platform_listing_id": (f"m{i}" if met_nummer else None)} for i in range(n)]


def test_een_nooit_geplaatste_advertentie_verdwijnt_echt(monkeypatch):
    db = _opzet(monkeypatch, _mislukt(3))
    uit = api.clear_listing_errors({"platform": "2dehands"}, user_id="u")
    assert uit["cleared"] == 3 and uit["removed"] == 3
    # Geen rij meer, dus geen rode balk, dus het artikel staat weer op "nog plaatsen".
    assert db.tabellen["listings"] == []


def test_een_advertentie_met_nummer_blijft_bestaan(monkeypatch):
    """Zo'n nummer geeft het platform alleen terug als de advertentie er echt
    kwam. Die rij weggooien maakt de link kwijt die auto-delist later nodig heeft."""
    db = _opzet(monkeypatch, _mislukt(2, met_nummer=True))
    uit = api.clear_listing_errors({"platform": "2dehands"}, user_id="u")
    assert uit["cleared"] == 2 and uit["removed"] == 0
    assert len(db.tabellen["listings"]) == 2
    assert all(r["status"] == "active" and r["error_message"] is None
               for r in db.tabellen["listings"])


def test_alleen_het_gevraagde_kanaal(monkeypatch):
    """Marktplaats werkt bij hem wél. Daar mag niets van verdwijnen."""
    db = _opzet(monkeypatch, _mislukt(2) + _mislukt(2, platform="marktplaats"))
    api.clear_listing_errors({"platform": "2dehands"}, user_id="u")
    over = db.tabellen["listings"]
    assert len(over) == 2 and all(r["platform"] == "marktplaats" for r in over)


def test_een_enkel_artikel_laat_de_rest_staan(monkeypatch):
    db = _opzet(monkeypatch, _mislukt(3))
    uit = api.clear_listing_errors({"platform": "2dehands", "item_id": "i1"}, user_id="u")
    assert uit["cleared"] == 1
    assert sorted(r["item_id"] for r in db.tabellen["listings"]) == ["i0", "i2"]


def test_andermans_artikel_kan_niet(monkeypatch):
    _opzet(monkeypatch, _mislukt(1))
    with pytest.raises(api.HTTPException) as e:
        api.clear_listing_errors({"platform": "2dehands", "item_id": "vreemd"}, user_id="u")
    assert e.value.status_code == 404


def test_zonder_kanaal_doen_we_niets(monkeypatch):
    _opzet(monkeypatch, _mislukt(1))
    with pytest.raises(api.HTTPException) as e:
        api.clear_listing_errors({}, user_id="u")
    assert e.value.status_code == 400


def test_niets_te_wissen_is_geen_fout(monkeypatch):
    _opzet(monkeypatch, [])
    assert api.clear_listing_errors({"platform": "2dehands"}, user_id="u")["cleared"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# 04-09-2026 — Egbert: "Ik kan nu de knop zien, maar hij werkt niet."
#
# Op zijn scherm kwam "2dehands: Something went wrong on our side (code
# F1F7E7)". De twee proeven hieronder zetten de oude versie van deze functie
# (commit 4687587) onder dezelfde omstandigheden naast de nieuwe.

OUDE_COMMIT = "4687587"


def _oude_versie():
    """De echte oude functie uit git, niet een nagemaakte.

    Tegen HEAD proeven kan niet: de auto-push-hook commit werk in uitvoering
    onder "auto: update ...", dus HEAD bevat de reparatie al.
    """
    bron = subprocess.run(["git", "show", f"{OUDE_COMMIT}:backend/api/listings.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    stuk = re.search(r"\ndef clear_listing_errors\(.*?(?=\n@router)", bron, re.S)
    assert stuk, "de oude functie staat niet in die commit"
    # `Depends(...)` wordt bij het inlezen van de functie uitgevoerd; hier is
    # geen FastAPI, dus die twee namen zijn alleen nodig om de def te halen.
    ruimte: dict = {"HTTPException": api.HTTPException,
                    "Depends": lambda _f: None, "get_current_user": None}
    exec(compile(stuk.group(0), "<oud>", "exec"), ruimte)
    return ruimte["clear_listing_errors"], ruimte


def _draai_oud(db, body, user_id="u"):
    functie, ruimte = _oude_versie()
    ruimte["get_db"] = lambda: db
    ruimte["fetch_all"] = lambda maak, *a, **k: maak().execute().data
    return functie(body, user_id=user_id)


def test_een_weggevallen_verbinding_wordt_geen_foutcode(monkeypatch):
    """De twee deletes waren de enige onbeschermde stappen.

    Leesacties worden sinds 30-08 overal automatisch herkanst (zie
    backend/database.py), schrijfacties met opzet niet: een insert blind
    herhalen maakt een tweede advertentie. Maar een rij weggooien die al weg
    moet is niet gevaarlijk om nog eens te proberen — en zonder die herkansing
    werd één verbroken verbinding een naamloze 500 op zijn scherm.
    """
    db = _opzet(monkeypatch, _mislukt(3), echte_herkansing=True)
    db.hik = True
    uit = api.clear_listing_errors({"platform": "2dehands"}, user_id="u")
    assert uit["cleared"] == 3 and uit["removed"] == 3
    assert db.tabellen["listings"] == []

    # VOOR: precies dezelfde hik, oude code -> de fout vliegt omhoog en wordt
    # buiten de functie een "Something went wrong on our side (code ...)".
    db2 = _DB(items=[{"id": f"i{i}", "user_id": "u"} for i in range(5)], listings=_mislukt(3))
    db2.hik = True
    with pytest.raises(httpx.RemoteProtocolError):
        _draai_oud(db2, {"platform": "2dehands"})
    assert len(db2.tabellen["listings"]) == 3   # en er is niets opgeruimd


def test_een_vraag_in_plaats_van_negenentwintig(monkeypatch):
    """Bij 5.533 artikelen deed de oude weg 29 vragen; elke vraag is een kans
    dat de verbinding wegvalt. Gemeten op zijn echte gegevens: 7,8 seconden
    tegen 0,2 seconde, met exact dezelfde 304 rijen als uitkomst."""
    db = _opzet(monkeypatch, _mislukt(3), aantal_items=5533)
    api.clear_listing_errors({"platform": "2dehands"}, user_id="u")
    nieuw_aantal = db.vragen

    db2 = _DB(items=[{"id": f"i{i}", "user_id": "u"} for i in range(5533)],
              listings=_mislukt(3))
    _draai_oud(db2, {"platform": "2dehands"})
    oud_aantal = db2.vragen

    # Nieuw: één opzoekvraag plus de twee opruimstappen (gebeurtenissen, rijen).
    assert oud_aantal >= 29, f"oude weg deed maar {oud_aantal} vragen"
    assert nieuw_aantal <= 4, f"nieuwe weg doet er {nieuw_aantal}"


def test_gaat_het_toch_mis_dan_staat_er_wat(monkeypatch):
    """Een kale foutcode zegt de klant niets. Er hoort in het antwoord te staan
    wát er stukging, en dat er niets van het platform is weggehaald."""
    db = _opzet(monkeypatch, _mislukt(2), echte_herkansing=True)

    def altijd_stuk(q, **k):
        raise RuntimeError("database zegt nee")

    monkeypatch.setattr(api, "execute_with_retry", altijd_stuk)
    with pytest.raises(api.HTTPException) as e:
        api.clear_listing_errors({"platform": "2dehands"}, user_id="u")
    assert e.value.status_code == 500, "502/503 wordt door Cloudflare vervangen"
    assert "RuntimeError" in e.value.detail and "database zegt nee" in e.value.detail
    assert "Nothing was removed from 2dehands" in e.value.detail


# ─────────────────────────────────────────────────────────────────────────────
# 04-09-2026, tweede ronde — de klikproef op Daniels eigen account
#
# Hij klikte op "Clear all 13". Vier gingen weg (3 Facebook, 1 2dehands), negen
# niet (8 eBay, 1 Shopify), met op zijn scherm "The server took too long to
# respond (502)". Gemeten: aan precies die negen rijen hingen 21 regels in
# `sync_events`, aan de vier andere geen enkele. eBay en Shopify schrijven zo'n
# regel bij elke poging (`_log_event` in crosslist.py), de extensiekanalen niet.

def test_een_rij_met_gebeurtenissen_gaat_ook_weg(monkeypatch):
    listings = _mislukt(3)
    gebeurtenissen = [{"id": "g1", "listing_id": listings[0]["id"], "event_type": "error"},
                      {"id": "g2", "listing_id": listings[0]["id"], "event_type": "error"},
                      {"id": "g3", "listing_id": listings[2]["id"], "event_type": "error"}]
    db = _opzet(monkeypatch, listings, gebeurtenissen=gebeurtenissen)
    uit = api.clear_listing_errors({"platform": "2dehands"}, user_id="u")
    assert uit["cleared"] == 3 and uit["removed"] == 3
    assert db.tabellen["listings"] == []
    assert db.tabellen["sync_events"] == [], "de gebeurtenissen horen mee te verdwijnen"

    # VOOR: dezelfde rijen op de vorige versie -> de database weigert, en de
    # klant zag daardoor negen rode balken die niet weg te krijgen waren.
    db2 = _DB(items=[{"id": f"i{i}", "user_id": "u"} for i in range(5)],
              listings=_mislukt(3),
              sync_events=[dict(g) for g in gebeurtenissen])
    with pytest.raises(RuntimeError, match="foreign key"):
        _draai_oud(db2, {"platform": "2dehands"})
    assert len(db2.tabellen["listings"]) == 3


def test_gebeurtenissen_van_andere_advertenties_blijven(monkeypatch):
    listings = _mislukt(2)
    gebeurtenissen = [{"id": "g1", "listing_id": listings[0]["id"], "event_type": "error"},
                      {"id": "vreemd", "listing_id": "van-iemand-anders", "event_type": "sold"}]
    db = _opzet(monkeypatch, listings, gebeurtenissen=gebeurtenissen)
    api.clear_listing_errors({"platform": "2dehands"}, user_id="u")
    assert [g["id"] for g in db.tabellen["sync_events"]] == ["vreemd"]


def test_nooit_een_502_of_503_terug():
    """Cloudflare vervangt een 502 of 503 door zijn eigen HTML-foutpagina, dus
    de uitleg die wij meesturen bereikt de browser nooit. Dat is precies wat er
    bij de proef gebeurde: een fout die in een fractie van een seconde optrad
    kwam op het scherm als "de server duurde te lang". 500 komt wél door."""
    bron = (ROOT / "backend/api/listings.py").read_text(encoding="utf-8")
    stuk = bron.split("def clear_listing_errors(", 1)[1].split("\n@router", 1)[0]
    assert "status_code=502" not in stuk and "status_code=503" not in stuk
    assert "status_code=500" in stuk
