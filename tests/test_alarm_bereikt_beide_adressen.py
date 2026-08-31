"""Een systeemmail aan de eigenaar moet bij álle eigenaren aankomen.

WAAROM DIT ER IS (31-08-2026)
Vanochtend lag Omnivaleur plat doordat Supabase het project op slot zette.
Daniel hoorde dat niet van zijn eigen server maar van Ronald, een klant, om
07:22. Daar is diezelfde dag een alarm voor gebouwd (`meld_quotastoring` in
backend/database.py) — maar dat alarm zou het ook niet gered hebben.

`owner_email` staat op Railway op twee adressen in één instelling:
"dkresellacademy@gmail.com, aertssen.pleun@gmail.com". `is_owner_email` in
billing.py splitste dat al netjes op komma's; de mailverzending deed dat niet
en gaf Resend `to: ["a@x.nl, b@y.nl"]` — één string met een komma erin, wat
Resend afwijst als ongeldig adres.

De combinatie maakte het onzichtbaar: `meld_quotastoring` vangt een mislukt
alarm expres af zodat een mailprobleem nooit iets blokkeert. De afwijzing
verdween dus in de logregels van de container, die bij de volgende deploy weg
zijn. Het alarm dat moest melden dat de site eruit lag, kon zichzelf niet
bezorgen en zei daar niets over.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import email as mail  # noqa: E402

TWEE = "dkresellacademy@gmail.com, aertssen.pleun@gmail.com"


def test_twee_adressen_in_een_instelling_worden_twee_ontvangers():
    """DE KERN. Dit is precies de waarde die op Railway staat."""
    assert mail.ontvangers(TWEE) == [
        "dkresellacademy@gmail.com", "aertssen.pleun@gmail.com"]


def test_een_enkel_adres_blijft_gewoon_een_adres():
    assert mail.ontvangers("info@zilverwebsite.nl") == ["info@zilverwebsite.nl"]


def test_lege_en_rommelige_waarden_leveren_niets_op():
    """Een lege instelling moet leiden tot een duidelijke fout bij het
    versturen, niet tot een mail aan het adres "" dat nergens aankomt."""
    for rommel in ("", None, "   ", ",", " , , "):
        assert mail.ontvangers(rommel) == [], f"{rommel!r} gaf wel adressen"


def test_resend_krijgt_een_echte_lijst_en_niet_een_string_met_kommas(monkeypatch):
    """Dit is wat er de deur uit ging: Resend wees het af, en niemand zag het."""
    verstuurd = {}

    class _Antwoord:
        status_code = 200
        text = "ok"

    class _Httpx:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            verstuurd.update(json or {})
            return _Antwoord()

    monkeypatch.setitem(sys.modules, "httpx", _Httpx)
    monkeypatch.setattr(mail.settings, "resend_api_key", "test", raising=False)
    monkeypatch.setattr(mail.settings, "resend_from", "hoi@omnivaleur.nl", raising=False)
    monkeypatch.setattr(mail.settings, "owner_email", TWEE, raising=False)

    mail.send_email_checked("Omnivaleur ligt eruit", "de tekst")

    assert verstuurd["to"] == ["dkresellacademy@gmail.com", "aertssen.pleun@gmail.com"], (
        f"Resend kreeg {verstuurd['to']!r}; met een komma in één string wordt "
        f"dat afgewezen en komt het alarm bij niemand aan")


def test_zonder_ontvanger_klapt_het_hoorbaar(monkeypatch):
    """Zwijgend niets versturen is hoe dit weken onopgemerkt bleef."""
    monkeypatch.setattr(mail.settings, "resend_api_key", "test", raising=False)
    monkeypatch.setattr(mail.settings, "resend_from", "hoi@omnivaleur.nl", raising=False)
    monkeypatch.setattr(mail.settings, "owner_email", "", raising=False)

    try:
        mail.send_email_checked("onderwerp", "tekst")
    except RuntimeError as e:
        assert "ontvangeradres" in str(e)
    else:
        raise AssertionError("een mail zonder ontvanger moet een fout geven")
