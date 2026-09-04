"""Het dataverkeer van het dashboard: waarom de Supabase-meter voller liep dan
zeven gebruikers kunnen verklaren.

WAAROM DIT ER IS (01-09-2026, Daniel over zijn Supabase-rekening)
De vraag was of Pro nog nodig was. Opslag bleek het probleem niet (0,64 GB van
1 GB) en de database ook niet (108,9 MB van 500 MB) — het dataverkeer wel:
2,17 GB in anderhalve dag, bij zeven actieve gebruikers.

Nagemeten op de echte database: het dashboard haalde elke 15 seconden de HELE
catalogus opnieuw op. Bij het grootste account (5.533 items) is dat 28 pagina's
van een halve MB — 11,8 MB — plus 2,9 MB advertenties, samen zo'n negentig
opvragingen per ronde, vier rondes per minuut. Ruim 3 GB per uur dat het
tabblad openstond. Daarbovenop werd bij ELK verzoek het inlogbewijs apart bij
Supabase nagevraagd: 61.030 keer in één etmaal, altijd met hetzelfde antwoord.

Elke test hieronder bewaakt één van de vier ingrepen.
"""
import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import items as api  # noqa: E402
from backend.api import deps  # noqa: E402


# ── Een minimale nabootsing van de Supabase-bouwer ───────────────────────────

class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.vanaf = {}, None
        self.telling, self.grens = None, None

    def select(self, *_a, count=None):
        # EXACT de handtekening van de client die op de server draait
        # (supabase 2.7.4 / postgrest 0.16.11): wél `count`, géén `head`.
        # Deze nabootsing slikte eerder alles, en daardoor stond hier drie dagen
        # een groene test terwijl /api/items/sync op Railway bij élke verversing
        # een interne fout gaf. Zie docs/kennisbank.md, "SDK-pin valstrik".
        self.telling = count
        return self

    def eq(self, k, v):
        self.filters[k] = v
        return self

    def gte(self, k, v):
        self.vanaf = (k, v)
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self.grens = n
        return self

    def execute(self):
        self.db.verzoeken.append(self)
        rijen = [r for r in self.db.rijen
                 if all(r.get(k) == v for k, v in self.filters.items())]
        if self.vanaf:
            kolom, waarde = self.vanaf
            rijen = [r for r in rijen if (r.get(kolom) or "") >= waarde]
        rijen.sort(key=lambda r: (r.get("updated_at") or "", r["id"]))
        # De telling staat in de kop van het antwoord en gaat dus NIET mee met
        # de beperking op het aantal rijen. Zo werkt PostgREST ook.
        aantal = len(rijen)
        if self.grens:
            rijen = rijen[:self.grens]
        return type("R", (), {"data": rijen,
                              "count": (aantal if self.telling == "exact" else None)})()


class _DB:
    def __init__(self, rijen):
        self.rijen, self.verzoeken = rijen, []

    def table(self, naam):
        return _Q(self, naam)


def _item(nr, updated, user="u1"):
    return {"id": f"it{nr}", "user_id": user, "title": f"item {nr}",
            "created_at": "2026-01-01T00:00:00+00:00", "updated_at": updated}


# ── 1. Alleen wat er veranderd is ────────────────────────────────────────────

def test_zonder_wijzigingen_komt_er_geen_enkele_rij_terug(monkeypatch):
    """De duurste ronde is de ronde waarin niets is gebeurd — en dat is negen
    van de tien rondes."""
    db = _DB([_item(1, "2026-09-01T10:00:00+00:00"),
              _item(2, "2026-09-01T10:00:01+00:00")])
    monkeypatch.setattr(api, "get_db", lambda: db)
    uit = api.sync_items(since="2026-09-01T10:00:02+00:00", user_id="u1")
    assert uit["items"] == []
    assert uit["count"] == 2


def test_alleen_het_gewijzigde_item_komt_mee(monkeypatch):
    db = _DB([_item(1, "2026-09-01T10:00:00+00:00"),
              _item(2, "2026-09-01T12:00:00+00:00")])
    monkeypatch.setattr(api, "get_db", lambda: db)
    uit = api.sync_items(since="2026-09-01T11:00:00+00:00", user_id="u1")
    assert [r["id"] for r in uit["items"]] == ["it2"]


