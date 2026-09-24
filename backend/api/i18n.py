"""Meldpunt voor de vertaallaag: tekst die in het Nederlands nog Engels bleef.

frontend/i18n.js vertaalt het dashboard op het scherm met frontend/i18n/nl.json.
Ziet het een zin die er Engels uitziet en niet in dat woordenboek staat, dan
stuurt het die hierheen. We bewaren de zin, waar hij stond en hoe vaak, in
leadgen_opslag onder "i18n_ontbrekend" (dezelfde sleutel-waardetabel als de
open-tracking). De volgende sessie haalt de lijst op met
`python3 scripts/i18n_extract.py --live` en voegt de vertalingen toe.

Geen inlog nodig: ook de inlogpagina's vertalen. Er wordt niets teruggegeven
en er gaat nooit iets mis voor de gebruiker; de lijst is begrensd, zodat
niemand hem kan volstoppen.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from backend.database import execute_with_retry, get_admin_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/i18n", tags=["i18n"])

SLEUTEL = "i18n_ontbrekend"
MAX_ZINNEN = 500
MAX_LENGTE = 300


class Tekst(BaseModel):
    tekst: str = Field(max_length=2000)
    plek: str = Field(default="", max_length=200)


class Melding(BaseModel):
    taal: str = Field(default="nl", max_length=5)
    pagina: str = Field(default="", max_length=100)
    teksten: list[Tekst] = Field(default_factory=list, max_length=40)


@router.post("/ontbrekend", status_code=204, response_class=Response)
def ontbrekend(melding: Melding) -> Response:
    nieuw = [t for t in melding.teksten if t.tekst.strip()][:40]
    if not nieuw:
        return Response(status_code=204)
    try:
        db = get_admin_db()
        rijen = execute_with_retry(db.table("leadgen_opslag")
                                   .select("inhoud").eq("naam", SLEUTEL)).data or []
        lijst = rijen[0]["inhoud"] if rijen else {}
        nu = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for t in nieuw:
            zin = t.tekst.strip()[:MAX_LENGTE]
            rij = lijst.get(zin)
            if rij is None:
                if len(lijst) >= MAX_ZINNEN:
                    continue
                rij = lijst[zin] = {"eerst": nu, "aantal": 0, "taal": melding.taal[:5]}
            rij["laatst"] = nu
            rij["aantal"] = int(rij.get("aantal", 0)) + 1
            rij["pagina"] = melding.pagina[:100]
            rij["plek"] = t.plek[:200]
        db.table("leadgen_opslag").upsert(
            {"naam": SLEUTEL, "inhoud": lijst}, on_conflict="naam").execute()
    except Exception as e:  # noqa: BLE001 — melden is een gunst, nooit een fout
        logger.warning("i18n: ontbrekende vertalingen niet opgeslagen: %s", e)
    return Response(status_code=204)
