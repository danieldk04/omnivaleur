"""
Etsy v3 API integration.
Requires ETSY_API_KEYSTRING + ETSY_SHARED_SECRET env vars and an OAuth2 user token.
"""
from __future__ import annotations
import asyncio
import base64
import re
import hashlib
import hmac
import logging
import os
import time
from datetime import datetime, timedelta, timezone
import httpx
from backend.platforms.base import PlatformBase

logger = logging.getLogger(__name__)

ETSY_BASE = "https://openapi.etsy.com/v3"
ETSY_SCOPES = "listings_r listings_w listings_d transactions_r shops_r shops_w"
STATE_GELDIG_SECONDEN = 15 * 60


def _keystring() -> str:
    # Eerst de nieuwe naam, daarna de oude variabele uit de eerste opzet.
    from backend.config import settings
    return settings.etsy_api_keystring or os.getenv("ETSY_CLIENT_ID", "")


def _api_key() -> str:
    """Etsy verwacht in x-api-key 'keystring:shared_secret' (OpenAPI-spec 2026)."""
    ks, sec = _keystring(), _secret()
    return f"{ks}:{sec}" if ks and sec else ks


def _secret() -> str:
    from backend.config import settings
    return settings.etsy_shared_secret


def _redirect_uri() -> str:
    from backend.config import settings
    return os.getenv("ETSY_REDIRECT_URI") or settings.etsy_redirect_uri


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def maak_state(user_id: str, nu: int | None = None) -> str:
    """Ondertekende state: user_id.tijd.handtekening. Geen opslag nodig tussen
    het starten en de terugkeer van Etsy."""
    sleutel = _secret()
    if not sleutel:
        raise RuntimeError("Etsy is not configured on this server (ETSY_SHARED_SECRET missing)")
    t = str(int(nu if nu is not None else time.time()))
    basis = f"{user_id}.{t}"
    sig = _b64(hmac.new(sleutel.encode(), basis.encode(), hashlib.sha256).digest())
    return f"{basis}.{sig}"


def lees_state(state: str, nu: int | None = None) -> str:
    """Geeft de user_id terug of gooit ValueError bij een vervalste of oude state."""
    sleutel = _secret()
    if not sleutel:
        raise ValueError("Etsy is not configured")
    try:
        user_id, t, sig = state.rsplit(".", 2)
        verwacht = _b64(hmac.new(sleutel.encode(), f"{user_id}.{t}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, verwacht):
            raise ValueError("bad signature")
        leeftijd = (nu if nu is not None else time.time()) - int(t)
    except (ValueError, TypeError) as e:
        raise ValueError("invalid state") from e
    if leeftijd < 0 or leeftijd > STATE_GELDIG_SECONDEN:
        raise ValueError("state expired")
    return user_id


def _verifier(state: str) -> str:
    # 43 tekens, afgeleid van de state: zo hoeft er niets bewaard te worden.
    return _b64(hmac.new(_secret().encode(), ("v:" + state).encode(), hashlib.sha256).digest())


def _met_verloop(data: dict) -> dict:
    verloopt = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3600)) - 60)
    return {**data, "token_expires_at": verloopt.isoformat()}