def test_een_rij_op_precies_hetzelfde_tijdstip_wordt_nooit_overgeslagen(monkeypatch):
    """Twee rijen kunnen dezelfde updated_at hebben. Met een scherpe grens (>)
    zou de tweede voorgoed onzichtbaar blijven; het scherm voegt samen op id,
    dus dezelfde rij nog eens sturen kost één regel en kan niets breken."""
    stempel = "2026-09-01T12:00:00+00:00"
    db = _DB([_item(1, stempel), _item(2, stempel)])
    monkeypatch.setattr(api, "get_db", lambda: db)
    uit = api.sync_items(since=stempel, user_id="u1")
    assert [r["id"] for r in uit["items"]] == ["it1", "it2"]


def test_de_telling_verraadt_een_verwijderd_item(monkeypatch):
    """Een verwijdering laat geen wijziging achter. Zonder deze telling zou het
    scherm een weggegooid item tot de volgende herlaadbeurt blijven tonen."""
    db = _DB([_item(1, "2026-09-01T10:00:00+00:00")])
    monkeypatch.setattr(api, "get_db", lambda: db)
    uit = api.sync_items(since="2026-09-01T11:00:00+00:00", user_id="u1")
    assert uit["items"] == [] and uit["count"] == 1


def test_de_telling_haalt_de_catalogus_niet_op(monkeypatch):
    """Het getal komt uit de kop van het antwoord. Zou dit een gewone select
    zijn, dan haalden we alsnog de hele catalogus op en was er niets gewonnen."""
    db = _DB([_item(n, "2026-09-01T10:00:00+00:00") for n in range(20)])
    monkeypatch.setattr(api, "get_db", lambda: db)
    uit = api.sync_items(since="2026-09-02T00:00:00+00:00", user_id="u1")
    telverzoeken = [v for v in db.verzoeken if v.telling == "exact"]
    assert len(telverzoeken) == 1
    assert telverzoeken[0].filters == {"user_id": "u1"}
    assert telverzoeken[0].grens == 1, "de telling mag hooguit één rij meenemen"
    assert uit["count"] == 20


def test_te_veel_wijzigingen_meldt_zichzelf(monkeypatch):
    """Bij een import verandert alles tegelijk. Dan is doorbladeren duurder dan
    één keer alles ophalen — het scherm moet dat kunnen zien."""
    db = _DB([_item(n, "2026-09-01T12:00:00+00:00") for n in range(30)])
    monkeypatch.setattr(api, "get_db", lambda: db)
    uit = api.sync_items(since="2026-09-01T11:00:00+00:00", limit=10, user_id="u1")
    assert uit["truncated"] is True and len(uit["items"]) == 10
    uit2 = api.sync_items(since="2026-09-01T11:00:00+00:00", limit=100, user_id="u1")
    assert uit2["truncated"] is False


def test_van_een_ander_account_komt_niets_mee(monkeypatch):
    db = _DB([_item(1, "2026-09-01T12:00:00+00:00", user="u1"),
              _item(2, "2026-09-01T12:00:00+00:00", user="u2")])
    monkeypatch.setattr(api, "get_db", lambda: db)
    uit = api.sync_items(since="", user_id="u1")
    assert [r["id"] for r in uit["items"]] == ["it1"]


# ── 2. updated_at beweegt echt mee ───────────────────────────────────────────

def test_elke_wijziging_aan_een_item_krijgt_een_tijdstempel():
    """Zonder dit stempel is het bijwerken-op-wijziging blind: de kolom stond bij
    vrijwel elke rij nog op het tijdstip van aanmaken, want er staat geen trigger
    op de tabel."""
    from backend.database import get_db
    db = get_db()
    verzoek = db.table("items").update({"title": "x"}).eq("id", "0").request
    assert "updated_at" in verzoek.json
    datetime.fromisoformat(verzoek.json["updated_at"])  # een echt tijdstip


