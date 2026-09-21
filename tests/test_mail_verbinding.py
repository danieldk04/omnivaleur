"""De 'verbinding'-campagne: drie groepen naar HUIDIGE abonnementsstatus, elke
verstuurpoging gelogd, en niemand twee keer binnen drie dagen.

WAT ER BEPROEFD WORDT, en waarom juist dit:

  * Groep A en C overlapten eerder echt (30 vs 41, zie docs/team-notes.md
    21-09-2026): iemand die nooit iets plaatste EN wiens proef verlopen was,
    zat in allebei. De fix koppelt de groep aan de HUIDIGE status, niet aan
    geschiedenis. Deze proef zet iemand met precies dat profiel in de fake
    database en bewijst dat hij nu in exact één groep valt.
  * Wie zich heeft afgemeld mag in GEEN ENKELE groep meer voorkomen, ook niet
    als zijn abonnementsstatus daar prima bij past.
  * Een test-/beoordelaarsaccount (plus-adressering, eigen domein) hoort nooit
    in een echte verzendlijst.
  * De 1-per-3-dagen-regel geldt over ALLE campagnesoorten heen: wie gisteren
    al een 'verbinding_trial'-mail kreeg, mag vandaag geen 'verbinding_customer'
    krijgen, ook al zit hij inmiddels in een andere groep.
  * dry_run verstuurt aantoonbaar niets: de nep-mailfunctie mag nul keer
    aangeroepen zijn.
  * Elke tekst bestaat uit een Engels stuk EN het Nederlandse stuk erbij; geen
    losse vertaalde variant, want er is geen betrouwbaar taalveld per gebruiker
    (zie de module-docstring in backend/services/mail_verbinding.py).
"""
from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta, timezone

import pytest


# ── Minimale nep-Supabase: precies de aanroepen die dit bestand echt doet ────

class _Uitkomst:
    def __init__(self, data):
        self.data = data


class _NepQuery:
    def __init__(self, rijen):
        # GEEN kopie: dit moet dezelfde lijst zijn als db._tabellen[naam], anders
        # verdwijnt een insert() zodra de volgende .table(...)-aanroep een
        # nieuwe _NepQuery om een kopie van de kopie heen bouwt.
        self._rijen = rijen
        self._filters = []
        self._bereik = None

    def select(self, *_a, **_kw):
        return self

    def eq(self, kolom, waarde):
        self._filters.append((kolom, "eq", waarde))
        return self

    def gte(self, kolom, waarde):
        self._filters.append((kolom, "gte", waarde))
        return self

    def in_(self, kolom, waarden):
        self._filters.append((kolom, "in", list(waarden)))
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, n):
        self._bereik = (0, n - 1)
        return self

    def range(self, start, end):
        # ECHT toepassen: fetch_all() in backend/database.py stopt pas zodra
        # een pagina leeg terugkomt. Een neppe .range() die niets doet geeft
        # altijd dezelfde volle set terug, en dan loopt die paginering nooit af.
        self._bereik = (start, end)
        return self

    def insert(self, lading):
        self._rijen.append(lading)
        return self

    def upsert(self, lading, **_kw):
        self._rijen.append(lading)
        return self

    def _past(self, rij):
        for kolom, soort, waarde in self._filters:
            v = rij.get(kolom)
            if soort == "eq" and v != waarde:
                return False
            if soort == "gte" and (v is None or v < waarde):
                return False
            if soort == "in" and v not in waarde:
                return False
        return True

    def execute(self):
        gefilterd = [r for r in self._rijen if self._past(r)]
        if self._bereik is not None:
            start, end = self._bereik
            gefilterd = gefilterd[start:end + 1]
        return _Uitkomst(gefilterd)


class _NepGebruiker:
    def __init__(self, id_, email):
        self.id = id_
        self.email = email


class _NepAuthAdmin:
    def __init__(self, gebruikers):
        self._gebruikers = gebruikers

    def list_users(self, page=1, per_page=200):
        start = (page - 1) * per_page
        return self._gebruikers[start:start + per_page]

    def get_user_by_id(self, uid):
        for g in self._gebruikers:
            if g.id == uid:
                return types.SimpleNamespace(user=g)
        return types.SimpleNamespace(user=None)


