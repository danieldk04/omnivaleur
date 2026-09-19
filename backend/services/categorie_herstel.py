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

WAAROM ER EEN OPGEEFGRENS BIJ KWAM (19-09-2026, gemeten).

De ronde vroeg het model elke nacht opnieuw naar precies dezelfde artikelen. Op
19-09 stonden er 404 zonder rubriek; van de 200 die de ronde die nacht las waren
er 175 PlayStation- en PSP-spellen, plus autobanden en sneeuwkettingen, bijna
allemaal van één verkoper. De taxonomie in api/imports._TAXONOMY kent 247
rubrieken verdeeld over dames, heren, kinderen, unisex, sieraden, wonen, antiek
en muziek. Daar zit geen enkele rubriek voor spellen, consoles, media of
auto-onderdelen tussen. Het model kán die dus niet plaatsen, hoe vaak je het ook
vraagt, en de controle in _classify_with_claude gooit een verzonnen rubriek
terecht weg.

Gemeten door de echte ronde te draaien met een nepmodel: 200 modelvragen per
nacht, 1.927.627 tekens aan prompt, ongeveer 551.000 invoertokens, zo'n 0,55
dollar per nacht alleen aan invoer. Dat is ruim 17 dollar per maand voor vragen
waarvan het antwoord van tevoren vaststaat.

Vanaf nu krijgt een artikel drie kansen. Daarna vraagt de ronde er niet meer
naar, tot de verkoper de titel of de omschrijving aanpast — dan begint het
tellen opnieuw, want dan is het een andere vraag geworden.

DRIE DINGEN DIE HIER BEWUST ZO ZIJN:

1. De teller telt alleen mee als de ronde in diezelfde nacht minstens één
   rubriek heeft kunnen invullen. Zonder die voorwaarde zou een storing of een
   leeg API-tegoed drie nachten lang iedereen zijn kansen afpakken en de hele
   voorraad definitief afschrijven. Precies dat stond op 19-09 te gebeuren: het
   tegoed was op, dus elke vraag kwam leeg terug.
2. Staan de kolommen er nog niet, dan gedraagt de ronde zich exact zoals
   hiervoor. De code mag vóór de migratie live staan zonder iets te veranderen.
3. De ronde schrijft nooit een rubriek die hij niet ook zonder deze grens zou
   schrijven. De teller kan alleen een modelvraag overslaan, nooit een uitkomst
   veranderen.

De migratie staat in scripts/migratie_rubriek_pogingen.sql.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from backend.database import get_db

logger = logging.getLogger(__name__)

# Per ronde. Eén modelvraag per artikel, dus dit is meteen het kostenplafond.
STANDAARD_LIMIET = 200

# Zoveel keer vraagt de ronde het model naar hetzelfde artikel. Daarna houdt hij
# op tot de verkoper de tekst aanpast.
MAX_POGINGEN = 3

# Hoeveel uitgeputte artikelen we per nacht nakijken op een tussentijdse
# bewerking. Alleen id en twee tijdstempels, dus een goedkope vraag.
HERKANSVENSTER = 2000

_TELLER = "rubriek_pogingen"
_GEPOOGD = "rubriek_gepoogd_op"


def _tijd(waarde) -> datetime | None:
    """Tijdstempel uit de database naar datetime met tijdzone, of None."""
    if not waarde:
        return None
    try:
        dt = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _geef_bewerkte_artikelen_een_nieuwe_kans(db, user_id: str | None) -> int:
    """Zet de teller terug op nul voor artikelen die na hun laatste poging zijn bewerkt.

    Een verkoper die de titel aanvult verdient een nieuwe beoordeling: het is
    letterlijk een andere vraag dan de vorige keer. PostgREST kan twee kolommen
    niet met elkaar vergelijken, dus we halen de uitgeputte artikelen op met
    alleen hun twee tijdstempels en vergelijken hier.
    """
    q = (db.table("items")
         .select(f"id,updated_at,{_GEPOOGD}")
         .or_("category.is.null,category.eq.")
         .gte(_TELLER, MAX_POGINGEN))
    if user_id:
        q = q.eq("user_id", user_id)
    rijen = q.limit(HERKANSVENSTER).execute().data or []

    opnieuw = []
    for rij in rijen:
        gepoogd = _tijd(rij.get(_GEPOOGD))
        bewerkt = _tijd(rij.get("updated_at"))
        # Geen tijdstempel van de vorige poging betekent dat we niet kunnen
        # vaststellen dat er niets veranderd is. Dan geldt het voordeel van de
        # twijfel en krijgt het artikel zijn kansen terug.
        if gepoogd is None or (bewerkt is not None and bewerkt > gepoogd):
            opnieuw.append(rij["id"])

    for brok in (opnieuw[i:i + 100] for i in range(0, len(opnieuw), 100)):
        db.table("items").update({_TELLER: 0}).in_("id", brok).execute()
    if opnieuw:
        logger.info(f"Rubriekherstel: {len(opnieuw)} bewerkte artikelen krijgen "
                    f"opnieuw {MAX_POGINGEN} kansen")
    return len(opnieuw)


