"""Bouwt de influencer-doellijst voor Omnivaleur uit TikTok-hashtagdata.

Bron: een Apify-dataset van funny_ground/tiktok-scraper (hashtag-sweep).
Datasets zijn publiek leesbaar, dus er is hier geen APIFY_TOKEN nodig.

Doel: van losse video's naar een gerangschikte lijst creators, gesplitst in
verkopers/resellers (de doelgroep) en kopers (haul-content, niet interessant).

Gebruik:
    python3 scripts/leadgen_creators.py <dataset_id> [<dataset_id> ...]

Schrijft scripts/output/leads/creators_tiktok.json en print de top.
"""
import csv
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

UIT = Path(__file__).resolve().parent / "output" / "leads"

# Woorden die verraden dat iemand VERKOOPT. Dat is onze doelgroep: die persoon
# heeft meerdere kanalen en dus baat bij crosslisten.
VERKOOP = {
    "reseller": 3, "resellen": 3, "resell": 3, "reselling": 3, "vintagereseller": 3,
    "supplier": 3, "suppliers": 3, "wholesale": 3, "groothandel": 3, "bulk": 2,
    "per kilo": 3, "partij": 2, "voorraad": 3, "stock": 2, "inkoop": 3,
    "verkoop": 2, "verkopen": 2, "verkoper": 3, "te koop": 2, "shop my": 3,
    "alles moet weg": 3, "alles mag weg": 3, "doe een bod": 2, "bieden": 1,
    "marge": 3, "winst": 2, "omzet": 3, "dropship": 2, "sourcing": 3,
    "mijn vinted": 2, "my vinted": 2, "vintedverkoop": 3, "webshop": 2,
    "link in bio": 1, "bestellen": 1, "marktplaats": 2, "2dehands": 2,
    "depop": 2, "ebay": 2, "etsy": 2, "shopify": 2, "crosslist": 4,
}

# Woorden die verraden dat iemand KOOPT. Die heeft niets aan Omnivaleur.
KOOP = {
    "haul": 3, "finds": 2, "aankopen": 3, "gekocht": 3, "unboxing": 3,
    "uitpakken": 2, "bestelling binnen": 3, "pakketje": 2, "wat ik kocht": 3,
    "shoplog": 3, "review": 1, "outfitinspo": 2, "ootd": 2, "inspo": 1,
}

# Onderwerpen die niet in de kledingniche vallen; die gooien we eruit.
BUITEN_NICHE = {"boeken", "booksoftiktok", "acotar", "makeup", "skincare", "recept"}

# De hashtags zijn internationaal, dus er komen ook Britse en Amerikaanse
# resellers mee. Omnivaleur bedient NL en BE, dus die moeten eruit. Losse
# woorden zijn betrouwbaarder dan een hashtag: #vintednederland zetten
# buitenlanders er ook onder om Nederlands publiek te bereiken.
NL_WOORDEN = {
    " de ", " het ", " een ", " en ", " van ", " ik ", " je ", " jij ", " niet ",
    " met ", " voor ", " op ", " dat ", " dit ", " zijn ", " heb ", " ook ",
    " maar ", " mijn ", " jouw ", " wat ", " hoe ", " kan ", " gaat ", " weer ",
    " echt ", " even ", " gewoon ", " alles ", " moet ", " wil ", " naar ",
    " deze ", " uit ", " nog ", " veel ", " zo ", " als ", " door ", " werd ",
    " tweedehands", " kleding", " verkopen", " kopen", " prijs", " duur",
    " goedkoop", " spullen", " winkel", " zoek",
}


def haal_dataset(dataset_id: str) -> list:
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?clean=true&format=json"
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.loads(r.read().decode())


def tel(tekst: str, woordenboek: dict) -> int:
    return sum(gewicht for woord, gewicht in woordenboek.items() if woord in tekst)


