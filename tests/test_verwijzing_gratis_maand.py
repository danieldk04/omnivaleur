"""Een vriend aanbrengen levert een maand gratis op. Aantoonbaar, niet aannemelijk.

WAT ER BEPROEFD WORDT, en waarom juist dit:

  * De maand komt er echt, op alle drie de manieren waarop dat kan (tegoed bij
    Stripe, proef bij Stripe opschuiven, eigen proef oprekken). Zonder deze
    proef zou "de beloning is toegekend" alleen betekenen dat er een rij in een
    tabel staat.
  * Dezelfde vriend levert nooit twee keer een maand op, ook niet als de webhook
    twee keer binnenkomt. Dat is de enige plek waar dit Daniel geld kan kosten.
  * Een mislukte toekenning blijft staan en lukt de volgende ronde alsnog.
  * DE VOOR-EN-NA-PROEF: zonder de herstelronde krijgt iemand bij een gemiste
    webhook NIETS. Dezelfde situatie mét de ronde levert de maand alsnog op.
  * De vriend betaalt de helft van zijn eerste maand, en alleen die eerste.
"""
import types
from datetime import datetime, timedelta, timezone

import pytest


# ── Een database die zich gedraagt zoals Supabase op de punten die tellen ────

class _Uitkomst:
    def __init__(self, data):
        self.data = data


class NepQuery:
    def __init__(self, db, tabel, soort, lading=None):
        self.db, self.tabel, self.soort, self.lading = db, tabel, soort, lading
        self.filters = []
        self.aflopend = False

    def eq(self, kolom, waarde):
        self.filters.append((kolom, "eq", waarde)); return self

    def in_(self, kolom, waarden):
        self.filters.append((kolom, "in", list(waarden))); return self

    def is_(self, kolom, waarde):
        self.filters.append((kolom, "is", waarde)); return self

    def limit(self, _n):
        return self

    def order(self, kolom, desc=False):
        self.aflopend = desc; self._sorteer = kolom; return self

    def _past(self, rij):
        for kolom, soort, waarde in self.filters:
            if soort == "eq" and rij.get(kolom) != waarde:
                return False
            if soort == "in" and rij.get(kolom) not in waarde:
                return False
            if soort == "is" and waarde == "null" and rij.get(kolom) is not None:
                return False
        return True

    def execute(self):
        rijen = self.db.data.setdefault(self.tabel, [])
        if self.soort == "select":
            uit = [dict(r) for r in rijen if self._past(r)]
            if getattr(self, "_sorteer", None):
                uit.sort(key=lambda r: r.get(self._sorteer) or "", reverse=self.aflopend)
            return _Uitkomst(uit)
        if self.soort == "insert":
            sleutel = self.db.uniek.get(self.tabel)
            if sleutel and any(r.get(sleutel) == self.lading.get(sleutel) for r in rijen):
                # Precies wat Postgres doet, en waar de hele bescherming tegen
                # dubbel uitkeren op rust.
                raise RuntimeError('duplicate key value violates unique constraint (23505)')
            rijen.append(dict(self.lading))
            return _Uitkomst([dict(self.lading)])
        if self.soort == "upsert":
            sleutel = "user_id" if self.tabel == "referrals" else self.db.uniek.get(self.tabel)
            for rij in rijen:
                if sleutel and rij.get(sleutel) == self.lading.get(sleutel):
                    rij.update(self.lading)
                    return _Uitkomst([dict(rij)])
            rijen.append(dict(self.lading))
            return _Uitkomst([dict(self.lading)])
        if self.soort == "update":
            geraakt = []
            for rij in rijen:
                if self._past(rij):
                    rij.update(self.lading)
                    geraakt.append(dict(rij))
            return _Uitkomst(geraakt)
        raise AssertionError(self.soort)


class NepTabel:
    def __init__(self, db, naam):
        self.db, self.naam = db, naam

    def select(self, *_a, **_kw):
        return NepQuery(self.db, self.naam, "select")

    def insert(self, rij):
        return NepQuery(self.db, self.naam, "insert", rij)

    def update(self, velden):
        return NepQuery(self.db, self.naam, "update", velden)

    def upsert(self, rij, on_conflict=None):
        return NepQuery(self.db, self.naam, "upsert", rij)


class NepDb:
    uniek = {"referral_rewards": "referred_user_id", "referral_codes": "code"}

    def __init__(self, **tabellen):
        self.data = {naam: [dict(r) for r in rijen] for naam, rijen in tabellen.items()}

    def table(self, naam):
        return NepTabel(self, naam)


