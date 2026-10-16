"""Het verkoopvangnet wist de webshop van een voorraadwinkel niet (16-10-2026).

WAAROM DEZE TEST BESTAAT — GEMETEN, NIET BEDACHT.

Janneke (31d28378): "Tussenjas Noppies maat 134" verkocht op Vinted om 21:09:49
UTC. handle_item_sold haalde één stuk van de Shopify-voorraad en liet het product
staan, zoals de voorraadregel zegt. Om 21:42:25 staat in haar Shopify-logboek
"destroy, Omnivaleur": reconcileer_verkochte_artikelen zag een verkochte
Vinted-rij naast een levende Shopify-rij en meldde Shopify alsnog af. Zo ook
08-10 en 12-10. Haar tweede jas van hetzelfde soort was daarmee weg.

DE VOOR-EN-NA-PROEF: de oude versie komt uit commit a65a57c5 (vóór de reparatie)
en meldt in exact dezelfde situatie Shopify af; de nieuwe niet.

Draaien:  python3 -m pytest tests/test_vangnet_spaart_voorraadwinkel.py -q
"""
import asyncio
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import crosslist as cl                    # noqa: E402
from backend.services import verkoop_reconciliatie as vr        # noqa: E402

OUDE_COMMIT = "a65a57c5"


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.eqs, self.ins, self.gtes = {}, {}, {}
        self.op, self.velden = "select", None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, v): self.op, self.velden = "update", v; return self
    def eq(self, k, v): self.eqs[k] = v; return self
    def in_(self, k, v): self.ins[k] = list(v); return self
    def gte(self, k, v): self.gtes[k] = v; return self
    def order(self, *_a, **_k): return self
    def limit(self, _n): return self

    def execute(self):
        if self.tabel in self.db.kapot:
            raise RuntimeError("520 van Cloudflare")
        rijen = [r for r in getattr(self.db, self.tabel)
                 if all(r.get(k) == v for k, v in self.eqs.items())
                 and all(r.get(k) in v for k, v in self.ins.items())
                 and all(str(r.get(k) or "") >= str(v) for k, v in self.gtes.items())]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return types.SimpleNamespace(data=rijen)


class _DB:
    def __init__(self, creds, mp_levend=False):
        nu = datetime.now(timezone.utc)
        self.kapot: set[str] = set()
        self.listings = [
            {"id": "L_v", "item_id": "jas", "platform": "vinted", "status": "sold",
             "sold_at": (nu - timedelta(minutes=33)).isoformat(), "platform_listing_id": "10391742298"},
            {"id": "L_s", "item_id": "jas", "platform": "shopify", "status": "active",
             "platform_listing_id": "16146488262981"},
        ]
        if mp_levend:
            self.listings.append({"id": "L_mp", "item_id": "jas", "platform": "marktplaats",
                                  "status": "active", "platform_listing_id": "m2454116395"})
        self.jobs: list[dict] = []
        self.items = [{"id": "jas", "user_id": "janneke"}]
        self.platform_credentials = creds

    def table(self, naam): return _Q(self, naam)


def _voorraadwinkel():
    return [{"user_id": "janneke", "platform": "shopify",
             "extra_data": {"shop_domain": "be297d-2.myshopify.com", "voorraad_meerdere": True}}]


def _draai(module, db) -> list[set | None]:
    """Eén ronde; geeft per afmelding de kanalen die hij mocht aanraken."""
    aanroepen: list[set | None] = []

    async def nep_delist(item_id, user_id, alleen_platforms=None):
        aanroepen.append(alleen_platforms)
        return []

    async def direct(fn, *_a, **_k):
        return fn()

    oud_get, oud_lus, oud_delist = cl.get_db, module.naast_de_lus, cl.delist_all_platforms
    module.get_db = lambda: db
    module.naast_de_lus = direct
    cl.delist_all_platforms = nep_delist
    try:
        asyncio.run(module.reconcileer_verkochte_artikelen())
    finally:
        module.get_db, module.naast_de_lus, cl.delist_all_platforms = oud_get, oud_lus, oud_delist
    return aanroepen


def _oude_module() -> types.ModuleType:
    tekst = subprocess.run(
        ["git", "show", f"{OUDE_COMMIT}:backend/services/verkoop_reconciliatie.py"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_winkels_die_blijven" not in tekst, "de oude commit bevat de reparatie al"
    mod = types.ModuleType("vr_oud")
    mod.__dict__["__file__"] = "vr_oud.py"
    exec(compile(tekst, "vr_oud.py", "exec"), mod.__dict__)
    return mod


def _raakt_shopify(aanroepen) -> bool:
    return any(a is None or "shopify" in a for a in aanroepen)


def test_oude_code_wiste_de_voorraadwinkel():
    aanroepen = _draai(_oude_module(), _DB(_voorraadwinkel()))
    assert _raakt_shopify(aanroepen), f"de oude code hoort Shopify af te melden: {aanroepen}"


def test_voorraadwinkel_blijft_staan():
    assert _draai(vr, _DB(_voorraadwinkel())) == []


def test_andere_kanalen_gaan_wel_offline():
    aanroepen = _draai(vr, _DB(_voorraadwinkel(), mp_levend=True))
    assert aanroepen == [{"marktplaats"}]


def test_webshop_zelf_bijhouden_blijft_staan():
    creds = [{"user_id": "janneke", "platform": "shopify", "extra_data": {}},
             {"user_id": "janneke", "platform": "_settings",
              "extra_data": {"webshop_met_rust": True}}]
    assert _draai(vr, _DB(creds)) == []


def test_uniek_artikel_gaat_nog_steeds_uit_de_winkel():
    creds = [{"user_id": "janneke", "platform": "shopify", "extra_data": {}}]
    aanroepen = _draai(vr, _DB(creds))
    assert aanroepen == [{"shopify"}]


def test_storing_bij_het_nagaan_wist_niets():
    db = _DB([{"user_id": "janneke", "platform": "shopify", "extra_data": {}}])
    db.kapot.add("platform_credentials")
    assert not _raakt_shopify(_draai(vr, db))
