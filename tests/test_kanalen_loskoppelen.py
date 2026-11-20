"""Een losgekoppeld kanaal krijgt niets (20-11-2026, Esther: bang voor een Vinted-blokkade).

Draait de echte code: de instelling, de opdrachtuitgifte en het publiceren.
"""
import asyncio
from types import SimpleNamespace

import pytest

from backend.services import instellingen as inst


def test_schoon_houdt_alleen_echte_kanalen_in_vaste_volgorde():
    uit = inst._schoon({"kanalen_uit": ["vinted", "bestaat-niet", "marktplaats", "vinted"]})
    assert uit["kanalen_uit"] == ["marktplaats", "vinted"]


def test_standaard_is_niets_uit_en_onzin_telt_niet():
    assert inst._schoon({})["kanalen_uit"] == []
    assert inst._schoon({"kanalen_uit": "vinted"})["kanalen_uit"] == []


def test_uitgifte_geeft_losgekoppeld_kanaal_niets(monkeypatch):
    from backend.api import jobs
    monkeypatch.setattr(inst, "kanalen_uit", lambda uid: ["vinted"])
    # Als de uitgifte het kanaal niet zelf afwijst, valt hij op de database; die is er hier niet.
    monkeypatch.setattr(jobs, "get_db", lambda: (_ for _ in ()).throw(AssertionError("database geraakt")))
    req = SimpleNamespace(headers={})
    assert jobs.get_pending_jobs(req, platform="vinted", user_id="u1") == []


def test_publiceren_naar_losgekoppeld_kanaal_wordt_geblokkeerd(monkeypatch):
    from backend.services import crosslist
    monkeypatch.setattr(inst, "kanalen_uit", lambda uid: ["vinted"])

    class Stop(Exception):
        pass

    async def exec_stop(*a, **k):
        raise Stop()
    monkeypatch.setattr(crosslist, "get_db", lambda: SimpleNamespace(table=lambda *a: SimpleNamespace(
        select=lambda *a: SimpleNamespace(eq=lambda *a: SimpleNamespace(eq=lambda *a: SimpleNamespace(limit=lambda *a: None))))))
    item = {"id": "i1", "user_id": "u1", "title": "x"}

    async def exec_item(q, *a, **k):
        return SimpleNamespace(data=[item])
    monkeypatch.setattr(crosslist, "_exec", exec_item)

    async def geen_light(*a, **k):
        return None
    monkeypatch.setattr(crosslist, "naast_de_lus", lambda f: geen_light())
    monkeypatch.setattr(crosslist, "publicatie_geblokkeerd", lambda *a, **k: None)
    try:
        res = asyncio.run(crosslist.publish_to_platforms("i1", ["vinted"], "u1"))
    except Stop:
        pytest.fail("vinted werd niet vooraf tegengehouden")
    blok = [r for r in res if r["platform"] == "vinted"]
    assert blok and blok[0]["status"] == "blocked" and "disconnected" in blok[0]["error"]
