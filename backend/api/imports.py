from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db
from backend.api.deps import get_current_user
from backend.models import ItemCreate
from datetime import datetime, timezone
import json
import logging
import re
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/imports", tags=["imports"])

SCANNABLE_PLATFORMS = {"vinted", "marktplaats", "2dehands"}


def _map_condition(raw: str | None) -> str:
    """Map a platform's free-text condition onto our new/good/fair/poor scale."""
    s = (raw or "").strip().lower()
    if not s:
        return "good"
    if "new" in s or "nieuw" in s or "tags" in s or "prijskaartje" in s:
        return "new"
    if "very good" in s or "zo goed als nieuw" in s or "good" in s or "goed" in s:
        return "good"
    if "satisf" in s or "redelijk" in s or "fair" in s:
        return "fair"
    if "poor" in s or "slecht" in s or "gebruikt" in s:
        return "poor"
    return "good"


# Closed colour vocabulary, English + Dutch (incl. common inflected forms like
# "grijze"/"blauwe"). Compound/longer entries first so "light blue"/"lichtblauw"
# win over "blue"/"blauw". Whole-word matched, so a re-scan on Dutch listings
# (Marktplaats/2dehands) fills colour just as well as English ones.
_COLORS = [
    # English compounds first
    "light blue", "dark blue", "light green", "dark green", "light grey", "dark grey",
    "off white", "navy", "royal blue",
    # Dutch compounds (base + inflected -e forms)
    "lichtblauwe", "donkerblauwe", "marineblauwe", "lichtgroene", "donkergroene",
    "lichtgrijze", "donkergrijze", "olijfgroene",
    "lichtblauw", "donkerblauw", "marineblauw", "lichtgroen", "donkergroen",
    "lichtgrijs", "donkergrijs", "gebroken wit",
    # English base
    "blue", "black", "white", "grey", "gray", "burgundy", "maroon", "wine", "red",
    "olive", "khaki", "green", "beige", "cream", "camel", "tan", "cognac", "brown",
    "pink", "lilac", "purple", "lavender", "yellow", "mustard", "orange", "silver",
    "gold", "teal", "turquoise", "multi",
    # Dutch base + inflected forms (irregular endings listed explicitly)
    "zwart", "zwarte", "wit", "witte", "grijs", "grijze", "blauw", "blauwe",
    "rood", "rode", "groen", "groene", "bruin", "bruine", "geel", "gele",
    "paars", "paarse", "roze", "lila", "oranje", "beige", "bordeaux", "marine",
    "olijfgroen", "kaki", "crème", "creme", "zilver", "zilveren", "goud", "gouden",
    "zalm", "mint", "ecru", "taupe", "camel", "cognac",
]

