"""Een klant kan zijn gegevens downloaden en zijn account helemaal wissen.

Aanleiding (15-10-2026, Benedikt): geen wisknop, en onduidelijk waar de data staat.

Wat hier bewezen wordt, op een nagemaakte database met TWEE klanten:
  - wissen haalt alles van de één weg (rijen, foto's, abonnement, inlog) en laat de
    ander helemaal intact;
  - lukt het stopzetten van het abonnement niet, dan blijft ALLES staan;
  - een fout wachtwoord raakt niets aan;
  - de download bevat alleen eigen gegevens en geen inlogsleutels van platforms.
"""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException  # noqa: E402

from backend.api import account  # noqa: E402

A, B = "aaaaaaaa-0000-0000-0000-000000000001", "bbbbbbbb-0000-0000-0000-000000000002"


class Zoek:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.actie, self.bereik = [], "select", None
        self.kolommen = None

    def select(self, kolommen="*", *_a, **_k):
        # Net als de echte database: alleen de gevraagde kolommen komen terug.
        self.kolommen = None if kolommen == "*" else [k.strip() for k in kolommen.split(",")]
        return self
    def order(self, *_a, **_k): return self
    def limit(self, n): self.bereik = (0, n - 1); return self
    def range(self, a, b): self.bereik = (a, b); return self
    def delete(self): self.actie = "delete"; return self
    def eq(self, k, v): self.filters.append((k, lambda x, v=v: x == v)); return self
    def in_(self, k, vs): self.filters.append((k, lambda x, vs=set(vs): x in vs)); return self

    def execute(self):
        rijen = self.db.rijen.setdefault(self.tabel, [])
        raak = [r for r in rijen if all(k in r and f(r[k]) for k, f in self.filters)]
        if self.actie == "delete":
            self.db.rijen[self.tabel] = [r for r in rijen if r not in raak]
            return SimpleNamespace(data=raak)
        if self.bereik:
            raak = raak[self.bereik[0]:self.bereik[1] + 1]
        if self.kolommen:
            return SimpleNamespace(data=[{k: r.get(k) for k in self.kolommen} for r in raak])
        return SimpleNamespace(data=[dict(r) for r in raak])


class NepEmmer:
    def __init__(self, bestanden): self.bestanden = bestanden
    def list(self, path="", options=None):
        diepte = len(path.split("/"))
        uit = []
        for p in self.bestanden:
            if p.rsplit("/", 1)[0] == path:
                uit.append({"name": p.rsplit("/", 1)[1], "id": "x"})
        return uit
    def remove(self, namen):
        for n in namen:
            self.bestanden.discard(n)


class NepDb:
    def __init__(self):
        self.rijen = {}
        self.foto = set()
        self.storage = SimpleNamespace(from_=lambda _b: NepEmmer(self.foto))
        self.auth_verwijderd = []
        self.auth = SimpleNamespace(admin=SimpleNamespace(delete_user=self.auth_verwijderd.append))

    def table(self, naam): return Zoek(self, naam)


def vul(db):
    for uid, n in ((A, "a"), (B, "b")):
        db.rijen.setdefault("items", []).extend(
            {"id": f"{n}-i{i}", "user_id": uid, "title": f"{n} {i}"} for i in range(3))
        db.rijen.setdefault("listings", []).extend(
            {"id": f"{n}-l{i}", "item_id": f"{n}-i{i}", "platform": "vinted"} for i in range(3))
        db.rijen.setdefault("sync_events", []).append({"id": f"{n}-s", "listing_id": f"{n}-l0"})
        db.rijen.setdefault("jobs", []).extend(
            {"id": f"{n}-j{i}", "user_id": uid, "item_id": f"{n}-i{i}" if i < 3 else None,
             "platform": "vinted", "action": "create", "status": "done",
             "result": {"geheim": 1}} for i in range(4))   # j3 heeft geen artikel meer
        db.rijen.setdefault("platform_credentials", []).append(
            {"id": f"{n}-c", "user_id": uid, "platform": "vinted", "access_token": "GEHEIM"})
        db.rijen.setdefault("subscriptions", []).append(
            {"id": f"{n}-sub", "user_id": uid, "stripe_customer_id": f"cus_{n}",
             "stripe_subscription_id": f"sub_{n}", "status": "active", "plan": "pro"})
        db.rijen.setdefault("extension_heartbeat", []).append({"user_id": uid})
        db.foto |= {f"{uid}/x{n}.jpg", f"{uid}/imported/y{n}.jpg"}