def main(dataset_ids: list) -> None:
    videos = []
    for did in dataset_ids:
        rijen = haal_dataset(did)
        print(f"dataset {did}: {len(rijen)} video's")
        videos.extend(rijen)
    if not videos:
        # Een lege uitkomst is eerst een reden om de meting te wantrouwen.
        raise SystemExit("GEEN video's opgehaald. Controleer de dataset-id's.")

    per_creator = defaultdict(lambda: {
        "videos": 0, "views": 0, "likes": 0, "verkoop": 0, "koop": 0,
        "buiten_niche": 0, "nickname": "", "voorbeelden": [], "hashtags": set(),
    })

    for v in videos:
        auteur = (v.get("author") or {})
        uid = auteur.get("uniqueId")
        if not uid:
            continue
        stats = (v.get("stats") or {})
        tekst = (v.get("text") or "").lower()
        c = per_creator[uid]
        c["videos"] += 1
        c["views"] += int(stats.get("playCount") or 0)
        c["likes"] += int(stats.get("diggCount") or 0)
        c["verkoop"] += tel(tekst, VERKOOP)
        c["koop"] += tel(tekst, KOOP)
        c["buiten_niche"] += tel(tekst, {w: 1 for w in BUITEN_NICHE})
        c["nickname"] = auteur.get("nickname") or c["nickname"]
        for h in (v.get("hashtags") or []):
            naam = h.get("name") if isinstance(h, dict) else h
            if naam:
                c["hashtags"].add(str(naam).lower())
        if len(c["voorbeelden"]) < 2:
            c["voorbeelden"].append((v.get("text") or "")[:160])

    resultaat = []
    for uid, c in per_creator.items():
        score = c["verkoop"] - c["koop"] - (c["buiten_niche"] * 4)
        gem_views = c["views"] // max(c["videos"], 1)
        if score > 0:
            soort = "verkoper"
        elif score < 0:
            soort = "koper"
        else:
            soort = "onduidelijk"
        resultaat.append({
            "username": uid,
            "url": f"https://www.tiktok.com/@{uid}",
            "nickname": c["nickname"],
            "soort": soort,
            "score": score,
            "videos_in_sweep": c["videos"],
            "views_totaal": c["views"],
            "views_gemiddeld": gem_views,
            "likes_totaal": c["likes"],
            "hashtags": sorted(c["hashtags"])[:15],
            "voorbeelden": c["voorbeelden"],
        })

    # Rangschikken: eerst of het een verkoper is, dan op gemiddeld bereik.
    resultaat.sort(key=lambda r: (r["soort"] != "verkoper", -r["score"], -r["views_gemiddeld"]))

    UIT.mkdir(parents=True, exist_ok=True)
    pad = UIT / "creators_tiktok.json"
    pad.write_text(json.dumps(resultaat, ensure_ascii=False, indent=2))

    # Voor het benaderen zelf telt bereik zwaarder dan de verkoopscore: iemand
    # die 50 keer "te koop" zegt tegen 400 kijkers levert niets op.
    csv_pad = UIT / "creators_tiktok.csv"
    op_bereik = sorted(
        [r for r in resultaat if r["soort"] == "verkoper"],
        key=lambda r: -r["views_gemiddeld"],
    )
    with csv_pad.open("w", newline="", encoding="utf-8") as f:
        schrijver = csv.writer(f)
        schrijver.writerow(["username", "naam", "tiktok_url", "gem_views", "totaal_views",
                            "likes", "videos_in_sweep", "verkoopscore", "benaderd_op",
                            "reactie", "code"])
        for r in op_bereik:
            schrijver.writerow([r["username"], r["nickname"], r["url"], r["views_gemiddeld"],
                                r["views_totaal"], r["likes_totaal"], r["videos_in_sweep"],
                                r["score"], "", "", ""])
    print(f"geschreven naar {csv_pad}")

    verkopers = [r for r in resultaat if r["soort"] == "verkoper"]
    kopers = [r for r in resultaat if r["soort"] == "koper"]
    onduidelijk = [r for r in resultaat if r["soort"] == "onduidelijk"]
    print(f"\nunieke creators: {len(resultaat)}")
    print(f"  verkopers (doelgroep): {len(verkopers)}")
    print(f"  kopers (afvallers):    {len(kopers)}")
    print(f"  onduidelijk:           {len(onduidelijk)}")
    print(f"\ngeschreven naar {pad}")

    print("\n=== TOP 40 VERKOPERS ===")
    for r in verkopers[:40]:
        print(f"  {r['views_gemiddeld']:>9,} gem.views  score {r['score']:>3}  "
              f"{r['videos_in_sweep']:>2}v  @{r['username']}  ({r['nickname']})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