class NepDb:
    """Eén db-object met vaste tabellen (subscriptions, mail_unsubscribed,
    mail_campaign_log) en een vaste gebruikerslijst voor auth.admin."""

    def __init__(self, gebruikers, subscriptions=None, unsubscribed=None, campaign_log=None,
                 update_actueel=None):
        self.auth = types.SimpleNamespace(admin=_NepAuthAdmin(gebruikers))
        self._tabellen = {
            "subscriptions": list(subscriptions or []),
            "mail_unsubscribed": list(unsubscribed or []),
            "mail_campaign_log": list(campaign_log or []),
            "mail_update_actueel": list(update_actueel or []),
        }

    def table(self, naam):
        return _NepQuery(self._tabellen.setdefault(naam, []))


def _gebruiker(uid, email):
    return _NepGebruiker(uid, email)


@pytest.fixture
def mail_verbinding(monkeypatch):
    """Fris geïmporteerd bij elke test, met een neppe settings.secret_key zodat
    de afmeldtoken voorspelbaar is."""
    for mod in ("backend.services.mail_verbinding",):
        sys.modules.pop(mod, None)
    from backend.services import mail_verbinding as mv
    monkeypatch.setattr(mv.settings, "secret_key", "test-secret-niet-echt")
    return mv


# ── Segmenten: geen overlap, ook niet in het exacte geval dat eerder brak ────

def test_trial_en_inactive_sluiten_elkaar_uit(monkeypatch, mail_verbinding):
    mv = mail_verbinding
    gebruikers = [
        _gebruiker("u-trial-leeg", "trial-leeg@voorbeeld.nl"),     # trialing, nog nooit geplaatst
        _gebruiker("u-verlopen", "verlopen@voorbeeld.nl"),          # trial_expired, ook nooit geplaatst
        _gebruiker("u-klant", "klant@voorbeeld.nl"),                # active
        _gebruiker("u-processing", "processing@voorbeeld.nl"),      # payment_processing -> telt als klant
        _gebruiker("u-opgezegd", "opgezegd@voorbeeld.nl"),          # canceled -> geen enkele groep
    ]
    subs = [
        {"user_id": "u-trial-leeg", "status": "trialing"},
        {"user_id": "u-verlopen", "status": "trial_expired"},
        {"user_id": "u-klant", "status": "active"},
        {"user_id": "u-processing", "status": "payment_processing"},
        {"user_id": "u-opgezegd", "status": "canceled"},
    ]
    db = NepDb(gebruikers, subscriptions=subs)
    monkeypatch.setattr("backend.database.get_admin_db", lambda: db)

    s = mv.segmenten()

    assert [r["user_id"] for r in s["trial"]] == ["u-trial-leeg"]
    assert [r["user_id"] for r in s["inactive"]] == ["u-verlopen"]
    assert sorted(r["user_id"] for r in s["customer"]) == ["u-klant", "u-processing"]
    # De vroegere bug: iemand die nooit plaatste EN wiens proef verlopen was
    # zat in zowel A (toen: "nooit geplaatst") als C ("trial_expired"). Met de
    # huidige, status-gebaseerde indeling kan dat niet meer: elke gebruiker
    # staat in precies één lijst, of in geen enkele (canceled).
    alle_ids = [r["user_id"] for groep in s.values() for r in groep]
    assert len(alle_ids) == len(set(alle_ids))
    assert "u-opgezegd" not in alle_ids


def test_afgemeld_verschijnt_in_geen_enkele_groep(monkeypatch, mail_verbinding):
    mv = mail_verbinding
    gebruikers = [_gebruiker("u-1", "afgemeld@voorbeeld.nl")]
    subs = [{"user_id": "u-1", "status": "trialing"}]
    afgemeld = [{"user_id": "u-1", "email": "afgemeld@voorbeeld.nl"}]
    db = NepDb(gebruikers, subscriptions=subs, unsubscribed=afgemeld)
    monkeypatch.setattr("backend.database.get_admin_db", lambda: db)

    s = mv.segmenten()

    assert all(r["user_id"] != "u-1" for groep in s.values() for r in groep)


