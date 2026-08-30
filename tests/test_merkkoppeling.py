"""Bewaakt dat de site en de profielen als één merk naar buiten komen.

Aanleiding, 30-08-2026. Wie op "omnivaleur" zocht kreeg de Instagram-accounts, de
YouTube-shorts en de Chrome Web Store bovenaan — en van Google de vraag of hij
niet "omnivore" bedoelde, waarna hij de zoekopdracht zelfs stilzwijgend
omzette naar dat woord. De site zelf stond er wél in (positie 1,8 op de
merknaam), maar Google had geen enkele reden om "Omnivaleur" als merk te
herkennen: de homepage noemde de profielen nergens en de profielen stonden los
van het domein.

Wat dat repareert is `sameAs`: de machineleesbare uitspraak "dit domein en deze
profielen zijn dezelfde organisatie", plus echte links met rel="me" die een
crawler kan volgen. Dat is stil kapot te maken — een profiel dat in
KANAAL_LINKS wordt bijgezet maar niet in de statische homepage, en de claim
klopt niet meer. Vandaar deze test.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

from backend.api.content import (  # noqa: E402
    KANAAL_LINKS, MERK_LINKS, WEBSTORE_URL, merk_json_ld, merk_profielen,
)

INDEX = (REPO / "frontend" / "index.html").read_text(encoding="utf-8")
FOOTER = (REPO / "frontend" / "templates" / "_footer.html").read_text(encoding="utf-8")
CONTENT_PY = (REPO / "backend" / "api" / "content.py").read_text(encoding="utf-8")


def _json_ld_blokken(html: str) -> list[dict]:
    blokken = []
    for ruw in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ):
        blokken.append(json.loads(ruw))
    return blokken


def test_profiellijst_dekt_alle_kanalen_en_de_webstore():
    """De lijst is afgeleid van KANAAL_LINKS; een kanaal erbij moet vanzelf
    meelopen, anders claimt de site straks een merk zonder zijn nieuwste account."""
    profielen = merk_profielen()
    for kanaal in KANAAL_LINKS:
        assert kanaal["profiel"] in profielen, f"{kanaal['kanaal']} ontbreekt in sameAs"
    assert WEBSTORE_URL in profielen
    assert len(profielen) == len(set(profielen)), "dubbel profiel in sameAs"
    assert all(p.startswith("https://") for p in profielen)


def test_homepage_draagt_hetzelfde_merkblok():
    """De homepage is een statisch bestand en kan de tabel niet zelf lezen. Loopt
    hij uit de pas, dan spreken twee pagina's van hetzelfde domein elkaar tegen
    over wie het merk is — precies het signaal dat we juist proberen te geven."""
    orgs = [b for b in _json_ld_blokken(INDEX) if b.get("@type") == "Organization"]
    assert len(orgs) == 1, "verwacht precies één Organization-blok op de homepage"
    org = orgs[0]
    verwacht = merk_json_ld()
    assert org["@id"] == verwacht["@id"]
    assert org["name"] == "Omnivaleur"
    assert org["sameAs"] == verwacht["sameAs"]


def test_homepage_linkt_zichtbaar_naar_elk_profiel():
    """sameAs alleen is een claim zonder bewijs. De volgbare link hoort erbij."""
    for url in merk_profielen():
        assert f'href="{url}" rel="me' in INDEX, f"geen rel=me-link naar {url}"


def test_gedeelde_footer_draagt_merk_en_links():
    """Blogpagina's en de blogindex gebruiken dit sjabloon; daar moet dezelfde
    uitspraak staan, anders komt de merkclaim maar van één pagina."""
    assert "org_json_ld | tojson" in FOOTER
    assert 'rel="me noopener"' in FOOTER
    assert "merk_links" in FOOTER


def test_beide_sjablonen_krijgen_het_merkblok_mee():
    """Het sjabloon toont niets als de server de variabele niet meegeeft — dat
    zou stil misgaan, want een ontbrekend blok is op de pagina niet te zien."""
    assert CONTENT_PY.count('"org_json_ld": merk_json_ld()') == 2
    assert CONTENT_PY.count('"merk_links": MERK_LINKS') == 2


def test_labels_houden_de_twee_talen_uit_elkaar():
    """Twee keer "Instagram" onder elkaar zonder verschil is voor een bezoeker
    een fout, niet een keuze."""
    labels = [l["label"] for l in MERK_LINKS]
    assert len(labels) == len(set(labels)), f"dubbel label in de footer: {labels}"
    assert "Instagram (NL)" in labels
