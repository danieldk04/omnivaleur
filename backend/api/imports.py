from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db, fetch_all, naast_de_lus
from backend.api.deps import get_current_user, require_active_subscription
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
    # Sporttakken vóór de algemene sportregels: een wielrenpak, skibroek of
    # voetbalshirt is geen "sportbroek", en belandde daardoor in de verkeerde
    # categorie (of, zonder gender, in damesjeans).
    (("cycling", "cycle jersey", "bib short", "bibshort", "wielren", "wielrenshirt",
      "fietsshirt", "fietsbroek", "cycling suit", "wielrenpak"),
     {"heren": "heren wielrenkleding", "dames": "wielrenkleding",
      "kinderen": "kinderen wielrenkleding", "unisex": "unisex wielrenkleding"}),
    (("football shirt", "voetbalshirt", "voetbaltenue", "voetbalbroekje",
      "football kit", "soccer jersey", "voetbalkleding"),
     {"heren": "heren voetbalkleding", "dames": "voetbalkleding",
      "kinderen": "kinderen voetbalkleding", "unisex": "unisex sportkleding"}),
    (("ski jacket", "ski pants", "skibroek", "skijas", "skipak", "snowboard",
      "skikleding", "wintersport"),
     {"heren": "heren skikleding", "dames": "skikleding",
      "kinderen": "kinderen sportkleding", "unisex": "unisex sportkleding"}),
    (("tracksuit", "trainingspak", "track suit", "trainingsjack", "trainingsjas"),
     {"heren": "heren trainingspakken", "dames": "trainingspakken",
      "kinderen": "kinderen sportkleding", "unisex": "unisex trainingspakken"}),
    (("running jacket", "hardloopjas", "sports jacket", "sportjas", "windbreaker",
      "windjack"),
     {"heren": "heren sportjassen", "dames": "sportjassen",
      "kinderen": "kinderen sportkleding", "unisex": "unisex sportkleding"}),
    (("running shirt", "hardloopshirt", "hardloopkleding", "running top", "running tee"),
     {"heren": "heren hardloopkleding", "dames": "hardloopkleding",
      "kinderen": "kinderen sportkleding", "unisex": "unisex hardloopkleding"}),
    (("yoga",), {"dames": "yogakleding", "heren": "heren gymkleding",
                 "unisex": "unisex sportkleding"}),
    (("sports top", "sportshirt", "sport top", "sporttop"),
     {"heren": "heren sport tops", "dames": "sport tops",
      "kinderen": "kinderen sportkleding", "unisex": "unisex sportkleding"}),
    (("swim shorts", "swimming trunks", "zwembroek"),
     {"heren": "heren zwembroeken", "dames": "zwemkleding",
      "kinderen": "kinderen zwemkleding", "unisex": "unisex sportkleding"}),
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
        "sport tops", "sportjassen", "trainingspakken", "hardloopkleding",
        "wielrenkleding", "voetbalkleding", "yogakleding", "gymkleding",
        "skikleding", "sportkleding",
    ],
    "heren": [
        "heren jeans", "heren chinos", "heren shorts", "heren t-shirts",
        "heren polo's", "heren overhemden", "heren truien", "heren hoodies",
        "heren jassen", "heren pakken", "heren sportbroeken", "heren sneakers",
        "heren schoenen", "heren formele schoenen", "heren laarzen",
        "heren accessoires",
        "heren sport tops", "heren sportjassen", "heren trainingspakken",
        "heren hardloopkleding", "heren wielrenkleding", "heren voetbalkleding",
        "heren gymkleding", "heren skikleding", "heren sportkleding",
        "heren zwembroeken", "heren ondergoed",
    ],
    "kinderen": [
        "babykleding", "peuterkleding", "jongens kleding", "meisjes kleding",
        "tieners jongens", "tieners meisjes", "kinderen sportkleding",
        "kinderen schoenen", "kinderen wielrenkleding", "kinderen voetbalkleding",
        "kinderen zwemkleding", "kinderen accessoires",
    ],
    "unisex": [
        "unisex truien", "unisex jassen", "unisex sportkleding",
        "unisex schoenen", "unisex accessoires",
        "unisex wielrenkleding", "unisex trainingspakken", "unisex hardloopkleding",
    ],
    # Niet-kleding: Muziek en Instrumenten. Zelfde sleutels als in
    # MP_CATEGORIES in extension/background.js — het "muziek "-voorvoegsel houdt
    # ze uit de buurt van de kledingtakken. Geslacht speelt hier geen rol.
    # Antiek en Kunst. Marktplaats' op een na grootste boom en volledig
    # ontbrekend: een zilverhandelaar met 1.200 advertenties kreeg voor 97 van
    # zijn 130 items GEEN categorie, waarna het dashboard om maat en merk vroeg
    # en een gembercouvert onder sieraden belandde. Twee niveaus, net als muziek.
    # Sieraden, tassen, horloges en zonnebrillen. Stond wél in het dashboard en
    # in de extensie, maar niet in deze lijst — waardoor het model een ring of
    # armband nooit als sieraad kón indelen en die in "unisex accessoires"
    # belandden. Gelijk aan CATEGORIES.sieraden in frontend/app.html.
    "sieraden": [
        "sieraden horloges dames",
        "sieraden horloges heren",
        "sieraden horloges kinderen",
        "sieraden horloges antiek",
        "sieraden smartwatch",
        "sieraden sporthorloge",
        "sieraden activity tracker",
        "sieraden kettingen",
        "sieraden kettinghangers",
        "sieraden armbanden",
        "sieraden ringen",
        "sieraden oorbellen",
        "sieraden bedels",
        "sieraden broches",
        "sieraden enkelbandjes",
        "sieraden kindersieraden",
        "sieraden antiek",
        "sieraden damestassen",
        "sieraden schoudertassen",
        "sieraden rugtassen",
        "sieraden reistassen",
        "sieraden sporttassen",
        "sieraden koffers",
        "sieraden portemonnees",
        "sieraden zonnebril dames",
        "sieraden zonnebril heren",
    ],
    # Huis, tuin en kerst. Drie takken van Marktplaats onder één noemer,
    # want voor de verkoper is het één soort voorraad. Kerst hangt bij
    # Marktplaats onder Diversen, niet onder wonen.
    "wonen": [
        "wonen tuinmeubel accessoires",
        "wonen parasols",
        "wonen tuinstoelen",
        "wonen tuintafels",
        "wonen tuinsets en loungesets",
        "wonen tuinbanken",
        "wonen ligbedden",
        "wonen bloembakken en plantenbakken",
        "wonen bloempotten",
        "wonen buitenverlichting",
        "wonen vuurkorven",
        "wonen terrasverwarmers",
        "wonen partytenten",
        "wonen overkappingen",
        "wonen schaduwdoeken",
        "wonen zonneschermen",
        "wonen hangmatten",
        "wonen picknicktafels",
        "wonen gordijnen en lamellen",
        "wonen barkrukken",
        "wonen stoelen",
        "wonen krukjes",
        "wonen fauteuils",
        "wonen eettafels",
        "wonen salontafels",
        "wonen bijzettafels",
        "wonen tapijten en kleden",
        "wonen kussens",
        "wonen plaids en woondekens",
        "wonen vazen",
        "wonen spiegels",
        "wonen wanddecoraties",
        "wonen kunstplanten",
        "wonen tafellampen",
        "wonen vloerlampen",
        "wonen hanglampen",
        "wonen kandelaars en kaarsen",
        "wonen tafelkleden",
        "wonen overige huis en inrichting",
        "wonen kerst",
    ],
    "antiek": [
        "antiek curiosa en brocante",
        "antiek glas en kristal",
        "kunst schilderijen klassiek",
        "antiek vazen",
        "antiek keramiek en aardewerk",
        "antiek overige antiek",
        "antiek woonaccessoires",
        "antiek porselein",
        "antiek servies los",
        "kunst beelden en houtsnijwerken",
        "antiek meubels stoelen en banken",
        "antiek lampen",
        "kunst schilderijen modern",
        "antiek wandborden en tegels",
        "kunst etsen en gravures",
        "antiek koper en brons",
        "antiek bestek",
        "antiek boeken en bijbels",
        "antiek klokken",
        "antiek meubels kasten",
        "antiek speelgoed",
        "kunst niet westerse kunst",
        "antiek schalen",
        "antiek meubels tafels",
        "antiek gereedschap en instrumenten",
        "kunst schilderijen abstract",
        "antiek religie",
        "kunst designobjecten",
        "antiek emaille",
        "antiek goud en zilver",
        "kunst litho s en zeefdrukken",
        "kunst tekeningen en foto s",
        "antiek keukenbenodigdheden",
        "antiek servies compleet",
        "antiek kandelaars",
        "antiek spiegels",
        "antiek tin",
        "antiek kleden en textiel",
        "kunst overige kunst",
        "antiek kantoor en zakelijk",
        "antiek schoolplaten",
        "antiek kleding en accessoires",
        "antiek naaimachines",
        "antiek tv s en audio",
        "antiek meubels bedden",
    ],
    "muziek": [
        "muziek accordeons", "muziek behuizingen en koffers",
        "muziek blaasinstrumenten blokfluiten", "muziek blaasinstrumenten didgeridoos",
        "muziek blaasinstrumenten dwarsfluiten en piccolo's",
        "muziek blaasinstrumenten hobo's", "muziek blaasinstrumenten hoorns",
        "muziek blaasinstrumenten klarinetten", "muziek blaasinstrumenten mondharmonica's",
        "muziek blaasinstrumenten overige", "muziek blaasinstrumenten saxofoons",
        "muziek blaasinstrumenten trombones", "muziek blaasinstrumenten trompetten",
        "muziek blaasinstrumenten tuba's", "muziek bladmuziek",
        "muziek dj-sets en draaitafels", "muziek draaiorgels", "muziek drumcomputers",
        "muziek drumstellen en slagwerk", "muziek effecten",
        "muziek instrumenten onderdelen", "muziek instrumenten toebehoren",
        "muziek kabels en stekkers", "muziek keyboards", "muziek licht en laser",
        "muziek mengpanelen", "muziek microfoons", "muziek midi-apparatuur",
        "muziek orgels", "muziek orkestbanden", "muziek overige muziek en instrumenten",
        "muziek percussie", "muziek piano's", "muziek samplers",
        "muziek snaarinstrumenten banjo's", "muziek snaarinstrumenten gitaren akoestisch",
        "muziek snaarinstrumenten gitaren bas",
        "muziek snaarinstrumenten gitaren elektrisch", "muziek snaarinstrumenten harpen",
        "muziek snaarinstrumenten klavecimbels", "muziek snaarinstrumenten mandolines",
        "muziek snaarinstrumenten overige", "muziek soundmodules", "muziek standaards",
        "muziek strijkinstrumenten cello's", "muziek strijkinstrumenten contrabassen",
        "muziek strijkinstrumenten overige",
        "muziek strijkinstrumenten violen en altviolen", "muziek synthesizers",
        "muziek theaterbelichting", "muziek versterkers bas en gitaar",
        "muziek versterkers keyboard, monitor en pa",
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
        # A per-call timeout so one slow/hanging Haiku response can never freeze a
        # bulk import indefinitely — on timeout we fall back to the keyword rules.
        client = _anthropic.Anthropic(api_key=_settings.anthropic_api_key, timeout=20.0)

        taxonomy_lines = "\n".join(
            f"  {g}: {', '.join(cats)}" for g, cats in _TAXONOMY.items()
        )
        prompt = (
            "You categorise second-hand listings for a Dutch marketplace. Most are"
            " clothing; a minority are musical instruments and their accessories, or"
            " antiques, art and collectables.\n\n"
            f"Brand: {brand or 'unknown'}\n"
            f"Title: {title or ''}\n"
            f"Description: {(description or '')[:1500]}\n\n"
            "Pick the single best gender and category from this exact taxonomy:\n"
            f"{taxonomy_lines}\n\n"
            "Rules:\n"
            "- The category MUST be copied verbatim from the list for the gender you pick.\n"
            "- WHAT the garment is comes from the title and description ONLY. The brand\n"
            "  never decides that: Puma shoes are shoes, Nike trousers are trousers.\n"
            "  Use the brand only to choose between a sporty and a casual variant of the\n"
            "  SAME garment (e.g. Gymshark shorts = sportbroeken rather than shorts).\n"
            "- Footwear (shoes, sneakers, trainers, boots, loafers, heels, sandals) always\n"
            "  goes in a footwear category, whatever the brand is.\n"
            "- Athletic shorts belong in a sportbroeken category, NOT shorts or jeans.\n"
            "- If gender is not stated or implied, use unisex where a sensible unisex\n"
            "  category exists; otherwise pick the most likely gender.\n"
            "- Set confidence low if you are guessing about what the garment is.\n"
            '- The "muziek" branch is ONLY for musical instruments, their parts and their\n'
            "  accessories (a guitar, a plectrum, a case, a cable). A band T-shirt, a\n"
            "  festival hoodie or anything else you wear is clothing, never muziek.\n"
            '  When you pick a "muziek" category, gender must be "muziek" too.\n'
            '- The "antiek" branch is for antiques, art and collectables: silverware,\n'
            "  cutlery, porcelain, vases, paintings, clocks, brocante, decorative objects.\n"
            "  DECIDE ON WHAT IT IS, NOT WHAT IT IS MADE OF. Anything a person WEARS is\n"
            '  jewellery and belongs in the "sieraden" branch, however old or silver:\n'
            "  a ring, a bracelet, a necklace, earrings, a brooch, a watch. Anything you\n"
            "  put on a table, a wall or a shelf is antiek: a serving spoon, a ginger jar\n"
            "  spoon, a candlestick, a vase, a plate. Modern mass-produced homeware is\n"
            "  NOT antiek.\n"
            '  When you pick an "antiek" category, gender must be "antiek" too.\n'
            '- The "wonen" branch is home, garden and Christmas: chairs, bar stools,\n'
            "  armchairs, garden sets, tables, curtains, rugs, cushions, lamps,\n"
            "  mirrors, planters, parasols, terrace heaters and Christmas\n"
            "  decorations. This is ordinary modern homeware — genuinely old or\n"
            '  collectable pieces belong in "antiek" instead.\n'
            '  When you pick a "wonen" category, gender must be "wonen" too.\n'
            '- The "sieraden" branch covers jewellery, watches, bags, suitcases, wallets\n'
            "  and sunglasses. Pick it for anything worn or carried as an accessory.\n"
            '  When you pick a "sieraden" category, gender must be "sieraden" too.\n\n'
            'Respond with ONLY JSON: {"gender":"...","category":"...","confidence":"high|medium|low"}'
        )
        # client.messages.create is a *blocking* sync call. Run it in a worker
        # thread so the surrounding asyncio.gather in bulk-import actually runs the
        # classifications concurrently instead of one-at-a-time on the event loop
        # (which stalled large imports and made them look frozen).
        import asyncio as _asyncio
        resp = await _asyncio.to_thread(
            client.messages.create,
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
        elif any(_garment_in(k) for k in ("cycling", "wielren", "wielrenshirt", "fietsshirt")):
            out["category"] = "kinderen wielrenkleding"
        elif any(_garment_in(k) for k in ("football", "voetbal", "voetbalshirt",
                                          "voetbaltenue", "soccer")):
            out["category"] = "kinderen voetbalkleding"
        elif any(_garment_in(k) for k in ("swimwear", "swimsuit", "zwempak", "zwembroek",
                                          "badpak", "bikini")):
            out["category"] = "kinderen zwemkleding"
        elif any(_garment_in(k) for k in ("sport", "sportshirt", "sportbroek", "legging",
                                          "trainingspak", "tracksuit", "activewear")):
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
    merged = {**keyword_out, **smart}

    # …except when it contradicts a word that leaves no room for interpretation.
    # A pair of "White Puma Shoes" came back as sportbroeken (athletic shorts),
    # because the brand was treated as a stronger signal than the noun in the
    # title. Marktplaats then filed a shoe under Jeans. The text says "shoes";
    # no brand changes that, so the keyword rule wins here.
    if _is_footwear_text(title, description):
        if not _is_footwear_category(merged.get("category")):
            kw = keyword_out.get("category")
            logger.warning(
                "Category override: text says footwear but classifier picked "
                f"{merged.get('category')!r}; using {kw or 'no category'} instead."
            )
            # No trustworthy footwear key (unknown gender) → leave it empty rather
            # than keep a wrong one. The user is asked, instead of silently
            # publishing a shoe as a pair of jeans.
            merged["category"] = kw if _is_footwear_category(kw) else None
            if merged["category"] is None:
                merged.pop("category")
    elif _is_footwear_category(merged.get("category")) and keyword_out.get("category"):
        # The mirror image: footwear picked with nothing in the text supporting it.
        merged["category"] = keyword_out["category"]

    return merged


# Category keys that ARE footwear, across every gender branch of _TAXONOMY.
_FOOTWEAR_CATEGORIES = {
    "sneakers dames", "schoenen dames", "hakken", "laarzen dames", "sandalen",
    "heren sneakers", "heren schoenen", "heren formele schoenen", "heren laarzen",
    "kinderen schoenen", "unisex schoenen",
}

# Words that can only mean footwear. Deliberately excludes ambiguous ones like
# "pump" (also a machine) and "slipper" (also a garment in Dutch listings).
# Dutch plurals are spelled out: the -s/-en suffix in the pattern below does not
# cover them all ("laars" → "laarzen"), and it was exactly the Dutch spelling
# that slipped through — a listing titled "Witte Puma schoenen" stayed filed as
# athletic shorts while the English "White Puma Shoes" was caught.
_FOOTWEAR_WORDS = (
    "shoe", "sneaker", "trainer", "boot", "loafer", "brogue", "derby", "heel",
    "sandal", "espadrille", "moccasin",
    "schoen", "schoenen", "laars", "laarzen", "sandaal", "sandalen",
    "instapper", "instappers", "veterschoen", "veterschoenen",
    "gymp", "gympen", "hakschoen", "hakschoenen", "pumps", "hakken",
)


def _is_footwear_category(category: str | None) -> bool:
    return (category or "").strip().lower() in _FOOTWEAR_CATEGORIES


def _is_footwear_text(title: str | None, description: str | None) -> bool:
    """True when the listing text names footwear. The title carries far more
    weight than the description — a jacket description mentioning "matching
    boots" must not turn the jacket into footwear — so the description only
    counts when the title says nothing about the garment at all."""
    t = (title or "").lower()
    if any(re.search(r"\b" + w + r"(?:s|en)?\b", t) for w in _FOOTWEAR_WORDS):
        return True
    if t.strip():
        return False
    d = (description or "").lower()
    return any(re.search(r"\b" + w + r"(?:s|en)?\b", d) for w in _FOOTWEAR_WORDS)


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
        # De staat komt van drie kanten, in deze volgorde: wat de gebruiker in het
        # formulier typte, wat het platform meegaf, en anders de standaard voor
        # deze hele lading. Die laatste bestaat omdat Admarkt geen staat meelevert
        # en alles dan op "Like new" belandde — een handelaar die uitsluitend
        # nieuwe spullen verkoopt moest dat 240 keer met de hand corrigeren.
        "condition": (body.get("condition")
                      or _map_condition(cand.get("condition"))
                      if cand.get("condition") else
                      (body.get("condition") or body.get("_default_condition") or "good")),
        "category": pick("category") or inferred.get("category"),
        "gender": pick("gender") or inferred.get("gender"),
        "color": pick("color") or inferred.get("color"),
        "material": pick("material"),
        # Fields the user types in the same form but that used to be dropped here,
        # so an imported item silently lost its SKU, its Shopify "was" price and
        # any per-platform price overrides.
        "sku": body.get("sku"),
        "shopify_title": body.get("shopify_title"),
        "compare_at_price": body.get("compare_at_price"),
        "price_marktplaats": body.get("price_marktplaats"),
        "price_2dehands": body.get("price_2dehands"),
        "price_vinted": body.get("price_vinted"),
        "price_ebay": body.get("price_ebay"),
        "price_shopify": body.get("price_shopify"),
    }


def _is_empty(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v)


def _listing_status_for(cand: dict) -> str:
    """
    What status the listing this import creates should start in.

    A candidate the platform reports as hidden must NOT land as 'active': it
    would sit in the dashboard as if it were for sale, and count as stale stock,
    until the next scan happened to correct it. Anything else starts active.
    """
    return "hidden" if cand.get("is_hidden") else "active"


BACKFILL_FIELDS = "id,description,brand,size,color,material,condition,photo_urls,gender,category"


def _backfill_item_from_candidate(db, item_id: str, cand: dict,
                                  inferred: dict | None = None) -> dict:
    """Fill ONLY the empty fields on an existing item from a freshly scanned
    candidate (description, colour, photos, …). Never overwrites data the user
    already has, so linking a rescanned listing enriches — never clobbers — the item.
    Returns the applied patch (empty if nothing to fill)."""
    current = db.table("items").select(BACKFILL_FIELDS).eq("id", item_id).execute().data
    if not current:
        return {}
    patch = _backfill_patch(current[0], cand, inferred)
    if patch:
        db.table("items").update(patch).eq("id", item_id).execute()
    return patch


def _backfill_patch(current: dict, cand: dict, inferred: dict | None = None) -> dict:
    """
    Work out what a scanned candidate would add to an item — pure, no database.

    Split out so a scan can compute hundreds of these from ONE prefetched read
    instead of a select per row; the scan-store used to do a query per candidate,
    which is what made saving a big wardrobe take minutes.
    """
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
    # Async callers pass the Claude-backed result; the sync scan path uses keywords.
    if inferred is None:
        inferred = _infer_attributes(cand.get("title"), cand.get("description"))
    for field in ("color", "gender", "category"):
        if field not in patch and _is_empty(current.get(field)) and inferred.get(field):
            patch[field] = inferred[field]
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


def _listing_index(db, items: list[dict]) -> tuple[dict, dict]:
    """
    Read the user's listings once and return two views of them:
      * (platform, platform_listing_id) → item_id  — for the certain re-import match
      * item_id → {platforms}                      — which channels an item is already on
    Scoped via the user's item ids (the listings table has no user_id column).
    """
    item_ids = [it["id"] for it in items]
    if not item_ids:
        return {}, {}
    rows = []
    for i in range(0, len(item_ids), 200):
        brok = item_ids[i:i + 200]
        rows.extend(fetch_all(lambda b=brok: db.table("listings")
                              .select("item_id,platform,platform_listing_id").in_("item_id", b)))
    by_listing_id, platforms = {}, {}
    for l in rows:
        item_id, plat = l.get("item_id"), l.get("platform")
        if not item_id:
            continue
        if plat:
            platforms.setdefault(item_id, set()).add(plat)
        pid = l.get("platform_listing_id")
        if pid is not None:
            by_listing_id[(plat, str(pid))] = item_id
    return by_listing_id, platforms


def _tweede_advertentie(db, item_id: str, platform: str, listing_id) -> bool:
    """Staat er voor dit item al een ANDERE advertentie op ditzelfde platform?

    Een verkoper kan hetzelfde artikel meerdere keren los te koop zetten — tien
    identieke blikjes plectrums zijn tien advertenties, geen één. De titelmatch
    hierboven ziet dat verschil niet, en de koppeling overschreef dan het
    advertentienummer van de vorige. Gevolg: negen advertenties die het dashboard
    niet meer kende en dus ook niet kon verwijderen als er één verkocht was.
    """
    if not item_id or listing_id is None:
        return False
    try:
        rijen = (db.table("listings").select("platform_listing_id")
                 .eq("item_id", item_id).eq("platform", platform).execute().data or [])
    except Exception:
        return False
    return any(
        (r.get("platform_listing_id") is not None
         and str(r["platform_listing_id"]) != str(listing_id))
        for r in rijen
    )


# ── Cross-platform duplicate detection ────────────────────────────────────
#
# The exact-title match above cannot see that "Blauwe Nike hoodie maat M" on
# Marktplaats and "Blue Nike hoodie size M" on Vinted are one and the same
# jumper. A seller who imports from BOTH platforms would end up with the item
# twice — and cross-listing one of those copies would post a genuine duplicate
# advert on a channel where the item is already for sale.
#
# So we look for translated twins, with two hard rules:
#   1. It NEVER links automatically. Merging two different items is much harder
#      to undo than leaving a duplicate, so the seller always confirms.
#   2. It only ever compares a candidate against items that are already listed
#      on a DIFFERENT channel and NOT on the candidate's own channel — the only
#      situation in which a translated twin can exist at all.
# Costs nothing for the common case: a seller who only imports from one
# platform has no cross-platform items, so the model is never called.

_TWIN_BATCH = 40          # candidates per model call
_TWIN_MAX_ITEMS = 250     # never build a prompt bigger than this
_TWIN_PRICE_FACTOR = 2.5  # a twin priced 2.5x apart is not the same object


def _twin_pool(platform: str, items: list[dict], platforms_by_item: dict) -> list[dict]:
    """
    The items a candidate from `platform` could plausibly be a translated twin of.

    Scoped to ONE platform on purpose: with a mixed set of candidates the union of
    their platforms excluded every item that was on any of them, which emptied the
    pool completely and quietly switched duplicate detection off.
    """
    pool = []
    for it in items:
        on = platforms_by_item.get(it["id"]) or set()
        if not on:
            continue                       # never published anywhere — nothing to be a twin of
        if platform in on:
            continue                       # already on this channel; not a cross-channel twin
        pool.append(it)
    return pool[:_TWIN_MAX_ITEMS]


def _price(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# Colour words that mean the same thing across the two languages. Everything not
# listed here canonicalises to itself, so an unknown colour simply never matches
# a different one. Built from _COLORS above, which already covers NL inflections.
_COLOR_CANON = {
    "zwart": "black", "zwarte": "black", "black": "black",
    "wit": "white", "witte": "white", "white": "white",
    "gebroken wit": "offwhite", "off white": "offwhite", "ecru": "offwhite", "crème": "cream",
    "creme": "cream", "cream": "cream",
    "grijs": "grey", "grijze": "grey", "grey": "grey", "gray": "grey",
    "lichtgrijs": "lightgrey", "lichtgrijze": "lightgrey", "light grey": "lightgrey",
    "donkergrijs": "darkgrey", "donkergrijze": "darkgrey", "dark grey": "darkgrey",
    "blauw": "blue", "blauwe": "blue", "blue": "blue", "royal blue": "blue",
    "lichtblauw": "lightblue", "lichtblauwe": "lightblue", "light blue": "lightblue",
    "donkerblauw": "navy", "donkerblauwe": "navy", "dark blue": "navy",
    "marine": "navy", "marineblauw": "navy", "marineblauwe": "navy", "navy": "navy",
    "rood": "red", "rode": "red", "red": "red",
    "bordeaux": "burgundy", "burgundy": "burgundy", "maroon": "burgundy", "wine": "burgundy",
    "groen": "green", "groene": "green", "green": "green",
    "lichtgroen": "lightgreen", "lichtgroene": "lightgreen", "light green": "lightgreen",
    "donkergroen": "darkgreen", "donkergroene": "darkgreen", "dark green": "darkgreen",
    "olijfgroen": "olive", "olijfgroene": "olive", "olive": "olive", "kaki": "khaki", "khaki": "khaki",
    "bruin": "brown", "bruine": "brown", "brown": "brown", "cognac": "cognac", "camel": "camel",
    "taupe": "taupe", "beige": "beige", "tan": "beige",
    "geel": "yellow", "gele": "yellow", "yellow": "yellow", "mustard": "mustard",
    "oranje": "orange", "orange": "orange",
    "roze": "pink", "pink": "pink", "zalm": "salmon",
    "paars": "purple", "paarse": "purple", "purple": "purple",
    "lila": "lilac", "lilac": "lilac", "lavender": "lilac",
    "zilver": "silver", "zilveren": "silver", "silver": "silver",
    "goud": "gold", "gouden": "gold", "gold": "gold",
    "mint": "mint", "teal": "teal", "turquoise": "turquoise", "multi": "multi",
}

_SIZE_WORDS = {
    "small": "S", "medium": "M", "large": "L",
    "extra small": "XS", "extra large": "XL",
}
_SIZE_TOKEN = re.compile(r"^(xxxs|xxs|xs|s|m|l|xl|xxl|xxxl|w\d{2}|\d{2})$", re.I)


def _canon_colors(text: str | None) -> set:
    """Every colour named in a title, in one language-neutral vocabulary."""
    s = f" {' '.join((text or '').lower().split())} "
    found = set()
    for word in sorted(_COLOR_CANON, key=len, reverse=True):
        if f" {word} " in s or f" {word}e " in s:
            found.add(_COLOR_CANON[word])
    return found


def _sizes(text: str | None) -> set:
    """Size labels in a title — 'Heren XXL', 'Men XXL', "Men's Medium", 'W36', 'maat 42'."""
    s = " ".join((text or "").lower().split())
    out = set()
    for word, canon in _SIZE_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", s):
            out.add(canon)
    for tok in re.split(r"[^a-z0-9]+", s):
        if not tok or not _SIZE_TOKEN.match(tok):
            continue
        if tok.isdigit() and not (28 <= int(tok) <= 52):
            continue      # a number that is not a plausible clothing/shoe size
        out.add(tok.upper())
    return out


def _brands(text: str | None, known: set) -> set:
    """Which of the seller's own brand names appear in a title."""
    s = " ".join((text or "").lower().split())
    return {b for b in known if b and re.search(rf"\b{re.escape(b)}\b", s)}


def _twin_plausible(cand: dict, item: dict, known_brands: set) -> str | None:
    """
    Hard checks the language model cannot talk its way past. Returns the reason
    for rejection, or None when the pair survives.

    Measured on real inventory: the model on its own paired grey with blue,
    Profuomo with Suitsupply and an M with an XL. Colour, size and brand are
    right there in the title, so they get decided by rules, not by judgement.
    """
    a, b = _price(cand.get("price")), _price(item.get("price"))
    if a and b and a > 0 and b > 0 and max(a, b) / min(a, b) > _TWIN_PRICE_FACTOR:
        return "price"

    ca, cb = _canon_colors(cand.get("title")), _canon_colors(item.get("title"))
    if ca and cb and not (ca & cb):
        return "colour"

    sa, sb = _sizes(cand.get("title")), _sizes(item.get("title"))
    if sa and sb and not (sa & sb):
        return "size"

    ba = _brands(cand.get("title"), known_brands) | ({(cand.get("brand") or "").lower()} - {""})
    bb = _brands(item.get("title"), known_brands) | ({(item.get("brand") or "").lower()} - {""})
    if ba and bb and not (ba & bb):
        return "brand"

    return None


async def _find_twins(cands: list[dict], items: list[dict], platforms_by_item: dict) -> dict:
    """
    candidate_id → item_id for listings that look like the same physical object
    already in the inventory under another language. Empty dict on any failure:
    a missing suggestion just means one extra row to review, never a wrong merge.
    """
    if not cands:
        return {}
    # One platform at a time: the pool of possible twins is different for each.
    by_platform: dict[str, list[dict]] = {}
    for c in cands:
        by_platform.setdefault(c.get("platform"), []).append(c)
    if len(by_platform) > 1:
        import asyncio as _a
        results = await _a.gather(*(
            _find_twins(group, items, platforms_by_item) for group in by_platform.values()
        ))
        merged = {}
        for r in results:
            merged.update(r)
        return merged

    pool = _twin_pool(cands[0].get("platform"), items, platforms_by_item)
    if not pool:
        return {}
    try:
        import anthropic as _anthropic
        import asyncio as _asyncio
        from backend.config import settings as _settings
        client = _anthropic.Anthropic(api_key=_settings.anthropic_api_key, timeout=30.0)
    except Exception as e:
        logger.warning(f"Twin detection unavailable: {e}")
        return {}

    # The seller's own brand vocabulary, so a brand can be spotted in a title even
    # when the scan didn't record one for that row.
    known_brands = {(it.get("brand") or "").strip().lower() for it in items}
    known_brands |= {(c.get("brand") or "").strip().lower() for c in cands}
    known_brands.discard("")

    item_lines = "\n".join(
        f"[{i}] {(it.get('title') or '').strip()[:120]}"
        f"{' — ' + it['brand'] if it.get('brand') else ''}"
        f"{' — €' + str(it['price']) if it.get('price') is not None else ''}"
        for i, it in enumerate(pool)
    )

    async def _chunk(batch: list[dict]) -> dict:
        cand_lines = "\n".join(
            f"({j}) {(c.get('title') or '').strip()[:120]}"
            f"{' — ' + c['brand'] if c.get('brand') else ''}"
            f"{' — €' + str(c['price']) if c.get('price') is not None else ''}"
            for j, c in enumerate(batch)
        )
        prompt = (
            "A second-hand seller lists the same physical object on several marketplaces,"
            " often in different languages (Dutch on Marktplaats/2dehands, English on Vinted).\n\n"
            "ITEMS ALREADY IN THE INVENTORY:\n"
            f"{item_lines}\n\n"
            "NEWLY SCANNED LISTINGS:\n"
            f"{cand_lines}\n\n"
            "For each newly scanned listing, decide whether it is the SAME PHYSICAL OBJECT"
            " as one of the inventory items, allowing for translation between Dutch and English.\n"
            "Rules:\n"
            "- Only answer when you are certain. Brand, model, size and colour must all match.\n"
            "- Two similar garments that differ in size, colour or model are DIFFERENT objects.\n"
            "- A seller with several of the same product is normal; if you cannot tell which"
            " one it is, leave it out.\n"
            "- Leave out anything you are unsure about. An omission is harmless; a wrong"
            " pairing destroys the seller's inventory.\n\n"
            'Respond with ONLY a JSON array, e.g. [{"listing":0,"item":3}] — [] if none match.'
        )
        try:
            resp = await _asyncio.to_thread(
                client.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            m = re.search(r"\[.*\]", raw, re.S)
            if not m:
                return {}
            pairs = json.loads(m.group(0))
        except Exception as e:
            logger.warning(f"Twin detection call failed: {e}")
            return {}

        out = {}
        seen_items = set()
        for p in pairs if isinstance(pairs, list) else []:
            try:
                j, i = int(p["listing"]), int(p["item"])
            except (TypeError, ValueError, KeyError):
                continue
            if not (0 <= j < len(batch) and 0 <= i < len(pool)):
                continue
            if i in seen_items:
                continue   # two candidates claiming one item — can't tell them apart, drop both
            reject = _twin_plausible(batch[j], pool[i], known_brands)
            if reject:
                logger.info(
                    "Twin rejected on %s: %r vs %r",
                    reject, (batch[j].get("title") or "")[:60], (pool[i].get("title") or "")[:60],
                )
                continue
            seen_items.add(i)
            out[batch[j]["id"]] = pool[i]["id"]
        return out

    chunks = [cands[i:i + _TWIN_BATCH] for i in range(0, len(cands), _TWIN_BATCH)]
    results = await _asyncio_gather_safe(chunks, _chunk)
    merged = {}
    for r in results:
        merged.update(r)
    return merged


async def _asyncio_gather_safe(chunks, fn):
    import asyncio as _asyncio
    return await _asyncio.gather(*(fn(c) for c in chunks))


@router.post("/scan/{platform}")
def start_scan(platform: str, user_id: str = Depends(require_active_subscription)):
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
    # Een zakelijk Marktplaats-account (Admarkt) kan tienduizenden advertenties
    # hebben. Die passen niet in één ronde, dus elke scan pakt de volgende lading
    # op. Zonder dit begon iedere scan weer bij advertentie 1 en leverde hij niets
    # nieuws op — de scan meldde "klaar" terwijl er niets bijkwam.
    payload: dict = {}
    if platform == "marktplaats":
        # WAT WE AL HEBBEN, MEE NAAR DE EXTENSIE.
        #
        # Hier stond een teller: "sla de eerste N advertenties over". Dat werkt
        # alleen als Admarkt zijn advertenties élke keer in dezelfde volgorde
        # teruggeeft, en dat doet hij niet. Gemeten bij een verkoper met 5.534
        # advertenties: drie scans achter elkaar, elke keer dezelfde 250 en nul
        # nieuwe kandidaten — terwijl het scherm netjes "klaar" meldde.
        #
        # Nu sturen we de nummers mee die we al kennen. De extensie slaat die
        # over, ongeacht de volgorde waarin ze langskomen. Elke ronde levert dan
        # gegarandeerd nieuwe advertenties op, tot ze op zijn.
        try:
            bekend: list[str] = []
            stap = 1000
            for offset in range(0, 40000, stap):
                rij = (db.table("import_candidates").select("platform_listing_id")
                       .eq("user_id", user_id).eq("platform", platform)
                       .range(offset, offset + stap - 1).execute().data or [])
                bekend += [str(r["platform_listing_id"]) for r in rij
                           if r.get("platform_listing_id") is not None]
                if len(rij) < stap:
                    break
            payload["bekende_ids"] = bekend
            # De oude teller blijft meegaan voor wie nog een oudere extensie
            # draait; die kan met bekende_ids niets.
            payload["scan_offset"] = len(bekend)
        except Exception as e:
            logger.warning("Kon scanpositie niet bepalen voor %s: %s", user_id, e)

    job = db.table("jobs").insert({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "item_id": None,
        "platform": platform,
        "action": "scan",
        "status": "pending",
        "payload": payload,
    }).execute()
    return {"job_id": job.data[0]["id"]}


@router.get("/")
async def list_import_candidates(platform: str = None, status: str = "pending", user_id: str = Depends(get_current_user)):
    import asyncio

    db = get_db()

    # De Supabase-client is SYNCHROON en deze functie is async: elke .execute()
    # hieronder liep dus rechtstreeks op de lus die de hele server bedient. Bij
    # een verkoper met duizenden advertenties kost dit blok een paar seconden —
    # en al die tijd stond ALLES stil, voor iedereen, inclusief de import die op
    # dat moment bezig was. Precies daar kwamen de 500'en vandaan die de lading
    # lieten halveren. Alles wat de database raakt gaat daarom naar een aparte
    # werkdraad.
    def _lees():
        q = db.table("import_candidates").select("*").eq("user_id", user_id)
        if platform:
            q = q.eq("platform", platform)
        if status:
            q = q.eq("status", status)
        cands = q.order("created_at", desc=True).limit(500).execute().data or []
        if not cands:
            return cands, [], {}, {}
        its = fetch_all(lambda: db.table("items").select("id,title,price,brand").eq("user_id", user_id))
        by_id, by_item = _listing_index(db, its)
        return cands, its, by_id, by_item

    candidates, items, listings_by_id, platforms_by_item = await asyncio.to_thread(_lees)
    if candidates:
        unmatched = []
        for c in candidates:
            item_id, reason = _match_candidate(c, items, listings_by_id)
            c["suggested_item_id"] = item_id
            c["match_reason"] = reason
            if not item_id:
                unmatched.append(c)
        # Anything the certain rules couldn't place: check whether it is the same
        # object under another language, already imported from another channel.
        for cand_id, item_id in (await _find_twins(unmatched, items, platforms_by_item)).items():
            for c in candidates:
                if c["id"] == cand_id:
                    c["suggested_item_id"] = item_id
                    c["match_reason"] = "likely_same"
    return candidates


@router.get("/summary")
def import_candidates_summary(user_id: str = Depends(get_current_user)):
    """
    What the last scan of each platform actually found, broken down by what has
    already been decided about it.

    The review list only shows PENDING candidates, and a re-scan deliberately
    keeps the status of anything you already imported, linked or ignored. Put
    together, that means a scan of a wardrobe you've fully imported before ends
    with an empty review list — which looked exactly like "the scan found
    nothing". This is what lets the UI say where those listings went instead.
    """
    db = get_db()
    rows = (
        db.table("import_candidates")
        .select("platform,status")
        .eq("user_id", user_id)
        .limit(5000)
        .execute()
        .data or []
    )
    by_status: dict[str, int] = {}
    by_platform: dict[str, dict[str, int]] = {}
    for r in rows:
        st = r.get("status") or "pending"
        pf = r.get("platform") or "unknown"
        by_status[st] = by_status.get(st, 0) + 1
        by_platform.setdefault(pf, {})
        by_platform[pf][st] = by_platform[pf].get(st, 0) + 1
    return {"total": len(rows), "by_status": by_status, "by_platform": by_platform}


# Only these may be put back on the review list. 'imported' and 'linked' are
# deliberately NOT reopenable: those listings already exist as items, so
# re-importing them would duplicate your stock.
REOPENABLE = ("ignored", "failed")


@router.post("/reopen")
def reopen_candidates(body: dict = None, user_id: str = Depends(get_current_user)):
    """Put ignored/failed candidates back on the review list."""
    body = body or {}
    statuses = [s for s in (body.get("statuses") or list(REOPENABLE)) if s in REOPENABLE]
    if not statuses:
        raise HTTPException(status_code=400, detail="Nothing reopenable requested")
    db = get_db()
    q = db.table("import_candidates").select("id").eq("user_id", user_id).in_("status", statuses)
    if body.get("platform"):
        q = q.eq("platform", body["platform"])
    ids = [c["id"] for c in (q.execute().data or [])]
    for i in range(0, len(ids), 100):
        (db.table("import_candidates").update({"status": "pending"})
           .eq("user_id", user_id).in_("id", ids[i:i + 100]).execute())
    return {"reopened": len(ids)}


@router.post("/{candidate_id}/link")
async def link_candidate(candidate_id: str, body: dict, user_id: str = Depends(get_current_user)):
    """Attach a scraped listing to an existing item — no new item, no guessed fields."""
    item_id = body.get("item_id")
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id required")
    db = get_db()
    cand = (await naast_de_lus(lambda: db.table("import_candidates").select("*").eq("id", candidate_id).eq("user_id", user_id).single().execute())).data
    if not cand:
        raise HTTPException(status_code=404, detail="Import candidate not found")
    item = (await naast_de_lus(lambda: db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()))
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")

    # Backfill any empty item fields from the freshly scanned candidate. Photos
    # first, so a link-to-existing-item stores our own urls too (same reason as
    # the create path).
    from backend.services.photo_mirror import mirror_photos
    _mirrored = await mirror_photos(_photos_from_candidate(cand), user_id)
    if _mirrored:
        cand["photo_urls"] = _mirrored
    _backfill_item_from_candidate(db, item_id, cand, inferred=await _infer_attributes_smart(
        cand.get("title"), cand.get("description"), cand.get("brand")))

    existing = (await naast_de_lus(lambda: db.table("listings").select("id").eq("item_id", item_id).eq("platform", cand["platform"]).execute()))
    listed_at = cand.get("platform_listed_at") or datetime.now(timezone.utc).isoformat()
    if existing.data:
        (await naast_de_lus(lambda: db.table("listings").update({
            "platform_listing_id": cand["platform_listing_id"],
            "platform_listing_url": cand["platform_listing_url"],
            "status": _listing_status_for(cand),
            "listed_at": listed_at,
        }).eq("id", existing.data[0]["id"]).execute()))
    else:
        (await naast_de_lus(lambda: db.table("listings").insert({
            "item_id": item_id,
            "platform": cand["platform"],
            "platform_listing_id": cand["platform_listing_id"],
            "platform_listing_url": cand["platform_listing_url"],
            "status": _listing_status_for(cand),
            "listed_at": listed_at,
        }).execute()))

    (await naast_de_lus(lambda: db.table("import_candidates").update({"status": "linked"}).eq("id", candidate_id).execute()))
    return {"ok": True}


@router.post("/{candidate_id}/create-item")
async def create_item_from_candidate(candidate_id: str, body: dict, user_id: str = Depends(require_active_subscription)):
    """
    Create a new item from a scraped listing. `body` carries the fields scraping
    can't see (purchase_price, brand, size, condition, category, color, material, ...)
    plus optional overrides for title/price/photo_urls that were pre-filled from the scrape.
    """
    db = get_db()
    cand = (await naast_de_lus(lambda: db.table("import_candidates").select("*").eq("id", candidate_id).eq("user_id", user_id).single().execute())).data
    if not cand:
        raise HTTPException(status_code=404, detail="Import candidate not found")

    item_data = _item_data_from_candidate(cand, body, inferred=await _infer_attributes_smart(
        cand.get("title"), cand.get("description"), cand.get("brand")))
    # Copy the photos into our own bucket before the item exists. A listing
    # imported from Vinted keeps CDN urls that the extension physically cannot
    # download from a Marktplaats page (their CDN blocks that origin), so an
    # item stored with source urls could never be published with its photos.
    from backend.services.photo_mirror import mirror_photos
    item_data["photo_urls"] = await mirror_photos(item_data.get("photo_urls"), user_id)
    item = ItemCreate(**item_data)
    data = item.model_dump()
    data["id"] = str(uuid.uuid4())
    data["user_id"] = user_id
    # Only auto-generate when the user left the SKU blank — this used to overwrite
    # unconditionally, so a SKU typed in the import form was always discarded.
    if not data.get("sku"):
        data["sku"] = f"IMP-{data['id'][:8].upper()}"
    created = (await naast_de_lus(lambda: db.table("items").insert(data).execute())).data[0]

    listed_at = cand.get("platform_listed_at") or datetime.now(timezone.utc).isoformat()
    (await naast_de_lus(lambda: db.table("listings").insert({
        "item_id": created["id"],
        "platform": cand["platform"],
        "platform_listing_id": cand["platform_listing_id"],
        "platform_listing_url": cand["platform_listing_url"],
        "status": _listing_status_for(cand),
        "listed_at": listed_at,
    }).execute()))

    (await naast_de_lus(lambda: db.table("import_candidates").update({"status": "imported"}).eq("id", candidate_id).execute()))
    return {"item": created}


@router.post("/bulk-import")
async def bulk_import_candidates(body: dict = None, user_id: str = Depends(require_active_subscription)):
    """
    Process every pending import candidate in one go: candidates with a high-confidence
    suggested_item_id get linked to that item, everything else becomes a new item
    (title/price/photo straight from the scrape, condition defaults to 'good' since
    scraping can't see purchase price/brand/size — those stay editable on the item after).

    One exception: a candidate that looks like the same physical object as an item
    already imported from ANOTHER channel is left alone (still `pending`) and
    reported as `parked`. Auto-merging could destroy an item, auto-creating would
    silently duplicate it — so those few rows go back to the seller to confirm.
    The caller walks past them with the returned `next_offset`.
    """
    db = get_db()
    body = body or {}
    platform = body.get("platform")
    # Eén staat voor de hele lading. Alleen gebruikt waar het platform zelf niets
    # meegaf; wat wél bekend is blijft leidend.
    standaard_staat = body.get("default_condition")
    if standaard_staat not in ("new_with_tags", "new", "good", "fair", "poor"):
        standaard_staat = None

    # Process in bounded batches so a single request can never run long enough for the
    # reverse proxy / gateway to time out and hand the browser an HTML error page (which
    # then surfaced as the cryptic "Unexpected token '<' … is not valid JSON"). The
    # frontend loops, calling this until `remaining` hits 0.
    try:
        batch = int(body.get("limit") or 25)
    except (TypeError, ValueError):
        batch = 25
    batch = max(1, min(batch, 100))
    try:
        offset = max(0, int(body.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0

    import asyncio

    # The Supabase client is SYNCHRONOUS, and this endpoint is async — so every
    # .execute() below ran directly on the event loop and froze the whole server
    # for the duration. Importing a few hundred listings means hundreds of
    # sequential round-trips, which is why the dashboard started returning 502/524
    # to everyone (including this very import) while a bulk run was going.
    # Everything that touches the database therefore runs in a worker thread.
    def _read():
        # One channel per pass. A seller who scanned Vinted AND Marktplaats before
        # importing has both sets pending, and neither exists as an item yet — so a
        # mixed batch could create the same object twice before duplicate detection
        # ever had something to compare against. Finishing one channel first means
        # the second channel is always matched against real inventory.
        q = db.table("import_candidates").select("*").eq("user_id", user_id).eq("status", "pending")
        if platform:
            q = q.eq("platform", platform)
        # Ordered by platform first, so the queue is walked one channel at a time
        # with a single stable offset. A batch that straddles two channels is cut
        # back to the first one; the next pass picks up from the boundary.
        cands = (q.order("platform").order("created_at")
                  .range(offset, offset + batch - 1).execute().data or [])
        if cands:
            head = cands[0].get("platform")
            cands = [c for c in cands if c.get("platform") == head]
        its = fetch_all(lambda: db.table("items").select("id,title,price,brand").eq("user_id", user_id))
        by_id, by_platform = _listing_index(db, its)
        return cands, its, by_id, by_platform

    candidates, items, listings_by_id, platforms_by_item = await asyncio.to_thread(_read)

    # Work out up front which rows must NOT be processed automatically, and drop
    # them from this pass entirely.
    unmatched = [c for c in candidates
                 if not _match_candidate(c, items, listings_by_id)[0]]
    twins = await _find_twins(unmatched, items, platforms_by_item)
    parked = len(twins)
    if twins:
        candidates = [c for c in candidates if c["id"] not in twins]

    linked, created, failed = 0, 0, 0
    now = datetime.now(timezone.utc).isoformat()

    # Classify every candidate up front and in parallel — one sequential Haiku
    # call per candidate inside the loop would stall a bulk import of 50 items
    # for minutes. Each entry falls back to keywords on its own failure.
    inferred_by_id = dict(zip(
        (c["id"] for c in candidates),
        await asyncio.gather(*(
            _infer_attributes_smart(c.get("title"), c.get("description"), c.get("brand"))
            for c in candidates
        )),
    )) if candidates else {}

    # Mirror every candidate's photos into our own bucket BEFORE the (synchronous)
    # processing loop, which runs in a worker thread and can't await. Writing the
    # result back onto the candidate means both paths below — creating a new item
    # and backfilling an existing one — store our urls instead of the source CDN's.
    if candidates:
        from backend.services.photo_mirror import mirror_photos_bulk
        mirrored = await mirror_photos_bulk(
            [_photos_from_candidate(c) for c in candidates], user_id
        )
        for cand, photos in zip(candidates, mirrored):
            if photos:
                cand["photo_urls"] = photos

    def _process():
        nonlocal linked, created, failed
        # Harde tijdgrens. Elke kandidaat kost hier een handvol losse
        # database-aanroepen, en bij een verkoper met duizenden advertenties
        # tikt dat op tot voorbij de tijd die de gateway een verzoek gunt — dan
        # kreeg de browser een foutpagina in plaats van antwoord, halveerde de
        # lading en kroop de import door op één advertentie per aanroep.
        # Wat niet meer past blijft gewoon 'pending' en gaat mee met de
        # volgende ronde; er gaat niets verloren.
        import time as _time
        deadline = _time.monotonic() + 20
        for cand in candidates:
            if _time.monotonic() > deadline:
                break
            try:
                listed_at = cand.get("platform_listed_at") or now
                match_id, reden = _match_candidate(cand, items, listings_by_id)
                # Alleen een titelmatch kan hiernaast zitten; hetzelfde
                # advertentienummer is per definitie dezelfde advertentie.
                if match_id and reden == "same_title" and _tweede_advertentie(
                        db, match_id, cand["platform"], cand.get("platform_listing_id")):
                    match_id = None
                if match_id:
                    existing = db.table("listings").select("id").eq("item_id", match_id).eq("platform", cand["platform"]).execute()
                    if existing.data:
                        db.table("listings").update({
                            "platform_listing_id": cand["platform_listing_id"],
                            "platform_listing_url": cand["platform_listing_url"],
                            "status": _listing_status_for(cand),
                            "listed_at": listed_at,
                        }).eq("id", existing.data[0]["id"]).execute()
                    else:
                        db.table("listings").insert({
                            "item_id": match_id,
                            "platform": cand["platform"],
                            "platform_listing_id": cand["platform_listing_id"],
                            "platform_listing_url": cand["platform_listing_url"],
                            "status": _listing_status_for(cand),
                            "listed_at": listed_at,
                        }).execute()
                    _backfill_item_from_candidate(db, match_id, cand, inferred=inferred_by_id.get(cand["id"]))
                    db.table("import_candidates").update({"status": "linked"}).eq("id", cand["id"]).execute()
                    linked += 1
                else:
                    item_data = _item_data_from_candidate(
                        cand,
                        {"_default_condition": standaard_staat} if standaard_staat else None,
                        inferred=inferred_by_id.get(cand["id"]),
                    )
                    item = ItemCreate(**item_data)
                    data = item.model_dump()
                    data["id"] = str(uuid.uuid4())
                    data["user_id"] = user_id
                    if not data.get("sku"):
                        data["sku"] = f"IMP-{data['id'][:8].upper()}"
                    created_item = db.table("items").insert(data).execute().data[0]

                    db.table("listings").insert({
                        "item_id": created_item["id"],
                        "platform": cand["platform"],
                        "platform_listing_id": cand["platform_listing_id"],
                        "platform_listing_url": cand["platform_listing_url"],
                        "status": _listing_status_for(cand),
                        "listed_at": listed_at,
                    }).execute()

                    db.table("import_candidates").update({"status": "imported"}).eq("id", cand["id"]).execute()
                    items.append({"id": created_item["id"], "title": created_item["title"]})
                    created += 1
            except Exception:
                # Mark it failed so it drops out of the pending set — otherwise the batched
                # loop would re-fetch the same broken candidate every pass and never finish.
                try:
                    db.table("import_candidates").update({"status": "failed"}).eq("id", cand["id"]).execute()
                except Exception:
                    pass
                failed += 1

        remaining_q = db.table("import_candidates").select("id", count="exact").eq("user_id", user_id).eq("status", "pending")
        if platform:
            remaining_q = remaining_q.eq("platform", platform)
        return remaining_q.execute().count or 0

    remaining = await asyncio.to_thread(_process)

    # Parked rows stay pending, so the next pass must start past them or it would
    # fetch the same rows forever and never reach the rest of the queue.
    return {
        "linked": linked, "created": created, "failed": failed,
        "parked": parked, "remaining": remaining,   # remaining still counts parked rows
        "next_offset": offset + parked,
    }


@router.post("/{candidate_id}/ignore")
def ignore_candidate(candidate_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    db.table("import_candidates").update({"status": "ignored"}).eq("id", candidate_id).eq("user_id", user_id).execute()
    return {"ok": True}
