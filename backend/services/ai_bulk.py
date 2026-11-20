"""Bulkopdracht in gewone taal: het model kiest, gewone code voert uit (20-11-2026).

HET ONTWERP IS DE VEILIGHEID, NIET DE NAUWKEURIGHEID VAN HET MODEL.
Gemeten 19-11: 25 van 30 opdrachten goed, en een misser was gevaarlijk ("1 euro
erbij" werd prijs_vast 1 in plaats van plus 1 euro). Een model blijft soms
missen. Daarom:

1. Het model mag alleen een van vaste bewerkingen kiezen (OPS). Alles wat geen
   geldige ENKELE bewerking is (lijst, kapotte JSON, onbekend) wordt nooit
   uitgevoerd; de klant krijgt de vraag het anders te zeggen.
2. Een tweede, domme controle in gewone code (`controleer`): het bedrag moet
   letterlijk in de opdracht staan, een richtingswoord ("erbij", "eraf") moet
   kloppen met het teken, en bij prijs_vast mag geen richtingswoord staan.
   Teksten die het model noemt moeten letterlijk in de opdracht voorkomen.
3. Altijd eerst een voorbeeld (5 artikelen, oud en nieuw, totaal aantal), de
   klant bevestigt, en er is 1 klik ongedaan maken (oude waarden bewaard).
4. Een prijs onder EUR 1 of meer dan verdubbeld vraagt een extra bevestiging.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from backend.services import taalmodel

logger = logging.getLogger(__name__)

OPS = ("prijs_procent", "prijs_bedrag", "prijs_vast",
       "tekst_toevoegen", "tekst_vervangen", "tekst_verwijderen")
KANALEN = ("marktplaats", "2dehands", "vinted", "ebay", "shopify", "woocommerce")
VELDEN = {"titel": "title", "beschrijving": "description"}
PRIJSVELD = {k: f"price_{k}" for k in KANALEN}
MAX_TITEL = 100
MAX_ARTIKELEN = 1500          # meer dan dit: de klant maakt de selectie kleiner
MAX_ONGEDAAN_BYTES = 1_500_000  # past het niet, dan voeren we niet uit
VOORBEELD_N = 5
VOORBEELD_GELDIG_S = 1800

_OMHOOG = re.compile(r"\b(erbij|extra|meer|plus|omhoog|verhoog\w*|verhogen|duurder|"
                     r"raise|increase\w*|up by|higher|more|add)\b|\+", re.I)
_OMLAAG = re.compile(r"\b(eraf|af|minder|min|omlaag|verlaag\w*|verlagen|korting|goedkoper|"
                     r"aftrekken|lower|decrease\w*|off|discount|cheaper|less|subtract|reduce\w*)\b|[−–-]\s*\d", re.I)


def opdracht_voor_model(opdracht: str) -> str:
    return (
        "You translate ONE instruction of a second-hand seller into ONE bulk edit of their "
        "product listings. Answer with ONLY one JSON object, never a list, no explanation.\n"
        'Fields: {"actie": one of prijs_procent | prijs_bedrag | prijs_vast | tekst_toevoegen | '
        'tekst_vervangen | tekst_verwijderen | onbekend, '
        '"kanaal": "alle" or one of marktplaats, 2dehands, vinted, ebay, shopify, woocommerce, '
        '"veld": "titel" or "beschrijving" (text actions only), '
        '"waarde": a number (price actions only), '
        '"tekst": text to add (tekst_toevoegen), "positie": "begin" or "einde", '
        '"zoek": text to find, "vervang": replacement text (tekst_vervangen)}.\n'
        "Meaning: prijs_procent = change price by a percentage (+10 = 10% more, -15 = 15% less). "
        "prijs_bedrag = add or subtract an amount in euro (+1 = one euro more, -2.5 = 2,50 less). "
        "prijs_vast = set the price to exactly this amount. tekst_verwijderen needs 'zoek'. "
        "If the instruction asks for two or more different edits, or you are not sure, answer "
        '{"actie": "onbekend"}.\n'
        'Examples: "alles 10% duurder" -> {"actie":"prijs_procent","kanaal":"alle","waarde":10}; '
        '"1 euro erbij op vinted" -> {"actie":"prijs_bedrag","kanaal":"vinted","waarde":1}; '
        '"alle prijzen 2 euro eraf" -> {"actie":"prijs_bedrag","kanaal":"alle","waarde":-2}; '
        '"zet de prijs op 15 euro" -> {"actie":"prijs_vast","kanaal":"alle","waarde":15}; '
        '"voeg onderaan de beschrijving \'Verzending binnen 2 dagen\' toe" -> '
        '{"actie":"tekst_toevoegen","kanaal":"alle","veld":"beschrijving","tekst":"Verzending binnen 2 dagen","positie":"einde"}.\n'
        "INSTRUCTION: " + json.dumps(opdracht, ensure_ascii=False)
    )


def _getal(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def valideer(antwoord: str) -> dict | None:
    """De ruwe modeltekst naar een geldige enkele bewerking, anders None."""
    try:
        t = re.sub(r"^```(?:json)?|```$", "", (antwoord or "").strip(), flags=re.M).strip()
        raw = json.loads(t)
    except ValueError:
        return None
    if not isinstance(raw, dict):          # een lijst is nooit uitvoerbaar
        return None
    actie = raw.get("actie")
    if actie not in OPS:
        return None
    kanaal = str(raw.get("kanaal") or "alle").lower()
    if kanaal != "alle" and kanaal not in KANALEN:
        return None
    bew: dict = {"actie": actie, "kanaal": kanaal}
    if actie.startswith("prijs_"):
        w = _getal(raw.get("waarde"))
        if w is None or w != w or w in (float("inf"), float("-inf")):
            return None
        grens = {"prijs_procent": (-90, 200), "prijs_bedrag": (-10000, 10000),
                 "prijs_vast": (1, 100000)}[actie]
        if not (grens[0] <= w <= grens[1]) or w == 0:
            return None
        bew["waarde"] = w
        return bew
    veld = str(raw.get("veld") or "beschrijving").lower()
    if veld not in VELDEN:
        return None
    bew["veld"] = veld
    bew["kanaal"] = "alle"
    if actie == "tekst_toevoegen":
        tekst = raw.get("tekst")
        if not isinstance(tekst, str) or not tekst.strip() or len(tekst) > 500:
            return None
        bew["tekst"] = tekst.strip()
        bew["positie"] = "begin" if raw.get("positie") == "begin" else "einde"
    else:
        zoek = raw.get("zoek")
        if not isinstance(zoek, str) or not zoek.strip() or len(zoek) > 200:
            return None
        bew["zoek"] = zoek
        if actie == "tekst_vervangen":
            vervang = raw.get("vervang")
            if not isinstance(vervang, str) or len(vervang) > 200:
                return None
            bew["vervang"] = vervang
    return bew


def _getal_staat_in(w: float, opdracht: str) -> bool:
    cijfers = {f"{abs(w):g}", f"{abs(w):.2f}", f"{abs(w):g}".replace(".", ",")}
    cijfers.add(f"{abs(w):.2f}".replace(".", ","))
    gevonden = re.findall(r"\d+(?:[.,]\d+)?", opdracht)
    return any(g in cijfers or g.replace(",", ".") in cijfers for g in gevonden)


def controleer(opdracht: str, bew: dict) -> str | None:
    """Tweede, domme controle in gewone code. None = akkoord, anders de reden."""
    laag = opdracht.lower()
    if bew["actie"].startswith("prijs_"):
        w = bew["waarde"]
        if not _getal_staat_in(w, laag):
            return "het bedrag staat niet in je opdracht"
        omhoog, omlaag = bool(_OMHOOG.search(laag)), bool(_OMLAAG.search(laag))
        if bew["actie"] == "prijs_vast":
            if omhoog or omlaag:
                return "onduidelijk of de prijs erbij of eraf moet, of een vast bedrag wordt"
            return None
        if omhoog and omlaag:
            return "je opdracht noemt zowel omhoog als omlaag"
        if not omhoog and not omlaag:
            return "niet duidelijk of de prijs omhoog of omlaag moet"
        if omhoog and w < 0 or omlaag and w > 0:
            return "de richting (erbij of eraf) klopt niet met je opdracht"
        return None
    for sleutel in ("tekst", "zoek", "vervang"):
        t = bew.get(sleutel)
        if t and t.lower().strip() not in laag:
            return "een tekst in de bewerking staat niet letterlijk in je opdracht"
    return None


def _afronden(x: float) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _prijs(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def _nieuwe_prijs(oud: float, bew: dict) -> float:
    if bew["actie"] == "prijs_procent":
        return _afronden(oud * (1 + bew["waarde"] / 100))
    if bew["actie"] == "prijs_bedrag":
        return _afronden(oud + bew["waarde"])
    return _afronden(bew["waarde"])


def _zoek_re(zoek: str):
    return re.compile(re.escape(zoek), re.I)


def _nieuwe_tekst(oud: str, bew: dict, veld: str) -> str:
    oud = oud or ""
    if bew["actie"] == "tekst_toevoegen":
        sep = " " if veld == "title" else "\n"
        if bew["positie"] == "begin":
            return f"{bew['tekst']}{sep}{oud}".strip()
        return f"{oud}{sep}{bew['tekst']}".strip()
    nieuw = _zoek_re(bew["zoek"]).sub(bew.get("vervang", ""), oud)
    if veld == "title":
        nieuw = re.sub(r"\s{2,}", " ", nieuw)
    return nieuw.strip()


def plan(items: list[dict], bew: dict) -> dict:
    """Wat er zou veranderen, zonder iets te schrijven.

    Geeft {"wijzigingen": [{id, titel, veld, oud, nieuw}], "onder_1", "dubbel", "te_lang"}."""
    wijz: list[dict] = []
    onder_1 = dubbel = te_lang = 0
    for it in items:
        if bew["actie"].startswith("prijs_"):
            if bew["kanaal"] == "alle":
                velden = ["price"] + [PRIJSVELD[k] for k in KANALEN
                                      if _prijs(it.get(PRIJSVELD[k])) is not None]
            else:
                velden = [PRIJSVELD[bew["kanaal"]]]
            for veld in velden:
                oud = _prijs(it.get(veld))
                if oud is None:
                    oud = _prijs(it.get("price"))    # kanaalprijs leeg: basisprijs telt
                if oud is None or oud <= 0:
                    continue
                nieuw = _nieuwe_prijs(oud, bew)
                if nieuw == oud:
                    continue
                if nieuw < 1:
                    onder_1 += 1
                if nieuw > oud * 2:
                    dubbel += 1
                wijz.append({"id": it["id"], "titel": it.get("title") or "", "veld": veld,
                             "oud": oud, "nieuw": nieuw})
        else:
            veld = VELDEN[bew["veld"]]
            oud = it.get(veld) or ""
            if bew["actie"] != "tekst_toevoegen" and not _zoek_re(bew["zoek"]).search(oud):
                continue
            nieuw = _nieuwe_tekst(oud, bew, veld)
            if nieuw == oud or not nieuw:
                continue
            if veld == "title" and len(nieuw) > MAX_TITEL:
                te_lang += 1
                continue
            wijz.append({"id": it["id"], "titel": it.get("title") or "", "veld": veld,
                         "oud": oud, "nieuw": nieuw})
    return {"wijzigingen": wijz, "onder_1": onder_1, "dubbel": dubbel, "te_lang": te_lang}


def voorbeeld(items: list[dict], bew: dict) -> dict:
    p = plan(items, bew)
    w = p["wijzigingen"]
    ids = list(dict.fromkeys(x["id"] for x in w))
    return {"artikelen": len(ids), "wijzigingen": len(w), "onder_1": p["onder_1"],
            "dubbel": p["dubbel"], "te_lang": p["te_lang"],
            "extra_bevestiging": bool(p["onder_1"] or p["dubbel"]),
            "te_veel": len(ids) > MAX_ARTIKELEN,
            "voorbeeld": [{"id": x["id"], "titel": x["titel"], "veld": x["veld"],
                           "oud": x["oud"], "nieuw": x["nieuw"]}
                          for x in _eerste_per_artikel(w)[:VOORBEELD_N]]}


def _eerste_per_artikel(w: list[dict]) -> list[dict]:
    gezien, uit = set(), []
    for x in w:
        if x["id"] not in gezien:
            gezien.add(x["id"])
            uit.append(x)
    return uit


def ongedaan_blok(wijzigingen: list[dict]) -> dict | None:
    """Wat nodig is om terug te draaien, of None als dat niet in de opslag past."""
    oud: dict = {}
    for x in wijzigingen:
        oud.setdefault(x["id"], {})[x["veld"]] = [x["oud"], x["nieuw"]]
    blok = {"id": uuid.uuid4().hex[:12], "tijd": datetime.now(timezone.utc).isoformat(),
            "items": oud}
    if len(json.dumps(blok, ensure_ascii=False)) > MAX_ONGEDAAN_BYTES:
        return None
    return blok


def vraag_model(opdracht: str) -> tuple[dict | None, str]:
    """(bewerking, reden). Bewerking is None als er niets veiligs uitkwam."""
    try:
        antwoord = taalmodel.vraag(opdracht_voor_model(opdracht), max_tokens=300,
                                   wat="AI-bulkopdracht", denken=False,
                                   claude_toegestaan=False)
    except taalmodel.TaalmodelOnbeschikbaar:
        return None, "storing"
    bew = valideer(antwoord)
    if bew is None:
        return None, "onduidelijk"
    reden = controleer(opdracht, bew)
    if reden:
        return None, reden
    return bew, ""
