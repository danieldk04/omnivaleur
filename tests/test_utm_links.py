"""Bewaakt de meetafspraak achter de links naar de site.

Aanleiding, 29-08-2026. Daniel wil kunnen zien waar bezoek vandaan komt, maar
had nog geen enkele getagde link. Zonder tags komt bezoek uit een bio in een
telefoon-app bij Google Analytics binnen als "direct" — dan staat er wel
verkeer, maar is niet te zien wélk kanaal het opleverde.

Die tags zijn losse tekst in een URL en dus stil kapot te maken. Eén hoofdletter
of streepje verschil (`TikTok`, `tik-tok`) en Analytics telt hetzelfde kanaal
als twee, waarna geen enkel totaal meer klopt. Daarom staat de afspraak op één
plek (KANAAL_LINKS in backend/api/content.py) en wordt hij hier nagerekend.
"""
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from backend.api.content import KANAAL_LINKS, MAIL_LINK, kanaal_link  # noqa: E402
from backend.main import KORTE_LINKS  # noqa: E402
from backend.services import ga4  # noqa: E402
import leadgen_mail as L  # noqa: E402

ALLE = KANAAL_LINKS + [MAIL_LINK]


def _tags(link: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(link).query).items()}


def test_elke_link_draagt_bron_medium_en_campagne():
    """Mist er één van de drie, dan valt de link in Analytics terug op 'direct'
    of op 'niet toegewezen' en is hij dus onvindbaar."""
    for k in ALLE:
        tags = _tags(kanaal_link(k, "https://omnivaleur.com"))
        assert tags.get("utm_source"), k["kanaal"]
        assert tags.get("utm_medium"), k["kanaal"]
        assert tags.get("utm_campaign"), k["kanaal"]


def test_geen_hoofdletters_of_spaties_in_de_tags():
    """Analytics is hoofdlettergevoelig: `TikTok` en `tiktok` zijn twee kanalen."""
    for k in ALLE:
        for veld in ("source", "medium", "campagne"):
            waarde = k[veld]
            assert waarde == waarde.lower(), f"{k['kanaal']}: {veld}={waarde}"
            assert re.fullmatch(r"[a-z0-9-]+", waarde), f"{k['kanaal']}: {veld}={waarde}"


def test_medium_is_een_woord_dat_analytics_zelf_herkent():
    """Alleen `social` en `email` komen in de standaard kanaalgroepering terecht.
    Een eigen vondst als `cold_email` belandt in de bak 'niet toegewezen'."""
    for k in ALLE:
        assert k["medium"] in ("social", "email"), f"{k['kanaal']}: {k['medium']}"


def test_analytics_herkent_elke_social_bron_als_platform():
    """De per-platform tabel in het weekrapport draait op ga4.platform_of. Een
    bron die daar niet in staat, valt uit het rapport."""
    for k in KANAAL_LINKS:
        assert ga4.platform_of(k["source"]), k["source"]


def test_nederlands_en_engels_zijn_uit_elkaar_te_houden():
    """Beide Instagram-accounts hebben dezelfde bron. Zonder verschil in
    campagne zijn ze in geen enkel rapport te scheiden."""
    per_bron: dict[str, set] = {}
    for k in KANAAL_LINKS:
        per_bron.setdefault(k["source"], set()).add(k["campagne"])
    for bron, campagnes in per_bron.items():
        aantal = sum(1 for k in KANAAL_LINKS if k["source"] == bron)
        assert len(campagnes) == aantal, f"{bron}: {aantal} kanalen, {len(campagnes)} campagnes"


def test_de_maillink_is_kort_en_de_omleiding_draagt_de_tags():
    """Het model dat de koude mail schrijft typt deze link over. Een lange URL
    met parameters is iets wat het kan verhaspelen; /mp niet."""
    assert L.VIDEO.endswith("/mp"), L.VIDEO
    doel = KORTE_LINKS["mp"]
    tags = _tags(doel)
    assert tags["utm_source"] == MAIL_LINK["source"]
    assert tags["utm_medium"] == MAIL_LINK["medium"]
    assert tags["utm_campaign"] == MAIL_LINK["campagne"]
    assert doel.startswith(MAIL_LINK["pad"] + "?")


def test_geen_getagde_links_binnen_de_eigen_site():
    """Analytics bepaalt de herkomst bij binnenkomst. Komt er halverwege een
    andere utm_source langs, dan begint er een nieuwe sessie met een nieuwe
    bron: één bezoeker wordt twee bezoeken en de herkomst is weg."""
    fout = []
    for pad in (REPO / "frontend").rglob("*.html"):
        for regel in re.findall(r'href="(/[^"]*)"', pad.read_text(errors="ignore")):
            if "utm_" in regel:
                fout.append(f"{pad.name}: {regel}")
    assert not fout, "getagde interne links: " + ", ".join(fout)
