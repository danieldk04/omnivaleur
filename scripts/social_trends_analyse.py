"""
Van ruwe video's naar antwoorden: wat werkt er, en waaruit blijkt dat?

Elke uitspraak hier is een vergelijking tussen twee groepen video's uit dezelfde
dataset — nooit een oordeel. "Vragen als openingszin werken" betekent hier: de
video's die met een vraag openen hebben een mediane engagement-ratio van X, de
rest Y, gemeten over N video's. Staat er te weinig materiaal onder een patroon,
dan verdwijnt het uit het rapport in plaats van dat we het afzwakken.

Drie rekenregels die het verschil maken:

  * De uitschieterfactor vergelijkt een video met het gewone werk van diezelfde
    maker. Een account met 2 miljoen volgers haalt vanzelf views; alleen als een
    video vér boven zijn eigen normaal uitkomt, zit er iets in het idee. Heeft
    een maker te weinig video's in onze dataset, dan vergelijken we met de
    mediaan van zijn niche en zeggen we dat erbij.

  * De viraliteitsscore weegt per platform anders. TikTok duwt wat mensen
    doorsturen en bewaren, dus daar wegen shares en saves het zwaarst. YouTube
    geeft ons alleen views, dus daar bestaat deze score niet — we doen niet
    alsof.

  * Overal de mediaan, nooit het gemiddelde. Eén video van 50 miljoen views
    trekt elk gemiddelde uit zijn verband.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

PERIODES = {"7d": 7, "30d": 30, "90d": 90}

# Woorden die overal voorkomen en dus niets onderscheiden. Bewust kort gehouden:
# hoe langer deze lijst, hoe meer je zelf bepaalt wat "interessant" is, en dat is
# precies wat we niet willen.
STOP = set("""
de het een en van in op is te dat die voor met als aan zijn er om ook maar niet
je jij ik we wij ze zij mijn mij deze dit naar bij uit door over nog wel wat hoe
al heb hebt heeft was waren word wordt worden kan kun kunt zou zal meer heel echt
the a an and or of to in on is it that this for with you your my me we they are
be was were have has had do does did so just get got can will would my i im
fyp foryou foryoupage viral fy tiktok reel reels shorts short video
""".split())

# Openingspatronen. Elk patroon kijkt naar de eerste ~80 tekens — dat is wat een
# kijker leest voordat hij besluit te blijven.
HOOKS: list[tuple[str, str]] = [
    ("vraag", r"^[^.!?]{0,80}\?"),
    ("getal-belofte", r"^\W*\d+\s+\w"),
    ("pov", r"(?i)^\W*pov\b"),
    ("ik-verhaal", r"(?i)^\W*(ik|i)\s+(heb|ben|kocht|verkocht|bought|sold|made|found|tried)"),
    ("hoe-uitleg", r"(?i)^\W*(hoe|how to|how i)\b"),
    ("stop-bevel", r"(?i)^\W*(stop|nooit|never|don'?t|niet doen)\b"),
    ("dit-aanwijzing", r"(?i)^\W*(dit|this|these|deze)\b"),
    ("bedrag", r"(?i)(€|\$|eur|euro)\s?\d"),
    ("resultaat-claim", r"(?i)\b(\d+[.,]?\d*\s?(k|mille|euro|€|\$)|winst|verdiend|profit|made)\b"),
]


# ── Basisbewerkingen ────────────────────────────────────────────────────────
def _dagen_oud(datum: str, nu: datetime) -> int | None:
    if not datum:
        return None
    try:
        d = datetime.strptime(datum, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (nu - d).days


def _eng_ratio(v: dict) -> float:
    if not v.get("views"):
        return 0.0
    eng = v["likes"] + v["comments"] + v["shares"] + v["saves"]
    return round(eng / v["views"] * 100, 2)


def _viraal(v: dict) -> float | None:
    """
    Hoe sterk duwt dit platform deze video?

    TikTok beloont doorsturen het hardst, daarna bewaren, dan reacties, dan pas
    likes — dat is de volgorde waarin het algoritme bereik toekent. We drukken
    dat uit per duizend views, zodat een kleine en een grote video vergelijkbaar
    zijn.

    YouTube krijgt None: de zoekpagina geeft geen likes of reacties, dus elke
    score zou hier verzonnen zijn.
    """
    if v["platform"] == "YouTube" or not v.get("views"):
        return None
    per_mille = 1000 / v["views"]
    return round((v["shares"] * 4 + v["saves"] * 3
                  + v["comments"] * 2 + v["likes"] * 0.5) * per_mille, 1)


def verrijk(videos: list[dict], nu: datetime | None = None) -> list[dict]:
    """Zet per video de afgeleide maten erbij: leeftijd, ratio, uitschieterfactor."""
    nu = nu or datetime.now(timezone.utc)

    per_maker: dict[tuple[str, str], list[int]] = defaultdict(list)
    per_niche: dict[str, list[int]] = defaultdict(list)
    for v in videos:
        if v.get("views"):
            per_maker[(v["platform"], v["handle"])].append(v["views"])
            per_niche[v["niche"]].append(v["views"])

    for v in videos:
        v["leeftijd_dagen"] = _dagen_oud(v.get("datum", ""), nu)
        v["eng_ratio"] = _eng_ratio(v)
        v["viraal"] = _viraal(v)
        v["hooks"] = [naam for naam, pat in HOOKS
                      if re.search(pat, (v.get("tekst") or "")[:80])]
        v["tekstlengte"] = len(v.get("tekst") or "")
        v["aantal_hashtags"] = len(v.get("hashtags") or [])

        eigen = per_maker[(v["platform"], v["handle"])]
        if len(eigen) >= 3:
            basis, herkomst = statistics.median(eigen), "eigen"
        else:
            basis, herkomst = statistics.median(per_niche[v["niche"]] or [1]), "niche"
        v["basis_views"] = int(basis)
        v["basis_herkomst"] = herkomst
        v["uitschieter"] = round(v["views"] / basis, 2) if basis else 0.0
    return videos


def in_periode(videos: list[dict], dagen: int) -> list[dict]:
    """Video's van de laatste N dagen. Zonder datum tellen ze nergens in mee —
    liever een lege periode dan een periode die stiekem oude video's bevat."""
    return [v for v in videos
            if v["leeftijd_dagen"] is not None and v["leeftijd_dagen"] <= dagen]