# Garment keyword -> the exact category key per gender (mirrors the frontend CATEGORIES
# map). Only genders with a sensible category are listed; anything else is left empty
# rather than guessed wrong. Keys are ordered so more specific words match first.
_CATEGORY_RULES = [
    # Sportswear first: an athletic short is a "sportbroek", not a "short", and
    # certainly not jeans. Without these rules "sport shorts" fell through to the
    # generic short/broek rules (or to nothing at all) — the MyProtein bug.
    (("sports bra", "sport bh", "sportbh"), {"dames": "sport bh"}),
    (("sports legging", "sportlegging", "gym legging", "yoga legging", "running tight",
      "hardlooptight", "legging"),
     {"dames": "sportleggings", "heren": "heren sportbroeken", "unisex": "unisex sportkleding"}),
    (("sport short", "sportshort", "sportbroek", "gym short", "running short",
      "training short", "hardloopshort", "korte sportbroek", "zwembroek"),
     {"dames": "sportbroeken", "heren": "heren sportbroeken",
      "kinderen": "kinderen sportkleding", "unisex": "unisex sportkleding"}),
    (("sportkleding", "sportswear", "trainingspak", "tracksuit", "gymwear",
      "activewear", "voetbalshirt", "wielrenshirt"),
     {"dames": "sportbroeken", "heren": "heren sportbroeken",
      "kinderen": "kinderen sportkleding", "unisex": "unisex sportkleding"}),
    (("blazer", "suit", "pak", "tuxedo", "colbert", "kostuum"), {"heren": "heren pakken"}),
    (("turtleneck", "half zip", "half-zip", "jumper", "sweater", "knitted", "knit",
      "pullover", "cardigan", "fleece", "zip vest", "gilet", "bodywarmer", "vest",
      "spencer", "tank top",
      # Dutch
      "trui", "coltrui", "col", "gebreid", "gebreide", "sweater", "vest"),
     {"heren": "heren truien", "dames": "truien", "unisex": "unisex truien"}),
    (("hoodie", "sweatshirt", "capuchontrui"),
     {"heren": "heren hoodies", "dames": "hoodies", "unisex": "unisex truien"}),
    (("polo",), {"heren": "heren polo's", "dames": "tops"}),
    (("overhemd", "buttoned shirt", "dress shirt", "shirt", "blouse"),
     {"heren": "heren overhemden", "dames": "blouses"}),
    (("t-shirt", "tee", "t shirt"), {"heren": "heren t-shirts", "dames": "tops"}),
    (("loafer", "loafers", "formal shoe", "derby", "brogue", "oxford", "nette schoen"),
     {"heren": "heren formele schoenen", "dames": "hakken"}),
    (("sneaker", "sneakers", "trainer", "trainers"), {"heren": "heren sneakers", "dames": "sneakers dames"}),
    (("boot", "boots", "laars", "laarzen"), {"heren": "heren laarzen", "dames": "laarzen dames"}),
    (("shoe", "shoes", "schoen", "schoenen"), {"heren": "heren schoenen", "dames": "schoenen dames"}),
    (("jeans", "denim", "spijkerbroek"), {"heren": "heren jeans", "dames": "jeans"}),
    (("chino", "trouser", "pants", "pantalon", "broek"),
     {"heren": "heren chinos", "dames": "broeken"}),
    (("short", "korte broek"), {"heren": "heren shorts", "dames": "shorts"}),
    (("coat", "jacket", "parka", "bomber", "shacket",
      "jas", "jassen", "winterjas", "zomerjas", "regenjas"),
     {"heren": "heren jassen", "dames": "jassen", "unisex": "unisex jassen"}),
    (("skirt", "rok"), {"dames": "rokken"}),
    (("dress", "jurk", "jurkje"), {"dames": "jurken casual"}),
    (("blouse", "tunic", "tuniek"), {"dames": "blouses"}),
]


# The complete taxonomy, mirroring frontend CATEGORIES. This is what the
# classifier is allowed to choose from — it may not invent a key, because the
# extension maps these to hardcoded platform category IDs.
_TAXONOMY = {
    "dames": [
        "jeans", "broeken", "shorts", "rokken", "jurken casual", "jurken feest",
        "blouses", "tops", "truien", "hoodies", "jassen", "sport bh",
        "sportleggings", "sportbroeken", "zwemkleding", "ondergoed",
        "sneakers dames", "schoenen dames", "hakken", "laarzen dames",
        "sandalen", "accessoires dames",
    ],
    "heren": [
        "heren jeans", "heren chinos", "heren shorts", "heren t-shirts",
        "heren polo's", "heren overhemden", "heren truien", "heren hoodies",
        "heren jassen", "heren pakken", "heren sportbroeken", "heren sneakers",
        "heren schoenen", "heren formele schoenen", "heren laarzen",
        "heren accessoires",
    ],
    "kinderen": [
        "babykleding", "peuterkleding", "jongens kleding", "meisjes kleding",
        "tieners jongens", "tieners meisjes", "kinderen sportkleding",
        "kinderen schoenen",
    ],
    "unisex": [
        "unisex truien", "unisex jassen", "unisex sportkleding",
        "unisex schoenen", "unisex accessoires",
    ],
}
_ALL_CATEGORIES = {c for cats in _TAXONOMY.values() for c in cats}


