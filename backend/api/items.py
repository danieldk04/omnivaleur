from fastapi import APIRouter, HTTPException, Depends
from backend.models import ItemCreate, ItemOut
from backend.database import get_db, execute_with_retry, fetch_all, IN_BROK
from backend.api.deps import get_current_user, require_active_subscription
from backend.services.tweelingen import (
    groepeer, zelfde_artikel, advertentiecode, bekende_merken_van,
)
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)

_PENDING_COLUMNS = set()

router = APIRouter(prefix="/items", tags=["items"])


def _strip_missing(data: dict) -> dict:
    return {k: v for k, v in data.items() if k not in _PENDING_COLUMNS}


def _raise_if_duplicate_sku(db, exc: Exception, sku: str | None, user_id: str) -> None:
    """
    Een SKU die al bestaat is geen storing maar een gewone vergissing: het item
    staat er al. De databasemelding daarover ("duplicate key value violates
    unique constraint") zegt de verkoper niets, dus die vertalen we naar het
    enige dat telt — welk item de SKU al gebruikt.
    """
    tekst = str(exc)
    if "23505" not in tekst or "sku" not in tekst.lower():
        return
    bestaand = None
    try:
        rijen = (
            db.table("items")
            .select("id,title,created_at")
            .eq("sku", sku)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )
        bestaand = rijen[0] if rijen else None
    except Exception:  # noqa: BLE001 - de melding mag hier niet op stuklopen
        pass
    if bestaand:
        raise HTTPException(
            status_code=409,
            detail=(
                f"SKU '{sku}' is already used by an item you have: "
                f"\"{bestaand['title']}\". Open that item to edit it, "
                f"or give this one a different SKU."
            ),
        )
    raise HTTPException(
        status_code=409,
        detail=f"SKU '{sku}' is already in use. Give this item a different SKU.",
    )


# De Supabase-client is synchroon. In een `async def`-route legt elke aanroep de
# hele server stil; in een gewone `def`-route niet, want die draait al apart.
async def _exec(query):
    return await asyncio.to_thread(query.execute)


@router.post("/", response_model=dict)
def create_item(item: ItemCreate, user_id: str = Depends(get_current_user)):
    db = get_db()
    data = item.model_dump()
    data["id"] = str(uuid.uuid4())
    data["user_id"] = user_id
    if not data.get("sku"):
        data["sku"] = f"REV-{data['id'][:8].upper()}"
    # Geen 502 of 503 als foutcode: Cloudflare vervangt die antwoorden door zijn
    # eigen foutpagina, waardoor de echte reden de browser nooit bereikte en de
    # gebruiker "de server duurde te lang" te zien kreeg bij een fout die in
    # 0,4 seconde optrad. 500 komt wél ongewijzigd door.
    try:
        result = execute_with_retry(
            db.table("items").insert(_strip_missing(data)), dubbel_is_ok=True
        )
    except Exception as e:
        _raise_if_duplicate_sku(db, e, data.get("sku"), user_id)
        logger.exception("Item insert failed for user %s", user_id)
        raise HTTPException(status_code=500, detail=f"Could not save: {e}")
    # None = de rij stond er al na een herhaalde poging (zie execute_with_retry).
    if result is None:
        return {**data, "id": data["id"]}
    if not result.data:
        logger.error("Item insert returned no row for user %s", user_id)
        raise HTTPException(status_code=500, detail="The item was not saved — please try again.")
    return result.data[0]


