"""Verkoopherkenning via de Vinted-mail.

De twee mails hieronder hebben de opbouw van de echte verkoopmails uit Daniels postvak
(30-10 NL, 21-11-2026 EN). Titels, prijzen en tekst komen van Daniel zelf; de kopers zijn
verzonnen (nooit echte persoonsgegevens in een openbare repo). Het koperadres staat er
met opzet in om te bewijzen dat het nergens terechtkomt.
"""
import asyncio
from datetime import datetime, timezone

from backend.services import vinted_verkoopmail as vm

EN_TEKST = """Hello revaleurnl,

koperone has bought

(623) Blue Suitsupply Jumper - Men M - Very Good
€29.99

We will transfer the buyer's payment to your Vinted Balance once the order is completed.
Please send this order within 5 days.

Buyer's contact information
Address: Jan Voorbeeld, Teststraat 1, Utrecht, 3500, NL
Email: koper1@voorbeeld.invalid
"""

NL_TEKST = """Hey revaleurnl,

kopertwee heeft gekocht

(1331) Beige Massimo Dutti T-shirt - Men XL - Very Good
€ 12,00

We maken de betaling over naar je Vinted Portemonnee zodra de bestelling is afgerond.

Kopers contactgegevens:
Adres: Piet Proef, Proefweg 2, Gent, 9000, BE
E-mail: koper2@voorbeeld.invalid
"""

# Zoals Resend het soms als platte tekst levert: titel en prijs op één regel.
NL_EENREGELIG = "Hey revaleurnl, kopertwee heeft gekocht (1331) Beige Massimo Dutti T-shirt - Men XL - Very Good € 12,00 We maken de betaling over"

EN_ONDERWERP = "You've sold an item on Vinted"
NL_ONDERWERP = "Je hebt een artikel verkocht op Vinted"
ECHT = {"dkim": "pass", "spf": "gray", "dmarc": "pass"}
VAN = "Team Vinted <no-reply@vinted.nl>"


def test_engelse_mail_titel_en_prijs():
    assert vm.lees_verkoopmail(EN_ONDERWERP, EN_TEKST, None) == {
        "titel": "(623) Blue Suitsupply Jumper - Men M - Very Good", "prijs": 29.99}


def test_nederlandse_mail_titel_en_prijs():
    assert vm.lees_verkoopmail(NL_ONDERWERP, NL_TEKST, None) == {
        "titel": "(1331) Beige Massimo Dutti T-shirt - Men XL - Very Good", "prijs": 12.0}


def test_zelfde_uitkomst_als_alles_op_een_regel_staat():
    r = vm.lees_verkoopmail(NL_ONDERWERP, NL_EENREGELIG, None)
    assert r == {"titel": "(1331) Beige Massimo Dutti T-shirt - Men XL - Very Good", "prijs": 12.0}


def test_alleen_html_wordt_ook_gelezen():
    html = ("<p>Hey revaleurnl,</p><p><b>kopertwee</b> heeft gekocht</p>"
            "<table><tr><td>(1331) Beige Massimo Dutti T-shirt &amp; meer - Men XL</td></tr>"
            "<tr><td><b>&euro; 12,00</b></td></tr></table>")
    r = vm.lees_verkoopmail("Fwd: " + NL_ONDERWERP, None, html)
    assert r == {"titel": "(1331) Beige Massimo Dutti T-shirt & meer - Men XL", "prijs": 12.0}


def test_koper_komt_nergens_in_het_resultaat():
    for onderwerp, tekst in ((EN_ONDERWERP, EN_TEKST), (NL_ONDERWERP, NL_TEKST)):
        r = vm.lees_verkoopmail(onderwerp, tekst, None)
        blob = str(r).lower()
        for lek in ("koperone", "kopertwee", "voorbeeld", "teststraat", "proefweg", "@"):
            assert lek not in blob


def test_bedragen_nooit_verkeerd_door_duizendtalpunt():
    assert vm._prijs_naar_getal("1.360,00") == 1360.0
    assert vm._prijs_naar_getal("1,360.00") == 1360.0
    assert vm._prijs_naar_getal("29.99") == 29.99
    assert vm._prijs_naar_getal("12,00") == 12.0
    assert vm._prijs_naar_getal("1.360") is None  # geen centen: geen bedrag uit een mail


