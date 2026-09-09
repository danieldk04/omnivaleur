"""De Resend-webhook mag alleen echte, ondertekende gebeurtenissen doorlaten.

WAAROM DIT ER IS
mail_events voedt de wekelijkse bezorgmeting. Een webhook zonder
handtekeningcontrole laat iedereen die het adres kent nep-bounces en
nep-bezorgingen in die tabel schrijven, en dan liegt het dashboard. De
handtekening volgt het Svix-schema dat Resend gebruikt: HMAC-SHA256 over
"{svix-id}.{svix-timestamp}.{body}" met de base64-gedecodeerde sleutel.
"""
import base64
import hashlib
import hmac
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import settings  # noqa: E402
from backend.api.webhooks import _resend_handtekening_klopt  # noqa: E402

GEHEIM = "whsec_" + base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()


def _onderteken(body: bytes, svix_id: str, ts: str, geheim: str = GEHEIM) -> str:
    sleutel = base64.b64decode(geheim.split("_", 1)[1])
    ondertekend = b"%s.%s.%s" % (svix_id.encode(), ts.encode(), body)
    sig = base64.b64encode(hmac.new(sleutel, ondertekend, hashlib.sha256).digest()).decode()
    return f"v1,{sig}"


class _Headers(dict):
    def get(self, k, d=None):  # request.headers is hoofdletterongevoelig
        return super().get(k.lower(), d)


def _kop(body, svix_id="msg_1", ts=None, sig=None):
    ts = ts or str(int(time.time()))
    return _Headers({
        "svix-id": svix_id,
        "svix-timestamp": ts,
        "svix-signature": sig if sig is not None else _onderteken(body, svix_id, ts),
    })


def test_geldige_handtekening_wordt_geaccepteerd(monkeypatch):
    monkeypatch.setattr(settings, "resend_webhook_secret", GEHEIM)
    body = b'{"type":"email.delivered","data":{"email_id":"x"}}'
    assert _resend_handtekening_klopt(body, _kop(body)) is True


def test_gemanipuleerde_body_wordt_geweigerd(monkeypatch):
    monkeypatch.setattr(settings, "resend_webhook_secret", GEHEIM)
    body = b'{"type":"email.delivered"}'
    kop = _kop(body)
    assert _resend_handtekening_klopt(b'{"type":"email.bounced"}', kop) is False


def test_zonder_geheim_gaat_er_niets_door(monkeypatch):
    monkeypatch.setattr(settings, "resend_webhook_secret", "")
    body = b"{}"
    assert _resend_handtekening_klopt(body, _kop(body)) is False


def test_oude_tijdstempel_wordt_geweigerd(monkeypatch):
    monkeypatch.setattr(settings, "resend_webhook_secret", GEHEIM)
    body = b"{}"
    oud = str(int(time.time()) - 4000)
    assert _resend_handtekening_klopt(body, _kop(body, ts=oud)) is False


def test_meerdere_handtekeningen_in_de_kop(monkeypatch):
    """Svix stuurt bij sleutelrotatie meerdere spaties-gescheiden waarden mee."""
    monkeypatch.setattr(settings, "resend_webhook_secret", GEHEIM)
    body = b'{"ok":1}'
    ts = str(int(time.time()))
    echt = _onderteken(body, "msg_9", ts)
    kop = _kop(body, svix_id="msg_9", ts=ts, sig=f"v1,ongeldige==== {echt}")
    assert _resend_handtekening_klopt(body, kop) is True
