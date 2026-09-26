"""Op 2dehands gelden de verzendkosten die de verkoper zelf op Marktplaats koos.

WAT ER GEBEURDE (25-09-2026, Egbert Brouwer / Papa's Plectrums). "Er wordt hier
automatisch iets van €7.20 verzendkosten bij gezet (...) ik wil nu ook patches
gaan uploaden, daar wil ik eigenlijk niet zulke dure verzendkosten bij hebben
staan." Nagemeten op 26-09-2026: zijn patch m2446754373 op 2dehands toont
"Thuisbezorgd via Bpost voor € 7,10", dezelfde patch a1475716652 op Marktplaats
"Zelf Verzenden, Verzenden voor € 4,95". Wij kozen op 2dehands altijd Bpost 0-2 kg.

De blokken hieronder zijn letterlijk van de openbare advertentiepagina's van
26-09-2026: zijn patch (zelf verzenden), zijn miniatuur a1529380210 (verzenden
via Marktplaats, PostNL en DHL) en een kast m2446675023 (alleen ophalen).
"""
import asyncio
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import backend.api.jobs as J  # noqa: E402
import backend.services.mp_enrich as M  # noqa: E402

VOOR_DE_REPARATIE = "241c4f78"   # vast nummer: HEAD vergelijkt zichzelf na de commit
NUMMER = "1475716652"            # zijn Marktplaats-advertentie van de patch

ZELF_495 = ('"shippingInformation":{"mappedShippingOptions":{},"augmentedLabels":[{"shouldShowMoreInfo":false,'
            '"carrierId":null,"labels":[{"label":"Verzenden voor","price":"€\xa04,95",'
            '"deliveryMethod":"UNKNOWN_BECAUSE_DIY","carrierName":"Zelf Verzenden"}]}],'
            '"deliveryType":{"attributeLabel":"Levering","attributeValueLabel":"Ophalen of Verzenden",'
            '"attributeValueKey":"Ophalen of Verzenden"}}')
VIA_MARKTPLAATS = (
    '"shippingInformation":{"mappedShippingOptions":{"bulletPoints":["Kies de bezorgdienst die past bij '
    'jouw deal.","Na betaling volg je het hele bezorgproces met track & trace in Berichten."],'
    '"shippingTypes":[{"title":"Stuur naar afhaalpunt","options":[{"title":"Pakket 0 - 10 kg",'
    '"subTitle":"max. 80 x 50 x 35 cm","price":"€\xa04,29","strikeThroughPrice":null,"carrierId":"dhl-nl"}],'
    '"campaignLabel":null},{"title":"Thuis laten bezorgen","options":[{"title":"Pakket 0 - 10 kg",'
    '"subTitle":"max. 40 x 40 x 30 cm","price":"€\xa06,29","strikeThroughPrice":null,"carrierId":"postnl"}],'
    '"campaignLabel":null}]},"augmentedLabels":[{"shouldShowMoreInfo":true,"carrierId":"dhl-nl","labels":'
    '[{"label":"Afhaalpunt via DHL vanaf","price":"€\xa04,29","carrierName":"DHL","deliveryMethod":"PICK_UP"}]},'
    '{"shouldShowMoreInfo":true,"carrierId":"postnl","labels":[{"label":"Thuisbezorgd via PostNL vanaf",'
    '"price":"€\xa06,29","carrierName":"PostNL","deliveryMethod":"DELIVERY"}]}]}')
ALLEEN_OPHALEN = ('"shippingInformation":{"mappedShippingOptions":{},"augmentedLabels":[],"deliveryType":'
                  '{"attributeLabel":"Levering","attributeValueLabel":"Ophalen","attributeValueKey":"Ophalen"}}')


def _pagina(blok: str) -> str:
    """Het blok zoals het in de pagina staat: midden in één groot JSON-object."""
    return ('<html><script>window.__CONFIG__={"listing":{"flags":{"isAdmarkt":true},'
            + blok + ',"stats":{"viewCount":10}}};</script></html>')