def test_andere_mails_van_vinted_worden_niet_gelezen():
    # Bestelbevestiging aan een KOPER, of een bericht: nooit een verkoop.
    assert vm.lees_verkoopmail("Je hebt een nieuw bericht", NL_TEKST, None) is None
    assert vm.lees_verkoopmail("Your order has been shipped", EN_TEKST, None) is None
    assert vm.lees_verkoopmail(NL_ONDERWERP, "Hey, er is iets gebeurd", None) is None
    assert vm.lees_verkoopmail(NL_ONDERWERP, "heeft gekocht geen prijs hier", None) is None


def test_onbekende_taal_wordt_niet_geraden():
    assert vm.lees_verkoopmail("Tu as vendu un article sur Vinted", NL_TEKST, None) is None


def test_echtheid_vraagt_dkim_pass_en_vinted_afzender():
    assert vm.is_echt_van_vinted(VAN, ECHT)
    assert not vm.is_echt_van_vinted(VAN, {"dkim": "gray"})
    assert not vm.is_echt_van_vinted(VAN, {"dkim": "fail"})
    assert not vm.is_echt_van_vinted(VAN, None)
    assert not vm.is_echt_van_vinted("Jan <jan@gmail.com>", ECHT)
    assert not vm.is_echt_van_vinted("Team <no-reply@vinted.nl.evil.com>", ECHT)
    assert not vm.is_echt_van_vinted("Team <no-reply@notvinted.nl>", ECHT)


def test_adres_token():
    t = "a1b2c3d4e5f6a1b2c3d4e5f6"
    assert vm.adres_token([f"Vinted <vinted-{t}@abc123.resend.app>"]) == t
    assert vm.adres_token(f"vinted-{t.upper()}@x.resend.app") == t
    assert vm.adres_token(["info@omnivaleur.com"]) is None
    assert vm.adres_token(["vinted-kort@x.resend.app"]) is None


def test_kies_artikel_titelgenoten_geven_geen_gok():
    mail = {"titel": "Blue Jumper - Men M", "prijs": 29.99}
    a = {"item_id": "a", "titel": "Blue Jumper - Men M", "prijs": 29.99}
    b = {"item_id": "b", "titel": "Blue Jumper - Men M", "prijs": 35.0}
    c = {"item_id": "c", "titel": "Blue Jumper - Men M", "prijs": 29.99}
    assert vm.kies_artikel(mail, [a])[0] == a
    assert vm.kies_artikel(mail, [a, b])[0] == a            # prijs beslist alleen bij twee of meer
    assert vm.kies_artikel(mail, [a, c])[0] is None         # nog steeds niet eenduidig
    assert vm.kies_artikel(mail, [b])[0] == b               # bod: prijs wijkt af, titel is uniek
    assert vm.kies_artikel(mail, [])[0] is None


def test_ingekorte_titel_telt_als_zelfde():
    lang = "(1331) Beige Massimo Dutti T-shirt - Men XL - Very Good extra lange tekst erachter"
    assert vm.zelfde_titel(lang[:60], lang)
    assert not vm.zelfde_titel("Beige", "Beige Massimo Dutti T-shirt")  # te kort om te vergelijken


# ── de hele weg, met een nagebootste database ────────────────────────────────

class _Q:
    def __init__(self, data):
        self.data = data

    def __getattr__(self, naam):
        return lambda *a, **k: self

    def execute(self):
        return self


class _Db:
    def __init__(self, items, listings):
        self._items, self._listings = items, listings

    def table(self, naam):
        return _Q(self._items if naam == "items" else self._listings)


async def _direct(aanroep, herkans=False):
    return aanroep()


def _draai(items, listings, **kw):
    boekingen = []

    async def sold(item_id, platform, sold_price=None, sold_at=None, bewijs=None):
        boekingen.append((item_id, platform, sold_price, bewijs))

    args = dict(db=_Db(items, listings), naast_de_lus=_direct, handle_item_sold=sold, bewijs="kanaal",
                user_id="u1", onderwerp=NL_ONDERWERP, van=VAN, tekst=NL_TEKST, html=None,
                authenticatie=ECHT, ontvangen_op=datetime(2026, 11, 21, 13, 37, tzinfo=timezone.utc))
    args.update(kw)
    uitkomst = asyncio.run(vm.verwerk_ontvangen_mail(**args))
    return uitkomst, boekingen


