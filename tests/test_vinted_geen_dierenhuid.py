"""Toon (96e30080), 21-10-2026: Vinted markeert echte vachten en koeienhuid als verboden
item en legt het account stil. Woonartikelen van dierenhuid gaan niet meer naar Vinted;
kleding van lamsvacht en 'bont' in de zin van veelkleurig blijven erbuiten."""
import inspect

from backend.services import crosslist as C

ZEKER = [
    ("wonen vachten", "Mooie volle schapenvacht 120/65 cm"),
    ("wonen tafelkleden", "Patchwork koeienhuid tafelkleed ovaal 80/47 cm"),
    ("wonen kussens", "Tibetaans schapenvacht kussen 40/40cm"),
    ("wonen vachten", "Bonte zachte berschaap 2 stuks"),
    ("wonen plaids en woondekens", "Bont kalfsvachtje 100/80"),
]
NIET = [
    ("jassen", "Vintage lamsvacht lederen jas"),
    ("wonen tapijten en kleden", "Perzisch tapijt bont patroon"),
    ("wonen tapijten en kleden", "Kelim vloerkleed 135/85"),
]


def test_dierenhuid_woonartikelen_geblokkeerd():
    for cat, titel in ZEKER:
        assert C.is_dierenhuid_woonartikel({"category": cat, "title": titel}), titel


def test_andere_artikelen_blijven_mogelijk():
    for cat, titel in NIET:
        assert not C.is_dierenhuid_woonartikel({"category": cat, "title": titel}), titel


def test_de_poort_gebruikt_het():
    assert "is_dierenhuid_woonartikel(item)" in inspect.getsource(C.publish_to_platforms)