# ── het lezen van de advertentiepagina ───────────────────────────────────────
def test_egberts_patch_wordt_zelf_versturen_voor_495():
    assert M.verzending_uit_html(_pagina(ZELF_495)) == {"soort": "zelf", "cents": 495}


def test_verzenden_via_marktplaats_is_geen_bedrag_van_de_verkoper():
    """PostNL en DHL met hun eigen tarief: dat hoort niet mee naar 2dehands."""
    assert M.verzending_uit_html(_pagina(VIA_MARKTPLAATS)) == {"soort": "platform"}


def test_alleen_ophalen():
    assert M.verzending_uit_html(_pagina(ALLEEN_OPHALEN)) == {"soort": "geen"}


def test_zonder_blok_of_zonder_bedrag_weten_we_het_niet():
    assert M.verzending_uit_html("<html>onderhoud</html>") is None
    assert M.verzending_uit_html("") is None
    zonder_bedrag = ZELF_495.replace('"price":"€\xa04,95",', '"price":null,')
    assert M.verzending_uit_html(_pagina(zonder_bedrag)) is None, \
        "een leeg bedrag is geen gratis verzenden: dan betaalt de verkoper het porto"


def test_bedragen():
    assert M._bedrag_in_centen("€\xa02,25") == 225
    assert M._bedrag_in_centen("€ 12,50") == 1250
    assert M._bedrag_in_centen("€ 0,00") == 0
    assert M._bedrag_in_centen("€ 5") == 500
    assert M._bedrag_in_centen("") is None
    assert M._bedrag_in_centen("gratis") is None


# ── het ophalen: een Admarkt-advertentie heet /a…, een gewone /m… ────────────
class _Antwoord:
    def __init__(self, status, tekst=""):
        self.status_code, self.text = status, tekst


class _Client:
    def __init__(self, antwoorden):
        self.antwoorden, self.gevraagd = dict(antwoorden), []

    async def get(self, url, headers=None):
        self.gevraagd.append(url)
        a = self.antwoorden.get(url.rsplit("/", 1)[-1], _Antwoord(404))
        if isinstance(a, Exception):
            raise a
        return a

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


def _haal(monkeypatch, antwoorden, nummer=NUMMER):
    client = _Client(antwoorden)
    monkeypatch.setattr(M.httpx, "AsyncClient", lambda *a, **kw: client)
    return asyncio.run(M.verzending_van_advertentie(nummer)), client


def test_admarkt_advertentie_wordt_gevonden_onder_de_a(monkeypatch):
    uit, client = _haal(monkeypatch, {f"a{NUMMER}": _Antwoord(200, _pagina(ZELF_495))})
    assert uit == {"soort": "zelf", "cents": 495}
    assert [u.rsplit("/", 1)[-1] for u in client.gevraagd] == [f"m{NUMMER}", f"a{NUMMER}"]


def test_weg_is_een_antwoord_een_storing_niet(monkeypatch):
    assert _haal(monkeypatch, {})[0] == {}, "twee keer 404: de advertentie bestaat niet meer"
    assert _haal(monkeypatch, {f"m{NUMMER}": _Antwoord(503)})[0] is None
    assert _haal(monkeypatch, {f"m{NUMMER}": TimeoutError("traag")})[0] is None
    assert _haal(monkeypatch, {f"m{NUMMER}": _Antwoord(200, "<html>toestemming</html>")})[0] is None