def etsy_titel(titel: str) -> str:
    """Etsy weigert een titel die niet met een letter of cijfer begint (live gemeten
    25-11-2026: "(1029) White Ralph Lauren..." gaf 400). Het artikelnummer tussen
    haakjes vooraan gaat eraf, daarna alle tekens voor de eerste letter of het cijfer."""
    t = re.sub(r"^\s*\(\s*\d+\s*\)\s*", "", titel or "")
    t = re.sub(r"^[^0-9A-Za-zÀ-ÿ]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 140:
        t = t[:140].rsplit(" ", 1)[0] if " " in t[:140] else t[:140]
    return t


def _etsy_fout(r) -> str:
    """Leesbare melding uit een Etsy-foutantwoord."""
    try:
        data = r.json()
        if isinstance(data, list):
            delen = [f"{d.get('path', '').replace(chr(92) + '/', '/')}: {d.get('message', '')}" for d in data]
            return "; ".join(delen)
        if isinstance(data, dict) and data.get("error"):
            return str(data["error"])
    except Exception:  # noqa: BLE001
        pass
    return (r.text or "")[:300]


def vintage_when_made(year) -> str:
    """Etsy: vintage = 20+ jaar oud. Jonger dan dat gaat niet naar Etsy."""
    try:
        jaar = int(year)
    except (TypeError, ValueError):
        raise ValueError("Etsy needs the item's year to prove it is vintage (20+ years old)")
    if jaar > datetime.now(timezone.utc).year - 20:
        raise ValueError("Etsy only allows vintage items (20+ years old)")
    if jaar >= 2000:
        return "2000_2006"
    if jaar >= 1900:
        return f"{jaar // 10 * 10}s"
    return "1800s" if jaar >= 1800 else "before_1700" if jaar < 1700 else "1700s"


_JAAR = re.compile(r"(?<!\d)(19\d{2}|200[0-6])(?!\d)")
_DECENNIUM = re.compile(r"(?<!\d)(?:19)?([2-9]0)['’]?s\b|jaren\s*(?:19)?([2-9]0)\b", re.I)


def jaar_uit_item(item: dict):
    """Het bouwjaar waarmee de verkoper laat zien dat het artikel vintage is.

    Eerst een uitdrukkelijk veld (year), daarna een jaartal of decennium in titel of
    omschrijving ("vintage 1992", "80s", "jaren 70"). Niets gevonden: None, en dan
    plaatsen we niet op Etsy: een geraden jaar maakt van tweedehands geen vintage."""
    for sleutel in ("vintage_year", "year"):
        if item.get(sleutel):
            return item[sleutel]
    tekst = f"{item.get('title') or ''} {item.get('description') or ''}"
    m = _JAAR.search(tekst)
    if m:
        return int(m.group(1))
    m = _DECENNIUM.search(tekst)
    if m:
        d = int(m.group(1) or m.group(2))
        return 1900 + d + 5
    return None


_taxonomie_cache: dict = {"tot": 0.0, "bladeren": []}


def _bladeren(knopen: list, pad: tuple = ()) -> list:
    uit = []
    for k in knopen:
        naam = (k.get("name") or "")
        nieuw = pad + (naam,)
        kinderen = k.get("children") or []
        if kinderen:
            uit += _bladeren(kinderen, nieuw)
        else:
            uit.append((k["id"], nieuw))
    return uit


def _woorden(tekst: str) -> set:
    uit = set()
    for w in re.findall(r"[a-zà-ÿ]+", (tekst or "").lower()):
        if len(w) > 2:
            if w.endswith(("ches", "shes", "xes")):
                uit.add(w[:-2])          # brooches -> brooch
            else:
                uit.add(w[:-1] if w.endswith("s") and len(w) > 3 else w)
    return uit


# Nederlandse en Engelse woorden naar de woorden die Etsy zelf gebruikt.
_SYNONIEM = {"vest": "cardigan", "trui": "sweater", "jas": "jacket", "jack": "jacket",
             "broek": "pant", "rok": "skirt", "jurk": "dress", "overhemd": "shirt",
             "heren": "men", "dames": "women", "dame": "women", "man": "men", "vrouw": "women",
             "hoodie": "sweatshirt", "gilet": "vest", "tas": "bag", "schoen": "shoe",
             "armband": "bracelet", "armbanden": "bracelet", "ketting": "necklace", "collier": "necklace",
             "oorbel": "earring", "oorbellen": "earring", "oorbel": "earring", "broche": "brooch",
             "hanger": "pendant", "horloge": "watch", "ringen": "ring", "manchetknoop": "cufflink",
             "kralenarmband": "bracelet", "kralenketting": "necklace", "slavenarmband": "bangle", "cocktailring": "statement"}
# Woorden die zeggen dat het om kralen gaat: dan hoort "Beaded ..." bij de keuze.
_KRALEN = re.compile(r"(kraal|kralen|bead|koraal|coral)", re.I)


def kies_taxonomie(bladeren: list, item: dict):
    """Kiest het Etsy-blad dat het best bij categorie, titel en doelgroep past, of None."""
    vraag = _woorden(f"{item.get('category') or ''} {item.get('title') or ''} {item.get('gender') or ''}")
    # Een kralenarmband zit onder "Beaded Bracelets"; "kraal" in titel, materiaal of
    # categorie is genoeg om dat blad voor te trekken.
    kralen = bool(_KRALEN.search(f"{item.get('title') or ''} {item.get('material') or ''} {item.get('category') or ''} {(item.get('description') or '')[:500]}"))
    vraag |= {_SYNONIEM[w] for w in list(vraag) if w in _SYNONIEM}
    if kralen:
        vraag.add("beaded")
    if not vraag:
        return None
    # Alleen om gelijke scores uit elkaar te halen: komt een woord uit de omschrijving
    # ("statement", "stud", "chain") in het pad voor, dan wint dat blad.
    tekst_w = _woorden(f"{item.get('title') or ''} {(item.get('description') or '')[:600]}")
    beste, beste_score = None, 0.0
    for tid, pad in bladeren:
        # "Craft Supplies & Tools" (onder andere "Bracelet Blanks" = blanco armbanden)
        # is voor wie knutselt; een afgewerkt sieraad hoort daar nooit.
        if pad and pad[0].lower().startswith("craft supplies") and not item.get("is_supply"):
            continue
        naam_w = _woorden(pad[-1])
        pad_w = _woorden(" ".join(pad[:-1]))
        if not naam_w:
            continue
        hit_naam = len(vraag & naam_w)
        if hit_naam == 0:
            continue
        score = hit_naam / len(naam_w) * 2 + len(vraag & pad_w) * 0.5
        score += min(len((tekst_w - vraag) & (naam_w | pad_w)), 3) * 0.05
        if score > beste_score:
            beste, beste_score = tid, score
    return beste


_TYPE_STAMMEN = (  # (woorden in titel/categorie, stam in de sectienaam van de verkoper)
    (("bracelet", "armband", "bangle"), "armband"),
    (("necklace", "ketting", "collier", "choker"), ("ketting", "collier")),
    (("earring", "oorbel", "oorbellen"), "oorbel"),
    (("brooch", "broche"), "broche"),
    (("pendant", "hanger"), "hanger"),
    (("ring", "ringen"), "ring"),
)


def eigen_artikelnummer(item: dict, user_id) -> str | None:
    """Het artikelnummer van de verkoper zelf (Mieneke, 27-11-2026: Etsy toonde
    REV-6A626740, haar nummer is 24-027.12). Een stuk dat via Herplaatsen een kopie
    is, krijgt een eigen REV-nummer; het origineel met dezelfde titel en foto's
    draagt het echte nummer. Is er precies één zo'n nummer, dan gebruiken we dat."""
    sku = str(item.get("sku") or "").strip()
    if not sku or not (sku.upper().startswith("REV-") or sku.upper().startswith("IMP-")):
        return sku or None
    try:
        from backend.database import get_db
        if not (user_id and item.get("title")):
            return sku
        rijen = (get_db().table("items").select("id,sku,photo_urls").eq("user_id", user_id)
                 .eq("title", item["title"]).limit(50).execute().data or [])
        fotos = set(u for u in (item.get("photo_urls") or []) if u)
        nummers = {str(r["sku"]).strip() for r in rijen
                   if r.get("sku") and r.get("id") != item.get("id")
                   and not str(r["sku"]).upper().startswith(("REV-", "IMP-"))
                   and set(u for u in (r.get("photo_urls") or []) if u) == fotos}
        if len(nummers) == 1:
            return nummers.pop()[:32]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Eigen artikelnummer niet gevonden: {e}")
    return sku


# ---------------------------------------------------------------------------
# Eigenschappen (Etsy "attributes": materiaal, goudgehalte, edelsteen, lengte, ...)
# Mieneke, 27-11-2026: alle "aanbevolen" opties waren goed en moesten vanzelf. Bewust
# zonder model: alleen wat letterlijk uit titel, omschrijving, materiaal en jaar blijkt,
# gekozen uit de lijst die Etsy zelf bij de categorie geeft. Staat het er niet, dan leeg.
# ---------------------------------------------------------------------------
_NL_STEEN = {
    "koraal": "Coral", "granaat": "Garnet", "parel": "Pearl", "diamant": "Diamond",
    "saffier": "Sapphire", "robijn": "Ruby", "smaragd": "Emerald", "amethist": "Amethyst",
    "turkoois": "Turquoise", "barnsteen": "Amber", "opaal": "Opal", "peridoot": "Peridot",
    "topaas": "Topaz", "aquamarijn": "Aquamarine", "citrien": "Citrine", "maansteen": "Moonstone",
    "lapis": "Lapis lazuli", "tijgeroog": "Tiger's eye", "agaat": "Agate", "jaspis": "Jasper",
    "toermalijn": "Tourmaline", "markasiet": "Marcasite", "onyx": "Onyx", "jade": "Jade",
    "carneool": "Carnelian", "bergkristal": "Quartz", "rozenkwarts": "Rose quartz",
    "malachiet": "Malachite", "granaten": "Garnet", "zirkonia": "Cubic zirconia",
}
_STEEN_KLEUR = {"Garnet": "Red", "Ruby": "Red", "Sapphire": "Blue", "Emerald": "Green",
                "Amethyst": "Purple", "Turquoise": "Blue", "Peridot": "Green",
                "Citrine": "Yellow", "Onyx": "Black"}
_NEP = re.compile(r"(imitatie|nep\b|glas|kunststof|plastic|synthet|faux|lab[- ]?grown|gekweekt|bakeliet)", re.I)


def _norm_waarde(tekst: str) -> str:
    return re.sub(r"[^a-z0-9' ]", "", (tekst or "").lower()).strip()


def kies_eigenschappen(eigenschappen: list, item: dict) -> list:
    """Geeft [{property_id, value_ids, values, scale_id}] voor de eigenschappen die
    uit het artikel blijken. `eigenschappen` = Etsy seller-taxonomy .../properties."""
    tekst = " ".join(str(item.get(k) or "") for k in ("title", "material", "description", "category")).lower()
    titel = str(item.get("title") or "")
    per_naam = {p.get("name"): p for p in eigenschappen if p.get("supports_attributes")}

    def waarde(naam, gewenst):
        p = per_naam.get(naam)
        if not p:
            return None
        for v in p.get("possible_values") or []:
            if _norm_waarde(v["name"]) == _norm_waarde(gewenst):
                return p, v
        return None

    uit: dict = {}

    def zet(naam, gewenst_lijst):
        gevonden = [waarde(naam, g) for g in gewenst_lijst]
        gevonden = [g for g in gevonden if g]
        if not gevonden:
            return
        p = gevonden[0][0]
        if not p.get("is_multivalued"):
            gevonden = gevonden[:1]
        elif p.get("max_values_allowed"):
            gevonden = gevonden[: int(p["max_values_allowed"])]
        uit[p["property_id"]] = {"property_id": p["property_id"],
                                 "value_ids": [v["value_id"] for _, v in gevonden],
                                 "values": [v["name"] for _, v in gevonden], "scale_id": None}

    # Stenen
    stenen: list = []
    if not _NEP.search(tekst):
        pos = []
        for nl, en in _NL_STEEN.items():
            for m in re.finditer(r"(?<![a-z])(?:[a-z]*?)" + nl + r"(?!moer)", tekst):
                if nl == "parel" and "parelmoer" in tekst[m.start():m.end() + 5]:
                    continue
                pos.append((m.start(), en))
        namen = {_norm_waarde(v["name"]): v["name"]
                 for v in (per_naam.get("Gemstone type") or {}).get("possible_values", []) if len(v["name"]) >= 4}
        for n, orig in namen.items():
            for m in re.finditer(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", tekst):
                pos.append((m.start(), orig))
        for _, en in sorted(pos):
            if en not in stenen and waarde("Gemstone type", en):
                stenen.append(en)
    if len(stenen) == 1:
        zet("Gemstone type", stenen)
        kleur = _STEEN_KLEUR.get(stenen[0])
        if re.search(r"roze|pink|zalm|salmon|engelenhuid|angel skin", tekst):
            kleur = None  # roze koraal is niet rood; liever leeg dan fout
        elif stenen[0] == "Coral" and re.search(r"bloed|\brood|\brode|\bred\b", tekst):
            kleur = "Red"
        if kleur:
            zet("Gem color", [kleur])
        if not re.search(r"\bgekweekt|lab", tekst):
            zet("Stone source", ["Natural"])

    # Goud en zilver
    metalen: list = []
    goud = re.search(r"(?<![a-z])(goud|gouden|geelgoud|geelgouden|witgoud|witgouden|roodgoud|roségoud|gold)(?![a-z])", tekst) \
        or re.search(r"[a-z]*goud", tekst)
    verguld = re.search(r"verguld|vergulde|gold[- ]?plated|doublé|goudkleurig|gold tone", tekst)
    if goud:
        # Gewoon "Gold" ook bij geelgoud: dat koos Mieneke zelf (Etsy: Aanbevolen Goud).
        if re.search(r"witgoud|white gold", tekst):
            metalen.append("White gold")
        elif re.search(r"roségoud|rosegoud|roodgoud|rose gold", tekst):
            metalen.append("Rose gold")
        else:
            metalen.append("Gold")
    if re.search(r"(?<![a-z])(zilver|zilveren|silver|925)(?![a-z])", tekst):
        metalen.append("Sterling silver" if re.search(r"925|sterling", tekst) else "Silver")
    zet("Material multi", [m for m in metalen if waarde("Material multi", m)] + [s for s in stenen if waarde("Material multi", s)])

    if goud and not verguld:
        karaat = None
        m = re.search(r"(\d{1,2})\s?(?:k\b|kt\b|karaat|carat|krt)", tekst)
        if m:
            karaat = f"{int(m.group(1))}k"
        else:
            m = re.search(r"(?<!\d)(333|375|417|585|750|916|999)(?!\d)", tekst)
            if m:
                karaat = {"333": "8k", "375": "9k", "417": "10k", "585": "14k", "750": "18k",
                          "916": "22k", "999": "24k"}[m.group(1)]
        if karaat and waarde("Gold purity", karaat):
            zet("Gold purity", [karaat])
            zet("Gold solidity", ["Solid gold"])
        elif re.search(r"massief|solid gold", tekst):
            zet("Gold solidity", ["Solid gold"])

    # Maat: lengte van een armband of ketting, alleen als die er letterlijk staat.
    pl = per_naam.get("Length")
    if pl:
        m = re.search(r"(?<![\d.,])(\d{1,3}(?:[.,]\d)?)\s?cm\b", titel.lower())
        if not m:
            m = re.search(r"(?:lengte|length|lang)\D{0,12}(\d{1,3}(?:[.,]\d)?)\s?cm\b", tekst) \
                or re.search(r"(?<![\d.,])(\d{1,3}(?:[.,]\d)?)\s?cm\b\s*(?:lang|long|lengte)", tekst)
        sc = next((x["scale_id"] for x in pl.get("scales") or [] if x.get("display_name") == "Centimeters"), None)
        if m and sc:
            uit[pl["property_id"]] = {"property_id": pl["property_id"], "value_ids": [],
                                      "values": [m.group(1).replace(",", ".")], "scale_id": sc}

    # Verstelbaar: standaard Nee (Mieneke), Ja alleen als het er staat.
    zet("Adjustable", ["Yes" if re.search(r"verstelbaar|adjustable", tekst) else "No"])

    # Kraalvorm
    if per_naam.get("Shape") and re.search(r"kraal|kralen|bead", tekst):
        if re.search(r"tonnetje|barrel", tekst):
            zet("Shape", ["Barrel"])
        elif re.search(r"druppel|teardrop", tekst):
            zet("Shape", ["Teardrop"])
        elif re.search(r"kaasje|kaasjes|rondel|facet|ovaal|oval|vierkant|square|disc|schijf", tekst):
            pass
        else:
            zet("Shape", ["Round"])

    # Stijl uit het jaar of de omschrijving
    stijl = None
    for woord, naam in (("art nouveau|jugendstil", "Art nouveau"), ("art deco", "Art deco"),
                        ("victoriaans|victorian", "Victorian"), ("edwardian|edwardiaans", "Edwardian"),
                        ("mid-century|midcentury|mid century", "Mid-century")):
        if re.search(woord, tekst):
            stijl = naam
            break
    if not stijl:
        jaar = jaar_uit_item(item)
        if jaar:
            stijl = ("Victorian" if 1837 <= jaar <= 1900 else "Edwardian" if 1901 <= jaar <= 1915 else
                     "Art deco" if 1920 <= jaar <= 1939 else "Mid-century" if 1945 <= jaar <= 1969 else None)
    if stijl:
        zet("Jewelry style", [stijl])

    # Ontvanger (alleen als de categorie die kent)
    if per_naam.get("Recipient"):
        man = re.search(r"\bheren\b|\bmannen|\bmen'?s\b|\bheer\b", tekst)
        vrouw = re.search(r"\bdames|\bvrouw|\bwomen|\bladies|\bmeisje", tekst)
        kind = re.search(r"\bkinder|\bkids?\b|\bbaby|\bmeisjes?\b|\bjongens", titel.lower()) \
            or (re.search(r"\bkinder|\bkids?\b|\bbaby|\bmeisjes?\b|\bjongens", tekst) and not (man or vrouw))
        if kind:
            zet("Recipient", ["Girls" if re.search(r"meisje", tekst) else "Unisex kids"])
        elif man and vrouw:
            zet("Recipient", ["Unisex adults"])
        elif man:
            zet("Recipient", ["Men"])
        else:
            zet("Recipient", ["Women"])
    return list(uit.values())


def kies_sectie(secties: list, item: dict, jaar) -> int | None:
    """Het winkelsectie-id waar dit artikel in hoort, of None.

    Mieneke (Voordeelsieraden) heeft secties als "Antieke Armbanden" en "Vintage
    Armbanden". We zoeken de sectie met de soort sieraad EN de leeftijdswoord
    (antiek = 100+ jaar, anders vintage). Geen duidelijke match: geen sectie; een
    verkeerde sectie is erger dan geen."""
    tekst = f"{item.get('category') or ''} {item.get('title') or ''}".lower()
    woorden = set(re.findall(r"[a-zà-ÿ]+", tekst))
    stammen = None
    for sleutels, stam in _TYPE_STAMMEN:
        if any(x.startswith(sl) for x in woorden for sl in sleutels):
            stammen = (stam,) if isinstance(stam, str) else stam
            break
    if not stammen:
        return None
    try:
        antiek = int(jaar) <= datetime.now(timezone.utc).year - 100
    except (TypeError, ValueError):
        antiek = False
    era = "antiek" if antiek else "vintage"
    for sec in secties or []:
        titel = (sec.get("title") or "").lower()
        if era in titel and any(st in titel for st in stammen):
            return int(sec["shop_section_id"])
    return None


def _etsy_woorden(lijst, maximaal: int, lengte: int, koppelteken: bool = True) -> list:
    """Tags/materialen zoals Etsy ze accepteert: letters, cijfers, spatie, koppelteken;
    maximaal `lengte` tekens, geen dubbelen."""
    uit, gezien = [], set()
    for t in lijst or []:
        # Tags mogen een koppelteken hebben, materialen alleen letters, cijfers en spaties
        # (Etsy-spec, 26-11-2026).
        t = re.sub(r"[^0-9A-Za-zÀ-ÿ \-]" if koppelteken else r"[^0-9A-Za-zÀ-ÿ ]", " " if not koppelteken else "", str(t)).strip().lower()
        t = re.sub(r"\s+", " ", t)
        if not t or len(t) > lengte or t in gezien:
            continue
        gezien.add(t)
        uit.append(t)
        if len(uit) >= maximaal:
            break
    return uit


def _basis_velden(item: dict, talen: list) -> dict:
    """Vangnet zonder taalmodel: tags, materialen en alt-tekst uit de artikelvelden."""
    ruw = [item.get("brand"), item.get("category"), item.get("color"), "vintage", "antique"]
    ruw += [w for w in re.findall(r"[A-Za-zÀ-ÿ]{4,}", item.get("title") or "")
            if w.lower() not in ("with", "from", "carat", "karaat", "voor", "met", "van")]
    ruw = [r for r in ruw if r]
    mats = [m for m in re.split(r"[,/;]", item.get("material") or "") if m.strip()]
    titel = etsy_titel(item.get("title") or "")
    return {
        "tags": {t: _etsy_woorden(ruw + mats, 13, 20) for t in talen},
        "materials": _etsy_woorden(mats, 13, 45, koppelteken=False),
        "alt_text": {t: titel[:500] for t in talen},
    }


def genereer_etsy_velden(item: dict, talen: list) -> dict:
    """Tags (13), materialen en alt-tekst per taal, met één klein modelverzoek.
    Lukt dat niet, dan de eenvoudige velden uit het artikel zelf."""
    basis = _basis_velden(item, talen)
    try:
        import json
        from backend.services.crosslist import _claude_client, VERTAAL_MODEL
        opdracht = (
            "You write Etsy search fields for ONE vintage/antique item. Use only facts in the data.\n"
            f"Languages needed: {', '.join(talen)} (ISO codes).\n"
            "Return ONLY JSON: {\"tags\": {<lang>: [13 tags]}, \"materials\": [up to 6 materials in the "
            f"FIRST language ({talen[0]})], \"alt_text\": {{<lang>: \"one factual sentence describing the main photo, "
            "max 300 chars\"}}}.\n"
            "Tags: exactly 13 per language, each max 20 characters, letters/digits/spaces only, lowercase, "
            "buyer search phrases (type of jewelry, material, style, era like vintage or antique, occasion/gift, "
            "colour). No brand-less guessing of facts that are not given.\n\n"
            f"Title: {item.get('title')}\nCategory: {item.get('category')}\nBrand: {item.get('brand')}\n"
            f"Material: {item.get('material')}\nColor: {item.get('color')}\n"
            f"Description: {(item.get('description') or '')[:1500]}")
        r = _claude_client().messages.create(model=VERTAAL_MODEL, max_tokens=2000,
                                             messages=[{"role": "user", "content": opdracht}])
        tekst = "".join(b.text for b in r.content if b.type == "text")
        data = json.loads(tekst[tekst.index("{"): tekst.rindex("}") + 1])
        for t in talen:
            tags = _etsy_woorden((data.get("tags") or {}).get(t), 13, 20)
            if tags:
                basis["tags"][t] = tags
            alt = ((data.get("alt_text") or {}).get(t) or "").strip()
            if alt:
                basis["alt_text"][t] = alt[:500]
        mats = _etsy_woorden(data.get("materials"), 13, 45, koppelteken=False)
        if mats:
            basis["materials"] = mats
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Etsy-velden via model mislukt, eenvoudige velden gebruikt: {e}")
    return basis


class EtsyPlatform(PlatformBase):
    platform_name = "etsy"

    def _token(self, credentials: dict) -> str:
        return credentials.get("access_token") or (credentials.get("extra_data") or {}).get("access_token", "")

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "x-api-key": _api_key(),
            "Content-Type": "application/json",
        }

    def get_authorization_url(self, user_id: str) -> str:
        """OAuth 2.0 met PKCE S256. Etsy weigert de methode 'plain'."""
        from urllib.parse import urlencode
        if not _keystring():
            raise RuntimeError("Etsy is not configured on this server (ETSY_API_KEYSTRING missing)")
        state = maak_state(user_id)
        challenge = _b64(hashlib.sha256(_verifier(state).encode()).digest())
        params = {
            "response_type": "code",
            "client_id": _keystring(),
            "redirect_uri": _redirect_uri(),
            "scope": ETSY_SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"https://www.etsy.com/oauth/connect?{urlencode(params)}"

    async def exchange_code(self, code: str, state: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.etsy.com/v3/public/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": _keystring(),
                    "redirect_uri": _redirect_uri(),
                    "code": code,
                    "code_verifier": _verifier(state),
                },
            )
            r.raise_for_status()
            return _met_verloop(r.json())

    async def refresh_credentials(self, credentials: dict) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.etsy.com/v3/public/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": _keystring(),
                    "refresh_token": credentials.get("refresh_token"),
                },
            )
            r.raise_for_status()
            data = _met_verloop(r.json())
            return {**credentials, "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token") or credentials.get("refresh_token"),
                    "token_expires_at": data["token_expires_at"]}

    async def _vers(self, credentials: dict) -> dict:
        """Geeft inloggegevens met een geldig access token (1 uur) en bewaart het
        verse token in de database. Zonder koppeling: duidelijke fout."""
        if not self._token(credentials):
            raise RuntimeError("Etsy isn't connected")
        if not self.verlopen(credentials):
            return credentials
        nieuw = await self.refresh_credentials(credentials)
        uid = credentials.get("user_id")
        if uid:
            try:
                from backend.database import get_db
                get_db().table("platform_credentials").update({
                    "access_token": nieuw.get("access_token"),
                    "refresh_token": nieuw.get("refresh_token"),
                    "token_expires_at": nieuw.get("token_expires_at"),
                }).eq("user_id", uid).eq("platform", "etsy").execute()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Kon ververste Etsy-token niet opslaan: {e}")
        return nieuw

    async def taxonomie_voor(self, item: dict):
        if item.get("etsy_taxonomy_id"):
            return int(item["etsy_taxonomy_id"])
        if time.time() > _taxonomie_cache["tot"]:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.get(f"{ETSY_BASE}/application/seller-taxonomy/nodes",
                                headers={"x-api-key": _api_key()})
                r.raise_for_status()
                _taxonomie_cache["bladeren"] = _bladeren(r.json().get("results") or [])
                # Etsy: andere inhoud maximaal 24 uur bewaren (API-voorwaarden §5).
                _taxonomie_cache["tot"] = time.time() + 20 * 3600
        return kies_taxonomie(_taxonomie_cache["bladeren"], item)

    def verlopen(self, credentials: dict) -> bool:
        t = credentials.get("token_expires_at")
        if not t:
            return True
        try:
            return datetime.fromisoformat(str(t)) <= datetime.now(timezone.utc)
        except ValueError:
            return True

    async def _get_shop_id(self, token: str) -> str:
        async with httpx.AsyncClient(timeout=30) as c:
            # user_id staat vooraan in het access token: "<user_id>.<token>"
            user_id = token.split(".")[0]
            r = await c.get(f"{ETSY_BASE}/application/users/{user_id}/shops", headers=self._headers(token))
            r.raise_for_status()
            data = r.json()
            shops = data.get("results") or ([data] if data.get("shop_id") else [])
            if not shops:
                raise RuntimeError("No Etsy shop found for this account")
            return str(shops[0]["shop_id"])

    async def _zorg_voor_profielen(self, c, token: str, shop_id: str, item: dict) -> tuple[int, int]:
        """Geeft (shipping_profile_id, readiness_state_id). Bestaat er geen, dan
        maken we een eenvoudig profiel aan; de verkoper kan het later aanpassen."""
        h = {"Authorization": f"Bearer {token}", "x-api-key": _api_key()}
        r = await c.get(f"{ETSY_BASE}/application/shops/{shop_id}/shipping-profiles", headers=h)
        r.raise_for_status()
        profielen = r.json().get("results") or []
        if profielen:
            verzend = profielen[0]["shipping_profile_id"]
        else:
            if not item.get("origin_postal_code"):
                raise RuntimeError("Your Etsy shop has no shipping profile yet. Create one on Etsy "
                                   "(Shop Manager, Settings, Shipping settings) and try again.")
            r = await c.post(f"{ETSY_BASE}/application/shops/{shop_id}/shipping-profiles", headers=h, data={
                "title": "Omnivaleur standard shipping",
                "origin_country_iso": item.get("origin_country_iso", "NL"),
                "origin_postal_code": item.get("origin_postal_code", ""),
                "primary_cost": float(item.get("shipping_price", 5.0)),
                "secondary_cost": 0.0,
                "destination_region": "eu",
                "min_delivery_days": 2,
                "max_delivery_days": 7,
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Etsy shipping profile failed {r.status_code}: {r.text}")
            verzend = r.json()["shipping_profile_id"]
        r = await c.get(f"{ETSY_BASE}/application/shops/{shop_id}/readiness-state-definitions", headers=h)
        r.raise_for_status()
        klaar = r.json().get("results") or []
        if klaar:
            gereed = klaar[0]["readiness_state_id"]
        else:
            r = await c.post(f"{ETSY_BASE}/application/shops/{shop_id}/readiness-state-definitions", headers=h, data={
                "readiness_state": "ready_to_ship",
                "min_processing_time": 1,
                "max_processing_time": 3,
                "processing_time_unit": "days",
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Etsy readiness state failed {r.status_code}: {r.text}")
            gereed = r.json()["readiness_state_id"]
        return int(verzend), int(gereed)

    async def _retourbeleid(self, c, token: str, shop_id: str) -> int:
        h = {"Authorization": f"Bearer {token}", "x-api-key": _api_key()}
        r = await c.get(f"{ETSY_BASE}/application/shops/{shop_id}/policies/return", headers=h)
        r.raise_for_status()
        bestaand = r.json().get("results") or []
        if bestaand:
            return int(bestaand[0]["return_policy_id"])
        # Vintage: geen retour en geen ruil. De verkoper kan dit op Etsy aanpassen.
        r = await c.post(f"{ETSY_BASE}/application/shops/{shop_id}/policies/return", headers=h,
                         data={"accepts_returns": "false", "accepts_exchanges": "false"})
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Etsy return policy failed {r.status_code}: {r.text}")
        return int(r.json()["return_policy_id"])

    async def create_listing(self, item: dict, credentials: dict) -> dict:
        """Vintage-listing in de winkel van de verkoper. Concept eerst; daarna foto's
        en pas dan actief (dat kost de verkoper de gewone Etsy-plaatsingskosten).
        `_etsy_concept` in het artikel houdt het bij een concept (voor tests)."""
        credentials = await self._vers(credentials)
        when_made = vintage_when_made(jaar_uit_item(item))
        if not (item.get("photo_urls") or item.get("_etsy_concept")):
            raise RuntimeError("Etsy needs at least one photo")
        token = self._token(credentials)
        shop_id = await self._get_shop_id(token)
        taxonomy_id = await self.taxonomie_voor(item)
        if not taxonomy_id:
            raise RuntimeError("Could not match this item to an Etsy category. "
                               "Fill in the category (for example jacket or dress) and try again.")
        item = {**item, **{k: v for k, v in (credentials.get("extra_data") or {}).get("etsy", {}).items()
                           if k not in item}}

        async with httpx.AsyncClient(timeout=60) as c:
            verzend, gereed = await self._zorg_voor_profielen(c, token, shop_id, item)
            headers = {"Authorization": f"Bearer {token}", "x-api-key": _api_key()}
            waarschuwingen: list[str] = []

            # Winkeltalen: de eerste is de standaardtaal van de winkel (Mieneke: Nederlands,
            # met Engels erbij). Titel en omschrijving staan in die taal; de rest als vertaling.
            talen = ["en"]
            ruwe_talen: dict = {}   # "en" -> "en-US": de code zoals Etsy hem in de winkel toont
            try:
                rs = await c.get(f"{ETSY_BASE}/application/shops/{shop_id}", headers=headers)
                if rs.status_code == 200 and rs.json().get("languages"):
                    ruwe_talen = {str(t).split("-")[0].lower(): str(t) for t in rs.json()["languages"]}
                    talen = [str(t).split("-")[0].lower() for t in rs.json()["languages"]]
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Etsy-winkeltalen niet gelezen: {e}")
            teksten = item.get("_etsy_teksten") or {}
            primair = talen[0] if talen[0] in ("nl", "en") else "en"
            tekst = teksten.get(primair) or {"title": item["title"], "description": item.get("description")}
            extra_talen = [t for t in ("en", "nl") if t in talen and t != primair and teksten.get(t)]

            velden = await asyncio.to_thread(genereer_etsy_velden, {**item, **tekst}, [primair] + [t for t in extra_talen])

            secties, sectie_id = [], None
            try:
                rsec = await c.get(f"{ETSY_BASE}/application/shops/{shop_id}/sections", headers=headers)
                if rsec.status_code == 200:
                    secties = rsec.json().get("results") or []
                    sectie_id = kies_sectie(secties, item, jaar_uit_item(item))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Etsy-secties niet gelezen: {e}")

            prijs = float(item.get("price_etsy") or item["price"])
            try:
                pct = float(item.get("price_markup_pct") or 0)
            except (TypeError, ValueError):
                pct = 0.0
            if pct and not item.get("price_etsy"):
                prijs = round(prijs * (1 + pct / 100), 2)

            payload = {
                "title": etsy_titel(tekst["title"]),
                "description": (tekst.get("description") or "")[:65000],
                "price": prijs,
                "quantity": 1,
                "who_made": "someone_else",
                "when_made": when_made,
                "is_supply": "false",
                "taxonomy_id": int(taxonomy_id),
                "shipping_profile_id": verzend,
                "readiness_state_id": gereed,
                "type": "physical",
                "should_auto_renew": "true",
            }
            if velden["tags"].get(primair):
                payload["tags"] = ",".join(velden["tags"][primair])
            if velden["materials"]:
                payload["materials"] = ",".join(velden["materials"])
            if sectie_id:
                payload["shop_section_id"] = sectie_id
            r = await c.post(f"{ETSY_BASE}/application/shops/{shop_id}/listings", data=payload, headers=headers)
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Etsy create listing failed {r.status_code}: {_etsy_fout(r)}")
            listing_id = str(r.json()["listing_id"])
            uitkomst = {
                "platform_listing_id": listing_id,
                "platform_listing_url": f"https://www.etsy.com/listing/{listing_id}",
            }
            etsy_sku = None
            eigenschappen_gezet = {}
            try:
                fouten = 0
                fotos = (item.get("photo_urls") or [])[:10]
                for i, foto in enumerate(fotos):
                    try:
                        # rank = plek in de reeks: zonder staat de laatst geuploade foto vooraan.
                        await self._upload_image(c, shop_id, listing_id, foto, token, rank=i + 1,
                                                 alt_text=(velden["alt_text"].get(primair) if i == 0 else None))
                    except Exception as e:  # noqa: BLE001
                        fouten += 1
                        logger.warning(f"Etsy image upload failed: {e}")
                if item.get("_etsy_concept"):
                    return {**uitkomst, "state": "draft"}
                if fouten == len(fotos):
                    raise RuntimeError("Etsy accepted none of the photos")

                # SKU (artikelnummer): kan alleen via de voorraad van de listing.
                etsy_sku = await asyncio.to_thread(eigen_artikelnummer, item, credentials.get("user_id"))
                if etsy_sku:
                    try:
                        await self._zet_sku(c, headers, listing_id, etsy_sku, prijs, gereed)
                    except Exception as e:  # noqa: BLE001
                        waarschuwingen.append(f"SKU niet gezet: {e}")
                        logger.warning(f"Etsy SKU mislukt: {e}")
                eigenschappen_gezet = await self._zet_eigenschappen(c, headers, shop_id, listing_id, taxonomy_id,
                                                                    item, waarschuwingen)
                # Vertalingen (bij Mieneke de Engelse titel, omschrijving en tags onderaan).
                for taal in extra_talen:
                    gegevens = {"title": etsy_titel(teksten[taal]["title"]),
                                "description": (teksten[taal].get("description") or "")[:65000],
                                **({"tags": ",".join(velden["tags"][taal])} if velden["tags"].get(taal) else {})}
                    fout_t = None
                    # Eerst de korte code ("en"); weigert Etsy die, dan de code van de winkel ("en-US").
                    for code in dict.fromkeys([taal, ruwe_talen.get(taal, taal)]):
                        try:
                            rt = await c.post(
                                f"{ETSY_BASE}/application/shops/{shop_id}/listings/{listing_id}/translations/{code}",
                                headers=headers, data=gegevens)
                            if rt.status_code in (200, 201):
                                fout_t = None
                                break
                            fout_t = f"{rt.status_code}: {_etsy_fout(rt)}"
                        except Exception as e:  # noqa: BLE001
                            fout_t = str(e)
                    if fout_t:
                        waarschuwingen.append(f"vertaling {taal} niet gezet: {fout_t}")
                        logger.warning(f"Etsy vertaling {taal} mislukt: {fout_t}")

                beleid = await self._retourbeleid(c, token, shop_id)
                r = await c.patch(f"{ETSY_BASE}/application/shops/{shop_id}/listings/{listing_id}",
                                  data={"state": "active", "return_policy_id": beleid}, headers=headers)
                if r.status_code not in (200, 201):
                    raise RuntimeError(f"Etsy activate failed {r.status_code}: {_etsy_fout(r)}")
            except Exception:
                # Geen half werk achterlaten: een concept dat we niet kunnen afmaken weg.
                try:
                    await c.delete(f"{ETSY_BASE}/application/listings/{listing_id}", headers=headers)
                except Exception:  # noqa: BLE001
                    pass
                raise
            rapport = {"listing_id": listing_id, "taxonomy_id": int(taxonomy_id),
                       "taxonomie_pad": next((" > ".join(pd) for tid, pd in _taxonomie_cache["bladeren"]
                                              if tid == int(taxonomy_id)), None),
                       "talen": talen, "primair": primair, "sectie_id": sectie_id,
                       "secties": [x.get("title") for x in secties], "prijs": prijs,
                       "tags": velden["tags"], "materialen": velden["materials"],
                       "sku": etsy_sku, "eigenschappen": eigenschappen_gezet, "waarschuwingen": waarschuwingen,
                       "tijd": datetime.now(timezone.utc).isoformat()}
            self._bewaar_rapport(credentials.get("user_id"), rapport)
        return {**uitkomst, "state": "active", **({"waarschuwingen": waarschuwingen} if waarschuwingen else {})}

    def _bewaar_rapport(self, uid, rapport: dict) -> None:
        """Wat we naar Etsy stuurden, in extra_data.laatste_listing van de koppeling:
        zo is een plaatsing na te kijken zonder Etsy-sleutels."""
        if not uid:
            return
        try:
            from backend.database import get_db
            db = get_db()
            rij = (db.table("platform_credentials").select("extra_data").eq("user_id", uid)
                   .eq("platform", "etsy").limit(1).execute().data or [{}])[0]
            extra = {**(rij.get("extra_data") or {}), "laatste_listing": rapport}
            db.table("platform_credentials").update({"extra_data": extra}).eq("user_id", uid).eq("platform", "etsy").execute()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Etsy-rapport niet bewaard: {e}")

    async def _zet_eigenschappen(self, c, headers: dict, shop_id, listing_id, taxonomy_id, item: dict,
                                 waarschuwingen: list) -> dict:
        """Vult de Etsy-eigenschappen (materiaal, goudgehalte, edelsteen, lengte, ...) die uit het
        artikel blijken. Een fout hier laat de plaatsing doorgaan: het wordt een waarschuwing."""
        gezet: dict = {}
        try:
            r = await c.get(f"{ETSY_BASE}/application/seller-taxonomy/nodes/{int(taxonomy_id)}/properties",
                            headers={"x-api-key": _api_key()})
            r.raise_for_status()
            lijst = r.json().get("results") or []
        except Exception as e:  # noqa: BLE001
            waarschuwingen.append(f"eigenschappen niet opgehaald: {e}")
            return gezet
        namen = {p.get("property_id"): p.get("display_name") or p.get("name") for p in lijst}
        for keuze in kies_eigenschappen(lijst, item):
            data = {"value_ids": ",".join(str(v) for v in keuze["value_ids"]),
                    "values": ",".join(keuze["values"])}
            if keuze.get("scale_id"):
                data["scale_id"] = keuze["scale_id"]
            naam = namen.get(keuze["property_id"]) or str(keuze["property_id"])
            try:
                rp = await c.put(f"{ETSY_BASE}/application/shops/{shop_id}/listings/{listing_id}/properties/{keuze['property_id']}",
                                 headers={k: v for k, v in headers.items() if k.lower() != "content-type"}, data=data)
                if rp.status_code in (200, 201):
                    gezet[naam] = keuze["values"] + ([f"scale {keuze['scale_id']}"] if keuze.get("scale_id") else [])
                else:
                    waarschuwingen.append(f"eigenschap {naam} niet gezet: {rp.status_code}: {_etsy_fout(rp)}")
            except Exception as e:  # noqa: BLE001
                waarschuwingen.append(f"eigenschap {naam} niet gezet: {e}")
        return gezet

    async def _zet_sku(self, c, headers: dict, listing_id: str, sku: str, prijs: float, gereed: int) -> None:
        r = await c.get(f"{ETSY_BASE}/application/listings/{listing_id}/inventory", headers=headers)
        r.raise_for_status()
        producten = r.json().get("products") or []
        nieuw = []
        for pr in producten or [{}]:
            aanbod = []
            for o in pr.get("offerings") or [{}]:
                pj = o.get("price")
                waarde = (pj.get("amount", 0) / (pj.get("divisor") or 100)) if isinstance(pj, dict) else prijs
                # Etsy-spec: price, quantity, is_enabled en readiness_state_id zijn alle vier verplicht.
                aanbod.append({"price": waarde or prijs, "quantity": o.get("quantity") or 1,
                               "is_enabled": True, "readiness_state_id": gereed})
            nieuw.append({"sku": sku, "property_values": [], "offerings": aanbod})
        r = await c.put(f"{ETSY_BASE}/application/listings/{listing_id}/inventory",
                        headers={**headers, "Content-Type": "application/json"}, json={"products": nieuw})
        if r.status_code not in (200, 201):
            raise RuntimeError(f"{r.status_code}: {_etsy_fout(r)}")

    async def _upload_image(self, client, shop_id, listing_id, photo_url, token, rank=None, alt_text=None):
        img_resp = await client.get(photo_url)
        img_resp.raise_for_status()
        r = await client.post(
            f"{ETSY_BASE}/application/shops/{shop_id}/listings/{listing_id}/images",
            headers={"Authorization": f"Bearer {token}", "x-api-key": _api_key()},
            files={"image": ("photo.jpg", img_resp.content, "image/jpeg")},
            data={**({"rank": str(rank)} if rank else {}), **({"alt_text": alt_text[:500]} if alt_text else {})},
        )
        r.raise_for_status()

    async def delete_listing(self, platform_listing_id: str, credentials: dict) -> bool:
        credentials = await self._vers(credentials)
        token = self._token(credentials)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.delete(
                f"{ETSY_BASE}/application/listings/{platform_listing_id}",
                headers=self._headers(token),
            )
            # 404: bestaat niet meer, dus weg. Net als bij de andere API-kanalen.
            return r.status_code in (200, 204, 404)

    async def renew_listing(self, platform_listing_id: str, credentials: dict) -> dict:
        """
        Official Etsy renewal: PATCH the listing's state to 'active'. Etsy charges the
        normal listing fee and gives the listing a fresh "listed" timestamp — this is
        Etsy's own renewal mechanism (same one their web UI "Renew" button uses), not
        a workaround. Works for 'sold_out' and 'expired' listings; a currently-active
        listing doesn't need renewing.
        """
        credentials = await self._vers(credentials)
        token = self._token(credentials)
        shop_id = await self._get_shop_id(token)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.patch(
                f"{ETSY_BASE}/application/shops/{shop_id}/listings/{platform_listing_id}",
                json={"state": "active", "quantity": 1},
                headers=self._headers(token),
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Etsy renew failed {r.status_code}: {r.text}")
            data = r.json()
            return {
                "platform_listing_id": str(data.get("listing_id", platform_listing_id)),
                "state": data.get("state"),
            }

    async def get_listing_status(self, platform_listing_id: str, credentials: dict) -> str:
        credentials = await self._vers(credentials)
        token = self._token(credentials)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                f"{ETSY_BASE}/application/listings/{platform_listing_id}",
                headers=self._headers(token),
            )
            if r.status_code == 404:
                return "not_found"
            if r.status_code != 200:
                raise RuntimeError(f"Etsy status check failed {r.status_code}")
            data = r.json()
            state = data.get("state", "")
            if state == "active":
                return "active"
            if state == "sold_out":
                return "sold"
            return state
