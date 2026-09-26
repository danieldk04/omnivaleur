"""Koude mail gaat nooit via Resend.

AANLEIDING, 26-09-2026. Sinds de koude reeks op de server (Railway) draait, gaat
hij via Resend. Gemeten per lead: gmail-ontvangers antwoordden via Zoho 14 van
38 keer, via Resend 1 van 29 (p=0,001). Resend verbiedt bovendien koude mail, en
hetzelfde account verstuurt de wachtwoord- en factuurmails van de app. De reeks
gaat daarom terug naar Zoho via GitHub Actions.

Twee plekken die tegelijk draaien schrijven in dezelfde administratie en kunnen
iemand dubbel mailen. Daarom doet een beurt met RESEND_API_KEY in de omgeving
(dat is de server) helemaal niets meer: niet versturen, en ook de administratie
niet lezen of schrijven. Dit bestand legt vast dat het zo blijft.
"""
import argparse
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import leadgen_mail as L  # noqa: E402


class Geraakt(Exception):
    pass


def _raak(*_a, **_k):
    raise Geraakt()


@pytest.fixture
def args():
    return argparse.Namespace(per_dag=20, max_per_beurt=3)


def test_op_de_server_doet_een_beurt_niets(monkeypatch, args, capsys):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setattr(L, "_controleer_afzender", _raak)
    monkeypatch.setattr(L, "_state", _raak)
    monkeypatch.setattr(L, "_verstuur", _raak)
    monkeypatch.setattr(L, "_resend_stuur", _raak)
    L.tick(args)                               # mag niets aanraken
    assert "Resend" in capsys.readouterr().out


def test_zonder_resend_gaat_de_beurt_gewoon_door(monkeypatch, args):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setattr(L, "_controleer_afzender", _raak)
    with pytest.raises(Geraakt):
        L.tick(args)