def test_testaccount_wordt_overgeslagen(monkeypatch, mail_verbinding):
    mv = mail_verbinding
    gebruikers = [
        _gebruiker("u-test", "iemand+omnitest@omnivaleur.com"),
        _gebruiker("u-echt", "echte.klant@voorbeeld.nl"),
    ]
    subs = [
        {"user_id": "u-test", "status": "trialing"},
        {"user_id": "u-echt", "status": "trialing"},
    ]
    db = NepDb(gebruikers, subscriptions=subs)
    monkeypatch.setattr("backend.database.get_admin_db", lambda: db)

    s = mv.segmenten()

    assert [r["email"] for r in s["trial"]] == ["echte.klant@voorbeeld.nl"]


# ── Afmeldtoken: geldig voor de juiste gebruiker, ongeldig voor een geraden of gewijzigd id ──

def test_token_klopt_alleen_voor_de_eigen_gebruiker(mail_verbinding):
    mv = mail_verbinding
    token = mv._token("u-1")
    assert mv.token_geldig("u-1", token)
    assert not mv.token_geldig("u-2", token)
    assert not mv.token_geldig("u-1", token[:-1] + ("0" if token[-1] != "0" else "1"))


# ── Teksten: Engels EN het Nederlandse stuk aanwezig, voor elke groep ────────

@pytest.mark.parametrize("groep", ["trial", "inactive", "customer"])
def test_render_bevat_engels_en_nederlands(mail_verbinding, groep):
    mv = mail_verbinding
    link = "https://omnivaleur.com/api/mail-verbinding/unsubscribe?u=x&t=y"
    html = mv.render_html(groep, link)
    tekst = mv.render_text(groep, link)
    onderwerp = mv.render_subject(groep)

    for inhoud in (html, tekst):
        assert "Earn a free month" in inhoud
        assert "gratis maand" in inhoud
        assert link in inhoud
        # Geen kale voornaam-placeholder: er is nergens een naam bekend, dus
        # dit moet altijd "Hi," zijn, nooit "Hi {voornaam},".
        assert "{voornaam}" not in inhoud
    assert "/" in onderwerp  # Engels / Nederlands in één onderwerpregel


def test_render_html_heeft_geen_markdown_sterretjes(mail_verbinding):
    # Regel: geen sterretjes of markdown in de platte-tekstversie.
    tekst = mail_verbinding.render_text("customer", "https://omnivaleur.com/x")
    assert "*" not in tekst


# ── Versturen: dry_run raakt de mailfunctie niet aan, en de 3-dagenregel werkt ──

def test_dry_run_verstuurt_niets(monkeypatch, mail_verbinding):
    mv = mail_verbinding
    gebruikers = [_gebruiker("u-1", "iemand@voorbeeld.nl")]
    subs = [{"user_id": "u-1", "status": "trialing"}]
    db = NepDb(gebruikers, subscriptions=subs)
    monkeypatch.setattr("backend.database.get_admin_db", lambda: db)

    aangeroepen = []
    monkeypatch.setattr("backend.services.email.send_email_checked",
                        lambda *a, **kw: aangeroepen.append((a, kw)) or "nep-id")

    uitslag = mv.verstuur_groep("trial", dry_run=True)

    assert uitslag["dry_run"] is True
    assert uitslag["zou_versturen_aan"] == 1
    assert aangeroepen == []


def test_recent_gemaild_wordt_overgeslagen_over_alle_soorten_heen(monkeypatch, mail_verbinding):
    mv = mail_verbinding
    gebruikers = [
        _gebruiker("u-vers", "vers@voorbeeld.nl"),
        _gebruiker("u-net-gemaild", "net-gemaild@voorbeeld.nl"),
    ]
    subs = [
        {"user_id": "u-vers", "status": "trialing"},
        {"user_id": "u-net-gemaild", "status": "trialing"},
    ]
    nu = datetime.now(timezone.utc)
    log = [{
        "id": 1, "user_id": "u-net-gemaild", "email": "net-gemaild@voorbeeld.nl",
        # Andere soort ('verbinding_customer'), maar de regel geldt over ALLE
        # soorten heen: dit moet hem tóch blokkeren voor de trial-groep.
        "kind": "verbinding_customer", "segment": "customer", "taal": "en",
        "sent_at": (nu - timedelta(hours=6)).isoformat(),
    }]
    db = NepDb(gebruikers, subscriptions=subs, campaign_log=log)
    monkeypatch.setattr("backend.database.get_admin_db", lambda: db)

    verstuurd = []

    def _nep_send(*_a, **kw):
        verstuurd.append(kw.get("to"))
        return "nep-id"

    monkeypatch.setattr("backend.services.email.send_email_checked", _nep_send)

    uitslag = mv.verstuur_groep("trial", dry_run=False)

    assert uitslag["verstuurd"] == 1
    assert verstuurd == ["vers@voorbeeld.nl"]
    # Terugkijken in de log: er moet nu een rij bij staan voor de verse mail.
    logrijen = db._tabellen["mail_campaign_log"]
    assert any(r.get("email") == "vers@voorbeeld.nl" and r.get("kind") == "verbinding_trial"
              for r in logrijen)


