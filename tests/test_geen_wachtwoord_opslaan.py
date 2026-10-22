"""Omnivaleur slaat nooit een Marktplaats-, 2dehands- of Vinted-wachtwoord op.

WAAROM (22-10-2026, Voordeelsieraden): een klant dacht dat haar gehackte
Marktplaats-account via ons was gelopen. Meten kon dat uitsluiten, op één ding
na: de server had eindpunten die een wachtwoord konden aannemen en in
platform_credentials zetten. Niemand riep ze aan, maar ze bestonden. Ze zijn
weg; deze proef zorgt dat ze niet terugkomen.
"""
from backend.api import platforms
from backend.main import app

VERBODEN = ("bootstrap", "sync-chrome-session")


def test_geen_route_neemt_een_kanaalwachtwoord_aan():
    # FastAPI nieuw: app.routes toont ingevoegde routers niet plat, dus kijken we
    # in de router zelf én in het openapi-schema van de hele app.
    paden = [getattr(r, "path", "") for r in platforms.router.routes]
    paden += list(app.openapi().get("paths", {}))
    assert any("/ebay/" in p for p in paden), "meting leeg: routes niet gelezen"
    gevonden = [p for p in paden if any(v in p for v in VERBODEN)]
    assert gevonden == [], f"Wachtwoord-eindpunten teruggekomen: {gevonden}"
