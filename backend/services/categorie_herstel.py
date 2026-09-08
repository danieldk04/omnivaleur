"""
Artikelen zonder rubriek alsnog indelen.

WAAROM DIT BESTAAT (07-09-2026, gemeten).

Bij het importeren krijgt elk artikel een rubriek toebedeeld: eerst de
woordenlijst, en anders het model. Lukt geen van beide, dan blijft de rubriek
leeg — en zonder rubriek weigert het publicatiepad het artikel ("This item has
no category set"). Dat gebeurt stil: in het overzicht is niet te zien dat zo'n
artikel nergens heen kan.

Gemeten in de voorraad: 959 artikelen zonder rubriek, verspreid over negen
accounts. Bij Toon (dejuistetoon) 114, waarvan 103 uit één importronde op
05-09-2026; bij een tweede verkoper 42 van de 59 uit diezelfde middag. Dezelfde
titels leveren, één voor één gevraagd, 20 van de 20 keer wél een rubriek op. De
gegevens waren dus prima; de lopende band liet ze vallen (zie de rem en de
herkansingen in api/imports._haiku_classificatie).

Deze ronde haalt dat in: hij vult alleen wat leeg is, schrijft nooit over wat er
al staat, en laat een artikel dat het model niet kan plaatsen gewoon leeg — dan
is het aan de verkoper.
"""
from __future__ import annotations
import logging

from backend.database import get_db

logger = logging.getLogger(__name__)

# Per ronde. Eén modelvraag per artikel, dus dit is meteen het kostenplafond.
STANDAARD_LIMIET = 200


async def herstel_rubrieken(limiet: int = STANDAARD_LIMIET,
                            user_id: str | None = None) -> dict:
    """Vul de rubriek van artikelen die er geen hebben. Geeft de telling terug."""
    from backend.api.imports import _infer_attributes_smart

    db = get_db()

    def _lees():
        q = (db.table("items")
             .select("id,title,description,brand,category,gender,color")
             .or_("category.is.null,category.eq.")
             .order("created_at", desc=True))
        if user_id:
            q = q.eq("user_id", user_id)
        return q.limit(limiet).execute().data or []

    try:
        items = _lees()
    except Exception as e:
        logger.error(f"Rubriekherstel kon de voorraad niet lezen: {e}")
        return {"gelezen": 0, "gevuld": 0, "leeg_gebleven": 0, "mislukt": 1}

    gevuld = leeg = mislukt = 0
    for item in items:
        try:
            uitkomst = await _infer_attributes_smart(
                item.get("title"), item.get("description"), item.get("brand")) or {}
        except Exception as e:
            logger.warning(f"Rubriekherstel mislukt voor {item.get('id')}: {e}")
            mislukt += 1
            continue
        # Alleen lege velden vullen — een leeggelopen ronde mag nooit iets wissen.
        patch = {
            k: v for k, v in uitkomst.items()
            if k in ("category", "gender", "color") and v
            and not str(item.get(k) or "").strip()
        }
        if not patch.get("category"):
            leeg += 1
            continue
        try:
            db.table("items").update(patch).eq("id", item["id"]).execute()
            gevuld += 1
        except Exception as e:
            logger.warning(f"Rubriek opslaan mislukt voor {item.get('id')}: {e}")
            mislukt += 1

    logger.info(f"Rubriekherstel: {len(items)} bekeken, {gevuld} gevuld, "
                f"{leeg} zonder uitkomst, {mislukt} mislukt")
    return {"gelezen": len(items), "gevuld": gevuld,
            "leeg_gebleven": leeg, "mislukt": mislukt}
