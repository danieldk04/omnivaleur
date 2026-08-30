"""Een mislukte verversing mag nooit als gelukt op het scherm komen.

WAT ER GEBEURDE (30-08-2026, account aertssen.pleun@gmail.com)
Zij ververste drie Vinted-advertenties. Alle drie mislukten bij de eerste stap:
de extensie kreeg de advertentie niet uit haar garderobe ("still in your wardrobe
after confirming delete"). Toch stond er daarna in het dashboard bij één van die
advertenties dat hij ververst was — teller op 1, geen foutmelding — terwijl er
niets was gebeurd en er ook niets meer stond te gebeuren.

Hoe dat kon, in volgorde:

1. Een verversing hoogt de teller op, zet de afkoelperiode van veertien dagen en
   snoept een dagquotum op zodra hij in de wachtrij staat — dus vóórdat er iets
   is gebeurd. Mislukt hij, dan geeft de foutafhandeling dat allemaal terug.
2. Bij een HERKANSING gebeurde dat niet. Die annuleerde de oude opdrachten, wiste
   de foutmelding, en botste daarna op de afkoelperiode die zijn eigen mislukte
   poging net had gezet: "This listing was refreshed 0d ago. Wait 14d more."
3. Wat overbleef: geen opdrachten, geen foutmelding, teller op 1. Het dashboard
   noemt dat een geslaagde verversing.

En een tweede, apart spoor: een herplaatsing waarvan de verwijdering was
GEANNULEERD bleef eeuwig "pending" staan te wachten op een verwijdering die nooit
meer zou lopen. Het scherm bleef melden "nieuwe advertentie over ~X min".
"""
import asyncio

import pytest

from backend.api import jobs as J


class _Bouwer:
    """Een minimale Supabase-bouwer die onthoudt wat er is gevraagd."""

    def __init__(self, tabel, log, antwoorden):
        self.tabel, self.log, self.antwoorden = tabel, log, antwoorden
        self.soort, self.velden, self.filters = "select", None, {}

    def select(self, *a, **kw):
        self.soort, self.kolommen = "select", (a[0] if a else "*")
        return self

    def update(self, velden):
        self.soort, self.velden = "update", velden
        return self

    def insert(self, velden):
        self.soort, self.velden = "insert", velden
        return self

    def eq(self, kolom, waarde):
        self.filters[kolom] = waarde
        return self

    def in_(self, kolom, waarden):
        self.filters[kolom] = list(waarden)
        return self

    def lte(self, *a, **kw):
        return self

    def order(self, *a, **kw):
        return self

    def limit(self, *a, **kw):
        return self

    def single(self):
        return self

    def execute(self):
        self.log.append({"tabel": self.tabel, "soort": self.soort,
                         "velden": self.velden, "filters": dict(self.filters)})
        data = self.antwoorden(self) if self.soort == "select" else []
        return type("R", (), {"data": data})()


class _DB:
    def __init__(self, antwoorden):
        self.log = []
        self._antwoorden = antwoorden

    def table(self, naam):
        return _Bouwer(naam, self.log, self._antwoorden)


ITEM, PLAT, USER = "item-1", "vinted", "user-1"
SNAPSHOT = {"day": "2026-08-30", "listing_id": "listing-1",
            "prior_refresh_count": 0, "prior_last_refreshed_at": None}


# ── 1. De herkansing draait de mislukte poging eerst terug ───────────────────

def _retry_opzet(monkeypatch, delete_status="error", refresh_werkt=True):
    def antwoorden(b):
        if b.tabel == "jobs" and b.filters.get("action") == "delete":
            return [{"status": delete_status, "payload": {"_refresh_rollback": SNAPSHOT}}]
        if b.tabel == "jobs" and isinstance(b.filters.get("action"), list):
            return [{"id": "oude-opdracht"}]      # de restanten van de mislukte poging
        return []

    db = _DB(antwoorden)
    monkeypatch.setattr(J, "get_db", lambda: db)

    teruggedraaid = []
    import backend.services.relist as R
    monkeypatch.setattr(R, "rollback_refresh", lambda rb, uid: teruggedraaid.append(rb))

    async def nep_refresh(item_id, platform, user_id, strategy):
        if not refresh_werkt:
            raise R.RefreshError("This listing was refreshed 0d ago. Wait 14d more.")
        return {"strategy": "relist", "status": "queued"}

    monkeypatch.setattr(R, "refresh_listing", nep_refresh)
    return db, teruggedraaid


def test_de_herkansing_geeft_de_afkoelperiode_eerst_terug(monkeypatch):
    db, teruggedraaid = _retry_opzet(monkeypatch)
    uit = asyncio.run(J.relist_retry({"item_id": ITEM, "platform": PLAT}, user_id=USER))
    assert uit["ok"] is True
    assert teruggedraaid == [SNAPSHOT], \
        "zonder dit botst de herkansing op de afkoelperiode van zijn eigen mislukte poging"


def test_een_geslaagde_verwijdering_wordt_niet_teruggedraaid(monkeypatch):
    """Was de advertentie écht van het platform gehaald, dan is de verversing
    echt gebeurd en mag de teller niet terug."""
    db, teruggedraaid = _retry_opzet(monkeypatch, delete_status="done")
    asyncio.run(J.relist_retry({"item_id": ITEM, "platform": PLAT}, user_id=USER))
    assert teruggedraaid == []