# ── Wekelijkse update: eigen inhoud, nooit stil terugvallen op verzonnen tekst ──

def test_weekupdate_wordt_vastgelegd_en_teruggelezen(monkeypatch, mail_verbinding):
    mv = mail_verbinding
    db = NepDb([])
    monkeypatch.setattr("backend.database.get_admin_db", lambda: db)

    blokjes = [{
        "titel_en": "Faster Vinted publishing", "tekst_en": "Listings go live sooner.",
        "titel_nl": "Vinted publiceert sneller", "tekst_nl": "Advertenties staan eerder live.",
    }]
    mv.stel_weekupdate_op(blokjes, "2026-09-21")

    update = mv.huidige_weekupdate()
    assert update["week_van"] == "2026-09-21"
    assert update["status"] == "concept"
    assert update["blokjes"][0]["titel_en"] == "Faster Vinted publishing"


def test_weekupdate_weigert_een_leeg_of_onvolledig_blokje(mail_verbinding):
    mv = mail_verbinding
    with pytest.raises(ValueError):
        mv.stel_weekupdate_op([], "2026-09-21")
    with pytest.raises(ValueError):
        # tekst_nl ontbreekt — dit zou een half ingevuld blokje versturen
        mv.stel_weekupdate_op([{"titel_en": "x", "tekst_en": "y", "titel_nl": "z"}], "2026-09-21")


def test_render_gebruikt_de_meegegeven_blokjes_niet_de_vaste(mail_verbinding):
    mv = mail_verbinding
    eigen_blokjes = [{
        "titel_en": "Unique weekly headline", "tekst_en": "Body text.",
        "titel_nl": "Unieke koptekst", "tekst_nl": "Body tekst.",
    }]
    html = mv.render_html("customer", "https://omnivaleur.com/x", blokjes=eigen_blokjes)
    tekst = mv.render_text("customer", "https://omnivaleur.com/x", blokjes=eigen_blokjes)

    assert "Unique weekly headline" in html
    assert "Unique weekly headline" in tekst
    # De vaste, evergreen inhoud hoort er dan NIET ook nog in te staan.
    assert "Earn a free month" not in html
    assert "Earn a free month" not in tekst


def test_afbeelding_url_komt_in_de_html_alleen_bij_https(mail_verbinding):
    mv = mail_verbinding
    met_https = [{
        "titel_en": "x", "tekst_en": "y", "titel_nl": "z", "tekst_nl": "w",
        "afbeelding_url": "https://img.omnivaleur.com/screenshot1.png",
    }]
    html = mv.render_html("customer", "https://omnivaleur.com/x", blokjes=met_https)
    assert 'src="https://img.omnivaleur.com/screenshot1.png"' in html

    met_onveilige_url = [{
        "titel_en": "x", "tekst_en": "y", "titel_nl": "z", "tekst_nl": "w",
        "afbeelding_url": "http://onveilig.example/foto.png",
    }]
    html = mv.render_html("customer", "https://omnivaleur.com/x", blokjes=met_onveilige_url)
    assert "onveilig.example" not in html

    zonder_afbeelding = [{"titel_en": "x", "tekst_en": "y", "titel_nl": "z", "tekst_nl": "w"}]
    html = mv.render_html("customer", "https://omnivaleur.com/x", blokjes=zonder_afbeelding)
    assert "<img" not in html.split("</tr>", 1)[-1] or "logo.png" in html
