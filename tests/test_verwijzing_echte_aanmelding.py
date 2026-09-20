"""Een echte, betaalde aanmelding via een gedeelde link. Van de eerste klik tot
de maand die er daadwerkelijk af gaat.

Waarom dit bestaat naast de andere verwijzingsproeven: die beproeven de losse
onderdelen. Deze loopt de weg die een mens aflegt, in één keer, door de echte
HTTP-routes en de echte webhook-afhandeling heen:

    klik op de link -> aanmelden met de code -> de helft betalen bij Stripe ->
    proef -> eerste echte afschrijving -> de aanbrenger krijgt zijn maand

Wat hier bewezen wordt en nergens anders:

  * Een AANMELDING levert nog niets op. Pas als er geld binnenkomt valt de maand.
    Dat is het verschil tussen een beloningssysteem en een lek.
  * De vriend krijgt zijn 50% echt mee naar de betaalpagina van Stripe, zonder
    dat iemand een code hoeft te typen, en alleen die eerste maand.
  * Dezelfde webhook die drie keer binnenkomt kost nooit drie maanden.
  * Het werkt voor een gewone klant net zo goed als voor Daniel zelf, met één
    verschil dat hier zwart op wit komt te staan: Daniels eigen account is al
    gratis, dus daar valt geen maand bij op te tellen.
  * VOOR-EN-NA: raakt de webhook onderweg kwijt, dan krijgt de aanbrenger
    zonder de herstelronde NIETS, en mét de ronde alsnog zijn maand.
"""
import asyncio
import types
from datetime import datetime, timedelta, timezone

import pytest
import stripe as echte_stripe
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_verwijzing_gratis_maand import NepDb

NU = datetime.now(timezone.utc)
OWNER = "daniel@omnivaleur.com"
PERIODE_EINDE = int((NU + timedelta(days=30)).timestamp())


# ── Een Stripe die alles vastlegt en niets verstuurt ────────────────────────

class NepStripe:
    def __init__(self):
        self.abonnementen: dict[str, dict] = {}
        self.tegoeden: list[tuple] = []
        self.sessies: list[dict] = []
        self.gebeurtenis: dict | None = None
        self.error = echte_stripe.error          # de echte foutklassen
        zelf = self

        class Subscription:
            @staticmethod
            def retrieve(sub_id, **_kw):
                return dict(zelf.abonnementen[sub_id])

            @staticmethod
            def modify(sub_id, **kw):
                zelf.abonnementen.setdefault(sub_id, {}).update(kw)
                return dict(zelf.abonnementen[sub_id])

            @staticmethod
            def list(**_kw):
                return types.SimpleNamespace(data=[])

        class Customer:
            @staticmethod
            def create(**_kw):
                return types.SimpleNamespace(id="cus_nieuw")

            @staticmethod
            def create_balance_transaction(klant, **kw):
                zelf.tegoeden.append((klant, kw))
                return {"id": f"cbtxn_{len(zelf.tegoeden)}"}

        class Coupon:
            @staticmethod
            def retrieve(coupon_id, **_kw):
                return {"id": coupon_id, "percent_off": 50, "duration": "once"}

        class Session:
            @staticmethod
            def create(**kw):
                zelf.sessies.append(kw)
                return types.SimpleNamespace(id=f"cs_{len(zelf.sessies)}",
                                             url="https://checkout.stripe.com/c/pay_1")

        class Webhook:
            @staticmethod
            def construct_event(_payload, _sig, _secret):
                return zelf.gebeurtenis

        self.Subscription, self.Customer, self.Coupon, self.Webhook = (
            Subscription, Customer, Coupon, Webhook)
        self.checkout = types.SimpleNamespace(Session=Session)

    def abonnement(self, sub_id, status, klant, prijs=1999, trial_end=None):
        self.abonnementen[sub_id] = {
            "id": sub_id, "status": status, "customer": klant,
            "trial_end": trial_end, "current_period_end": PERIODE_EINDE,
            "items": {"data": [{"price": {"unit_amount": prijs}, "quantity": 1,
                                "current_period_end": PERIODE_EINDE}]},
        }
        return sub_id


# ── De wereld: echte routes, echte modules, nepdatabase en nep-Stripe ───────