def test_andere_tabellen_krijgen_geen_stempel():
    """`jobs` en `listings` hebben die kolom niet — een stempel daar zou elke
    schrijfactie laten mislukken."""
    from backend.database import get_db
    db = get_db()
    assert "updated_at" not in get_db().table("jobs").update({"status": "done"}).eq("id", "0").request.json
    assert "updated_at" not in db.table("listings").update({"status": "sold"}).eq("id", "0").request.json


def test_een_eigen_tijdstempel_blijft_staan():
    from backend.database import get_db
    eigen = "2020-01-01T00:00:00+00:00"
    verzoek = get_db().table("items").update({"updated_at": eigen}).eq("id", "0").request
    assert verzoek.json["updated_at"] == eigen


def test_ook_een_upsert_van_meerdere_rijen_wordt_gestempeld():
    from backend.database import get_db
    lading = get_db().table("items").upsert([{"id": "1"}, {"id": "2"}]).request.json
    assert all("updated_at" in rij for rij in lading)


# ── 3. Het inlogbewijs wordt een minuut onthouden ────────────────────────────

class _NepAuth:
    def __init__(self, user):
        self.user, self.keren = user, 0

    class _Res:
        def __init__(self, user):
            self.user = user

    def get_user(self, _token):
        self.keren += 1
        return self._Res(self.user)


def _zet_auth(monkeypatch, nep):
    deps._auth_cache.clear()
    monkeypatch.setattr(deps, "get_auth_db", lambda: type("C", (), {"auth": nep})())
    monkeypatch.setattr(deps, "auth_met_herkansing", lambda fn: fn())


def test_hetzelfde_token_wordt_maar_een_keer_nagevraagd(monkeypatch):
    """61.030 auth-verzoeken in één etmaal voor zeven gebruikers: steeds dezelfde
    vraag met hetzelfde antwoord."""
    nep = _NepAuth(type("U", (), {"id": "u1", "email": "a@b.nl"})())
    _zet_auth(monkeypatch, nep)
    for _ in range(20):
        assert asyncio.run(deps.get_current_user(authorization="Bearer abc")) == "u1"
    assert nep.keren == 1


def test_een_ander_token_wordt_wel_nagevraagd(monkeypatch):
    nep = _NepAuth(type("U", (), {"id": "u1", "email": "a@b.nl"})())
    _zet_auth(monkeypatch, nep)
    asyncio.run(deps.get_current_user(authorization="Bearer abc"))
    asyncio.run(deps.get_current_user(authorization="Bearer xyz"))
    assert nep.keren == 2


def test_na_een_minuut_wordt_het_opnieuw_gecontroleerd(monkeypatch):
    nep = _NepAuth(type("U", (), {"id": "u1", "email": "a@b.nl"})())
    _zet_auth(monkeypatch, nep)
    asyncio.run(deps.get_current_user(authorization="Bearer abc"))
    verschoven = time.monotonic() + deps._AUTH_GELDIG_SECONDEN + 1
    monkeypatch.setattr(deps.time, "monotonic", lambda: verschoven)
    asyncio.run(deps.get_current_user(authorization="Bearer abc"))
    assert nep.keren == 2


def test_na_een_wachtwoordwijziging_is_het_meteen_vergeten(monkeypatch):
    """Anders kon iemand met het oude bewijs nog een minuut door, en dat is
    precies het moment waarop dat niet mag."""
    nep = _NepAuth(type("U", (), {"id": "u1", "email": "a@b.nl"})())
    _zet_auth(monkeypatch, nep)
    asyncio.run(deps.get_current_user(authorization="Bearer abc"))
    deps.vergeet_inlogbewijs("Bearer abc")
    asyncio.run(deps.get_current_user(authorization="Bearer abc"))
    assert nep.keren == 2


def test_het_token_zelf_staat_niet_in_het_geheugen(monkeypatch):
    """Wat onthouden wordt is een hash, geen bruikbaar inlogbewijs."""
    nep = _NepAuth(type("U", (), {"id": "u1", "email": "a@b.nl"})())
    _zet_auth(monkeypatch, nep)
    asyncio.run(deps.get_current_user(authorization="Bearer geheim-token"))
    assert "geheim-token" not in " ".join(deps._auth_cache.keys())