# ── Patroonanalyse ──────────────────────────────────────────────────────────
def _vergelijk(met: list[dict], zonder: list[dict], minimum: int = 8) -> dict | None:
    """
    Eén patroon versus de rest. Geeft None als er te weinig materiaal is —
    dat is geen fout maar het enige eerlijke antwoord bij vijf video's.
    """
    if len(met) < minimum or len(zonder) < minimum:
        return None
    m_eng = statistics.median([v["eng_ratio"] for v in met])
    z_eng = statistics.median([v["eng_ratio"] for v in zonder])
    m_view = statistics.median([v["views"] for v in met])
    z_view = statistics.median([v["views"] for v in zonder])
    return {
        "aantal": len(met),
        "eng": round(m_eng, 2),
        "eng_rest": round(z_eng, 2),
        "eng_lift": round((m_eng / z_eng - 1) * 100) if z_eng else 0,
        "views": int(m_view),
        "views_rest": int(z_view),
        "views_lift": round((m_view / z_view - 1) * 100) if z_view else 0,
    }


def hook_analyse(videos: list[dict]) -> list[dict]:
    uit = []
    for naam, _ in HOOKS:
        met = [v for v in videos if naam in v["hooks"]]
        zonder = [v for v in videos if naam not in v["hooks"]]
        r = _vergelijk(met, zonder)
        if r:
            r["patroon"] = naam
            voorbeeld = max(met, key=lambda v: v["eng_ratio"])
            r["voorbeeld"] = voorbeeld["tekst"][:110]
            r["voorbeeld_url"] = voorbeeld["url"]
            uit.append(r)
    uit.sort(key=lambda r: -r["eng_lift"])
    return uit


def onderwerp_analyse(videos: list[dict], top_n: int = 18) -> list[dict]:
    """
    Welke woorden komen vaker voor in de best presterende helft?

    We splitsen op de mediane engagement-ratio en tellen woorden in beide helften.
    Een woord dat in beide helften even vaak staat zegt niets; het verschil is
    het signaal. Woorden die minder dan 6 keer voorkomen laten we vallen — onder
    dat aantal is elk verschil toeval.
    """
    if len(videos) < 30:
        return []
    grens = statistics.median([v["eng_ratio"] for v in videos])
    boven = [v for v in videos if v["eng_ratio"] >= grens]
    onder = [v for v in videos if v["eng_ratio"] < grens]

    def woorden_van(v) -> set[str]:
        # Hashtags eruit knippen vóór het tellen. Anders bestaat deze lijst
        # vrijwel volledig uit hashtags — die zijn geen onderwerp maar een label,
        # en ze worden hieronder apart geanalyseerd.
        kaal = re.sub(r"#\w+", " ", (v.get("tekst") or "").lower())
        return set(re.findall(r"[a-zA-ZÀ-ÿ]{3,}", kaal)) - STOP

    def tel(groep):
        c = Counter()
        for v in groep:
            for w in woorden_van(v):
                c[w] += 1
        return c

    b, o = tel(boven), tel(onder)
    uit = []
    for w, n in b.items():
        totaal = n + o.get(w, 0)
        if totaal < 6:
            continue
        aandeel = n / totaal
        if aandeel <= 0.55:
            continue
        # Dezelfde woordsplitsing als hierboven gebruiken, niet een losse
        # regex-zoektocht: die miste woorden met accenten en telde er andere
        # dubbel, waardoor deze lijst leeg kon uitkomen.
        hits = [v for v in boven if w in woorden_van(v)]
        if not hits:
            continue
        uit.append({
            "woord": w, "aantal": totaal, "aandeel_boven": round(aandeel * 100),
            "med_eng": round(statistics.median([v["eng_ratio"] for v in hits]), 2),
            "med_views": int(statistics.median([v["views"] for v in hits])),
        })
    uit.sort(key=lambda r: (-r["aandeel_boven"], -r["aantal"]))
    return uit[:top_n]