# ── Gereedschap ─────────────────────────────────────────────────────────────

AANBRENGER = "u-aanbrenger"
VRIEND = "u-vriend"
NU = datetime.now(timezone.utc)


def _basis(sub: dict, code_eigenaar=AANBRENGER, betaald=None):
    return NepDb(
        referrals=[{"user_id": VRIEND, "code": "daniel", "created_at": NU.isoformat(),
                    "first_paid_at": betaald}],
        referral_codes=[{"code": "daniel", "kind": "user", "owner_user_id": code_eigenaar,
                         "active": True}],
        subscriptions=[sub],
        referral_rewards=[],
        referral_clicks=[],
    )


class NepStripe:
    """Legt vast wat er naar Stripe zou gaan. Geen enkele test praat met Stripe."""

    def __init__(self, abonnement=None, stuk=False):
        self.abonnement = abonnement or {}
        self.stuk = stuk
        self.tegoeden = []
        self.wijzigingen = []
        zelf = self

        class Subscription:
            @staticmethod
            def retrieve(sub_id, **_kw):
                if zelf.stuk:
                    raise RuntimeError("Stripe is onbereikbaar")
                return dict(zelf.abonnement)

            @staticmethod
            def modify(sub_id, **kw):
                zelf.wijzigingen.append((sub_id, kw))
                return dict(zelf.abonnement)

        class Customer:
            @staticmethod
            def create_balance_transaction(klant, **kw):
                if zelf.stuk:
                    raise RuntimeError("Stripe is onbereikbaar")
                zelf.tegoeden.append((klant, kw))
                return {"id": "cbtxn_1"}

        self.Subscription = Subscription
        self.Customer = Customer


@pytest.fixture()
def rw(monkeypatch):
    from backend.services import referral_rewards as r
    monkeypatch.setattr(r.settings, "stripe_secret_key", "sk_test", raising=False)
    # Geen mail en geen Supabase-auth in een test.
    monkeypatch.setattr(r, "mail_beloning", lambda *a, **k: True)
    monkeypatch.setattr(r, "mail_aanmelding", lambda *a, **k: True)
    monkeypatch.setattr(r, "email_van", lambda uid: f"{uid}@example.nl")
    monkeypatch.setattr(r, "is_owner_email", lambda e: False)
    monkeypatch.setattr(r, "invalidate_access_cache", lambda *a, **k: None)
    r.vergeet_kortingsrecht()
    return r


def _zet_db(monkeypatch, rw, db):
    """Dezelfde nepdatabase voor alle modules die eraan komen."""
    from backend.services import referral_codes
    monkeypatch.setattr(rw, "get_db", lambda: db)
    monkeypatch.setattr(referral_codes, "get_db", lambda: db)


# ── 1. De maand komt er echt ────────────────────────────────────────────────

def test_betalende_aanbrenger_krijgt_precies_een_maand_tegoed(rw, monkeypatch):
    db = _basis({"user_id": AANBRENGER, "status": "active",
                 "stripe_subscription_id": "sub_1", "stripe_customer_id": "cus_1"})
    _zet_db(monkeypatch, rw, db)
    stripe = NepStripe({"status": "active", "customer": "cus_1",
                        "items": {"data": [{"price": {"unit_amount": 1999}, "quantity": 1}]}})
    monkeypatch.setattr(rw, "stripe", stripe)

    assert rw.verwerk_beloning(VRIEND) == "toegekend"

    assert len(stripe.tegoeden) == 1, "er hoort precies één tegoed geboekt te zijn"
    klant, kw = stripe.tegoeden[0]
    assert klant == "cus_1"
    assert kw["amount"] == -1999, "negatief = tegoed; positief zou een SCHULD zijn"
    assert kw["currency"] == "eur"

    beloning = db.data["referral_rewards"][0]
    assert beloning["status"] == "granted"
    assert beloning["method"] == "tegoed"
    assert beloning["amount_cents"] == 1999


def test_tegoed_volgt_de_eigen_prijs_van_de_klant(rw, monkeypatch):
    """Wie ooit met korting is ingestapt betaalt minder dan 19,99. Eén maand
    gratis is dan ook minder, anders geven we meer weg dan een maand."""
    db = _basis({"user_id": AANBRENGER, "status": "active",
                 "stripe_subscription_id": "sub_1", "stripe_customer_id": "cus_1"})
    _zet_db(monkeypatch, rw, db)
    stripe = NepStripe({"status": "active", "customer": "cus_1",
                        "items": {"data": [{"price": {"unit_amount": 1499}, "quantity": 1}]}})
    monkeypatch.setattr(rw, "stripe", stripe)

    rw.verwerk_beloning(VRIEND)
    assert stripe.tegoeden[0][1]["amount"] == -1499