async def _classify_with_claude(title: str | None, description: str | None,
                                brand: str | None) -> dict:
    """
    Ask Claude for gender + category, choosing only from _TAXONOMY.

    The keyword rules below can't see brand context and have no sportswear rule
    for adults, so "MyProtein sport shorts" matched nothing, fell through to an
    empty category, and the extension's MP_DEFAULT turned it into women's jeans.
    Claude gets the brand too, which is usually the strongest signal about what
    kind of garment this is.

    Returns {} on any failure or low confidence — callers fall back to the
    keyword rules, and an unresolved category is surfaced to the user rather
    than guessed (see _infer_attributes).
    """
    if not (title or description):
        return {}
    try:
        import anthropic as _anthropic
        from backend.config import settings as _settings
        client = _anthropic.Anthropic(api_key=_settings.anthropic_api_key)

        taxonomy_lines = "\n".join(
            f"  {g}: {', '.join(cats)}" for g, cats in _TAXONOMY.items()
        )
        prompt = (
            "You categorise second-hand clothing listings for a Dutch marketplace.\n\n"
            f"Brand: {brand or 'unknown'}\n"
            f"Title: {title or ''}\n"
            f"Description: {(description or '')[:1500]}\n\n"
            "Pick the single best gender and category from this exact taxonomy:\n"
            f"{taxonomy_lines}\n\n"
            "Rules:\n"
            "- The category MUST be copied verbatim from the list for the gender you pick.\n"
            "- Use the brand as a signal (e.g. MyProtein/Gymshark/Nike = sportswear).\n"
            "- Athletic shorts belong in a sportbroeken category, NOT shorts or jeans.\n"
            "- If gender is not stated or implied, use unisex where a sensible unisex\n"
            "  category exists; otherwise pick the most likely gender.\n"
            "- Set confidence low if you are guessing about what the garment is.\n\n"
            'Respond with ONLY JSON: {"gender":"...","category":"...","confidence":"high|medium|low"}'
        )
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return {}
        data = json.loads(m.group(0))

        gender, category = data.get("gender"), data.get("category")
        # Never trust the model's key blindly: an invented category would be
        # mapped to MP_DEFAULT downstream, recreating the exact bug this fixes.
        if data.get("confidence") == "low":
            return {}
        if gender not in _TAXONOMY or category not in _TAXONOMY.get(gender, []):
            logger.warning(f"Claude returned category outside taxonomy: {gender}/{category}")
            return {}
        return {"gender": gender, "category": category}
    except Exception as e:
        logger.warning(f"Claude classification failed, falling back to keywords: {e}")
        return {}


def _word_in(word: str, text: str) -> bool:
    """Whole-word match so a garment/colour word inside a brand name (e.g. 'suit'
    in 'Suitsupply') never triggers a false category."""
    return re.search(r"\b" + re.escape(word) + r"\b", text) is not None