class Wereld:
    def __init__(self, client, db, stripe, mails, huidig):
        self.client, self.db, self.stripe = client, db, stripe
        self.mails, self._huidig = mails, huidig

    def als(self, user_id, email):
        self._huidig["u"] = types.SimpleNamespace(id=user_id, email=email)

    def rijen(self, tabel):
        return self.db.data.setdefault(tabel, [])

    def verwijzing(self, user_id):
        return next(r for r in self.rijen("referrals") if r["user_id"] == user_id)

    def beloning(self, user_id):
        return next((r for r in self.rijen("referral_rewards")
                     if r["referred_user_id"] == user_id), None)

    def abo(self, user_id):
        return next(r for r in self.rijen("subscriptions") if r["user_id"] == user_id)

    # -- de stappen die een mens zet -------------------------------------
    def klik(self, code):
        return self.client.get(f"/r/{code}", follow_redirects=False,
                               headers={"accept-language": "nl-NL,nl;q=0.9"})

    def meld_aan(self, user_id, email, code):
        from backend.api import auth
        gebruiker = types.SimpleNamespace(user=types.SimpleNamespace(id=user_id))
        auth.verse_auth_client = lambda: types.SimpleNamespace(
            auth=types.SimpleNamespace(sign_up=lambda *_a, **_k: gebruiker))
        return self.client.post("/api/auth/register",
                                json={"email": email, "password": "geheim12345", "ref": code})

    def webhook(self, gebeurtenis):
        self.stripe.gebeurtenis = gebeurtenis
        return self.client.post("/api/billing/webhook", content=b"{}",
                                headers={"stripe-signature": "t=1,v1=nep"})

    def betaalt_echt(self, sub_id):
        """Stripe schrijft af en meldt dat het abonnement lopend is."""
        self.stripe.abonnementen[sub_id]["status"] = "active"
        return self.webhook({"type": "customer.subscription.updated",
                             "data": {"object": self.stripe.abonnementen[sub_id]}})


@pytest.fixture()
def wereld(monkeypatch):
    from backend.api import auth, billing, referrals
    from backend.services import billing as billing_dienst
    from backend.services import referral_codes, referral_rewards

    db = NepDb(
        referral_codes=[
            {"code": "danieldk", "kind": "user", "owner_user_id": "u-daniel",
             "active": True, "created_at": NU.isoformat(), "bounty_cents": 0},
            {"code": "anna", "kind": "user", "owner_user_id": "u-anna",
             "active": True, "created_at": NU.isoformat(), "bounty_cents": 0},
        ],
        referrals=[], referral_clicks=[], referral_rewards=[],
        subscriptions=[
            {"user_id": "u-daniel", "status": "complimentary", "plan": "pro"},
            {"user_id": "u-anna", "status": "active", "plan": "pro",
             "stripe_subscription_id": "sub_anna", "stripe_customer_id": "cus_anna"},
        ],
    )
    for mod in (auth, billing, referrals, referral_codes, referral_rewards):
        monkeypatch.setattr(mod, "get_db", lambda: db, raising=False)
    monkeypatch.setattr(billing, "get_admin_db", lambda: db, raising=False)

    nep = NepStripe()
    nep.abonnement("sub_anna", "active", "cus_anna")
    monkeypatch.setattr(billing, "stripe", nep)
    monkeypatch.setattr(referral_rewards, "stripe", nep)

    for naam, waarde in (("stripe_secret_key", "sk_test"), ("stripe_price_id", "price_1"),
                         ("stripe_webhook_secret", "whsec_test"),
                         ("app_url", "https://omnivaleur.com"), ("owner_email", OWNER)):
        for mod in (billing, referrals, referral_rewards, billing_dienst):
            monkeypatch.setattr(mod.settings, naam, waarde, raising=False)

    # Geen actiecode in de weg, en e-mail gaat nergens heen.
    monkeypatch.setattr(billing, "find_active_promo", lambda: None)
    mails = {"beloning": [], "aanmelding": [], "alarm": []}
    monkeypatch.setattr(referral_rewards, "mail_beloning",
                        lambda uid, manier, uitleg: mails["beloning"].append((uid, manier)) or True)
    monkeypatch.setattr(referral_rewards, "mail_aanmelding",
                        lambda uid, wie, code: mails["aanmelding"].append((uid, wie, code)) or True)
    monkeypatch.setattr(referral_rewards, "mail_beloning_mislukt",
                        lambda *a: mails["alarm"].append(a) or True)

    adressen = {"u-daniel": OWNER, "u-anna": "anna@example.nl"}
    for mod in (referrals, referral_rewards):
        monkeypatch.setattr(mod, "email_van",
                            lambda uid: adressen.get(uid, f"{uid}@example.nl"))
    monkeypatch.setattr(referrals, "_tegoed_eur", lambda uid: None)
    referral_rewards.vergeet_kortingsrecht()
    referral_rewards._coupon_cache = None

    huidig = {"u": types.SimpleNamespace(id="u-anna", email="anna@example.nl")}
    app = FastAPI()
    for r in (referrals.router, billing.router, auth.router):
        app.include_router(r)
    app.dependency_overrides[referrals.get_current_user_full] = lambda: huidig["u"]
    from backend.api.deps import get_current_user_full
    app.dependency_overrides[get_current_user_full] = lambda: huidig["u"]

    return Wereld(TestClient(app), db, nep, mails, huidig)