def test_proef_bij_stripe_schuift_een_maand_op(rw, monkeypatch):
    einde = NU + timedelta(days=3)
    db = _basis({"user_id": AANBRENGER, "status": "trialing",
                 "stripe_subscription_id": "sub_1", "stripe_customer_id": "cus_1",
                 "trial_ends_at": einde.isoformat()})
    _zet_db(monkeypatch, rw, db)
    stripe = NepStripe({"status": "trialing", "customer": "cus_1",
                        "trial_end": int(einde.timestamp()),
                        "items": {"data": [{"price": {"unit_amount": 1999}, "quantity": 1}]}})
    monkeypatch.setattr(rw, "stripe", stripe)

    assert rw.verwerk_beloning(VRIEND) == "toegekend"

    assert not stripe.tegoeden, "een proef hoeft geen tegoed, die schuift op"
    assert len(stripe.wijzigingen) == 1
    _sub, kw = stripe.wijzigingen[0]
    verschoven = datetime.fromtimestamp(kw["trial_end"], tz=timezone.utc)
    assert timedelta(days=32, hours=23) < verschoven - NU < timedelta(days=33, hours=1)
    # en onze eigen tabel weet het ook, anders zou de app een andere datum tonen
    assert db.data["subscriptions"][0]["trial_ends_at"][:10] == verschoven.date().isoformat()


def test_lopende_proef_zonder_stripe_houdt_zijn_resterende_dagen(rw, monkeypatch):
    einde = NU + timedelta(days=2)
    db = _basis({"user_id": AANBRENGER, "status": "trialing",
                 "stripe_subscription_id": None, "trial_ends_at": einde.isoformat()})
    _zet_db(monkeypatch, rw, db)
    monkeypatch.setattr(rw, "stripe", NepStripe())

    assert rw.verwerk_beloning(VRIEND) == "toegekend"
    nieuw = datetime.fromisoformat(db.data["subscriptions"][0]["trial_ends_at"])
    # 2 dagen die hij nog had + 30 erbij, niet 30 vanaf vandaag
    assert timedelta(days=31, hours=23) < nieuw - NU < timedelta(days=32, hours=1)


def test_verlopen_proef_gaat_weer_open(rw, monkeypatch):
    """Wie buitengesloten stond en een betalende klant aanbrengt, hoort binnen te
    komen. Anders is "een maand gratis" een maand die hij niet kan gebruiken."""
    db = _basis({"user_id": AANBRENGER, "status": "trial_expired",
                 "stripe_subscription_id": None,
                 "trial_ends_at": (NU - timedelta(days=5)).isoformat()})
    _zet_db(monkeypatch, rw, db)
    monkeypatch.setattr(rw, "stripe", NepStripe())

    assert rw.verwerk_beloning(VRIEND) == "toegekend"
    rij = db.data["subscriptions"][0]
    assert rij["status"] == "trialing"
    nieuw = datetime.fromisoformat(rij["trial_ends_at"])
    assert timedelta(days=29, hours=23) < nieuw - NU < timedelta(days=30, hours=1)


# ── 2. Nooit twee keer ──────────────────────────────────────────────────────

def test_dezelfde_vriend_levert_nooit_twee_maanden_op(rw, monkeypatch):
    db = _basis({"user_id": AANBRENGER, "status": "active",
                 "stripe_subscription_id": "sub_1", "stripe_customer_id": "cus_1"})
    _zet_db(monkeypatch, rw, db)
    stripe = NepStripe({"status": "active", "customer": "cus_1",
                        "items": {"data": [{"price": {"unit_amount": 1999}, "quantity": 1}]}})
    monkeypatch.setattr(rw, "stripe", stripe)

    assert rw.verwerk_beloning(VRIEND) == "toegekend"
    assert rw.verwerk_beloning(VRIEND) == "al_toegekend"
    assert rw.verwerk_beloning(VRIEND) == "al_toegekend"

    assert len(stripe.tegoeden) == 1, "twee webhooks mogen samen één maand opleveren"
    assert len(db.data["referral_rewards"]) == 1


