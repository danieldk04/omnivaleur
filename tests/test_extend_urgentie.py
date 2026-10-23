"""Verlengopdrachten gaan op urgentie, niet op aanmaakvolgorde (23-10-2026).

Egbert (bcdf9aa4) had 824 wachtende verlengingen. De rij stond op created_at:
gemeten stond 112 keer een zoekertje met meer dagen te gaan vóór een dringender
zoekertje. Nu zet `_wachtrij_volgorde` de verlengingen onderling op einddatum
(`sluit`, uit payload._sluit), en laat al het andere precies staan waar het stond.

Draaien:  python3 -m pytest tests/test_extend_urgentie.py -q
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as jobsapi  # noqa: E402

NU = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


def _t(dagen):
    return (NU + timedelta(days=dagen)).isoformat()


def _ext(i, aangemaakt, dagen_te_gaan, gepland=None):
    return {"id": i, "action": "extend", "platform": "2dehands", "item_id": f"it{i}",
            "created_at": aangemaakt, "scheduled_for": gepland,
            "sluit": _t(dagen_te_gaan) if dagen_te_gaan is not None else None}


def test_dringendste_verlenging_eerst():
    licht = [
        _ext("a", "2026-10-21T10:00:00+00:00", 6),
        _ext("b", "2026-10-21T10:01:00+00:00", 5),
        _ext("c", "2026-10-21T10:02:00+00:00", 1.9),
        _ext("d", "2026-10-21T10:03:00+00:00", 4),
    ]
    volgorde = [j["id"] for j in jobsapi._wachtrij_volgorde(licht, NU)]
    assert volgorde == ["c", "d", "b", "a"]


def test_plaatsing_blijft_op_zijn_plek():
    """Een gewone plaatsing ertussen verschuift niet; alleen de verlengingen
    wisselen onderling van plek."""
    plaatsing = {"id": "p", "action": "create", "platform": "2dehands", "item_id": "itp",
                 "created_at": "2026-10-21T10:01:30+00:00", "scheduled_for": None}
    licht = [
        _ext("a", "2026-10-21T10:00:00+00:00", 6),
        plaatsing,
        _ext("c", "2026-10-21T10:02:00+00:00", 1.9),
    ]
    volgorde = [j["id"] for j in jobsapi._wachtrij_volgorde(licht, NU)]
    assert volgorde == ["c", "p", "a"]


def test_verlenging_zonder_einddatum_blijft_waar_hij_stond():
    licht = [
        _ext("a", "2026-10-21T10:00:00+00:00", None),
        _ext("b", "2026-10-21T10:01:00+00:00", 5),
        _ext("c", "2026-10-21T10:02:00+00:00", 1.9),
    ]
    volgorde = [j["id"] for j in jobsapi._wachtrij_volgorde(licht, NU)]
    assert volgorde == ["a", "c", "b"]


def test_verlenging_die_nog_niet_aan_de_beurt_is_blijft_staan():
    """Een opdracht met een tijdstip in de toekomst mag niet vooraan komen:
    de uitgifte slaat hem over en de kop zou leeg uitkomen."""
    licht = [
        _ext("a", "2026-10-21T10:00:00+00:00", 6),
        _ext("b", "2026-10-21T10:01:00+00:00", 1.0, gepland=_t(0.5)),
        _ext("c", "2026-10-21T10:02:00+00:00", 3),
    ]
    volgorde = [j["id"] for j in jobsapi._wachtrij_volgorde(licht, NU)]
    assert volgorde == ["c", "b", "a"]