def test_een_afgewezen_token_wordt_niet_onthouden(monkeypatch):
    """Een 'nee' onthouden zou betekenen dat wie zich net aanmeldde een minuut
    lang buiten blijft staan."""
    nep = _NepAuth(None)
    _zet_auth(monkeypatch, nep)
    for _ in range(3):
        with pytest.raises(Exception):
            asyncio.run(deps.get_current_user(authorization="Bearer fout"))
    assert nep.keren == 3


# ── 4. De herplaatsvraag laat de database filteren ───────────────────────────

def test_de_herplaatsvraag_haalt_niet_alle_opdrachten_op():
    """Deze vraag hangt aan dezelfde ronde van 15 seconden. Hij haalde ALLE
    create-opdrachten op om er vervolgens alleen de geplande uit te vissen — en
    die stapel groeit met elke publicatie mee."""
    bron = (ROOT / "backend" / "api" / "jobs.py").read_text(encoding="utf-8")
    ronde = bron.split("def relist_status(", 1)[1].split("\n@router", 1)[0]
    assert '.not_.is_("scheduled_for", "null")' in ronde, \
        "relist_status haalt weer alle create-opdrachten op in plaats van alleen de geplande"


# ─────────────────────────────────────────────────────────────────────────────
# 04-09-2026 — de verversing gaf drie dagen lang een interne fout
#
# Vanaf commit 8747493 (01-09) telde `sync_items` met `head=True`. Dat kent de
# clientversie die in requirements.txt staat niet, dus antwoordde de server bij
# élke verversing met "Something went wrong on our side (code ...)". Het
# foutenlogboek stond er vol mee: 60 van de 60 regels, allemaal dezelfde.

class _Verboden(dict):
    """Namen die de oude functie bij het inlezen nodig heeft (Depends en
    vrienden) mogen hier leeg zijn; get_db zetten we er daarna zelf in."""
    def __missing__(self, _naam):
        return lambda *a, **k: None


def _oude_sync():
    import re
    import subprocess
    bron = subprocess.run(["git", "show", "4687587:backend/api/items.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    stuk = re.search(r"\ndef sync_items\(.*?(?=\n@router)", bron, re.S)
    assert stuk, "sync_items staat niet in die commit"
    ruimte = _Verboden()
    exec(compile(stuk.group(0), "<oud>", "exec"), ruimte)
    return ruimte["sync_items"], ruimte


def test_de_telling_werkt_met_de_client_die_op_de_server_staat(monkeypatch):
    db = _DB([_item(1, "2026-09-01T10:00:00+00:00"),
              _item(2, "2026-09-01T11:00:00+00:00"),
              _item(3, "2026-09-01T12:00:00+00:00")])
    monkeypatch.setattr(api, "get_db", lambda: db)
    uit = api.sync_items(since="2026-09-01T11:00:00+00:00", user_id="u1")
    assert uit["count"] == 3, "de telling hoort ALLE artikelen te zijn, niet alleen de gewijzigde"
    assert len(uit["items"]) == 2

    # VOOR: dezelfde aanroep op de oude code loopt stuk op precies de fout die
    # zestig keer in het foutenlogboek stond.
    oud, ruimte = _oude_sync()
    ruimte["get_db"] = lambda: db
    with pytest.raises(TypeError, match="head"):
        oud(since="2026-09-01T11:00:00+00:00", user_id="u1")


def test_er_wordt_nergens_meer_met_head_geteld():
    """Eén plek repareren helpt niet als de volgende sessie hem terugzet."""
    for pad in (ROOT / "backend").rglob("*.py"):
        for nr, regel in enumerate(pad.read_text(encoding="utf-8").splitlines(), 1):
            code = regel.split("#", 1)[0]     # de waarschuwing in het commentaar mag
            assert "head=True" not in code, f"{pad.name}:{nr} telt weer met head=True"