def test_zelfverwijzing_levert_niets_op(rw, monkeypatch):
    db = _basis({"user_id": VRIEND, "status": "active", "stripe_subscription_id": "sub_1",
                 "stripe_customer_id": "cus_1"}, code_eigenaar=VRIEND)
    _zet_db(monkeypatch, rw, db)
    stripe = NepStripe({"status": "active"})
    monkeypatch.setattr(rw, "stripe", stripe)

    assert rw.verwerk_beloning(VRIEND) == "zelfverwijzing"
    assert not db.data["referral_rewards"]
    assert not stripe.tegoeden


def test_creatorcode_geeft_geen_gratis_maand(rw, monkeypatch):
    """Een influencer krijgt geld volgens zijn eigen afspraak. Zou hij hier ook
    een maand krijgen, dan werd er twee keer betaald voor dezelfde klant."""
    db = _basis({"user_id": AANBRENGER, "status": "active", "stripe_subscription_id": "sub_1"},
                code_eigenaar=None)
    _zet_db(monkeypatch, rw, db)
    monkeypatch.setattr(rw, "stripe", NepStripe({"status": "active"}))

    assert rw.verwerk_beloning(VRIEND) == "creatorcode"
    assert not db.data["referral_rewards"]


# ── 3. Wat er misgaat, gaat niet stil mis ───────────────────────────────────

def test_mislukte_toekenning_blijft_staan_en_lukt_daarna_alsnog(rw, monkeypatch):
    db = _basis({"user_id": AANBRENGER, "status": "active",
                 "stripe_subscription_id": "sub_1", "stripe_customer_id": "cus_1"})
    _zet_db(monkeypatch, rw, db)
    stuk = NepStripe(stuk=True)
    monkeypatch.setattr(rw, "stripe", stuk)

    assert rw.verwerk_beloning(VRIEND) == "mislukt"
    beloning = db.data["referral_rewards"][0]
    assert beloning["status"] == "pending"
    assert beloning["attempts"] == 1
    assert "onbereikbaar" in (beloning["last_error"] or "")

    # Stripe is er weer: dezelfde aanroep moet het alsnog afmaken.
    werkend = NepStripe({"status": "active", "customer": "cus_1",
                         "items": {"data": [{"price": {"unit_amount": 1999}, "quantity": 1}]}})
    monkeypatch.setattr(rw, "stripe", werkend)
    assert rw.verwerk_beloning(VRIEND) == "toegekend"
    assert db.data["referral_rewards"][0]["status"] == "granted"
    assert len(werkend.tegoeden) == 1


# ── 4. De voor-en-na-proef: een gemiste webhook ─────────────────────────────

def test_gemiste_webhook_zonder_herstelronde_levert_niets_op(rw, monkeypatch):
    """DE SITUATIE VOOR. De gratis maand hangt aan een Stripe-webhook. Komt die
    niet aan (uitrol, storing, een gemiste poging), dan wordt er niets
    aangeroepen en gebeurt er ook niets. Niemand merkt het: de aanbrenger weet
    niet beter, en in de database staat gewoon geen rij."""
    db = _basis({"user_id": AANBRENGER, "status": "active",
                 "stripe_subscription_id": "sub_1", "stripe_customer_id": "cus_1"})
    _zet_db(monkeypatch, rw, db)
    monkeypatch.setattr(rw, "stripe", NepStripe({"status": "active", "customer": "cus_1"}))

    # De vriend betaalt al een maand, maar de webhook is nooit aangekomen.
    db.data["subscriptions"].append({"user_id": VRIEND, "status": "active",
                                     "stripe_subscription_id": "sub_vriend"})
    assert db.data["referral_rewards"] == []
    assert db.data["referrals"][0]["first_paid_at"] is None


def test_de_herstelronde_kent_de_gemiste_maand_alsnog_toe(rw, monkeypatch):
    """DE SITUATIE NA. Precies dezelfde toestand, nu met de ronde die elk uur
    draait. Die kijkt zelf wie er betaalt en maakt het in orde."""
    import asyncio

    db = _basis({"user_id": AANBRENGER, "status": "active",
                 "stripe_subscription_id": "sub_1", "stripe_customer_id": "cus_1"})
    db.data["subscriptions"].append({"user_id": VRIEND, "status": "active",
                                     "stripe_subscription_id": "sub_vriend"})
    _zet_db(monkeypatch, rw, db)
    stripe = NepStripe({"status": "active", "customer": "cus_1",
                        "items": {"data": [{"price": {"unit_amount": 1999}, "quantity": 1}]}})
    monkeypatch.setattr(rw, "stripe", stripe)

    uitkomst = asyncio.run(rw.verwerk_openstaande_beloningen())

    assert uitkomst["toegekend"] == 1
    assert db.data["referral_rewards"][0]["status"] == "granted"
    assert len(stripe.tegoeden) == 1
    # en de commissieklok is alsnog gestempeld, anders loopt de creatortelling scheef
    assert db.data["referrals"][0]["first_paid_at"] is not None


