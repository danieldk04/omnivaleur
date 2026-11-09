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


class _NepDb:
    """Spiegelt alleen wat ids_zonder_bruikbare_foto vraagt: eq-filters en één or_-filter."""

    def __init__(self, rijen):
        self.rijen, self.f, self.or_f = rijen, [], None

    def table(self, _):
        return _NepDb(self.rijen)

    def select(self, _):
        return self

    def eq(self, k, v):
        self.f.append((k, v))
        return self

    def or_(self, s):
        self.or_f = s
        return self

    def limit(self, _):
        return self

    def execute(self):
        def klopt(r):
            if any(r.get(k) != v for k, v in self.f):
                return False
            u = r.get("photo_url")
            if self.or_f == "photo_url.is.null":
                return u is None
            if self.or_f == "photo_url.eq.":
                return u == ""
            if self.or_f.startswith("photo_url.like."):
                return bool(u) and "icas.io/" in u
            return False
        return type("R", (), {"data": [r for r in self.rijen if klopt(r)]})()


def test_scan_leest_advertenties_zonder_bruikbare_foto_opnieuw():
    from backend.api.imports import ids_zonder_bruikbare_foto
    rij = lambda i, u, uid="a", pf="marktplaats": {"user_id": uid, "platform": pf, "platform_listing_id": i, "photo_url": u}
    db = _NepDb([
        rij("1", INTERN), rij("2", None), rij("3", ""), rij("4", CDN), rij("5", EIGEN),
        rij("6", None, uid="andere-klant"), rij("7", None, pf="vinted"),
    ])
    # Voor de reparatie viel alleen het interne adres hieronder: nummer 2 en 3 bleven "bekend" en kwamen nooit terug.
    assert ids_zonder_bruikbare_foto(db, "a", "marktplaats") == {"1", "2", "3"}
