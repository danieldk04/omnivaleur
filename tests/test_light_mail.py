"""De Light-mail aan iedereen zonder lopend abonnement.

Moet de juiste mensen bereiken (ook wie opzegde), nooit wie al betaalt, een gratis
meegegeven account, Daniel zelf, en nooit dezelfde persoon twee keer.
"""
import types
from datetime import datetime, timedelta, timezone

from backend.services import announcement as ann


def _nu(dagen):
    return (datetime.now(timezone.utc) + timedelta(days=dagen)).isoformat()


class _Tabel:
    def __init__(self, data):
        self.data = data
        self.upserts = []

    def __getattr__(self, naam):
        return lambda *a, **k: self

    def upsert(self, rij):
        self.upserts.append(rij)
        return self

    def execute(self):
        return types.SimpleNamespace(data=self.data)


def _nep_database(monkeypatch, subs, gebruikers, mail_events=None):
    tabellen = {"subscriptions": _Tabel(subs), "mail_events": _Tabel(mail_events or [])}
    db = types.SimpleNamespace(table=lambda n: tabellen[n])
    pagina = {"eerste": True}

    def list_users(page, per_page):
        if page > 1:
            return []
        return [types.SimpleNamespace(id=i, email=e) for i, e in gebruikers]

    admin = types.SimpleNamespace(
        auth=types.SimpleNamespace(admin=types.SimpleNamespace(list_users=list_users)),
        table=lambda n: tabellen[n])
    monkeypatch.setattr(ann, "get_db", lambda: db)
    monkeypatch.setattr(ann, "get_admin_db", lambda: admin)
    return tabellen


def test_juiste_mensen_krijgen_de_mail(monkeypatch):
    subs = [
        {"user_id": "betaalt", "status": "active", "stripe_subscription_id": "sub_1", "trial_ends_at": _nu(-60)},
        {"user_id": "proef_met_abo", "status": "trialing", "stripe_subscription_id": "sub_2", "trial_ends_at": _nu(5)},
        {"user_id": "opgezegd", "status": "canceled", "stripe_subscription_id": "sub_3", "trial_ends_at": _nu(-90)},
        {"user_id": "proef_zonder_abo", "status": "trialing", "stripe_subscription_id": None, "trial_ends_at": _nu(3)},
        {"user_id": "verlopen", "status": "trial_expired", "stripe_subscription_id": None, "trial_ends_at": _nu(-10)},
        {"user_id": "gratis_meegegeven", "status": "trialing", "stripe_subscription_id": None, "trial_ends_at": _nu(400)},
    ]
    gebruikers = [
        ("betaalt", "betaalt@example.nl"), ("proef_met_abo", "proefabo@example.nl"),
        ("opgezegd", "opgezegd@example.nl"), ("proef_zonder_abo", "proef@example.nl"),
        ("verlopen", "Verlopen@Example.nl"), ("gratis_meegegeven", "vriend@example.nl"),
        ("eigen", "info@revaleur.com"), ("eigen2", "daniel@omnivaleur.eu"), ("test", "x@example.invalid"), ("nogeen", "dkresellacademy@gmail.com"),
        ("dubbel", "proef@example.nl"),
    ]
    _nep_database(monkeypatch, subs, gebruikers)
    assert sorted(ann.collect_light_recipients()) == [
        "opgezegd@example.nl", "proef@example.nl", "verlopen@example.nl"]


def test_wie_de_mail_al_kreeg_wordt_herkend(monkeypatch):
    _nep_database(monkeypatch, [], [], mail_events=[{"ontvanger": "Al@Example.nl"}])
    assert ann.al_verstuurd(["al@example.nl", "nieuw@example.nl"]) == {"al@example.nl"}
    assert ann.al_verstuurd([]) == set()


def test_versturen_wordt_vastgelegd_per_adres(monkeypatch):
    tabellen = _nep_database(monkeypatch, [], [])
    assert ann.markeer_verstuurd("a@example.nl", "re_123") is True
    rij = tabellen["mail_events"].upserts[0]
    assert rij["svix_id"] == "light-mail-a@example.nl" and rij["type"] == ann.LIGHT_MAIL_TYPE


def test_vastleggen_faalt_zonder_de_verzending_te_breken(monkeypatch):
    def stuk():
        raise RuntimeError("tabel weg")
    monkeypatch.setattr(ann, "get_admin_db", stuk)
    assert ann.markeer_verstuurd("a@example.nl") is False


def test_mailtekst_is_platte_tekst_met_de_juiste_feiten():
    tekst = ann.LIGHT_BODY + ann.LIGHT_SUBJECT
    for verboden in ("—", "–", "**", "##", " - ", "€", "%"):
        assert verboden not in tekst, f"opmaak of leesteken in de mail: {verboden!r}"
    for feit in ("9,99", "19,99", "20 actieve artikelen", "omnivaleur.com/app"):
        assert feit in ann.LIGHT_BODY


def test_light_mail_draagt_een_meetpixel_die_de_telling_terugvindt(monkeypatch):
    """02-10-2026: Daniel wilde weten hoeveel mensen de mail openen. De echte
    verstuurroute moet een html-deel met pixel meegeven, en de code in die pixel
    moet door de echte tellerroute naar adres en mailnaam terug te lezen zijn."""
    import re
    from backend.api import billing, tracking
    from backend.services import email as mail

    verstuurd = []
    monkeypatch.setattr(mail, "send_email_checked",
                        lambda subject, body, to=None, reply_to=None, html=None, **k:
                        verstuurd.append((to, body, html)) or "rid-1")
    monkeypatch.setattr(ann, "markeer_verstuurd", lambda e, r=None: True)
    monkeypatch.setattr(ann, "al_verstuurd", lambda emails: set())
    monkeypatch.setattr(billing, "_is_owner_email", lambda e: True)

    billing.send_announcement(dry_run=False, emails="Klant@Voorbeeld.nl", soort="light",
                              user=types.SimpleNamespace(email="o@x.nl"))

    (to, body, html), = verstuurd
    assert to == "klant@voorbeeld.nl"
    assert html and body.split("\n")[0] in html            # zelfde tekst, plus opmaak
    code = re.search(r"/t/o/([A-Za-z0-9_-]+)", html).group(1)
    assert tracking._decode(code) == ("klant@voorbeeld.nl", "light-mail")
