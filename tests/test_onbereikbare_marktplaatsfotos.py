"""Egbert Brouwer, 31-10-2026: de laatste 7 Marktplaats-advertenties kwamen zonder
afbeelding binnen. De Admarkt-scan had het interne adres dmz.mp.prod.icas.io
opgeslagen (10.37.x.x, voor niemand bereikbaar). Een herscan moet zo'n foto
vervangen zodra Marktplaats hem verwerkt heeft, en een bereikbare foto nooit."""
from backend.api.imports import (
    _backfill_patch, _photos_from_candidate, alleen_onbereikbare_fotos, foto_onbereikbaar,
)

INTERN = "https://dmz.mp.prod.icas.io/api/sellside/image/19c4d8bdb82af845/5a098dc9-b86f-448d-9239-46c5a4502dec"
CDN = "https://admarkt-cdn.marktplaats.com/api/v1/icas-mp-pro-admarkt/images/b6/b6ec5faf?rule=r-1024x1024"
EIGEN = "https://img.omnivaleur.com/u/imported/abc.avif"


def test_herkent_het_interne_adres_en_niets_anders():
    assert foto_onbereikbaar(INTERN)
    assert not foto_onbereikbaar(CDN)
    assert not foto_onbereikbaar(EIGEN)
    assert not foto_onbereikbaar(None)
    assert not foto_onbereikbaar("https://nepicas.io.example.com/a.jpg")


def test_kandidaatfotos_laten_het_interne_adres_weg():
    assert _photos_from_candidate({"photo_url": INTERN, "photo_urls": [INTERN]}) == []
    assert _photos_from_candidate({"photo_urls": [INTERN, CDN]}) == [CDN]


def test_herscan_vervangt_alleen_onbereikbare_fotos():
    cand = {"photo_url": CDN, "photo_urls": [CDN, CDN + "2"]}
    patch = _backfill_patch({"photo_urls": [INTERN]}, cand, inferred={})
    assert patch["photo_urls"] == [CDN, CDN + "2"]


def test_herscan_raakt_bereikbare_fotos_niet_aan():
    cand = {"photo_url": CDN, "photo_urls": [CDN]}
    assert "photo_urls" not in _backfill_patch({"photo_urls": [EIGEN]}, cand, inferred={})
    # Een mengeling is niet "alleen onbereikbaar": er is dus iets te redden en we laten het staan.
    assert "photo_urls" not in _backfill_patch({"photo_urls": [INTERN, EIGEN]}, cand, inferred={})
    assert not alleen_onbereikbare_fotos([INTERN, EIGEN])


def test_herscan_met_opnieuw_een_intern_adres_schrijft_niets():
    cand = {"photo_url": INTERN, "photo_urls": [INTERN]}
    assert "photo_urls" not in _backfill_patch({"photo_urls": [INTERN]}, cand, inferred={})
