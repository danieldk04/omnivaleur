#!/usr/bin/env python3
"""Leert uit data/social/gedaan.jsonl welke reacties bereik kregen.

Elke regel is een reactie. Metingen staan op dezelfde regel (velden likes, antwoorden,
weergaven, zichtbaar, positie, meting_datum) of als aparte regel met "meting": true en
dezelfde "url" en "tekst". Het script telt per kenmerk (platform, cat, lengte, vraag,
slordig, openingstype, leeftijd van de post, uur) de gemiddelde score en zet de uitkomst
in het blok AUTOMATISCHE INZICHTEN onderaan data/social/lessen.md.

Score = likes + 3 * antwoorden + (5 als bovenaan) - (10 als verborgen of verwijderd).
Gebruik:  python3 scripts/social_leren.py [--schrijf]
"""
import json, sys, statistics, collections, re, pathlib

BASIS = pathlib.Path(__file__).resolve().parent.parent / "data" / "social"
MARKER = "## AUTOMATISCHE INZICHTEN"


def lees():
    rijen = {}
    for lijn in (BASIS / "gedaan.jsonl").read_text(encoding="utf-8").splitlines():
        lijn = lijn.strip()
        if not lijn:
            continue
        try:
            d = json.loads(lijn)
        except ValueError:
            continue
        if d.get("status") == "klaargezet":
            continue
        sleutel = (d.get("platform"), d.get("url"), (d.get("tekst") or "")[:60])
        basis = rijen.setdefault(sleutel, {})
        basis.update({k: v for k, v in d.items() if v not in (None, "")})
    return [r for r in rijen.values() if r.get("tekst")]


def score(r):
    if "likes" not in r and "antwoorden" not in r and "weergaven" not in r:
        return None
    s = float(r.get("likes", 0)) + 3 * float(r.get("antwoorden", 0))
    if "bovenaan" in str(r.get("positie", "")):
        s += 5
    if r.get("zichtbaar") is False:
        s -= 10
    return s


def kenmerken(r):
    t = r["tekst"]
    woorden = len(t.split())
    k = {
        "platform": r.get("platform", "?"),
        "cat": r.get("cat", "?"),
        "lengte": "kort (<=20 woorden)" if woorden <= 20 else "middel (21-40)" if woorden <= 40 else "lang (>40)",
        "eindigt op vraag": "ja" if t.rstrip().endswith("?") else "nee",
        "slordig": "ja" if re.search(r"\b(iig|pb|haha|imo|w/)\b|^[a-z]", t) else "nee",
        "opent met korte reactie": "ja" if re.match(r"^(\w+\W+){0,3}(hoor|haha|pfff|ja|nee|eerlijk|herkenbaar|lekker)", t, re.I) else "nee",
    }
    if "post_leeftijd_min" in r:
        m = float(r["post_leeftijd_min"])
        k["post leeftijd"] = "<60 min" if m < 60 else "1 tot 6 uur" if m < 360 else ">6 uur"
    if "variant" in r:
        k["variant"] = r["variant"]
    return k


def main():
    rijen = lees()
    gemeten = [(r, score(r)) for r in rijen]
    gemeten = [(r, s) for r, s in gemeten if s is not None]
    regels = [f"{MARKER} (gemeten {len(gemeten)} van {len(rijen)} reacties, script scripts/social_leren.py)"]
    if len(gemeten) < 10:
        regels.append(f"- Nog te weinig metingen ({len(gemeten)}; vanaf 10 komen hier uitkomsten). Blijf elke ronde 24 uur oude reacties meten.")
    else:
        groepen = collections.defaultdict(list)
        for r, s in gemeten:
            for naam, waarde in kenmerken(r).items():
                groepen[(naam, waarde)].append(s)
        gemiddeld = statistics.mean(s for _, s in gemeten)
        regels.append(f"- Gemiddelde score alle reacties: {gemiddeld:.1f} (likes + 3 per antwoord + 5 bovenaan).")
        uitkomst = []
        for (naam, waarde), lijst in groepen.items():
            if len(lijst) >= 4:
                uitkomst.append((statistics.mean(lijst) - gemiddeld, naam, waarde, len(lijst), statistics.mean(lijst)))
        uitkomst.sort(reverse=True)
        for verschil, naam, waarde, n, gem in [u for u in uitkomst if u[0] > 0.5][:5]:
            regels.append(f"- Beter dan gemiddeld: {naam} = {waarde} (n={n}, score {gem:.1f}, {verschil:+.1f}). Doe dit vaker.")
        for verschil, naam, waarde, n, gem in uitkomst[-3:]:
            if verschil < -0.5:
                regels.append(f"- Slechter dan gemiddeld: {naam} = {waarde} (n={n}, score {gem:.1f}, {verschil:+.1f}). Doe dit minder.")
        regels.append("- 80% van de reacties volgt de beste vorm, 20% is een bewuste proef (zet dan veld variant in gedaan.jsonl).")
    tekst = "\n".join(regels) + "\n"
    print(tekst)
    if "--schrijf" in sys.argv:
        pad = BASIS / "lessen.md"
        inhoud = pad.read_text(encoding="utf-8")
        if MARKER in inhoud:
            inhoud = inhoud[: inhoud.index(MARKER)].rstrip() + "\n\n"
        else:
            inhoud = inhoud.rstrip() + "\n\n"
        pad.write_text(inhoud + tekst, encoding="utf-8")
        print("geschreven in", pad)


if __name__ == "__main__":
    main()
