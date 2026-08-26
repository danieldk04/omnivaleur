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

import random
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

# Gesproken openingen. Dit is een andere taal dan een bijschrift: niemand zegt
# hardop "POV". Wat iemand in de eerste drie seconden zégt bepaalt of er
# doorgekeken wordt, en dat is de enige plek waar de hook echt zit. Deze
# patronen komen uit het gesproken woord dat TikTok zelf meelevert.
SPREEKHOOKS: list[tuple[str, str]] = [
    ("aanspreken", r"(?i)\b(als je|jij die|voor jou|iedereen die|ben jij|wil je|"
                   r"if you|for anyone|do you|are you)\b"),
    ("waarschuwing", r"(?i)\b(let op|pas op|kijk uit|waarschuw|scam|oplichting|"
                     r"nooit|niet doen|fout|never|warning|careful|don'?t|mistake)\b"),
    ("belofte", r"(?i)\b(ik ga je|zo doe je|hier is hoe|dit is hoe|ik laat je zien|"
                r"i'?ll show|here'?s how|here'?s what|this is how|let me show)\b"),
    ("geheim", r"(?i)\b(niemand|geheim|wist je|weet je dat|trucje|truc|secret|"
               r"nobody|hidden|hack|tip|tips)\b"),
    ("cijfer-opening", r"^\W*\w{0,12}\s?\d+\b"),
    ("bedrag", r"(?i)\b(\d+\s?(euro|dollar|cent|k)\b|euro|winst|verdiend|"
               r"opgeleverd|profit|made|sold for|paid)\b"),
    ("vraag", r"(?i)^\W*(hoe|waarom|wat|wie|wanneer|welke|how|why|what|who|which)\b"),
    ("verhaal-start", r"(?i)(^\W*(ik|i'?m|i)\s|\b(laatst|gisteren|vandaag|"
                      r"vorige week|yesterday|today|last week)\b)"),
    ("bevel", r"(?i)^\W*(stop|kijk|luister|doe|pak|ga|onthoud|schrijf|sla op|"
              r"listen|look|watch|save this|stop scrolling)\b"),
    ("tegenspraak", r"(?i)\b(iedereen zegt|klopt niet|mythe|actually|wrong|"
                    r"maar nee|toch niet|denk je)\b"),
    ("dit-aanwijzing", r"(?i)^\W*(dit|deze|this|these|that)\b"),
    ("emotie", r"(?i)\b(oh my|niet te geloven|serieus|echt waar|insane|crazy|"
               r"wtf|omg|kan niet)\b"),
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

    YouTube en Instagram krijgen None: daar zijn delen en bewaren niet zichtbaar,
    dus elke score zou hier verzonnen zijn. Ze doen wel gewoon mee in de
    engagement-vergelijking, want likes en reacties zijn er wél.
    """
    if v["platform"] in ("YouTube", "Instagram") or not v.get("views"):
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
        gesproken = (v.get("gesproken_3s") or "").strip()
        # Alleen Nederlands en Engels. Er komt ook Duits en Pools voorbij in
        # deze hashtags, en die woorden door dezelfde patronen halen levert
        # cijfers op die over een andere markt gaan dan waar Daniel in zit.
        taal_ok = (v.get("stem_taal") or "").lower() in ("", "nld", "eng")
        v["heeft_stem"] = bool(gesproken) and taal_ok
        v["spreekhooks"] = [naam for naam, pat in SPREEKHOOKS
                            if re.search(pat, gesproken)] if gesproken else []
        v["spreekwoorden"] = len(gesproken.split()) if gesproken else 0
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
    """
    Video's van de laatste N dagen. Zonder datum tellen ze nergens in mee —
    liever een lege periode dan een periode die stiekem oude video's bevat.

    YouTube geeft alleen "3 weken geleden" en geen echte datum (tenzij er een
    API-sleutel is). Voor 30 en 90 dagen is dat nauwkeurig genoeg, voor 7 dagen
    niet: "1 week geleden" kan alles tussen 7 en 13 dagen zijn, en dan zou de
    weeklaag stilletjes oudere video's bevatten. Daar houden we ze dus buiten.
    """
    uit = []
    for v in videos:
        if v["leeftijd_dagen"] is None or v["leeftijd_dagen"] > dagen:
            continue
        if dagen <= 7 and v.get("datum_geschat"):
            continue
        uit.append(v)
    return uit


# ── Patroonanalyse ──────────────────────────────────────────────────────────
def _zekerheid(met: list[float], zonder: list[float], rondes: int = 1500) -> int:
    """
    Hoe zeker is het dat dit verschil echt is en geen toeval?

    Een lift van +40% op tien video's betekent weinig: haal er één uitschieter
    uit en hij is weg. Daarom trekken we duizend keer opnieuw een steekproef uit
    dezelfde video's en kijken hoe vaak het verschil dezelfde kant op wijst.
    Wijst het 95 van de 100 keer dezelfde kant op, dan is het een patroon;
    wijst het 60 van de 100 keer dezelfde kant op, dan is het ruis met een mooi
    percentage ervoor. Dit getal is het verschil tussen "opvallend" en "waar".
    """
    if len(met) < 5 or len(zonder) < 5:
        return 0
    hoger = 0
    for _ in range(rondes):
        a = statistics.median(random.choices(met, k=len(met)))
        b = statistics.median(random.choices(zonder, k=len(zonder)))
        if a > b:
            hoger += 1
    deel = hoger / rondes
    return round(max(deel, 1 - deel) * 100)


def voorbeelden_van(groep: list[dict], n: int = 4) -> list[dict]:
    """
    De bewijsstukken bij een patroon: niet één video maar meerdere.

    Eén voorbeeld bewijst niets — dat is een anekdote, en het voelt ook als een
    anekdote. Daarom leveren we er meerdere, van verschillende makers, zodat je
    het patroon zelf kunt zien in plaats van het van mij aan te moeten nemen.

    Twee filters: minstens 5.000 views (anders is de engagement-ratio een
    toevalstreffer op 40 kijkers) en één video per maker (anders staat er vijf
    keer dezelfde persoon en zie je nog steeds geen patroon).
    """
    bruikbaar = [v for v in groep if v.get("views", 0) >= 5000]
    # Video's waarvan we het eigen normaal van de maker kennen gaan voor. Bij de
    # rest is de uitschieterfactor tegen de hele niche gemeten en kan er een
    # spectaculair getal uitkomen dat niets bewijst; als bewijsstuk is zo'n
    # video zwakker, hoe groot het getal ook is.
    bruikbaar.sort(key=lambda v: (v.get("basis_herkomst") != "eigen",
                                  -(v.get("uitschieter") or 0), -v["eng_ratio"]))
    uit, makers = [], set()
    for v in bruikbaar:
        sleutel = (v["platform"], v["handle"])
        if sleutel in makers:
            continue
        makers.add(sleutel)
        uit.append(v)
        if len(uit) >= n:
            break
    return uit


def _vergelijk(met: list[dict], zonder: list[dict], minimum: int = 8) -> dict | None:
    """
    Eén patroon versus de rest. Geeft None als er te weinig materiaal is —
    dat is geen fout maar het enige eerlijke antwoord bij vijf video's.

    Naast de lift geven we het aantal video's, het aantal verschillende makers
    en de zekerheid. Die drie samen bepalen of iets een advies mag worden:
    twintig video's van één maker is één maker, geen patroon.
    """
    if len(met) < minimum or len(zonder) < minimum:
        return None
    m_eng = statistics.median([v["eng_ratio"] for v in met])
    z_eng = statistics.median([v["eng_ratio"] for v in zonder])
    m_view = statistics.median([v["views"] for v in met])
    z_view = statistics.median([v["views"] for v in zonder])
    makers = len({(v["platform"], v["handle"]) for v in met})
    zekerheid = _zekerheid([v["eng_ratio"] for v in met],
                           [v["eng_ratio"] for v in zonder])
    return {
        "aantal": len(met),
        "makers": makers,
        "zekerheid": zekerheid,
        # Hard genoeg om op te varen: genoeg video's, van genoeg verschillende
        # makers, en een verschil dat de hertrekking overleeft.
        "hard": len(met) >= 15 and makers >= 8 and zekerheid >= 90,
        "eng": round(m_eng, 2),
        "eng_rest": round(z_eng, 2),
        "eng_lift": round((m_eng / z_eng - 1) * 100) if z_eng else 0,
        "views": int(m_view),
        "views_rest": int(z_view),
        "views_lift": round((m_view / z_view - 1) * 100) if z_view else 0,
        "voorbeelden": voorbeelden_van(met),
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


def spreekhook_analyse(videos: list[dict]) -> list[dict]:
    """
    Welke gesproken opening werkt?

    We vergelijken alleen binnen de video's waarvan we het gesproken woord
    hebben. Anders zou "geen hook" ook alle video's zonder ondertiteling
    bevatten en meten we het bestaan van ondertiteling in plaats van de hook.
    """
    met_stem = [v for v in videos if v.get("heeft_stem")]
    uit = []
    for naam, _ in SPREEKHOOKS:
        met = [v for v in met_stem if naam in v["spreekhooks"]]
        zonder = [v for v in met_stem if naam not in v["spreekhooks"]]
        r = _vergelijk(met, zonder)
        if r:
            r["patroon"] = naam
            beste = max(met, key=lambda v: v["eng_ratio"])
            r["voorbeeld"] = (beste.get("gesproken_3s") or "")[:140]
            r["voorbeeld_url"] = beste["url"]
            uit.append(r)
    uit.sort(key=lambda r: (-r["hard"], -r["eng_lift"]))
    return uit


def spreekwoord_analyse(videos: list[dict], minimum: int = 8,
                        top_n: int = 20) -> list[dict]:
    """
    Welke woorden in de eerste drie seconden hangen samen met betere cijfers?

    Dit is bewust géén lijst die ik vooraf verzin. De vaste patronen hierboven
    vangen maar een deel: mensen beginnen op honderd manieren, en de manier die
    deze maand werkt staat niet in mijn lijstje. Daarom tellen we gewoon álle
    woorden die vaak genoeg gezegd worden en kijken welke bovengemiddeld scoren.
    Wat eruit komt is wat er gemeten is, niet wat ik verwachtte.
    """
    met_stem = [v for v in videos if v.get("heeft_stem")]
    if len(met_stem) < 30:
        return []
    per_woord: dict[str, list[dict]] = defaultdict(list)
    for v in met_stem:
        for w in set(re.findall(r"[a-zA-ZÀ-ÿ']{3,}",
                                (v.get("gesproken_3s") or "").lower())) - STOP:
            per_woord[w].append(v)

    uit = []
    for woord, groep in per_woord.items():
        if len(groep) < minimum:
            continue
        rest = [v for v in met_stem if v not in groep]
        r = _vergelijk(groep, rest, minimum=minimum)
        if not r or r["eng_lift"] <= 0:
            continue
        r["patroon"] = f'"{woord}"'
        beste = max(groep, key=lambda v: v["eng_ratio"])
        r["voorbeeld"] = (beste.get("gesproken_3s") or "")[:140]
        r["voorbeeld_url"] = beste["url"]
        uit.append(r)
    uit.sort(key=lambda r: (-r["hard"], -r["zekerheid"], -r["eng_lift"]))
    return uit[:top_n]


def spreektempo_analyse(videos: list[dict]) -> list[dict]:
    """Snel of rustig praten in de eerste seconden — maakt dat uit?"""
    met_stem = [v for v in videos if v.get("heeft_stem") and v.get("spreektempo")]
    if len(met_stem) < 20:
        return []
    grens = statistics.median([v["spreektempo"] for v in met_stem])
    snel = [v for v in met_stem if v["spreektempo"] > grens]
    rustig = [v for v in met_stem if v["spreektempo"] <= grens]
    uit = []
    for naam, groep, rest in (("snel praten", snel, rustig),
                              ("rustig praten", rustig, snel)):
        r = _vergelijk(groep, rest)
        if r:
            r["patroon"] = f"{naam} (grens {grens:.1f} woorden/sec)"
            beste = max(groep, key=lambda v: v["eng_ratio"])
            r["voorbeeld"] = (beste.get("gesproken_3s") or "")[:140]
            r["voorbeeld_url"] = beste["url"]
            uit.append(r)
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
            "spreekhooks": spreekhook_analyse(deel),
            "spreekwoorden": spreekwoord_analyse(deel),
            "spreektempo": spreektempo_analyse(deel),
            "met_stem": len([v for v in deel if v.get("heeft_stem")]),
            "onderwerpen": onderwerp_analyse(deel),
            "hashtags": hashtag_analyse(deel),
            "vorm": vorm_analyse(deel),
            "sounds": sound_analyse(deel),
        }
    uit["met_stem_totaal"] = len([v for v in videos if v.get("heeft_stem")])
    uit["alles"] = videos
    return uit