ITEMS = [{"id": "i1", "title": "(1331) Beige Massimo Dutti T-shirt - Men XL - Very Good", "price": 15.0},
         {"id": "i2", "title": "(1332) Zwarte broek - Men L", "price": 20.0}]
ACTIEF = [{"item_id": "i1"}]


def test_hele_weg_boekt_op_vinted_met_de_echte_prijs():
    uitkomst, boekingen = _draai(ITEMS, ACTIEF)
    assert uitkomst["uitkomst"] == "geboekt"
    assert boekingen == [("i1", "vinted", 12.0, "kanaal")]  # bod van 12 op vraagprijs 15


def test_nepmail_zonder_dkim_boekt_niets():
    uitkomst, boekingen = _draai(ITEMS, ACTIEF, authenticatie={"dkim": "gray"})
    assert uitkomst["uitkomst"] == "genegeerd" and boekingen == []


def test_niet_vinted_als_afzender_boekt_niets():
    uitkomst, boekingen = _draai(ITEMS, ACTIEF, van="Jan <jan@gmail.com>")
    assert boekingen == []


def test_advertentie_al_niet_meer_actief_boekt_niets():
    uitkomst, boekingen = _draai(ITEMS, [])
    assert uitkomst["uitkomst"] == "overgeslagen" and boekingen == []


def test_geen_artikel_met_die_titel_boekt_niets():
    # De advertentie is wel actief, alleen de titel hoort bij een ander artikel.
    uitkomst, boekingen = _draai([ITEMS[1]], [{"item_id": "i2"}])
    assert uitkomst["reden"] == "geen_actieve_advertentie_met_deze_titel" and boekingen == []


def test_twee_identieke_titels_boekt_niets():
    dubbel = ITEMS[:1] + [{"id": "i3", "title": ITEMS[0]["title"], "price": 15.0}]
    uitkomst, boekingen = _draai(dubbel, [{"item_id": "i1"}, {"item_id": "i3"}])
    assert uitkomst["reden"] == "meerdere_artikelen_met_deze_titel" and boekingen == []


# ── het ontvangstpunt zelf: handtekening, adres, ophalen, boeken ─────────────

import base64
import hashlib
import hmac
import json
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import webhooks as wh

TOKEN = "a1b2c3d4e5f6a1b2c3d4e5f6"
GEHEIM = "whsec_" + base64.b64encode(b"proefgeheim").decode()


class _Tabellen:
    def __init__(self, creds, items, listings):
        self.creds, self.items, self.listings = creds, items, listings

    def table(self, naam):
        return _Q({"platform_credentials": self.creds, "items": self.items}.get(naam, self.listings))


def _aanroep(monkeypatch, *, mail, tabellen, ondertekenen=True, status=200):
    boekingen = []

    async def sold(item_id, platform, sold_price=None, sold_at=None, bewijs=None):
        boekingen.append((item_id, platform, sold_price, bewijs))

    class _Antwoord:
        status_code = status

        def json(self):
            return mail

    class _Klant:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, headers=None):
            assert "/emails/receiving/" in url and headers["Authorization"].startswith("Bearer ")
            return _Antwoord()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _Klant)
    monkeypatch.setattr(wh, "get_admin_db", lambda: tabellen)
    monkeypatch.setattr(wh, "naast_de_lus", _direct)
    monkeypatch.setattr(wh, "handle_item_sold", sold)
    monkeypatch.setattr(wh.settings, "resend_webhook_secret", GEHEIM)
    monkeypatch.setattr(wh.settings, "resend_api_key", "re_proef")

    app = FastAPI()
    app.include_router(wh.router, prefix="/api")
    body = json.dumps({"type": "email.received", "created_at": "2026-11-21T13:37:00Z",
                       "data": {"email_id": "m1", "to": [f"vinted-{TOKEN}@abc.resend.app"]}}).encode()
    sid, ts = "msg_1", str(int(time.time()))
    sleutel = base64.b64decode(GEHEIM.split("_", 1)[1])
    sig = base64.b64encode(hmac.new(sleutel, b"%s.%s.%s" % (sid.encode(), ts.encode(), body),
                                    hashlib.sha256).digest()).decode()
    kop = {"svix-id": sid, "svix-timestamp": ts, "svix-signature": f"v1,{sig if ondertekenen else 'fout'}"}
    r = TestClient(app).post("/api/webhooks/resend", content=body, headers=kop)
    return r, boekingen


