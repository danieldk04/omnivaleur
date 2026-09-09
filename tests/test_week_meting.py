"""De wekelijkse meting telt alleen wat binnen die ene week (ma..zo) valt.

WAAROM DIT ER IS
Het dashboard vergelijkt straks week op week. Dat werkt alleen als een mail die
op zondag 23:50 verstuurd is bij die week hoort en niet bij de volgende, en als
een open van mail 2 in week A niet meetelt in week B. Ook: mail 1 draagt geen
pixel, dus daar hoort nooit een open-percentage bij.
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import week_meting as W  # noqa: E402


class _Q:
    def __init__(self, data):
        self._data = data
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def gte(self, *a, **k): return self
    def lte(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self): return type("R", (), {"data": self._data})()
    def upsert(self, rij, **k):
        self._data.append(rij); return self


class _Admin:
    def __init__(self, tabellen, users):
        self._t = tabellen
        self.auth = type("A", (), {"admin": type("Ad", (), {
            "list_users": staticmethod(lambda page=1, per_page=1000: type("U", (), {"users": users})())
        })()})()
    def table(self, naam):
        return _Q(self._t.setdefault(naam, []))


def _zet(monkeypatch, mail_state=None, mail_opens=None, mail_reacties=None,
         users=None, mail_events=None):
    tabellen = {
        "leadgen_opslag": [
            {"naam": "mail_state", "inhoud": mail_state or {}},
            {"naam": "mail_opens", "inhoud": mail_opens or {}},
            {"naam": "mail_reacties", "inhoud": mail_reacties or []},
        ],
        "mail_events": mail_events or [],
        "week_metingen": [],
    }
    # leadgen_opslag: .eq(naam) filtert niet in de nep-Q, dus geef per naam terug
    class _AdminMetFilter(_Admin):
        def table(self, naam):
            if naam == "leadgen_opslag":
                return _LeadgenQ(tabellen["leadgen_opslag"])
            return _Q(tabellen.setdefault(naam, []))
    class _LeadgenQ(_Q):
        def __init__(self, rijen): self._rijen = rijen; self._naam = None
        def select(self, *a, **k): return self
        def eq(self, kol, waarde): self._naam = waarde; return self
        def execute(self):
            d = [r for r in self._rijen if r["naam"] == self._naam]
            return type("R", (), {"data": d})()
    admin = _AdminMetFilter(tabellen, users or [])
    monkeypatch.setattr(W, "get_admin_db", lambda: admin)
    return tabellen


WK = date(2026, 8, 31)  # maandag; week loopt t/m zo 2026-09-06


def test_alleen_deze_week_telt_mee(monkeypatch):
    state = {
        "a@x.nl": {"verstuurd": [
            {"op": "2026-09-07T23:50:00", "beurt": "mail1"},   # binnen
            {"op": "2026-09-08T00:10:00", "beurt": "mail1"},   # volgende week
        ]},
        "b@x.nl": {"verstuurd": [
            {"op": "2026-08-31T12:00:00", "beurt": "mail2"},   # vorige week
            {"op": "2026-09-03T09:00:00", "beurt": "mail2"},   # binnen
        ]},
    }
    opens = {
        "b@x.nl": {"mail2": {"eerst": "2026-09-04T10:00:00", "aantal": 2}},
        "c@x.nl": {"mail2": {"eerst": "2026-08-30T10:00:00", "aantal": 1}},  # vorige week
        "d@x.nl": {"mail3": {"eerst": "2026-09-05T10:00:00", "aantal": 1}},  # telt niet: geen mail3 verstuurd deze week
    }
    reacties = [
        {"op": "2026-09-02T08:00:00", "soort": "warm"},
        {"op": "2026-09-06T08:00:00", "soort": "afwijzing"},
        {"op": "2026-08-20T08:00:00", "soort": "warm"},   # vorige periode
    ]
    users = [
        {"created_at": "2026-09-01T00:00:01Z", "email_confirmed_at": "2026-09-01T01:00:00Z"},
        {"created_at": "2026-09-07T23:59:00Z", "email_confirmed_at": None},
        {"created_at": "2026-08-25T00:00:00Z", "email_confirmed_at": "x"},  # buiten
    ]
    _zet(monkeypatch, state, opens, reacties, users)

    r = W.meet_week(WK)
    assert r["week_maandag"] == "2026-09-01"
    assert r["signups_nieuw"] == 2 and r["signups_bevestigd"] == 1
    assert r["km_mail1"] == 1 and r["km_mail2"] == 1 and r["km_mail3"] == 0
    assert r["km_verstuurd"] == 2
    assert r["km_geopend_mail2"] == 1
    assert r["km_open_pct_mail2"] == 100.0     # 1 open op 1 verstuurde mail2
    assert r["km_open_pct_mail3"] is None      # niets verstuurd
    assert r["km_antwoorden"] == 2 and r["km_positief"] == 1


def test_bezorging_uit_mail_events(monkeypatch):
    events = [
        {"type": "email.delivered", "domein": "omnivaleur.nl", "gebeurd_op": "2026-09-02T10:00:00+00:00"},
        {"type": "email.delivered", "domein": "omnivaleur.nl", "gebeurd_op": "2026-09-03T10:00:00+00:00"},
        {"type": "email.bounced", "domein": "omnivaleur.nl", "gebeurd_op": "2026-09-03T11:00:00+00:00"},
        {"type": "email.delivered", "domein": "omnivaleur.com", "gebeurd_op": "2026-09-04T10:00:00+00:00"},
        {"type": "email.complained", "domein": "omnivaleur.nl", "gebeurd_op": "2026-09-05T10:00:00+00:00"},
    ]
    _zet(monkeypatch, mail_events=events)
    r = W.meet_week(WK)
    assert r["km_afgeleverd"] == 2 and r["km_bounced"] == 1 and r["km_geklaagd"] == 1
    assert r["km_bounce_pct"] == 33.3
    assert r["app_afgeleverd"] == 1
    assert r["details"]["resend_webhook_liep"] is True


def test_geen_mail_events_laat_bezorging_leeg(monkeypatch):
    _zet(monkeypatch)
    r = W.meet_week(WK)
    assert r["km_bounced"] is None and r["km_afgeleverd"] is None
    assert r["details"]["resend_webhook_liep"] is False


def test_sla_op_schrijft_een_rij(monkeypatch):
    tabellen = _zet(monkeypatch, users=[])
    uit = W.sla_op(WK)
    assert uit["ok"] is True
    assert tabellen["week_metingen"][0]["week_maandag"] == "2026-09-01"