def hashtag_analyse(videos: list[dict], minimum: int = 10) -> list[dict]:
    """
    Welke hashtag hangt samen met betere cijfers?

    Let op de richting: dit zegt niet dat de hashtag de views veroorzaakt. Een
    hashtag markeert een sóórt video, en dat soort presteert beter of slechter.
    Zo moet je het ook lezen — als aanwijzing welk type content loont, niet als
    knop die je kunt indrukken.
    """
    per: dict[str, list[dict]] = defaultdict(list)
    for v in videos:
        for h in set(t.lower() for t in (v.get("hashtags") or [])):
            per[h].append(v)
    if not videos:
        return []
    alle_eng = statistics.median([v["eng_ratio"] for v in videos])
    uit = []
    for tag, groep in per.items():
        if len(groep) < minimum or tag in STOP:
            continue
        med = statistics.median([v["eng_ratio"] for v in groep])
        uit.append({
            "tag": tag, "aantal": len(groep),
            "med_eng": round(med, 2),
            "lift": round((med / alle_eng - 1) * 100) if alle_eng else 0,
            "med_views": int(statistics.median([v["views"] for v in groep])),
        })
    uit.sort(key=lambda r: -r["lift"])
    return uit[:16]


def _bucket_analyse(videos, sleutel, grenzen, labels) -> list[dict]:
    groepen = defaultdict(list)
    for v in videos:
        w = v.get(sleutel)
        if w is None:
            continue
        idx = next((i for i, g in enumerate(grenzen) if w <= g), len(grenzen))
        groepen[labels[idx]].append(v)
    uit = []
    for label in labels:
        g = groepen.get(label, [])
        if len(g) < 8:
            continue
        uit.append({
            "groep": label, "aantal": len(g),
            "med_eng": round(statistics.median([v["eng_ratio"] for v in g]), 2),
            "med_views": int(statistics.median([v["views"] for v in g])),
        })
    return uit


def vorm_analyse(videos: list[dict]) -> dict:
    """Lengte van de video, lengte van de beschrijving, aantal hashtags."""
    return {
        "duur": _bucket_analyse(
            [v for v in videos if v.get("duur")], "duur",
            [10, 20, 35, 60], ["≤10 sec", "11-20 sec", "21-35 sec", "36-60 sec", "> 60 sec"]),
        "tekstlengte": _bucket_analyse(
            videos, "tekstlengte", [40, 90, 150],
            ["≤40 tekens", "41-90", "91-150", "> 150"]),
        "hashtags": _bucket_analyse(
            videos, "aantal_hashtags", [0, 2, 5],
            ["geen", "1-2", "3-5", "6 of meer"]),
    }


def sound_analyse(videos: list[dict], minimum: int = 3) -> list[dict]:
    """Sounds die meerdere makers gebruiken — dat is wat een trend onderscheidt
    van één toevallig goede video."""
    per: dict[str, list[dict]] = defaultdict(list)
    for v in videos:
        if v.get("sound_id") and v["platform"] == "TikTok":
            per[v["sound_id"]].append(v)
    uit = []
    for sid, groep in per.items():
        makers = {v["handle"] for v in groep}
        if len(makers) < minimum:
            continue
        uit.append({
            "sound": groep[0]["sound"] or "(zonder titel)",
            "makers": len(makers), "videos": len(groep),
            "med_views": int(statistics.median([v["views"] for v in groep])),
            "med_eng": round(statistics.median([v["eng_ratio"] for v in groep]), 2),
            "url": max(groep, key=lambda v: v["views"])["url"],
        })
    uit.sort(key=lambda r: (-r["makers"], -r["med_views"]))
    return uit[:12]


def beste_videos(videos: list[dict], n: int = 60) -> list[dict]:
    """
    De sterkste video's, gemeten als uitschieter tegenover de eigen basis, met
    de viraliteitsscore als tweede maat. Video's onder de 5.000 views vallen af:
    daaronder is een hoge ratio wiskunde, geen prestatie.
    """
    kandidaten = [v for v in videos if v["views"] >= 5000]
    kandidaten.sort(key=lambda v: (-(v["uitschieter"] or 0), -(v["viraal"] or 0)))
    return kandidaten[:n]


def analyseer(videos: list[dict]) -> dict:
    """Alles, per periode. De 90-dagenlaag is de enige die genoeg materiaal heeft
    voor patronen; 7 dagen is te dun en dient om te zien wat er nú loopt."""
    videos = verrijk(videos)
    uit = {"totaal": len(videos), "met_datum": len([v for v in videos
                                                    if v["leeftijd_dagen"] is not None])}
    for naam, dagen in PERIODES.items():
        deel = in_periode(videos, dagen)
        uit[naam] = {
            "aantal": len(deel),
            "top": beste_videos(deel, 60),
            "hooks": hook_analyse(deel),
            "onderwerpen": onderwerp_analyse(deel),
            "hashtags": hashtag_analyse(deel),
            "vorm": vorm_analyse(deel),
            "sounds": sound_analyse(deel),
        }
    uit["alles"] = videos
    return uit