def test_herstelronde_kent_niet_toe_zolang_er_nog_niet_betaald_is(rw, monkeypatch):
    """Een vriend in proef is nog geen maand waard. Dit is de rem die voorkomt
    dat iemand met tien e-mailadressen tien maanden pakt."""
    import asyncio

    db = _basis({"user_id": AANBRENGER, "status": "active",
                 "stripe_subscription_id": "sub_1", "stripe_customer_id": "cus_1"})
    db.data["subscriptions"].append({"user_id": VRIEND, "status": "trialing",
                                     "stripe_subscription_id": None})
    _zet_db(monkeypatch, rw, db)
    stripe = NepStripe({"status": "active", "customer": "cus_1"})
    monkeypatch.setattr(rw, "stripe", stripe)

    uitkomst = asyncio.run(rw.verwerk_openstaande_beloningen())

    assert uitkomst["toegekend"] == 0
    assert db.data["referral_rewards"] == []
    assert not stripe.tegoeden
    # de aanbrenger hoort wél te horen dat er iemand binnen is
    assert uitkomst["gemaild"] == 1
    assert db.data["referrals"][0]["aanmelding_gemeld_at"] is not None


def test_herstelronde_mailt_niet_over_oude_aanmeldingen(rw, monkeypatch):
    """De eerste ronde na de uitgifte zou anders iedereen mailen over
    aanmeldingen van weken geleden."""
    import asyncio

    db = _basis({"user_id": AANBRENGER, "status": "trialing", "stripe_subscription_id": None,
                 "trial_ends_at": (NU + timedelta(days=3)).isoformat()})
    db.data["referrals"][0]["created_at"] = (NU - timedelta(days=40)).isoformat()
    _zet_db(monkeypatch, rw, db)
    monkeypatch.setattr(rw, "stripe", NepStripe())
    gemaild = []
    monkeypatch.setattr(rw, "mail_aanmelding", lambda *a, **k: gemaild.append(a) or True)

    uitkomst = asyncio.run(rw.verwerk_openstaande_beloningen())

    assert uitkomst["gemaild"] == 0
    assert gemaild == []
    # wel afvinken, anders begint de ronde er elk uur opnieuw over
    assert db.data["referrals"][0]["aanmelding_gemeld_at"] is not None


# ── 5. De vriend betaalt de helft, en alleen de eerste maand ────────────────

def test_vriend_heeft_recht_op_korting_tot_hij_betaald_heeft(rw, monkeypatch):
    db = _basis({"user_id": AANBRENGER, "status": "active", "stripe_subscription_id": "sub_1"})
    _zet_db(monkeypatch, rw, db)

    rw.vergeet_kortingsrecht()
    assert rw.heeft_recht_op_vriendenkorting(VRIEND) is True

    # betaald: de korting was voor de eerste maand en is nu op
    db.data["referrals"][0]["first_paid_at"] = NU.isoformat()
    rw.vergeet_kortingsrecht()
    assert rw.heeft_recht_op_vriendenkorting(VRIEND) is False


def test_creatorcode_geeft_de_vriend_geen_halve_maand(rw, monkeypatch):
    """Bij een influencer betaalt Daniel al 25 euro bounty. Daar nog eens tien
    euro korting bovenop zou de klant duurder maken dan hij oplevert."""
    db = _basis({"user_id": AANBRENGER, "status": "active", "stripe_subscription_id": "sub_1"},
                code_eigenaar=None)
    _zet_db(monkeypatch, rw, db)
    rw.vergeet_kortingsrecht()
    assert rw.heeft_recht_op_vriendenkorting(VRIEND) is False