# ── de uitgifte ──────────────────────────────────────────────────────────────
def _rubriekproef():
    spec = importlib.util.spec_from_file_location(
        "rubriekproef", ROOT / "tests" / "test_2dehands_volgt_de_marktplaats_rubriek.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _rubriekproef()
RUBRIEK = {"l1": 895, "l1_naam": "Verzamelen", "l2": 926, "l2_naam": "Muziek, Artiesten en Beroemdheden"}


def _patch_opdracht(**extra):
    job = R._echte_opdracht()
    job["payload"] = {**job["payload"], "title": "Disturbed - Evolution - Rugpatch officiële merchandise",
                      "price": 11.95, "mp_category": dict(RUBRIEK), **extra}
    return job


def _nep_verzending(monkeypatch, uitkomst):
    vragen = []

    async def verzending(nummer):
        vragen.append(nummer)
        return uitkomst
    monkeypatch.setattr(M, "verzending_van_advertentie", verzending)
    return vragen


def test_de_patch_krijgt_zijn_eigen_bedrag_en_het_wordt_bewaard(monkeypatch):
    J._VERZENDING_STORING.clear()
    vragen = _nep_verzending(monkeypatch, {"soort": "zelf", "cents": 495})
    job = _patch_opdracht()
    db = R._DB([job], op_marktplaats={job["item_id"]: NUMMER})
    J._zet_verzending_van_marktplaats(db, R.USER, job)
    assert job["payload"]["verzending"] == {"soort": "zelf", "cents": 495}
    assert vragen == [NUMMER]
    assert [u[2]["payload"]["verzending"] for u in db.updates] == [{"soort": "zelf", "cents": 495}]
    # Tweede keer (bijvoorbeeld na een herkansing): niet opnieuw naar Marktplaats.
    J._zet_verzending_van_marktplaats(db, R.USER, job)
    assert vragen == [NUMMER]


def test_niet_op_marktplaats_blijft_het_oude_formulier(monkeypatch):
    vragen = _nep_verzending(monkeypatch, {"soort": "zelf", "cents": 495})
    job = _patch_opdracht()
    J._zet_verzending_van_marktplaats(R._DB([job]), R.USER, job)
    assert job["payload"]["verzending"] == {"soort": "onbekend"}
    assert vragen == []


def test_een_storing_legt_niets_vast_en_houdt_niets_tegen(monkeypatch):
    J._VERZENDING_STORING.clear()
    vragen = _nep_verzending(monkeypatch, None)
    job = _patch_opdracht()
    db = R._DB([job], op_marktplaats={job["item_id"]: NUMMER})
    J._zet_verzending_van_marktplaats(db, R.USER, job)
    assert "verzending" not in job["payload"], "een storing is geen antwoord"
    assert db.updates == []
    # Binnen de rust niet opnieuw bellen: dat is precies het salvo waar
    # Marktplaats op dichtklapt.
    tweede = _patch_opdracht()
    J._zet_verzending_van_marktplaats(db, R.USER, tweede)
    assert vragen == [NUMMER]
    J._VERZENDING_STORING.clear()


def test_alleen_een_2dehands_plaatsing(monkeypatch):
    vragen = _nep_verzending(monkeypatch, {"soort": "zelf", "cents": 495})
    for wijziging in ({"platform": "marktplaats"}, {"action": "delete"}, {"action": "extend"}):
        job = {**_patch_opdracht(), **wijziging}
        J._zet_verzending_van_marktplaats(R._DB([job], op_marktplaats={job["item_id"]: NUMMER}), R.USER, job)
        assert "verzending" not in job["payload"]
    assert vragen == []


def test_de_uitgifte_geeft_de_extensie_zijn_bedrag_mee_en_vroeger_niet(monkeypatch):
    """De echte uitgifte (get_pending_jobs), nu en zoals op 241c4f78."""
    J._VERZENDING_STORING.clear()
    _nep_verzending(monkeypatch, {"soort": "zelf", "cents": 495})
    job = _patch_opdracht()
    uit = R._uitgifte(J, monkeypatch, R._DB([dict(job)], op_marktplaats={job["item_id"]: NUMMER}))
    assert len(uit) == 1
    assert uit[0]["payload"]["verzending"] == {"soort": "zelf", "cents": 495}

    oud = R._oude_module("backend/api/jobs.py", VOOR_DE_REPARATIE, "oude_jobs_verzending",
                         moet_bevatten=("_zet_rubriek_van_marktplaats",),
                         moet_missen=("_zet_verzending_van_marktplaats",))
    uit_oud = R._uitgifte(oud, monkeypatch, R._DB([dict(_patch_opdracht())],
                                                  op_marktplaats={job["item_id"]: NUMMER}))
    assert len(uit_oud) == 1
    assert "verzending" not in uit_oud[0]["payload"], \
        "de oude uitgifte gaf niets mee, dus koos de extensie altijd Bpost 0-2 kg"
