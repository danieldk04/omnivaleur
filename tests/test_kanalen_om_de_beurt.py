"""Krijgt 2dehands een beurt terwijl er een Marktplaats-rij staat?

WAAROM DIT ER IS (05-09-2026, Lynn van De Juiste Toon)

"Marktplaats ging vandaag helemaal super, niks op aan te merken. Naar
tweedehands pakt ie nog niet." Gemeten in haar eigen opdrachten: op 04-09 stond
er om 14:08:09 één 2dehands-publicatie klaar. Die is nooit opgepakt en is om
18:23 met de hand geannuleerd, terwijl er in diezelfde vier uur negen
Marktplaats-publicaties wél doorheen gingen (14:09:55, 14:14:30, 14:17:51,
14:25:01, 14:31:32, 14:35:02, 14:42:33, 14:46:02, 14:54:03). Op haar twee
drukste dagen ging er van de 75 en de 98 publicaties telkens precies één naar
2dehands.

De extensie vraagt de kanalen in een vaste volgorde met marktplaats voorop,
terwijl er maar één publicatie tegelijk mag lopen. Wie vooraan staat pakt dus
elke vrijgekomen plek. De extensie deelt de beurt sinds 1.0.306 zelf rond, maar
een nieuwe versie is er pas na de Web Store — daarom doet de server het ook.

Deze proef draait de ECHTE uitgifte (`get_pending_jobs`) tegen een nagemaakte
database met twintig Marktplaats-opdrachten en één voor 2dehands.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as J  # noqa: E402

NU = datetime.now(timezone.utc)


def _job(jid, platform, minuten_geleden, actie="create"):
    return {
        "id": jid,
        "user_id": "u1",
        "item_id": "item-" + jid,
        "platform": platform,
        "action": actie,
        "status": "pending",
        "payload": {"price": 20},
        "created_at": (NU - timedelta(minutes=minuten_geleden)).isoformat(),
        "claimed_at": None,
        "done_at": None,
        "scheduled_for": None,
    }


def _bouw_db(wachtrij, laatst_bediend, laatst_geleden_sec=30):
    """Nagemaakte Supabase-client: alleen wat de uitgifte echt vraagt."""
    op_id = {j["id"]: j for j in wachtrij}

    class _B:
        def __init__(self, tabel):
            self.tabel, self.soort, self.filters = tabel, "select", {}
            self.niet_leeg = None
            self.ongelijk = {}

        def select(self, *a, **kw): self.soort = "select"; return self
        def update(self, v): self.soort = "update"; return self
        def eq(self, k, v): self.filters[k] = v; return self
        def neq(self, k, v): self.ongelijk[k] = v; return self
        def in_(self, k, v): self.filters[k] = list(v); return self
        def lte(self, *a, **kw): return self
        def gte(self, *a, **kw): return self
        def or_(self, *a, **kw): return self
        def order(self, *a, **kw): return self
        def limit(self, *a, **kw): return self

        @property
        def not_(self):
            buiten = self

            class _Niet:
                def is_(self, kolom, waarde):
                    buiten.niet_leeg = kolom
                    return buiten
            return _Niet()

        def execute(self):
            data = []
            if self.tabel == "jobs" and self.soort == "select":
                if self.filters.get("status") == "claimed":
                    data = []                      # niets in de lucht
                elif self.niet_leeg == "claimed_at":
                    # "wie deed de vorige publicatie?"
                    data = [{"platform": laatst_bediend, "action": "create",
                             "claimed_at": (NU - timedelta(seconds=laatst_geleden_sec)).isoformat()}] \
                        if laatst_bediend else []
                elif "id" in self.filters:
                    data = [op_id[i] for i in self.filters["id"] if i in op_id]
                elif self.filters.get("action") == "delete":
                    data = []
                elif self.filters.get("status") == "pending":
                    rijen = [j for j in wachtrij if j["status"] == "pending"]
                    if "platform" in self.filters:
                        rijen = [j for j in rijen if j["platform"] == self.filters["platform"]]
                    if "platform" in self.ongelijk:
                        rijen = [j for j in rijen if j["platform"] != self.ongelijk["platform"]]
                    if "action" in self.filters:
                        rijen = [j for j in rijen if j["action"] in self.filters["action"]]
                    data = sorted(rijen, key=lambda j: j["created_at"])
            elif self.tabel == "items":
                data = [{"id": self.filters.get("id", "x"), "user_id": "u1",
                         "title": "t", "sku": None, "brand": None, "price": 20}]
            elif self.tabel == "listings":
                data = []
            return type("R", (), {"data": data})()

    class _Db:
        def table(self, naam): return _B(naam)

    return _Db()


def _uitgifte(monkeypatch, db, platform):
    monkeypatch.setattr(J, "get_db", lambda: db)
    monkeypatch.setattr(J, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(J, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(J, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(J, "_zet_kleur_goed", lambda rijen: None)
    return J.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.305"}})(),
        platform=platform, user_id="u1")


def _lynn_wachtrij():
    rij = [_job(f"mp{i}", "marktplaats", 60 - i) for i in range(20)]
    rij.append(_job("td0", "2dehands", 30))
    return rij


def test_2dehands_komt_aan_de_beurt_na_een_marktplaats_publicatie(monkeypatch):
    """Dit is Lynns geval: twintig Marktplaats-opdrachten, één voor 2dehands."""
    wachtrij = _lynn_wachtrij()
    db = _bouw_db(wachtrij, laatst_bediend="marktplaats")
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit, "er moet werk uitgedeeld worden"
    assert uit[0]["platform"] == "2dehands", (
        "Marktplaats deed de vorige publicatie, dus 2dehands is nu aan de beurt; "
        f"gekregen: {uit[0]['platform']} ({uit[0]['id']})")


def test_daarna_is_marktplaats_weer_aan_de_beurt(monkeypatch):
    """Om de beurt is twee kanten op: 2dehands legt Marktplaats niet stil."""
    wachtrij = _lynn_wachtrij()
    db = _bouw_db(wachtrij, laatst_bediend="2dehands")
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit and uit[0]["platform"] == "marktplaats", (
        f"na een 2dehands-publicatie is Marktplaats aan de beurt; gekregen: {uit}")


def test_zonder_werk_op_een_ander_kanaal_gaat_alles_gewoon_door(monkeypatch):
    """Nooit een beurt doorgeven aan een leeg kanaal — dat legt de rij stil."""
    wachtrij = [_job(f"mp{i}", "marktplaats", 60 - i) for i in range(5)]
    db = _bouw_db(wachtrij, laatst_bediend="marktplaats")
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit and uit[0]["platform"] == "marktplaats", (
        "er is geen ander kanaal dat wacht, dus Marktplaats gaat gewoon door")


def test_een_scan_geeft_geen_beurt_door(monkeypatch):
    """Lezen is geen publiceren: een scan hoort de beurt niet te verschuiven."""
    wachtrij = [_job("sc0", "marktplaats", 10, actie="scan")]
    db = _bouw_db(wachtrij, laatst_bediend="marktplaats")
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit and uit[0]["id"] == "sc0", f"de scan hoort gewoon uitgedeeld te worden: {uit}"
