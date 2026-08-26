"""
Open-tracking voor de koude-mailmachine.

Alleen voor de warme-opvolgmails (zie scripts/leadgen_mail.py, _warme_opvolging)
— NIET voor de eerste koude mail. Die moet juist lezen als een persoonlijk
berichtje zonder marketing-kenmerken (zie de opmerking bij AFZENDER_NAAM in
leadgen_mail.py); een trackingpixel is precies zo'n kenmerk en hoort daar niet
in het eerste contact thuis. Bij een opvolgmail op een bestaand gesprek is dat
risico kleiner en is het weten of iemand nog leest de moeite waard.

Geen authenticatie: een mailprogramma dat de pixel ophaalt, doet dat nooit met
een inlogtoken. Het adres zit versleuteld noch geheim in de link — dit is
analytics, geen toegangscontrole — maar wel alleen leesbaar als je de link al
hebt (die alleen in de mail zelf staat).
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Response

from backend.database import execute_with_retry, get_admin_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/t", tags=["tracking"])

# 1x1 transparante gif, de kleinst mogelijke geldige afbeelding.
_PIXEL = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBTAA7"
)


def _decode(code: str) -> str | None:
    try:
        pad = "=" * (-len(code) % 4)
        return base64.urlsafe_b64decode(code + pad).decode().lower()
    except Exception:  # noqa: BLE001 — een kapotte link mag nooit een fout teruggeven
        return None


@router.get("/o/{code}")
def open_pixel(code: str) -> Response:
    adres = _decode(code)
    if adres:
        try:
            db = get_admin_db()
            rijen = execute_with_retry(db.table("leadgen_opslag")
                                       .select("inhoud").eq("naam", "mail_opens")).data or []
            opens = rijen[0]["inhoud"] if rijen else {}
            nu = datetime.now(timezone.utc).isoformat(timespec="seconds")
            item = opens.setdefault(adres, {"eerst": nu, "aantal": 0})
            item["laatst"] = nu
            item["aantal"] += 1
            db.table("leadgen_opslag").upsert(
                {"naam": "mail_opens", "inhoud": opens}, on_conflict="naam").execute()
        except Exception as e:  # noqa: BLE001 — een mislukte telling mag de pixel niet breken
            logger.warning("Open-tracking mislukt voor %s: %s", code, e)
    return Response(content=_PIXEL, media_type="image/gif", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
    })
