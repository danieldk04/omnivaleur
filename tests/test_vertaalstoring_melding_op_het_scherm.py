"""Wat de verkoper leest als de vertaling plat ligt — uit het échte eindpunt.

De Juiste Toon, 09-09-2026: "wit blok wat elke keer verschijnt", met de tekst
"The server didn't answer in time (503) ... it was busy or restarting". De
server was niet druk. Het Anthropic-tegoed was op, de vertaalstap viel om, en
zijn "Perzisch tapijtje versleten sleets rood taupe 128/79" heeft te weinig
Nederlandse stopwoorden om zonder vertaling door te mogen. Dat tegenhouden is
juist; het antwoord dat hij erover kreeg niet.

Deze proef roept het echte crosslist-eindpunt aan met een omgevallen
vertaalstap en kijkt naar wat er precies terugkomt: een statuscode die
Cloudflare ongemoeid doorlaat, en een tekst die klopt over de wachtrij.
"""
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.items as items_api  # noqa: E402
import backend.services.crosslist as cl  # noqa: E402

HET_TAPIJTJE = {
    "id": "75d4f88f-3ff8-4707-aaff-da1850fa698e",
    "user_id": "96e30080-ab81-47ac-8626-e8637f1e2a9e",
    "title": "Perzisch tapijtje versleten sleets rood taupe 128/79",
    "description": ("Perzisch tapijtje Versleten Sleets Rood taupe "
                    "Tweezijdig franje Afmetingen: 118/79 excl franje "
                    "Tl79 \nDejuistetoon Etten-Leur"),
}
# Eén van de zeven artikelen die diezelfde avond wél een opdracht kregen.
EEN_LEDERHOSEN = {
    "title": "Lederhosen kort incl bretels maat 50",
    "description": ("Korte Lederhosen handgemaakt\nEr staat maat 50 in\n"
                    "Vermoed gemaakt voor dame\nTaille plat gemeten 48 cm\n"
                    "Incl hippe bretels\nZeker geschikt voor de oktober feesten"),
}


def test_alleen_dit_artikel_wordt_tegengehouden():
    """De zeef die het verschil maakte, op de echte teksten van die avond.

    Zonder deze tegenmeting bewijst de rest niets: dan weten we alleen dat er
    íéts misging, niet waarom juist dit ene artikel vastliep terwijl de andere
    zeven gewoon in de wachtrij kwamen.
    """
    def samen(item):
        return f"{item['title']}\n{item['description']}"

    assert cl.lijkt_al_in_taal(samen(EEN_LEDERHOSEN), "nl") is True
    assert cl.lijkt_al_in_taal(samen(HET_TAPIJTJE), "nl") is False


class _Query:
    def __init__(self, rijen):
        self._rijen = rijen

    def __getattr__(self, _naam):
        def bouw(*_a, **_kw):
            return self
        return bouw

    def execute(self):
        class R:
            data = self._rijen
        return R()


class _DB:
    def table(self, _naam):
        return _Query([HET_TAPIJTJE])


def test_publiceren_bij_een_vertaalstoring(monkeypatch):
    async def valt_om(*_a, **_kw):
        raise cl.VertalingOnbeschikbaar("De vertaling naar het Nederlands lukte niet")

    monkeypatch.setattr(items_api, "get_db", lambda: _DB())
    monkeypatch.setattr(cl, "publish_to_platforms", valt_om)
    monkeypatch.setattr("backend.services.instellingen.lees", lambda _u: {})

    with pytest.raises(HTTPException) as val:
        asyncio.run(items_api.crosslist_item(
            HET_TAPIJTJE["id"], {"platforms": ["marktplaats"]}, HET_TAPIJTJE["user_id"]))

    fout = val.value
    # 502 en 503 worden door Cloudflare vervangen door een eigen storingspagina,
    # dus dan bereikt geen enkele uitleg de browser (gemeten 04-09-2026).
    assert fout.status_code not in (502, 503, 504)
    tekst = str(fout.detail)
    # Hij moet lezen dat er niets is geplaatst én dat er niets staat te wachten.
    assert "nothing was published" in tekst
    assert "nothing is waiting" in tekst
    # En niet de belofte van het uitgiftepad, waar de opdracht al bestaat.
    assert "vanzelf" not in tekst