def _meld_en_betaal(w, vriend, code, sub_id, klant="cus_v"):
    """De hele weg van één aangebrachte vriend, precies zoals hij echt loopt."""
    w.klik(code)
    w.meld_aan(vriend, f"{vriend}@example.nl", code)
    w.als(vriend, f"{vriend}@example.nl")
    w.client.post("/api/billing/checkout")
    w.stripe.abonnement(sub_id, "trialing", klant,
                        trial_end=int((NU + timedelta(days=5)).timestamp()))
    w.webhook({"type": "checkout.session.completed",
               "data": {"object": {"metadata": {"user_id": vriend},
                                   "subscription": sub_id, "customer": klant}}})
    return sub_id


# ── 1. De hele keten voor een gewone klant ──────────────────────────────────

def test_van_klik_tot_maand_voor_een_gewone_klant(wereld):
    w = wereld

    # 1. Iemand klikt op de link van Anna.
    klik = w.klik("anna")
    assert klik.status_code == 302
    assert klik.headers["location"] == "https://omnivaleur.com/nl.html?ref=anna"
    assert len(w.rijen("referral_clicks")) == 1

    # 2. Hij maakt een account met die code erbij.
    aanmelding = w.meld_aan("u-vriend1", "vriend1@example.nl", "anna")
    assert aanmelding.status_code == 200, aanmelding.text
    assert w.verwijzing("u-vriend1")["code"] == "anna"

    # 3. Het scherm van de vriend belooft de halve eerste maand.
    w.als("u-vriend1", "vriend1@example.nl")
    status = w.client.get("/api/billing/status").json()
    assert status["referral_discount"] == {"percent_off": 50}

    # 4. Hij klikt op betalen: de korting gaat mee naar Stripe, zonder handwerk.
    afrekenen = w.client.post("/api/billing/checkout")
    assert afrekenen.status_code == 200, afrekenen.text
    assert w.stripe.sessies[-1]["discounts"] == [
        {"coupon": "omnivaleur-vriendenkorting-50"}]

    # 5. Hij rondt af, maar zijn proef loopt nog: er is nog geen euro binnen.
    sub = w.stripe.abonnement("sub_v1", "trialing", "cus_v1",
                              trial_end=int((NU + timedelta(days=5)).timestamp()))
    w.webhook({"type": "checkout.session.completed",
               "data": {"object": {"metadata": {"user_id": "u-vriend1"},
                                   "subscription": sub, "customer": "cus_v1"}}})
    assert w.verwijzing("u-vriend1").get("first_paid_at") is None
    assert w.beloning("u-vriend1") is None, "aanmelden alleen mag nooit een maand kosten"
    assert w.stripe.tegoeden == []

    # 6. De proef loopt af en de eerste 9,99 wordt echt afgeschreven.
    assert w.betaalt_echt(sub).status_code == 200

    # NU pas valt de maand, en precies één.
    assert w.verwijzing("u-vriend1")["first_paid_at"], "de betaaldatum hoort gestempeld"
    beloning = w.beloning("u-vriend1")
    assert beloning["status"] == "granted"
    assert beloning["method"] == "tegoed"
    assert beloning["amount_cents"] == 1999
    assert w.stripe.tegoeden == [("cus_anna", w.stripe.tegoeden[0][1])]
    assert w.stripe.tegoeden[0][1]["amount"] == -1999, "negatief = tegoed"
    assert w.mails["beloning"] == [("u-anna", "tegoed")]

    # 7. De korting was eenmalig: de tweede maand betaalt hij gewoon vol.
    assert w.client.get("/api/billing/status").json()["referral_discount"] is None

    # 8. Anna ziet het op haar eigen pagina terug.
    w.als("u-anna", "anna@example.nl")
    body = w.client.get("/api/referrals/me").json()
    assert body["stats"]["signups"] == 1
    assert body["stats"]["paying"] == 1
    assert body["stats"]["months_earned"] == 1
    assert body["friends"][0]["name"].endswith("@example.nl")
    assert "vriend1" not in body["friends"][0]["name"], "nooit het hele adres"


# ── 2. Dezelfde webhook drie keer kost nooit drie maanden ───────────────────

def test_dezelfde_betaling_drie_keer_gemeld_kost_een_maand(wereld):
    w = wereld
    sub = _meld_en_betaal(w, "u-vriend1", "anna", "sub_v1", "cus_v1")
    for _ in range(3):
        assert w.betaalt_echt(sub).status_code == 200

    assert len(w.stripe.tegoeden) == 1, "één vriend, één maand, hoe vaak Stripe ook belt"
    assert len([r for r in w.rijen("referral_rewards")]) == 1
    assert len(w.mails["beloning"]) == 1