def test_een_geweigerde_herkansing_laat_de_foutmelding_staan(monkeypatch):
    db, _ = _retry_opzet(monkeypatch, refresh_werkt=False)
    with pytest.raises(Exception) as fout:
        asyncio.run(J.relist_retry({"item_id": ITEM, "platform": PLAT}, user_id=USER))
    assert "14d" in str(getattr(fout.value, "detail", fout.value))

    gewist = [r for r in db.log
              if r["tabel"] == "listings" and r["soort"] == "update"
              and "error_message" in (r["velden"] or {})
              and (r["velden"] or {}).get("error_message") is None]
    assert not gewist, \
        "de foutmelding wissen terwijl er geen nieuwe poging staat = 'gelukt' melden"


def test_na_een_geslaagde_herkansing_gaat_de_foutmelding_wel_weg(monkeypatch):
    db, _ = _retry_opzet(monkeypatch)
    asyncio.run(J.relist_retry({"item_id": ITEM, "platform": PLAT}, user_id=USER))
    gewist = [r for r in db.log
              if r["tabel"] == "listings" and r["soort"] == "update"
              and (r["velden"] or {}).get("error_message", "x") is None]
    assert gewist, "staat er een nieuwe poging klaar, dan mag de oude melding weg"


def test_de_oude_opdrachten_worden_pas_na_het_terugdraaien_geannuleerd(monkeypatch):
    """Sneuvelt het verzoek halverwege, dan is 'nog niet geannuleerd' een veel
    betere afloop dan 'geannuleerd en de boekhouding klopt niet meer'."""
    db, _ = _retry_opzet(monkeypatch)
    asyncio.run(J.relist_retry({"item_id": ITEM, "platform": PLAT}, user_id=USER))
    soorten = [(r["tabel"], r["soort"]) for r in db.log]
    eerste_annulering = next(i for i, r in enumerate(db.log)
                             if r["tabel"] == "jobs" and r["soort"] == "update")
    eerste_delete_lezing = next(i for i, r in enumerate(db.log)
                                if r["tabel"] == "jobs" and r["soort"] == "select"
                                and r["filters"].get("action") == "delete")
    assert eerste_delete_lezing < eerste_annulering, soorten


# ── 2. Een herplaatsing die op een afgebroken verwijdering wacht ─────────────

def _uitgifte(monkeypatch, delete_status, teruggedraaid):
    """De echte uitgifte draaien met één wachtende herplaatsing."""
    CREATE = {"id": "create-1", "user_id": USER, "item_id": ITEM, "platform": PLAT,
              "action": "create", "status": "pending", "payload": {},
              "created_at": "2026-08-30T12:35:38+00:00",
              # De geplande tijd is verstreken: de herplaatsing is aan de beurt.
              "scheduled_for": "2020-01-01T00:00:00+00:00"}

    def antwoorden(b):
        if b.tabel == "jobs" and b.filters.get("action") == "delete":
            return [{"status": delete_status,
                     "payload": {"_refresh_rollback": SNAPSHOT}}]
        if b.tabel == "jobs" and b.filters.get("status") == "pending":
            return [CREATE]
        return []

    db = _DB(antwoorden)
    monkeypatch.setattr(J, "get_db", lambda: db)
    monkeypatch.setattr(J, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(J, "_recover_stale_claims", lambda *a, **kw: None)
    import backend.services.relist as R
    monkeypatch.setattr(R, "rollback_refresh", lambda rb, uid: teruggedraaid.append(rb))

    class _Verzoek:
        headers = {"x-omnivaleur-ext": "1.0.268", "user-agent": "test"}

    uit = J.get_pending_jobs(_Verzoek(), platform=PLAT, user_id=USER)
    return db, uit


@pytest.mark.parametrize("delete_status", ["error", "cancelled"])
def test_een_herplaatsing_zonder_verwijdering_blijft_niet_hangen(monkeypatch, delete_status):
    """Een verwijdering die is mislukt OF afgebroken gaat nooit meer lopen. De
    herplaatsing die erop wacht moet dus worden afgesloten — anders blijft het
    scherm eeuwig 'nieuwe advertentie over ~X min' melden."""
    teruggedraaid = []
    db, uit = _uitgifte(monkeypatch, delete_status, teruggedraaid)

    assert uit == [], "deze herplaatsing mag niet worden uitgedeeld"
    afgesloten = [r for r in db.log if r["tabel"] == "jobs" and r["soort"] == "update"
                  and (r["velden"] or {}).get("status") == "error"]
    assert afgesloten, f"een {delete_status} verwijdering laat de herplaatsing hangen"
    assert "duplicate" in afgesloten[0]["velden"]["result"]["error"]


@pytest.mark.parametrize("delete_status", ["error", "cancelled"])
def test_de_afgeblazen_verversing_telt_niet_mee(monkeypatch, delete_status):
    """Teller, veertien dagen afkoeling en een dagquotum teruggeven. Zonder dit
    staat er 'ververst' bij een advertentie waar niets mee is gebeurd, én kan de
    verkoper hem twee weken lang niet opnieuw proberen."""
    teruggedraaid = []
    _uitgifte(monkeypatch, delete_status, teruggedraaid)
    assert teruggedraaid == [SNAPSHOT]


def test_een_geslaagde_verwijdering_laat_de_herplaatsing_gewoon_door(monkeypatch):
    teruggedraaid = []
    db, uit = _uitgifte(monkeypatch, "done", teruggedraaid)
    assert [j["id"] for j in uit] == ["create-1"]
    assert teruggedraaid == []