@router.get("/", response_model=list)
def list_items(limit: int = 50, offset: int = 0, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = (
        db.table("items")
        .select("*")
        .eq("user_id", user_id)
        # Without an explicit order the database is free to return rows in any
        # order it likes, and it does not have to pick the same order twice. The
        # dashboard reads the catalogue page by page, so an unstable order made
        # rows show up on two pages or on none at all — which is why a
        # just-created item could be missing from the list entirely. id breaks
        # ties so the order is total, not just mostly-sorted.
        .order("created_at", desc=True)
        .order("id")
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data


@router.get("/settings")
def read_settings(user_id: str = Depends(get_current_user)):
    """De persoonlijke instellingen van deze verkoper."""
    from backend.services.instellingen import (RELIST_DAGEN_MAX, RELIST_DAGEN_MIN,
                                               lees)
    return {**lees(user_id), "relist_dagen_min": RELIST_DAGEN_MIN,
            "relist_dagen_max": RELIST_DAGEN_MAX}


@router.put("/settings")
def write_settings(body: dict, user_id: str = Depends(get_current_user)):
    """Instellingen opslaan. Geeft terug wat er echt is bewaard, want een waarde
    buiten bereik wordt bijgesteld en dat hoort het scherm te laten zien."""
    from backend.services.instellingen import (RELIST_DAGEN_MAX, RELIST_DAGEN_MIN,
                                               schrijf)
    try:
        bewaard = schrijf(user_id, body or {})
    except Exception as e:  # noqa: BLE001
        logger.exception("instellingen opslaan mislukt voor %s", user_id)
        raise HTTPException(status_code=500, detail=f"Could not save settings: {e}")
    return {**bewaard, "relist_dagen_min": RELIST_DAGEN_MIN,
            "relist_dagen_max": RELIST_DAGEN_MAX}


# Welke staten er bestaan. Alles daarbuiten weigeren, anders zet één typefout
# duizenden items op een waarde die de platforms niet kennen.
_CONDITIES = {"new_with_tags", "new", "good", "fair", "poor"}


@router.post("/bulk-condition")
async def bulk_condition(body: dict, user_id: str = Depends(get_current_user)):
    """De staat van veel items in één keer zetten.

    WAAROM DIT BESTAAT: Marktplaats/Admarkt levert bij een import geen staat mee,
    dus belandde alles op "Like new". Een verkoper die uitsluitend nieuwe spullen
    verkoopt (Egbert Brouwer, 2.135 items) moest dat pagina voor pagina
    corrigeren, met één verzoek per item — bij hem ruim tweeduizend klikrondjes.

    `ids` leeg laten betekent: alle items van deze verkoper. Dat is bewust een
    aparte, expliciete keuze in het scherm en geen standaardwaarde.
    """
    conditie = str((body or {}).get("condition") or "").strip()
    if conditie not in _CONDITIES:
        raise HTTPException(status_code=400, detail=f"Unknown condition: {conditie or '(empty)'}")

    db = get_db()
    ids = [str(i) for i in ((body or {}).get("ids") or []) if i]
    alles = bool((body or {}).get("all_items"))
    if not ids and not alles:
        raise HTTPException(status_code=400, detail="No items selected")

    def _doe() -> int:
        doel = ids
        if alles:
            doel = [r["id"] for r in fetch_all(
                lambda: db.table("items").select("id").eq("user_id", user_id))]
        # Altijd op user_id blijven filteren: id's komen uit de browser en mogen
        # nooit als bewijs van eigenaarschap gelden.
        gedaan = 0
        for i in range(0, len(doel), IN_BROK):
            stuk = doel[i:i + IN_BROK]
            rijen = execute_with_retry(
                db.table("items").update({"condition": conditie})
                .eq("user_id", user_id).in_("id", stuk)
            )
            gedaan += len(getattr(rijen, "data", None) or [])
        return gedaan

    try:
        aantal = await asyncio.to_thread(_doe)
    except Exception as e:  # noqa: BLE001
        logger.exception("bulk-condition mislukt voor %s", user_id)
        raise HTTPException(status_code=500, detail=f"Could not update the condition: {e}")
    return {"updated": aantal, "condition": conditie}


@router.post("/fill-from-marktplaats")
async def fill_from_marktplaats(limit: int = 150,
                                user_id: str = Depends(get_current_user)):
    """Prijs en omschrijving ophalen bij de eigen Marktplaats-advertenties.

    Voor zakelijke verkopers (Admarkt) levert de import geen prijs en geen tekst;
    die staan alleen op de openbare advertentie. Deze knop haalt ze daar op voor
    items die ze missen. Bestaande waarden blijven altijd staan.

    Werkt per lading van hooguit `limit` items. Bij duizenden advertenties duurt
    het ophalen langer dan de gateway een verbinding openhoudt, en dan krijgt de
    verkoper een foutpagina te zien terwijl het werk gewoon doorliep. Het scherm
    roept dit dus net zo vaak aan tot er niets meer te doen is.
    """
    from backend.services.mp_enrich import verrijk

    db = get_db()
    try:
        # De aanroepen naar Marktplaats zijn traag; buiten de request-lus houden
        # zodat de rest van het dashboard ondertussen blijft reageren.
        uit = await verrijk(db, user_id, schrijf=True, maximaal=max(1, min(limit, 400)))
    except Exception as e:  # noqa: BLE001
        logger.exception("fill-from-marktplaats mislukt voor %s", user_id)
        raise HTTPException(status_code=502, detail=f"Marktplaats lookup failed: {e}")
    return uit


@router.get("/duplicates")
def list_duplicates(user_id: str = Depends(get_current_user)):
    """
    Welke items in deze voorraad in werkelijkheid hetzelfde artikel zijn.

    Gegroepeerd op het artikelnummer dat de verkoper zelf voor de titel zet,
    en alleen als kleur, maat, merk en prijs elkaar niet tegenspreken. Per groep
    staat het OUDSTE item vooraan: dat is het item dat de rest opslokt, want
    daar hangt de langste geschiedenis aan.
    """
    db = get_db()
    items = fetch_all(lambda: db.table("items")
                      .select("id,title,sku,brand,price,photo_urls,created_at")
                      .eq("user_id", user_id))
    groepen = groepeer(items)
    if not groepen:
        return {"groups": []}

    ids = [i["id"] for g in groepen for i in g]
    rijen = []
    for s_ in range(0, len(ids), IN_BROK):
        brok = ids[s_:s_ + IN_BROK]
        rijen.extend(fetch_all(lambda b=brok: db.table("listings")
                               .select("item_id,platform,status,platform_listing_url")
                               .in_("item_id", b)))
    per_item = {}
    for r in rijen:
        per_item.setdefault(r["item_id"], []).append(r)

    return {"groups": [
        {
            "code": advertentiecode(g[0].get("title"), g[0].get("sku")),
            "items": [
                {
                    "id": i["id"], "title": i.get("title"), "sku": i.get("sku"),
                    "price": i.get("price"), "created_at": i.get("created_at"),
                    "photo": (i.get("photo_urls") or [None])[0],
                    "listings": sorted(
                        ({"platform": r["platform"], "status": r["status"],
                          "url": r.get("platform_listing_url")}
                         for r in per_item.get(i["id"], [])),
                        key=lambda r: (r["platform"], r["status"]),
                    ),
                }
                for i in g
            ],
        }
        for g in groepen
    ]}


@router.post("/merge")
def merge_items(body: dict, user_id: str = Depends(get_current_user)):
    """
    Voeg dubbele rijen van hetzelfde artikel samen tot één item.

    Alle advertenties en opdrachten verhuizen naar `keep`, de overige items
    verdwijnen. Onomkeerbaar, dus: alleen eigen items, en alleen items die de
    controle in tweelingen.py als hetzelfde artikel ziet. Een verzoek dat langs
    die controle glipt wordt geweigerd in plaats van uitgevoerd — twee
    verschillende truien samenvoegen is niet terug te draaien.

    De foto's blijven staan. `_release_photos` zou een foto kunnen weghalen die
    het overgebleven item zelf ook gebruikt, en een advertentie zonder plaatje
    is erger dan een paar ongebruikte bestanden.

    WAAROM ER VOORAF OP HET PLATFORM WORDT GECONTROLEERD (31-08-2026). Daniel
    drukte op "Merge all" en kreeg elf keer op rij een serverfout (codes 269E80,
    0A2143, 07F3A8 en verder). De oorzaak stond in de database, niet hier:
    `listings` heeft een unieke sleutel op (item_id, platform), dus één item kan
    hoogstens één advertentie per kanaal hebben. Precies wat samenvoegen
    oplevert — acht kopieën van dezelfde trui met elk een eigen Marktplaats-
    advertentie — botst daarmee. De regel hieronder ging er in bulk overheen en
    liet de hele aanroep klappen.

    Er ging niets verloren (de listings-regel is de eerste van de drie, dus de
    verwijdering werd nooit bereikt), maar de klant zag alleen een foutcode en
    de dubbele rijen bleven staan. Nu wordt zo'n botsing vóóraf herkend en die
    ene groep overgeslagen, met een reden die de app kan uitleggen. Zolang de
    unieke sleutel bestaat is overslaan het enige juiste: doorgaan zou betekenen
    dat een echte advertentie van een kanaal verdwijnt uit onze administratie
    terwijl hij online gewoon doorloopt.
    """
    keep = (body or {}).get("keep")
    losers = [i for i in ((body or {}).get("merge") or []) if i and i != keep]
    if not keep or not losers:
        raise HTTPException(status_code=400, detail="keep and merge[] are required")

    db = get_db()
    rijen = (db.table("items").select("id,title,sku,brand,price")
             .eq("user_id", user_id).in_("id", [keep, *losers]).execute().data or [])
    per_id = {r["id"]: r for r in rijen}
    if keep not in per_id:
        raise HTTPException(status_code=404, detail="Item not found")

    # Welke LOPENDE advertenties hebben deze items. In één vraag, want per item
    # vragen is bij "Merge all" honderden aanroepen. Alleen 'active' telt: de
    # unieke index draagt `WHERE status = 'active'`, dus een verkochte of
    # ingetrokken advertentie blokkeert niets.
    bezet: dict[str, set] = {}
    for rij in (db.table("listings").select("item_id,platform,platform_listing_id,status")
                .in_("item_id", [keep, *losers]).execute().data or []):
        if rij.get("status") != "active":
            continue
        bezet.setdefault(rij["item_id"], set()).add(
            (rij.get("platform"), rij.get("platform_listing_id")))

    merken = bekende_merken_van(rijen)
    samengevoegd, geweigerd = [], []
    for lid in losers:
        ander = per_id.get(lid)
        if not ander:
            geweigerd.append({"id": lid, "reason": "not_found"})
            continue
        if not zelfde_artikel(per_id[keep], ander, merken):
            geweigerd.append({"id": lid, "reason": "not_the_same_article"})
            continue
        botsing = _botsende_kanalen(bezet.get(keep, set()), bezet.get(lid, set()))
        if botsing:
            geweigerd.append({"id": lid, "reason": "advert_on_same_platform",
                              "platforms": sorted(botsing)})
            continue
        try:
            db.table("listings").update({"item_id": keep}).eq("item_id", lid).execute()
        except Exception as e:  # noqa: BLE001
            # HET VANGNET, EN WAAROM HET ER NAAST DE CONTROLE HIERBOVEN STAAT.
            # De controle modelleert de index zoals die er ná
            # scripts/fix_listings_unique.sql uitziet. Zolang die wijziging niet
            # gedraaid is, is de index nog de striktere oude versie en laat de
            # controle dus iets door dat de database alsnog weigert. Dat mag
            # nooit meer als serverfout bij de klant belanden — dat was precies
            # de storing van 31-08-2026.
            if "23505" not in str(e) and "duplicate key" not in str(e).lower():
                raise
            geweigerd.append({"id": lid, "reason": "advert_on_same_platform",
                              "platforms": sorted(
                                  {p for p, _ in bezet.get(lid, set()) if p})})
            continue
        db.table("jobs").update({"item_id": keep}).eq("item_id", lid).execute()
        db.table("items").delete().eq("id", lid).eq("user_id", user_id).execute()
        # Het bewaarde item draagt nu ook de advertenties van deze rij; een
        # volgende loser in dezelfde aanroep moet daar tegenaan botsen.
        bezet.setdefault(keep, set()).update(bezet.get(lid, set()))
        samengevoegd.append(lid)

    return {"kept": keep, "merged": samengevoegd, "refused": geweigerd}


def _botsende_kanalen(van_keep: set, van_ander: set) -> set:
    """De kanalen waarop deze twee items niet samen kunnen.

    Twee lopende advertenties botsen alleen als het dezelfde advertentie zou
    worden: hetzelfde kanaal én hetzelfde advertentienummer. Twee echte,
    verschillende advertenties op Marktplaats mogen naast elkaar bestaan — dat
    is juist wat samenvoegen oplevert.

    Een ontbrekend advertentienummer telt daarbij als één en dezelfde waarde,
    net als `NULLS NOT DISTINCT` in de index. Anders zou een item onbeperkt
    lopende advertenties zonder nummer kunnen verzamelen, en dat is precies hoe
    dubbel publiceren eruitziet.
    """
    per_kanaal = {}
    for kanaal, nummer in van_keep:
        per_kanaal.setdefault(kanaal, set()).add(nummer or "")
    return {kanaal for kanaal, nummer in van_ander
            if kanaal and (nummer or "") in per_kanaal.get(kanaal, set())}


@router.get("/{item_id}")
def get_item(item_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Item not found")
    return result.data


@router.patch("/{item_id}")
async def update_item(item_id: str, updates: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    clean = _strip_missing(updates)

    # A price change has to reach the marketplaces, not just this row. Without
    # this the dashboard showed the new price while every channel kept selling
    # at the old one — which made the whole Stale stock "Apply" flow pointless.
    prior = None
    price_fields = {"price", "price_marktplaats", "price_2dehands",
                    "price_vinted", "price_ebay", "price_shopify"}
    if price_fields & set(clean):
        prior = (await _exec(db.table("items").select("*").eq("id", item_id).eq("user_id", user_id))).data
        prior = prior[0] if prior else None

    try:
        result = await asyncio.to_thread(
            execute_with_retry,
            db.table("items")
            .update(clean)
            .eq("id", item_id)
            .eq("user_id", user_id),
        )
    except Exception as e:
        _raise_if_duplicate_sku(db, e, clean.get("sku"), user_id)
        logger.exception("Item update failed for %s", item_id)
        raise HTTPException(status_code=500, detail=f"Change was not saved: {e}")
    if not result.data:
        raise HTTPException(status_code=404, detail="Item not found")
    item = result.data[0]

    def _changed(field: str) -> bool:
        if field not in clean or prior is None:
            return False
        try:
            return float(prior.get(field) or 0) != float(clean.get(field) or 0)
        except (TypeError, ValueError):
            return prior.get(field) != clean.get(field)

    if prior is not None and any(_changed(f) for f in price_fields):
        from backend.services.crosslist import sync_price_to_platforms
        # Best-effort: a marketplace that refuses the new price must not fail the
        # save itself, so the outcome is reported alongside the item instead.
        try:
            item["price_sync"] = await sync_price_to_platforms(item_id, user_id)
        except Exception as e:  # noqa: BLE001 - never break the save
            logger.exception("Price sync raised for item %s", item_id)
            item["price_sync"] = [{"status": "error", "error": str(e)}]

    return item


@router.delete("/{item_id}")
def delete_item(item_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    # Verify ownership
    item = db.table("items").select("id,photo_urls").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    photo_urls = list(item.data[0].get("photo_urls") or [])
    listing_ids = [l["id"] for l in (db.table("listings").select("id").eq("item_id", item_id).execute().data or [])]
    for lid in listing_ids:
        db.table("sync_events").delete().eq("listing_id", lid).execute()
    db.table("listings").delete().eq("item_id", item_id).execute()
    db.table("jobs").delete().eq("item_id", item_id).execute()
    db.table("items").delete().eq("id", item_id).execute()
    _release_photos(db, user_id, photo_urls)
    return {"deleted": item_id}


def _release_photos(db, user_id: str, photo_urls: list) -> None:
    """Delete the item's photos from storage — but ONLY the truly unused ones.

    Photos are stored content-addressed, so two items with the same picture
    share one object, and an import candidate can point at it too. Deleting on
    sight would blank out a photo on an item the user still has. Every url is
    therefore checked against everything that could still reference it, and
    anything we cannot prove is orphaned is left in the bucket.

    Never raises: a failed cleanup costs storage, a failed delete costs the user
    their item.
    """
    from backend.services.image_upload import delete_objects, locate_object

    try:
        candidates = {ref for ref in (locate_object(u) for u in photo_urls) if ref}
        if not candidates:
            return  # nothing of ours to clean up (marketplace CDN urls)

        # Compare on PATH, never on the url string. The stored urls are not
        # byte-identical across versions of the Supabase client — older ones
        # append a bare "?" — so matching on the raw string would call a photo
        # unused while another item is still showing it.
        in_use: set[tuple[str, str]] = set()
        for row in (db.table("items").select("photo_urls")
                      .eq("user_id", user_id).execute().data or []):
            for u in (row.get("photo_urls") or []):
                ref = locate_object(u)
                if ref:
                    in_use.add(ref)
        for row in (db.table("import_candidates").select("photo_url,photo_urls")
                      .eq("user_id", user_id).execute().data or []):
            for u in [row.get("photo_url"), *(row.get("photo_urls") or [])]:
                ref = locate_object(u)
                if ref:
                    in_use.add(ref)

        orphaned = sorted(candidates - in_use)
        if orphaned:
            delete_objects(orphaned)
    except Exception:  # noqa: BLE001 - the item is already gone; this is bookkeeping
        logger.warning("photo cleanup skipped for user %s", user_id, exc_info=True)


@router.post("/{item_id}/delist")
async def delist_item(item_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    item = await _exec(db.table("items").select("id").eq("id", item_id).eq("user_id", user_id))
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    from backend.services.crosslist import delist_all_platforms
    results = await delist_all_platforms(item_id, user_id)
    return {"item_id": item_id, "results": results}


@router.post("/{item_id}/crosslist")
async def crosslist_item(item_id: str, body: dict, user_id: str = Depends(require_active_subscription)):
    db = get_db()
    item = await _exec(db.table("items").select("*").eq("id", item_id).eq("user_id", user_id))
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    platforms = body.get("platforms", [])
    if not platforms:
        raise HTTPException(status_code=400, detail="No platforms specified")

    # Artikelen weigeren die op dit platform niet kunnen bestaan. Dit staat hier
    # en niet alleen in het scherm, want een bulkactie loopt langs dezelfde
    # ingang: een vinkje dat per ongeluk aanstaat mag geen honderd zoekertjes
    # opleveren die het platform toch niet accepteert.
    from backend.services.platformregels import geblokkeerde_platforms
    from backend.services.instellingen import lees as lees_instellingen
    voorkeur = lees_instellingen(user_id).get("vinted_groepen") or []
    geblokkeerd = geblokkeerde_platforms(item.data[0], platforms, voorkeur)
    platforms = [p for p in platforms if p not in geblokkeerd]
    if not platforms:
        raise HTTPException(status_code=422, detail={"blocked_platforms": geblokkeerd})
    from backend.services.crosslist import publish_to_platforms, CrosslistValidationError
    try:
        results = await publish_to_platforms(item_id, platforms, user_id)
    except CrosslistValidationError as e:
        raise HTTPException(status_code=422, detail={"missing_fields": e.missing})
    return {"item_id": item_id, "results": results, "blocked_platforms": geblokkeerd}