def _infer_attributes(title: str | None, description: str | None = None) -> dict:
    """Best-effort colour / gender / category from the listing text. Conservative:
    only returns a value when confident, so callers can fill empty fields without
    ever writing a wrong guess (worst case a field just stays empty, as before)."""
    text = f"{title or ''} {description or ''}".lower()
    out = {}

    # Pick the colour that appears EARLIEST in the text (titles lead with the
    # colour: "Grey … Blazer"), preferring the longest match at that position.
    best_pos, best_len, best_color = None, 0, None
    for c in _COLORS:
        m = re.search(r"\b" + re.escape(c) + r"\b", text)
        if m and (best_pos is None or m.start() < best_pos or (m.start() == best_pos and len(c) > best_len)):
            best_pos, best_len, best_color = m.start(), len(c), c
    if best_color:
        out["color"] = "grey" if best_color == "gray" else best_color

    # Gender from explicit whole-word keywords only.
    if any(_word_in(w, text) for w in ("men", "mens", "male", "heren")):
        gender = "heren"
    elif any(_word_in(w, text) for w in ("women", "woman", "womens", "ladies", "dames", "female")):
        gender = "dames"
    elif any(_word_in(w, text) for w in ("kids", "child", "children", "boys", "girls", "junior",
                                          "kinderen", "baby", "toddler",
                                          "jongen", "jongens", "meisje", "meisjes", "peuter", "tiener")):
        gender = "kinderen"
    elif _word_in("unisex", text):
        gender = "unisex"
    else:
        gender = None
    # "women"/"womens" also contain "men" as a substring, but whole-word matching
    # keeps them distinct, so the order above is safe.
    if gender:
        out["gender"] = gender

    # Category needs a known gender to pick the right key. Match is plural-tolerant
    # ("shoe"→"shoes", "shirt"→"shirts") while whole-word, so brand names like
    # "Suitsupply" still never match a garment keyword.
    def _garment_in(k):
        return re.search(r"\b" + re.escape(k) + r"s?\b", text) is not None

    if gender == "kinderen":
        # Kids' taxonomy is age/gender-based, not garment-based: a "Boys XL vest"
        # is simply "jongens kleding". Shoes/sportswear are the only garment splits.
        if any(_garment_in(k) for k in ("shoe", "sneaker", "boot", "trainer")):
            out["category"] = "kinderen schoenen"
        elif any(_garment_in(k) for k in ("sport", "legging", "trainingspak")):
            out["category"] = "kinderen sportkleding"
        elif any(_word_in(w, text) for w in ("boys", "boy", "jongens", "jongen")):
            out["category"] = "jongens kleding"
        elif any(_word_in(w, text) for w in ("girls", "girl", "meisjes", "meisje")):
            out["category"] = "meisjes kleding"
    elif gender:
        for keywords, per_gender in _CATEGORY_RULES:
            if any(_garment_in(k) for k in keywords):
                key = per_gender.get(gender)
                if key:
                    out["category"] = key
                break

    return out


def _photos_from_candidate(cand: dict) -> list[str]:
    """Full photo list if the scan captured it, else the single thumbnail."""
    photos = cand.get("photo_urls")
    if isinstance(photos, list) and photos:
        return [p for p in photos if p]
    return [cand["photo_url"]] if cand.get("photo_url") else []


async def _infer_attributes_smart(title: str | None, description: str | None,
                                  brand: str | None = None) -> dict:
    """
    Category/gender inference for user-facing import paths: Claude first (it can
    weigh the brand and understands the garment), keyword rules as fallback.

    Kept separate from _infer_attributes because the bulk scan-store path is
    synchronous and runs per scanned row — it would fire one LLM call per
    listing. Colour always comes from the cheap keyword pass.
    """
    keyword_out = _infer_attributes(title, description)
    smart = await _classify_with_claude(title, description, brand)
    if not smart:
        return keyword_out
    # Claude wins on gender/category; keep the keyword colour.
    return {**keyword_out, **smart}


def _item_data_from_candidate(cand: dict, body: dict | None = None,
                              inferred: dict | None = None) -> dict:
    """
    Build the full item payload from a scraped candidate, so an import lands
    with everything the scan captured (all photos, description, brand, size,
    condition, category, colour, material). `body` overrides any field the user
    edited in the import dialog and carries data the scan can't see (e.g.
    purchase_price).
    """
    body = body or {}
    # Fill colour/gender/category the scan can't see by inferring them from the
    # listing text — only used as a last resort below (body + scan always win).
    # Async callers pass the Claude-backed result; otherwise keywords only.
    if inferred is None:
        inferred = _infer_attributes(cand.get("title"), cand.get("description"))

    def pick(key, cand_key=None, default=None):
        v = body.get(key)
        return v if v is not None else (cand.get(cand_key or key) or default)

    return {
        "title": pick("title") or "Untitled",
        "price": body.get("price") if body.get("price") is not None else (cand.get("price") or 0),
        "photo_urls": body.get("photo_urls") or _photos_from_candidate(cand),
        "description": pick("description"),
        "purchase_price": body.get("purchase_price"),
        "brand": pick("brand"),
        "size": pick("size"),
        "condition": body.get("condition") or _map_condition(cand.get("condition")),
        "category": pick("category") or inferred.get("category"),
        "gender": pick("gender") or inferred.get("gender"),
        "color": pick("color") or inferred.get("color"),
        "material": pick("material"),
    }