def _nep_checkout(monkeypatch, billing, verwezen: bool, promo=None):
    class Subscription:
        @staticmethod
        def list(**_kw):
            return types.SimpleNamespace(data=[])

    class Sessions:
        aangemaakt = []

        @staticmethod
        def create(**kw):
            Sessions.aangemaakt.append(kw)
            return types.SimpleNamespace(url="https://checkout.example/nieuw")

    monkeypatch.setattr(billing.stripe, "Subscription", Subscription, raising=False)
    monkeypatch.setattr(billing.stripe.checkout, "Session", Sessions, raising=False)
    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test", raising=False)
    monkeypatch.setattr(billing.settings, "stripe_price_id", "price_1", raising=False)
    monkeypatch.setattr(billing, "_get_or_create_subscription",
                        lambda uid: {"user_id": uid, "stripe_customer_id": "cus_1",
                                     "status": "trialing", "trial_ends_at": None})
    monkeypatch.setattr(billing, "find_active_promo", lambda: promo)
    monkeypatch.setattr(billing, "heeft_recht_op_vriendenkorting", lambda uid: verwezen)
    monkeypatch.setattr(billing, "vriendenkorting_coupon", lambda: "omnivaleur-vriendenkorting-50")
    Sessions.aangemaakt.clear()
    return Sessions


def test_afrekenen_zet_de_vriendenkorting_er_zelf_op(monkeypatch):
    import backend.api.billing as billing

    sessies = _nep_checkout(monkeypatch, billing, verwezen=True)
    billing.create_checkout(types.SimpleNamespace(id=VRIEND, email="vriend@example.nl"))

    args = sessies.aangemaakt[0]
    assert args["discounts"] == [{"coupon": "omnivaleur-vriendenkorting-50"}]
    # geen invulvakje ernaast: Stripe staat die twee niet samen toe
    assert "allow_promotion_codes" not in args


def test_zonder_uitnodiging_geen_korting(monkeypatch):
    import backend.api.billing as billing

    sessies = _nep_checkout(monkeypatch, billing, verwezen=False)
    billing.create_checkout(types.SimpleNamespace(id="u-los", email="los@example.nl"))

    args = sessies.aangemaakt[0]
    assert "discounts" not in args
    assert args["allow_promotion_codes"] is True


def test_de_hoogste_korting_wint(monkeypatch):
    """Een lopende actie van 25 procent mag iemand met een uitnodiging niet
    slechter af maken dan zonder."""
    import backend.api.billing as billing

    sessies = _nep_checkout(monkeypatch, billing, verwezen=True,
                            promo={"id": "promo_1", "percent_off": 25})
    billing.create_checkout(types.SimpleNamespace(id=VRIEND, email="vriend@example.nl"))
    assert sessies.aangemaakt[0]["discounts"] == [{"coupon": "omnivaleur-vriendenkorting-50"}]

    sessies = _nep_checkout(monkeypatch, billing, verwezen=True,
                            promo={"id": "promo_2", "percent_off": 70})
    billing.create_checkout(types.SimpleNamespace(id=VRIEND, email="vriend@example.nl"))
    assert sessies.aangemaakt[0]["discounts"] == [{"promotion_code": "promo_2"}]


# ── 6. Randgevallen die geld of toegang kosten als ze fout gaan ─────────────

def test_gratis_account_raakt_zijn_toegang_niet_kwijt(rw, monkeypatch):
    """Een handmatig gegeven gratis account (complimentary) heeft geen
    einddatum. Zou de beloning er een proefperiode van maken, dan zou een
    aanbrenger zijn onbeperkte toegang INLEVEREN voor dertig dagen."""
    db = _basis({"user_id": AANBRENGER, "status": "complimentary",
                 "stripe_subscription_id": None})
    _zet_db(monkeypatch, rw, db)
    monkeypatch.setattr(rw, "stripe", NepStripe())

    assert rw.verwerk_beloning(VRIEND) == "gratis_account"
    rij = db.data["subscriptions"][0]
    assert rij["status"] == "complimentary", "de gratis toegang moet blijven staan"
    assert db.data["referral_rewards"][0]["status"] == "skipped"


def test_zonder_abonnementsrij_blijft_de_beloning_openstaan(rw, monkeypatch):
    """Ontbreekt de abonnementsrij (RLS heeft dat hier eerder gedaan), dan mag de
    beloning niet stilletjes als afgehandeld worden weggeschreven: dan zou hij
    nooit meer komen."""
    db = _basis({"user_id": "iemand-anders", "status": "active",
                 "stripe_subscription_id": "sub_x"})
    _zet_db(monkeypatch, rw, db)
    monkeypatch.setattr(rw, "stripe", NepStripe({"status": "active"}))

    assert rw.verwerk_beloning(VRIEND) == "mislukt"
    beloning = db.data["referral_rewards"][0]
    assert beloning["status"] == "pending"
    assert beloning["attempts"] == 1
