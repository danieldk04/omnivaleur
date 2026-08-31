"""De postbus moet leesbaar zijn zonder de wachtwoorden te kennen.

WAAROM DIT ER IS (31-08-2026, Daniel)
Daniel: "kijk beter naar de mailbox en wat er ook al verzonden is en wat er in
concept staat (en of dat nog juist is). er is namelijk niks meer mbt
zilverwebsite wat openstaat op dit moment."

Dat kon de developer niet. De mailwachtwoorden (IMAP_HOST, MAIL_USER, MAIL_PASS)
staan alleen op Railway, dus vanaf een ontwikkelmachine is de postbus onzichtbaar.
Het gevolg was niet "een vraag die openbleef" maar een verkeerd antwoord: de
status werd opgemaakt uit de storingenlijst alleen, en daar stonden zeventien
meldingen van Zilverwebsite als "open" terwijl ze allang waren afgehandeld.

De agent draait tóch al elke tien minuten mét die toegang. Die legt nu vast wát
hij ziet, zodat iedereen die bij de administratie kan de postbus kan lezen
zonder één wachtwoord te kennen.

De grens die deze proeven bewaken: aan wie, waarover en wanneer — nooit de
inhoud van klantpost.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import leadgen_mail as L  # noqa: E402


class _NepImap:
    """Een postbus met één concept."""

    def __init__(self):
        self.gekozen = None

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def login(self, *_a):
        return ("OK", [])

    def list(self):
        return ("OK", [b'(\\HasNoChildren) "/" "Concept"',
                       b'(\\HasNoChildren) "/" "Sent"'])

    def select(self, naam, readonly=False):
        self.gekozen = naam
        return ("OK", [b"1"])

    def search(self, *_a):
        return ("OK", [b"1"])


def _zet_klaar(monkeypatch, verzonden=None):
    bewaard = {}
    monkeypatch.setenv("IMAP_HOST", "imap.test")
    monkeypatch.setenv("MAIL_USER", "hoi@test.nl")
    monkeypatch.setenv("MAIL_PASS", "geheim")
    monkeypatch.setattr(L.imaplib, "IMAP4_SSL", lambda *a, **k: _NepImap())
    monkeypatch.setattr(L, "_koppen_in_bulk", lambda _i, _n: {
        "1": {"To": "info@zilverwebsite.nl", "Subject": "Re: verversen",
              "Date": "Sun, 31 Aug 2026 09:34:55 +0200"}})
    monkeypatch.setattr(L, "_verzonden_lezen", lambda: verzonden if verzonden is not None else [
        {"adres": "info@papas-plectrums.nl", "naar": "info@papas-plectrums.nl",
         "op": 1788166066.0, "eigen": "de tekst van de mail", "verwijst": set()}])

    import mail_analyse
    monkeypatch.setattr(mail_analyse, "_schrijf",
                        lambda naam, inhoud: bewaard.update({naam: inhoud}) or True)
    return bewaard


def test_de_stand_wordt_weggeschreven(monkeypatch):
    """DE KERN. Zonder dit is de postbus onzichtbaar voor wie hem moet
    beoordelen."""
    bewaard = _zet_klaar(monkeypatch)

    L._leg_mailboxstand_vast()

    stand = bewaard.get("mailbox_stand")
    assert stand, "er is niets vastgelegd"
    assert stand["concepten"][0]["aan"] == "info@zilverwebsite.nl"
    assert stand["concepten"][0]["onderwerp"] == "Re: verversen"
    assert stand["verzonden_recent"][0]["aan"] == "info@papas-plectrums.nl"


def test_de_inhoud_van_klantpost_gaat_er_niet_in(monkeypatch):
    """De grens. Dit is een administratie om te weten óf er al een antwoord is,
    geen tweede opslagplaats voor klantpost."""
    bewaard = _zet_klaar(monkeypatch)

    L._leg_mailboxstand_vast()

    plat = repr(bewaard.get("mailbox_stand"))
    assert "de tekst van de mail" not in plat, "de berichtinhoud is meegeschreven"
    assert "eigen" not in plat, "het tekstveld is meegeschreven"


def test_verzonden_tijd_is_leesbaar(monkeypatch):
    """Een kaal getal als 1788166066.0 zegt niemand iets — en juist de vraag
    'is dit al beantwoord, en wanneer' moet in één oogopslag te zien zijn."""
    bewaard = _zet_klaar(monkeypatch)

    L._leg_mailboxstand_vast()

    op = bewaard["mailbox_stand"]["verzonden_recent"][0]["op"]
    assert op and op.startswith("2026-"), f"onleesbare tijd: {op!r}"


def test_zonder_mailtoegang_gebeurt_er_niets(monkeypatch):
    """Op een machine zonder wachtwoorden mag dit geen fout opleveren; de ronde
    moet gewoon doorgaan."""
    bewaard = _zet_klaar(monkeypatch)
    monkeypatch.delenv("MAIL_PASS", raising=False)

    L._leg_mailboxstand_vast()

    assert "mailbox_stand" not in bewaard, (
        "er is een lege stand weggeschreven; die zou de echte overschrijven")