def _is_empty(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v)


def _backfill_item_from_candidate(db, item_id: str, cand: dict,
                                  inferred: dict | None = None) -> dict:
    """Fill ONLY the empty fields on an existing item from a freshly scanned
    candidate (description, colour, photos, …). Never overwrites data the user
    already has, so linking a rescanned listing enriches — never clobbers — the item.
    Returns the applied patch (empty if nothing to fill)."""
    current = db.table("items").select(
        "description,brand,size,color,material,condition,photo_urls"
    ).eq("id", item_id).execute().data
    if not current:
        return {}
    current = current[0]
    patch = {}
    for field in ("description", "brand", "size", "color", "material"):
        if _is_empty(current.get(field)) and not _is_empty(cand.get(field)):
            patch[field] = cand[field]
    if _is_empty(current.get("condition")) and cand.get("condition"):
        patch["condition"] = _map_condition(cand.get("condition"))
    if _is_empty(current.get("photo_urls")):
        photos = _photos_from_candidate(cand)
        if photos:
            patch["photo_urls"] = photos
    # Colour/gender/category the scan couldn't see: infer from the listing text,
    # but only fill fields still empty on the item (and never wrong — see _infer_attributes).
    inferred = _infer_attributes(cand.get("title"), cand.get("description"))
    for field in ("color", "gender", "category"):
        if field not in patch and _is_empty(current.get(field)) and inferred.get(field):
            patch[field] = inferred[field]
    if patch:
        db.table("items").update(patch).eq("id", item_id).execute()
    return patch


def _norm_title(t: str | None) -> str:
    """Normalise a title for matching: lowercase, collapse all whitespace."""
    return " ".join((t or "").lower().split())


def _best_match(title: str, items: list[dict]) -> str | None:
    """
    Only auto-suggest an EXACT title match. Titles are published verbatim to the
    platform, so a genuine re-import of an existing item has an identical title.
    Fuzzy matching is dangerous here: items differ only by size/colour/number
    ("Navy … Men L" vs "Navy … Men XL"), which score ~0.95+ on a character-ratio
    and get wrongly linked. Exact-only means "no confident match" (→ create new)
    rather than a wrong link the user has to notice and undo.
    """
    want = _norm_title(title)
    if not want:
        return None
    matches = [it["id"] for it in items if _norm_title(it.get("title")) == want]
    # Only trust an exact title if it's UNIQUE — if two items share the title we
    # can't tell them apart, so leave it unmatched rather than pick one at random.
    return matches[0] if len(matches) == 1 else None


def _match_candidate(cand: dict, items: list[dict], listings_by_id: dict) -> tuple[str | None, str | None]:
    """
    Decide which existing item (if any) a scraped listing belongs to, and why.
    Two confident signals, strongest first:
      1. same_listing — the exact same platform listing id already lives on an
         item (we imported/created this listing before). 100% certain.
      2. same_title  — a single existing item has an identical title.
    Anything else → (None, None): no auto-link, the row becomes a new item.
    Returns (item_id, reason).
    """
    lid = cand.get("platform_listing_id")
    if lid is not None:
        item_id = listings_by_id.get((cand.get("platform"), str(lid)))
        if item_id and any(it["id"] == item_id for it in items):
            return item_id, "same_listing"
    title_match = _best_match(cand.get("title"), items)
    if title_match:
        return title_match, "same_title"
    return None, None


