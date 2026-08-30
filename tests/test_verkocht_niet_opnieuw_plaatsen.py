"""Een verkocht artikel wordt nergens meer geplaatst, en verkopen worden op elk
kanaal opgemerkt.

Daniel, 30-08-2026: Omnivaleur herplaatste op Marktplaats terwijl het artikel al
verkocht was, en verkopen werden alleen op Vinted herkend.
"""
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[1]


class NepTabel:
    def __init__(self, db, naam):
        self.db, self.naam, self.filters, self.patch = db, naam, {}, None

    def select(self, *a, **kw): return self
    def order(self, *a, **kw): return self
    def limit(self, *a, **kw): return self
    def lte(self, *a, **kw): return self

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
        import types
        if self.patch is not None:
            self.db.updates.append((self.naam, dict(self.filters), self.patch))
            return types.SimpleNamespace(data=[])
        if self.naam == "listings":
            rijen = [r for r in self.db.listings
                     if r["item_id"] in self.filters.get("item_id", [])
                     and r["status"] == self.filters.get("status", r["status"])]
            return types.SimpleNamespace(data=rijen)
        if self.naam == "jobs":
            return types.SimpleNamespace(data=[])
        if self.naam == "items":
            return types.SimpleNamespace(data=[])
        return types.SimpleNamespace(data=[])


class NepDb:
    def __init__(self, listings):
        self.listings, self.updates = listings, []

    def table(self, naam): return NepTabel(self, naam)


def test_publicatie_van_een_verkocht_artikel_wordt_geannuleerd(monkeypatch):
    import backend.api.jobs as jobs

    db = NepDb([{"item_id": "i1", "platform": "vinted", "status": "sold"}])
    monkeypatch.setattr(jobs, "get_db", lambda: db)
    monkeypatch.setattr(jobs, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(jobs, "_recover_stale_claims", lambda *a, **kw: None)

    class NepJobsTabel(NepTabel):
        def execute(self):
            import types
            if self.patch is None and self.naam == "jobs" and "status" in self.filters:
                if self.filters.get("status") == "pending":
                    return types.SimpleNamespace(data=[{
                        "id": "j1", "item_id": "i1", "platform": "marktplaats",
                        "action": "create", "status": "pending",
                        "created_at": "2026-08-30T10:00:00+00:00", "payload": {},
                    }])
                return types.SimpleNamespace(data=[])
            return super().execute()

    db.table = lambda naam: NepJobsTabel(db, naam)

    uit = jobs.get_pending_jobs(
        request=type("R", (), {"headers": {}})(), platform="marktplaats", user_id="u1")

    assert uit == [], "een verkocht artikel mag nooit uitgedeeld worden"
    geannuleerd = [u for u in db.updates
                   if u[0] == "jobs" and u[2].get("status") == "cancelled"]
    assert geannuleerd, "de opdracht hoort geannuleerd te worden, niet blijven hangen"
    assert "sold on vinted" in geannuleerd[0][2]["result"]["cancelled"].lower()


def test_de_verversronde_slaat_verkochte_artikelen_over():
    bron = (WORTEL / "backend/services/crosslist.py").read_text()
    kop = bron.index("async def relist_expiring_marktplaats")
    blok = bron[kop:kop + 12000]
    assert '.eq("status", "sold")' in blok


def test_verkoopcontrole_dekt_ook_ebay_en_etsy():
    from backend.services.polling import POLL_PLATFORMS
    assert {"marktplaats", "2dehands", "ebay", "etsy"} <= POLL_PLATFORMS


def test_werkvenster_wordt_altijd_geminimaliseerd():
    """Op macOS weigert Chrome state:minimized bij het aanmaken; zonder de losse
    update popte er elke ronde een Marktplaats-venster open."""
    bron = (WORTEL / "extension/background.js").read_text()
    kop = bron.index("async function openWorkerTabInner")
    blok = bron[kop:bron.index("async function processJob")]
    assert blok.count('chrome.windows.update(w.id, { state: "minimized", focused: false })') == 2


# ── Tweelingen: dezelfde trui, twee rijen in de voorraad ────────────────────

def test_nummer_uit_titel_en_sku():
    from backend.services.tweelingen import nummer_van
    assert nummer_van({"title": "(1237) Navy Suitsupply Half Zip"}) == "1237"
    assert nummer_van({"title": "Navy Suitsupply", "sku": "AB-12"}) == "ab-12"
    assert nummer_van({"title": "Navy Suitsupply"}) == ""
    # Niets waar een zoekopdracht op kan stukgaan.
    assert nummer_van({"title": "(1237, 1238) Twee truien"}) == ""


def test_familie_zoekt_op_nummer_en_sku():
    from backend.services.tweelingen import familie_ids

    gezien = {}

    class T:
        def select(self, *a, **kw): return self
        def eq(self, k, v): gezien[k] = v; return self
        def or_(self, expr): gezien["or"] = expr; return self
        def limit(self, n): return self
        def execute(self):
            import types
            return types.SimpleNamespace(data=[{"id": "b"}, {"id": "a"}])

    class D:
        def table(self, naam): return T()

    ids = familie_ids(D(), {"id": "a", "user_id": "u1", "title": "(1237) Navy"})
    assert ids == ["a", "b"]
    assert gezien["or"] == "sku.eq.1237,title.ilike.(1237)%"


def test_tweeling_met_dezelfde_titel_krijgt_wel_een_koppeling():
    """Twee rijen met hetzelfde nummer én dezelfde titel zijn hetzelfde product.
    Zonder dit bleef een live Vinted-advertentie ongekoppeld en zei het dashboard
    dat het item daar niet stond."""
    from backend.api.jobs import _unique_index

    titels = {"i2": "navy suitsupply half zip", "i1": "navy suitsupply half zip"}
    index = _unique_index([("1237", "i2"), ("1237", "i1")], titels)
    assert index["1237"] == "i1", "altijd dezelfde keuze, anders wisselt de koppeling per ronde"


def test_verschillende_producten_met_hetzelfde_nummer_blijven_ongekoppeld():
    from backend.api.jobs import _unique_index

    titels = {"i1": "navy half zip", "i2": "rode broek"}
    assert _unique_index([("1237", "i1"), ("1237", "i2")], titels) == {}


def test_de_verkoopafhandeling_kijkt_naar_de_hele_familie():
    bron = (WORTEL / "backend/services/crosslist.py").read_text()
    kop = bron.index("async def handle_item_sold")
    blok = bron[kop:kop + 9000]
    assert "familie_ids" in blok and '.in_("item_id", familie)' in blok


def test_werkvenster_wordt_ook_na_openen_en_sluiten_klein_gehouden():
    bron = (WORTEL / "extension/background.js").read_text()
    assert "async function houdWerkvensterGeminimaliseerd" in bron
    kop = bron.index("async function maakWerkTabblad")
    assert "houdWerkvensterGeminimaliseerd" in bron[kop:kop + 600]
    kop2 = bron.index("function sluitWerkTabblad")
    assert "houdWerkvensterGeminimaliseerd" in bron[kop2:kop2 + 600]