# ── 3. Onbeperkt: elke volgende vriend levert opnieuw een maand op ──────────

def test_drie_vrienden_leveren_drie_maanden_op(wereld):
    w = wereld
    for n in (1, 2, 3):
        sub = _meld_en_betaal(w, f"u-vriend{n}", "anna", f"sub_v{n}", f"cus_v{n}")
        w.betaalt_echt(sub)

    assert len(w.stripe.tegoeden) == 3
    assert [t[1]["amount"] for t in w.stripe.tegoeden] == [-1999, -1999, -1999]
    w.als("u-anna", "anna@example.nl")
    assert w.client.get("/api/referrals/me").json()["stats"]["months_earned"] == 3


# ── 4. VOOR EN NA: de webhook raakt kwijt ───────────────────────────────────

def test_gemiste_webhook_wordt_binnen_het_uur_alsnog_rechtgezet(wereld):
    w = wereld
    from backend.services import referral_rewards

    _meld_en_betaal(w, "u-vriend1", "anna", "sub_v1", "cus_v1")
    # Stripe schrijft af, maar de melding komt nooit aan (uitrol, storing).
    w.stripe.abonnementen["sub_v1"]["status"] = "active"
    w.abo("u-vriend1").update({"status": "active", "stripe_subscription_id": "sub_v1"})

    # VOOR: zonder de herstelronde krijgt Anna niets.
    assert w.beloning("u-vriend1") is None
    assert w.stripe.tegoeden == []

    # NA: de ronde die elk uur draait maakt het alsnog in orde.
    uit = asyncio.run(referral_rewards.verwerk_openstaande_beloningen())

    assert uit["toegekend"] == 1
    assert w.beloning("u-vriend1")["status"] == "granted"
    assert w.stripe.tegoeden[0][1]["amount"] == -1999
    assert w.verwijzing("u-vriend1")["first_paid_at"], "ook de betaaldatum wordt bijgewerkt"
    assert w.mails["aanmelding"] == [("u-anna", "u-vriend1@example.nl", "anna")]

    # En hij doet het niet nog eens dunnetjes over.
    assert asyncio.run(referral_rewards.verwerk_openstaande_beloningen())["toegekend"] == 0
    assert len(w.stripe.tegoeden) == 1


# ── 5. Daniels eigen link: alles werkt, behalve wat niet kán werken ─────────

def test_daniels_eigen_link_levert_de_vriend_zijn_korting_op(wereld):
    """Daniels account is al gratis en onbeperkt. Daar valt geen maand bij op te
    tellen, en dat mag nooit als een storing eindigen."""
    w = wereld
    sub = _meld_en_betaal(w, "u-vriend1", "danieldk", "sub_v1", "cus_v1")
    assert w.stripe.sessies[-1]["discounts"] == [{"coupon": "omnivaleur-vriendenkorting-50"}]
    w.betaalt_echt(sub)

    beloning = w.beloning("u-vriend1")
    assert beloning["status"] == "skipped", "afgehandeld, niet blijven hangen"
    assert beloning["method"] == "eigenaar"
    assert w.stripe.tegoeden == [], "zijn eigen account heeft geen factuur om iets van af te halen"
    assert w.mails["alarm"] == [], "en dit is geen storing"

    w.als("u-daniel", OWNER)
    body = w.client.get("/api/referrals/me").json()
    assert body["stats"]["signups"] == 1 and body["stats"]["paying"] == 1


# ── 6. Een aanbrenger die zelf nog in de proef zit ──────────────────────────

def test_aanbrenger_in_de_proef_krijgt_dertig_dagen_erbij(wereld):
    w = wereld
    # Anna betaalt nog niet: haar proef loopt bij Stripe.
    w.abo("u-anna").update({"status": "trialing"})
    einde = NU + timedelta(days=4)
    w.stripe.abonnementen["sub_anna"].update({"status": "trialing",
                                              "trial_end": int(einde.timestamp())})

    sub = _meld_en_betaal(w, "u-vriend1", "anna", "sub_v1", "cus_v1")
    w.betaalt_echt(sub)

    assert w.beloning("u-vriend1")["method"] == "stripe_proef"
    nieuw = datetime.fromtimestamp(w.stripe.abonnementen["sub_anna"]["trial_end"],
                                   tz=timezone.utc)
    assert 29 < (nieuw - einde).days + 1 <= 31, "dertig dagen erbij, niet opnieuw beginnen"
    assert w.stripe.tegoeden == [], "wie nog niets betaalt krijgt geen geld terug"