def _listings_by_platform_id(db, items: list[dict]) -> dict:
    """
    Map (platform, platform_listing_id) → item_id for the user's known listings.
    Scoped via the user's item ids (the listings table has no user_id column).
    """
    item_ids = [it["id"] for it in items]
    if not item_ids:
        return {}
    rows = db.table("listings").select("item_id,platform,platform_listing_id").in_("item_id", item_ids).execute().data or []
    out = {}
    for l in rows:
        pid = l.get("platform_listing_id")
        if pid is not None and l.get("item_id"):
            out[(l.get("platform"), str(pid))] = l["item_id"]
    return out


@router.post("/scan/{platform}")
async def start_scan(platform: str, user_id: str = Depends(get_current_user)):
    if platform not in SCANNABLE_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Scanning isn't available for {platform}")
    db = get_db()
    # The extension now also triggers Vinted scans autonomously on a timer; avoid
    # piling up duplicate scan jobs (and opening a second tab) if one is already
    # queued or actively running.
    existing = (
        db.table("jobs")
        .select("id")
        .eq("user_id", user_id)
        .eq("platform", platform)
        .eq("action", "scan")
        .in_("status", ["pending", "claimed"])
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return {"job_id": existing[0]["id"]}
    job = db.table("jobs").insert({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "item_id": None,
        "platform": platform,
        "action": "scan",
        "status": "pending",
        "payload": {},
    }).execute()
    return {"job_id": job.data[0]["id"]}


@router.get("/")
async def list_import_candidates(platform: str = None, status: str = "pending", user_id: str = Depends(get_current_user)):
    db = get_db()
    q = db.table("import_candidates").select("*").eq("user_id", user_id)
    if platform:
        q = q.eq("platform", platform)
    if status:
        q = q.eq("status", status)
    result = q.order("created_at", desc=True).limit(500).execute()
    candidates = result.data or []
    if candidates:
        items = db.table("items").select("id,title").eq("user_id", user_id).execute().data or []
        listings_by_id = _listings_by_platform_id(db, items)
        for c in candidates:
            item_id, reason = _match_candidate(c, items, listings_by_id)
            c["suggested_item_id"] = item_id
            c["match_reason"] = reason
    return candidates


@router.post("/{candidate_id}/link")
async def link_candidate(candidate_id: str, body: dict, user_id: str = Depends(get_current_user)):
    """Attach a scraped listing to an existing item — no new item, no guessed fields."""
    item_id = body.get("item_id")
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id required")
    db = get_db()
    cand = db.table("import_candidates").select("*").eq("id", candidate_id).eq("user_id", user_id).single().execute().data
    if not cand:
        raise HTTPException(status_code=404, detail="Import candidate not found")
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")

    # Backfill any empty item fields from the freshly scanned candidate.
    _backfill_item_from_candidate(db, item_id, cand)

    existing = db.table("listings").select("id").eq("item_id", item_id).eq("platform", cand["platform"]).execute()
    listed_at = cand.get("platform_listed_at") or datetime.now(timezone.utc).isoformat()
    if existing.data:
        db.table("listings").update({
            "platform_listing_id": cand["platform_listing_id"],
            "platform_listing_url": cand["platform_listing_url"],
            "status": "active",
            "listed_at": listed_at,
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        db.table("listings").insert({
            "item_id": item_id,
            "platform": cand["platform"],
            "platform_listing_id": cand["platform_listing_id"],
            "platform_listing_url": cand["platform_listing_url"],
            "status": "active",
            "listed_at": listed_at,
        }).execute()

    db.table("import_candidates").update({"status": "linked"}).eq("id", candidate_id).execute()
    return {"ok": True}


@router.post("/{candidate_id}/create-item")
async def create_item_from_candidate(candidate_id: str, body: dict, user_id: str = Depends(get_current_user)):
    """
    Create a new item from a scraped listing. `body` carries the fields scraping
    can't see (purchase_price, brand, size, condition, category, color, material, ...)
    plus optional overrides for title/price/photo_urls that were pre-filled from the scrape.
    """
    db = get_db()
    cand = db.table("import_candidates").select("*").eq("id", candidate_id).eq("user_id", user_id).single().execute().data
    if not cand:
        raise HTTPException(status_code=404, detail="Import candidate not found")

    item_data = _item_data_from_candidate(cand, body)
    item = ItemCreate(**item_data)
    data = item.model_dump()
    data["id"] = str(uuid.uuid4())
    data["user_id"] = user_id
    data["sku"] = f"IMP-{data['id'][:8].upper()}"
    created = db.table("items").insert(data).execute().data[0]

    listed_at = cand.get("platform_listed_at") or datetime.now(timezone.utc).isoformat()
    db.table("listings").insert({
        "item_id": created["id"],
        "platform": cand["platform"],
        "platform_listing_id": cand["platform_listing_id"],
        "platform_listing_url": cand["platform_listing_url"],
        "status": "active",
        "listed_at": listed_at,
    }).execute()

    db.table("import_candidates").update({"status": "imported"}).eq("id", candidate_id).execute()
    return {"item": created}


@router.post("/bulk-import")
async def bulk_import_candidates(body: dict = None, user_id: str = Depends(get_current_user)):
    """
    Process every pending import candidate in one go: candidates with a high-confidence
    suggested_item_id get linked to that item, everything else becomes a new item
    (title/price/photo straight from the scrape, condition defaults to 'good' since
    scraping can't see purchase price/brand/size — those stay editable on the item after).
    """
    db = get_db()
    platform = (body or {}).get("platform")
    q = db.table("import_candidates").select("*").eq("user_id", user_id).eq("status", "pending")
    if platform:
        q = q.eq("platform", platform)
    candidates = q.execute().data or []

    linked, created, failed = 0, 0, 0
    now = datetime.now(timezone.utc).isoformat()
    items = db.table("items").select("id,title").eq("user_id", user_id).execute().data or []
    listings_by_id = _listings_by_platform_id(db, items)

    for cand in candidates:
        try:
            listed_at = cand.get("platform_listed_at") or now
            match_id, _reason = _match_candidate(cand, items, listings_by_id)
            if match_id:
                existing = db.table("listings").select("id").eq("item_id", match_id).eq("platform", cand["platform"]).execute()
                if existing.data:
                    db.table("listings").update({
                        "platform_listing_id": cand["platform_listing_id"],
                        "platform_listing_url": cand["platform_listing_url"],
                        "status": "active",
                        "listed_at": listed_at,
                    }).eq("id", existing.data[0]["id"]).execute()
                else:
                    db.table("listings").insert({
                        "item_id": match_id,
                        "platform": cand["platform"],
                        "platform_listing_id": cand["platform_listing_id"],
                        "platform_listing_url": cand["platform_listing_url"],
                        "status": "active",
                        "listed_at": listed_at,
                    }).execute()
                _backfill_item_from_candidate(db, match_id, cand)
                db.table("import_candidates").update({"status": "linked"}).eq("id", cand["id"]).execute()
                linked += 1
            else:
                item_data = _item_data_from_candidate(cand)
                item = ItemCreate(**item_data)
                data = item.model_dump()
                data["id"] = str(uuid.uuid4())
                data["user_id"] = user_id
                data["sku"] = f"IMP-{data['id'][:8].upper()}"
                created_item = db.table("items").insert(data).execute().data[0]

                db.table("listings").insert({
                    "item_id": created_item["id"],
                    "platform": cand["platform"],
                    "platform_listing_id": cand["platform_listing_id"],
                    "platform_listing_url": cand["platform_listing_url"],
                    "status": "active",
                    "listed_at": listed_at,
                }).execute()

                db.table("import_candidates").update({"status": "imported"}).eq("id", cand["id"]).execute()
                items.append({"id": created_item["id"], "title": created_item["title"]})
                created += 1
        except Exception:
            failed += 1

    return {"linked": linked, "created": created, "failed": failed}


@router.post("/{candidate_id}/ignore")
async def ignore_candidate(candidate_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    db.table("import_candidates").update({"status": "ignored"}).eq("id", candidate_id).eq("user_id", user_id).execute()
    return {"ok": True}
