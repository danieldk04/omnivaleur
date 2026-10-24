"""Vast pakketformaat Middel op Vinted (24-10-2026, Janneke): alleen met de instelling, nooit bij bundels."""
from backend.api.jobs import _vinted_pakket_voor as pakket
from backend.services.instellingen import _schoon, STANDAARD, VINTED_PAKKET


def _p(title="Schoenen Pinocchio schoenmaat 24", cat="kinderen schoenen"):
    return {"title": title, "category": cat}


def test_zonder_instelling_verandert_er_niets():
    assert "package_size" not in pakket(_p(), None)


def test_met_instelling_middel():
    assert pakket(_p(), "middel")["package_size"] == "middel"


def test_bundel_blijft_bij_vinted():
    assert "package_size" not in pakket(_p("Bundel meisjeskleding maat 92"), "middel")
    assert "package_size" not in pakket(_p("Kledingbundel Noppies"), "middel")
    assert "package_size" not in pakket(_p("Jas", "kledingbundels"), "middel")


def test_instelling_standaard_uit_en_onzin_wordt_genegeerd():
    assert STANDAARD[VINTED_PAKKET] is None
    assert _schoon({VINTED_PAKKET: "middel"})[VINTED_PAKKET] == "middel"
    assert _schoon({VINTED_PAKKET: "groot"})[VINTED_PAKKET] is None


def test_opdracht_zelf_blijft_onaangeroerd():
    p = _p()
    pakket(p, "middel")
    assert "package_size" not in p