def _schrijf_pogingen(db, per_aantal: dict[int, list[str]]) -> None:
    """Werk de teller bij, gegroepeerd per nieuwe stand zodat het drie vragen blijft."""
    nu = datetime.now(timezone.utc).isoformat()
    for aantal, ids in per_aantal.items():
        for brok in (ids[i:i + 100] for i in range(0, len(ids), 100)):
            try:
                (db.table("items")
                   .update({_TELLER: aantal, _GEPOOGD: nu})
                   .in_("id", brok).execute())
            except Exception as e:  # noqa: BLE001
                # De teller bijhouden is een besparing, geen taak. Mislukt het,
                # dan vraagt de ronde morgen gewoon opnieuw: dat is de oude
                # situatie en die brak niets.
                logger.warning(f"Rubriekteller bijwerken mislukt: {e}")


async def herstel_rubrieken(limiet: int = STANDAARD_LIMIET,
                            user_id: str | None = None) -> dict:
    """Vul de rubriek van artikelen die er geen hebben. Geeft de telling terug."""
    from backend.api.imports import _infer_attributes_smart

    db = get_db()
    velden = "id,title,description,brand,category,gender,color"

    def _lees_met_grens():
        q = (db.table("items")
             .select(f"{velden},{_TELLER}")
             .or_("category.is.null,category.eq.")
             .lt(_TELLER, MAX_POGINGEN)
             .order("created_at", desc=True))
        if user_id:
            q = q.eq("user_id", user_id)
        return q.limit(limiet).execute().data or []

    def _lees_zonder_grens():
        q = (db.table("items")
             .select(velden)
             .or_("category.is.null,category.eq.")
             .order("created_at", desc=True))
        if user_id:
            q = q.eq("user_id", user_id)
        return q.limit(limiet).execute().data or []

    # STAAN DE KOLOMMEN ER AL? Zo niet, dan draait deze ronde precies zoals
    # hiervoor. Zo mag de code live staan voordat de migratie is gedraaid.
    grens_actief = True
    try:
        _geef_bewerkte_artikelen_een_nieuwe_kans(db, user_id)
        items = _lees_met_grens()
    except Exception as e:  # noqa: BLE001
        grens_actief = False
        logger.info(f"Rubriekherstel draait zonder opgeefgrens ({e}); "
                    f"zie scripts/migratie_rubriek_pogingen.sql")
        try:
            items = _lees_zonder_grens()
        except Exception as e2:  # noqa: BLE001
            logger.error(f"Rubriekherstel kon de voorraad niet lezen: {e2}")
            return {"gelezen": 0, "gevuld": 0, "leeg_gebleven": 0, "mislukt": 1}

    gevuld = leeg = mislukt = 0
    zonder_uitkomst: dict[int, list[str]] = {}
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
            stand = int(item.get(_TELLER) or 0) + 1
            zonder_uitkomst.setdefault(min(stand, MAX_POGINGEN), []).append(item["id"])
            continue
        try:
            db.table("items").update(patch).eq("id", item["id"]).execute()
            gevuld += 1
        except Exception as e:
            logger.warning(f"Rubriek opslaan mislukt voor {item.get('id')}: {e}")
            mislukt += 1

    # DE TELLER LOOPT ALLEEN ALS HET MODEL BEWEZEN BEREIKBAAR WAS.
    #
    # Een lege uitkomst betekent twee heel verschillende dingen: "het model kan
    # dit artikel niet plaatsen" en "het model deed het niet". _classify_with_claude
    # geeft in allebei de gevallen {} terug, dus van één artikel is het verschil
    # hier niet te zien. Over de hele ronde wel: lukt er geen enkele, dan is niet
    # de voorraad kapot maar de dienst. Dan telt deze nacht niet mee.
    if grens_actief and gevuld > 0 and zonder_uitkomst:
        _schrijf_pogingen(db, zonder_uitkomst)
    elif zonder_uitkomst and gevuld == 0:
        logger.warning(
            f"Rubriekherstel: geen enkele van de {len(items)} artikelen kreeg een "
            f"rubriek. Dat telt als storing, niet als uitkomst, dus niemand "
            f"verliest een kans.")

    logger.info(f"Rubriekherstel: {len(items)} bekeken, {gevuld} gevuld, "
                f"{leeg} zonder uitkomst, {mislukt} mislukt")
    return {"gelezen": len(items), "gevuld": gevuld,
            "leeg_gebleven": leeg, "mislukt": mislukt}