class NepStripe:
    def __init__(self, faalt=False):
        self.gestopt, self.faalt = [], faalt
        self.Subscription = self

    def list(self, customer, status, limit):
        sid = "sub_" + customer[-1]
        return SimpleNamespace(data=[{"id": sid, "status": "active"}])

    def cancel(self, sid):
        if self.faalt:
            raise RuntimeError("Stripe is stuk")
        self.gestopt.append(sid)


@pytest.fixture
def wereld(monkeypatch):
    db = NepDb()
    vul(db)
    stripe = NepStripe()
    monkeypatch.setattr(account, "get_db", lambda: db)
    monkeypatch.setattr(account, "get_admin_db", lambda: db)
    monkeypatch.setattr(account, "stripe", stripe)
    monkeypatch.setattr(account.r2_storage, "is_configured", lambda: False)
    monkeypatch.setattr(account, "vergeet_inlogbewijs", lambda *a, **k: None)
    monkeypatch.setattr(account, "_wachtwoord_klopt", lambda e, w: w == "goed")
    return db, stripe


def namen(db, tabel, kolom, waarde):
    return [r for r in db.rijen.get(tabel, []) if r.get(kolom) == waarde]


def test_wissen_haalt_alles_van_a_weg_en_laat_b_intact(wereld):
    db, stripe = wereld
    account.wis_account(A)

    assert stripe.gestopt == ["sub_a"]
    assert db.auth_verwijderd == [A]
    assert not any(f.startswith(A) for f in db.foto)
    assert {f for f in db.foto} == {f"{B}/xb.jpg", f"{B}/imported/yb.jpg"}
    assert namen(db, "items", "user_id", A) == []
    assert namen(db, "jobs", "user_id", A) == []          # ook de opdracht zonder artikel
    assert namen(db, "subscriptions", "user_id", A) == []
    assert namen(db, "platform_credentials", "user_id", A) == []
    assert [r["id"] for r in db.rijen["listings"]] == ["b-l0", "b-l1", "b-l2"]
    assert [r["id"] for r in db.rijen["sync_events"]] == ["b-s"]
    # B is niet aangeraakt
    assert len(namen(db, "items", "user_id", B)) == 3
    assert len(namen(db, "jobs", "user_id", B)) == 4
    assert len(namen(db, "subscriptions", "user_id", B)) == 1


def test_lukt_stopzetten_niet_dan_blijft_alles_staan(wereld):
    db, stripe = wereld
    stripe.faalt = True
    with pytest.raises(RuntimeError):
        account.wis_account(A)
    assert db.auth_verwijderd == []
    assert len(namen(db, "items", "user_id", A)) == 3
    assert any(f.startswith(A) for f in db.foto)


def test_fout_wachtwoord_raakt_niets_aan(wereld):
    db, stripe = wereld
    user = SimpleNamespace(id=A, email="a@example.nl")
    with pytest.raises(HTTPException) as e:
        asyncio.run(account.verwijder_mijn_account(account.WisVerzoek(password="fout"), user))
    assert e.value.status_code == 401
    assert stripe.gestopt == [] and db.auth_verwijderd == []
    assert len(namen(db, "items", "user_id", A)) == 3


def test_goed_wachtwoord_wist_via_het_endpoint(wereld):
    db, stripe = wereld
    user = SimpleNamespace(id=A, email="a@example.nl")
    uit = asyncio.run(account.verwijder_mijn_account(account.WisVerzoek(password="goed"), user))
    assert uit == {"ok": True}
    assert db.auth_verwijderd == [A]


def test_tweede_poging_na_halve_mislukking_werkt(wereld):
    """Wissen is herhaalbaar: een halve poging mag de volgende niet blokkeren."""
    db, _ = wereld
    db.rijen["items"] = [r for r in db.rijen["items"] if r["id"] != "a-i0"]   # half gewist
    account.wis_account(A)
    assert namen(db, "items", "user_id", A) == []
    assert db.auth_verwijderd == [A]


def test_download_bevat_alleen_eigen_gegevens_en_geen_sleutels(wereld):
    db, _ = wereld
    data = account.bouw_download(A, "a@example.nl", "2026-01-01")
    tekst = json.dumps(data, default=str)
    assert len(data["artikelen"]) == 3 and len(data["advertenties"]) == 3
    assert all(a["user_id"] == A for a in data["artikelen"])
    assert "b-i" not in tekst and "b-l" not in tekst
    assert "GEHEIM" not in tekst and "cus_a" not in tekst and "sub_a" not in tekst
    assert [p["platform"] for p in data["gekoppelde_platforms"]] == ["vinted"]
    assert all("result" not in j for j in data["opdrachten"])
    assert data["account"]["email"] == "a@example.nl"