MAIL = {"subject": NL_ONDERWERP, "from": VAN, "text": NL_TEKST, "html": None,
        "authentication": {"dkim": "pass", "spf": "gray", "dmarc": "pass"}}
CREDS = [{"user_id": "u1"}]


def test_ontvangstpunt_boekt_een_echte_mail(monkeypatch):
    r, boekingen = _aanroep(monkeypatch, mail=MAIL, tabellen=_Tabellen(CREDS, ITEMS, ACTIEF))
    assert r.status_code == 200 and r.json()["uitkomst"] == "geboekt"
    assert boekingen == [("i1", "vinted", 12.0, "kanaal")]


def test_ontvangstpunt_weigert_een_verkeerde_handtekening(monkeypatch):
    r, boekingen = _aanroep(monkeypatch, mail=MAIL, tabellen=_Tabellen(CREDS, ITEMS, ACTIEF), ondertekenen=False)
    assert r.status_code == 401 and boekingen == []


def test_onbekend_adres_boekt_niets(monkeypatch):
    r, boekingen = _aanroep(monkeypatch, mail=MAIL, tabellen=_Tabellen([], ITEMS, ACTIEF))
    assert r.status_code == 200 and boekingen == []


def test_mail_niet_op_te_halen_boekt_niets_en_geeft_toch_200(monkeypatch):
    r, boekingen = _aanroep(monkeypatch, mail=MAIL, tabellen=_Tabellen(CREDS, ITEMS, ACTIEF), status=500)
    assert r.status_code == 200 and boekingen == []


def test_mail_zonder_dkim_via_het_ontvangstpunt_boekt_niets(monkeypatch):
    nep = dict(MAIL, authentication={"dkim": "gray"})
    r, boekingen = _aanroep(monkeypatch, mail=nep, tabellen=_Tabellen(CREDS, ITEMS, ACTIEF))
    assert r.status_code == 200 and boekingen == []


def test_genegeerde_mail_meldt_wat_de_server_zei_zonder_inhoud():
    r, boekingen = _draai(ITEMS, ACTIEF, authenticatie={"dkim": "gray", "spf": "pass"}, van="Google <forwarding-noreply@google.com>")
    assert r["afzender_domein"] == "google.com"
    assert r["authenticatie"] == {"dkim": "gray", "spf": "pass", "dmarc": None}
    assert "Voorbeeld" not in str(r) and boekingen == []
    r2, _ = _draai(ITEMS, ACTIEF, authenticatie=None)
    assert r2["authenticatie"].startswith("geen_veld")


def test_eigenaar_krijgt_mail_bij_doorgestuurde_vinted_mail(monkeypatch):
    verstuurd = []
    import backend.services.email as em
    monkeypatch.setattr(em, "send_email", lambda onderwerp, tekst, **k: verstuurd.append((onderwerp, tekst)) or True)
    monkeypatch.setattr(wh.settings, "vinted_mail_open_voor_klanten", False)
    r, boekingen = _aanroep(monkeypatch, mail=MAIL, tabellen=_Tabellen(CREDS, ITEMS, ACTIEF))
    assert len(verstuurd) == 1 and verstuurd[0][0] == "Vinted verkoopmail doorgestuurd: geboekt"
    assert "dkim" in verstuurd[0][1] and "Voorbeeld" not in verstuurd[0][1] and " - " not in verstuurd[0][1]
    # Een mail van een ander (Google): geen melding.
    verstuurd.clear()
    r, _ = _aanroep(monkeypatch, mail=dict(MAIL, **{"from": "Google <forwarding-noreply@google.com>"}),
                    tabellen=_Tabellen(CREDS, ITEMS, ACTIEF))
    assert verstuurd == []
    # Open voor klanten: nooit meer meldingen aan Daniel.
    monkeypatch.setattr(wh.settings, "vinted_mail_open_voor_klanten", True)
    r, _ = _aanroep(monkeypatch, mail=MAIL, tabellen=_Tabellen(CREDS, ITEMS, ACTIEF))
    assert verstuurd == []
