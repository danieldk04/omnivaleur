"""Proef op de zuivere hulpjes van scripts/zoho_mail_mcp.py (geen netwerk, geen mcp-pakket)."""
import email
import email.policy
import importlib.util
from pathlib import Path

import pytest

_pad = Path(__file__).resolve().parent.parent / "scripts" / "zoho_mail_mcp.py"
_spec = importlib.util.spec_from_file_location("zoho_mail_mcp", _pad)
Z = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(Z)


def test_utf7_rondje_met_accent_en_ampersand():
    for naam in ["Klanten", "Café & Bar", "Prullenbak ë"]:
        assert Z.utf7_decode(Z.utf7_encode(naam)) == naam


def test_mapnaam_wordt_gequote():
    assert Z.q("Klanten") == '"Klanten"'
    assert Z.q('a"b') == '"a\\"b"'


def test_datum_voor_imap():
    assert Z.imap_datum("2026-10-05") == "05-Oct-2026"
    with pytest.raises(ValueError):
        Z.imap_datum("2026-13-01")


def test_zoekcriteria_combineert_en_valt_terug_op_all():
    assert Z.zoekcriteria() == "ALL"
    c = Z.zoekcriteria(zoek="factuur", van="jan@x.nl", sinds="2026-10-01", alleen_ongelezen=True)
    assert c == 'UNSEEN TEXT "factuur" FROM "jan@x.nl" SINCE 01-Oct-2026'


def test_uid_lijst_weigert_rommel():
    assert Z.uid_lijst("12, 13") == ["12", "13"]
    with pytest.raises(ValueError):
        Z.uid_lijst("12; DELETE")


def test_antwoord_onderwerp_krijgt_re_maar_niet_dubbel():
    assert Z.antwoord_onderwerp("Vraag", "") == "Re: Vraag"
    assert Z.antwoord_onderwerp("Re: Vraag", "") == "Re: Vraag"
    assert Z.antwoord_onderwerp("Vraag", "Iets anders") == "Iets anders"


def test_antwoord_blijft_in_de_draad_en_is_platte_tekst():
    orig = email.message_from_string(
        "From: k@x.nl\nMessage-ID: <abc@x.nl>\nSubject: Vraag\n\nhoi",
        policy=email.policy.default)
    m = Z.bouw_bericht("daniel@omnivaleur.nl", "k@x.nl", "Re: Vraag", "Hallo", antwoord_op=orig)
    assert m["In-Reply-To"] == "<abc@x.nl>"
    assert m.get_content_type() == "text/plain"


def test_html_wordt_leesbare_tekst():
    raw = ("From: a@b.nl\nSubject: x\nContent-Type: text/html; charset=utf-8\n\n"
           "<style>p{}</style><p>Eerste</p><div>Tweede&nbsp;regel</div>")
    msg = email.message_from_string(raw, policy=email.policy.default)
    tekst = Z.mail_tekst(msg)
    assert "Eerste" in tekst and "Tweede regel" in tekst and "<" not in tekst
