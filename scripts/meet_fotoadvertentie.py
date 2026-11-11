#!/usr/bin/env python3
"""Meting: kan een model uit één foto de velden van een advertentie invullen?

Gratis, over meerdere dagen uitgesmeerd (besluit Daniel 11-11-2026). De gratis laag
van Gemini laat voor het sterke model 20 aanvragen per dag toe, dus elke dag komt er
een brokje van BROK artikelen bij, tot de steekproef (STEEKPROEF) af is.

  meet_fotoadvertentie.py dag            vandaag een brok verwerken (voor de planner)
  meet_fotoadvertentie.py samenvatting   toont de stand van zaken

Leest alleen (artikelen en foto's, per klant). Schrijft naar ~/.omnivaleur/meting_foto/.
Maakt nooit iets aan in de echte database en belooft niets aan klanten.
"""
from __future__ import annotations

import ast
import base64
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DIR = Path.home() / ".omnivaleur" / "meting_foto"
SLEUTEL = Path.home() / ".omnivaleur" / "gemini-gratis.txt"
MODELLEN = ("gemini-3.5-flash", "gemini-3.1-flash-lite")
STEEKPROEF = 110
PER_KLANT = 10
BROK = 18          # onder de 20 per dag van de gratis laag
WINKELNAAM_DREMPEL = 0.30   # een "merk" dat zo vaak voorkomt is de winkelnaam, geen merk

KLEUREN = {
    "zwart": "zwart", "black": "zwart", "wit": "wit", "white": "wit", "grijs": "grijs", "grey": "grijs",
    "gray": "grijs", "bruin": "bruin", "brown": "bruin", "beige": "beige", "creme": "beige", "cream": "beige",
    "rood": "rood", "red": "rood", "burgundy": "rood", "bordeaux": "rood", "roze": "roze", "pink": "roze",
    "oranje": "oranje", "orange": "oranje", "geel": "geel", "yellow": "geel", "groen": "groen",
    "green": "groen", "blauw": "blauw", "blue": "blauw", "navy": "blauw", "paars": "paars",
    "purple": "paars", "goud": "goud", "goudkleur": "goud", "gold": "goud", "zilver": "zilver",
    "zilverkleur": "zilver", "silver": "zilver", "meerkleurig": "multi", "multi": "multi",
    "multicolor": "multi", "various": "multi", "diverse": "multi",
}
GEEN_MAAT = {"", "none", "overige", "eén maat", "een maat", "one size", "onesize", "os"}
PROMPT = (
    "Look at this photo of a second-hand item for sale. Return ONLY JSON with keys: "
    '"type" (short Dutch product name), "brand" (only if you can read it on a label or logo, else null), '
    '"color" (one Dutch word from: zwart, wit, grijs, bruin, beige, rood, roze, oranje, geel, groen, '
    'blauw, paars, goud, zilver, multi), "size" (only if a size label is readable, else null), '
    '"material" (Dutch, or null). Never guess a brand or size.'
)


def kleur(tekst) -> str | None:
    for w in re.findall(r"[a-zë]+", (tekst or "").lower()):
        if w in KLEUREN:
            return KLEUREN[w]
    return None


def is_maat(tekst) -> bool:
    return (tekst or "").strip().lower() not in GEEN_MAAT


def winkelmerken(artikelen: list[dict]) -> dict[str, set[str]]:
    """Per klant de 'merken' die zo vaak voorkomen dat het zijn winkelnaam is."""
    uit: dict[str, set[str]] = {}
    per: dict[str, list[str]] = {}
    for a in artikelen:
        per.setdefault(a["uid"], []).append((a.get("brand") or "").strip().lower())
    for uid, lijst in per.items():
        n = len(lijst) or 1
        uit[uid] = {m for m in set(lijst) if m and m != "none" and lijst.count(m) / n >= WINKELNAAM_DREMPEL}
    return uit


def beoordeel(gt: dict, ai: dict, winkel: set[str]) -> dict:
    """Per veld: True/False als er iets te beoordelen valt, anders None."""
    uit = {}
    k = kleur(gt.get("color"))
    uit["kleur"] = (k == kleur(ai.get("color"))) if k else None
    merk = (gt.get("brand") or "").strip().lower()
    echt_merk = merk and merk != "none" and merk not in winkel
    ai_merk = (ai.get("brand") or "").strip().lower()
    uit["merk"] = (ai_merk == merk) if echt_merk else None
    uit["merk_verzonnen"] = bool(ai_merk) if not echt_merk and merk in ("", "none") else None
    maat = (gt.get("size") or "").strip().lower()
    uit["maat"] = (str(ai.get("size") or "").strip().lower() == maat) if is_maat(maat) else None
    uit["maat_verzonnen"] = bool(ai.get("size")) if not is_maat(maat) else None
    return uit


# ── Steekproef ──────────────────────────────────────────────────────────────

def maak_steekproef() -> list[dict]:
    from backend.database import get_db
    d = get_db()
    random.seed(11)
    subs = d.table("subscriptions").select("user_id").in_("status", ["active"]).execute().data or []
    artikelen = []
    for s in subs:                      # per klant, nooit over meerdere klanten heen
        rijen = (d.table("items").select("id,title,brand,size,color,photo_urls")
                 .eq("user_id", s["user_id"]).order("created_at", desc=True).limit(400).execute().data or [])
        goed = [r for r in rijen if r.get("photo_urls") and r.get("color") and r["color"] != "None"]
        random.shuffle(goed)
        artikelen += [dict(r, uid=s["user_id"][:8]) for r in goed[:PER_KLANT]]
    random.shuffle(artikelen)
    return artikelen[:STEEKPROEF]


def eerste_foto(a: dict) -> str | None:
    u = a.get("photo_urls")
    try:
        u = ast.literal_eval(u) if isinstance(u, str) else u
        return u[0] if u else None
    except Exception:
        return None


def vraag_model(model: str, foto: bytes, mime: str, sleutel: str) -> tuple[dict | None, str]:
    body = {"contents": [{"parts": [{"text": PROMPT},
                                    {"inline_data": {"mime_type": mime, "data": base64.b64encode(foto).decode()}}]}],
            "generationConfig": {"maxOutputTokens": 800, "responseMimeType": "application/json"}}
    q = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(), headers={"x-goog-api-key": sleutel, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(q, timeout=90) as f:
            b = json.loads(f.read())
        return json.loads(b["candidates"][0]["content"]["parts"][-1]["text"]), "ok"
    except urllib.error.HTTPError as e:
        return None, f"http{e.code}"
    except Exception as e:
        return None, type(e).__name__


def dag() -> int:
    DIR.mkdir(parents=True, exist_ok=True)
    manifest = DIR / "steekproef.json"
    if not manifest.exists():
        manifest.write_text(json.dumps(maak_steekproef(), ensure_ascii=False))
    artikelen = json.loads(manifest.read_text())
    uitslag = DIR / "resultaten.jsonl"
    klaar = {json.loads(r)["id"] for r in uitslag.read_text().splitlines()} if uitslag.exists() else set()
    sleutel = SLEUTEL.read_text().strip()
    gedaan = 0
    for a in artikelen:
        if a["id"] in klaar:
            continue
        if gedaan >= BROK:
            break
        url = eerste_foto(a)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as f:
                foto, mime = f.read(), (f.headers.get("Content-Type") or "image/jpeg").split(";")[0]
        except Exception as e:
            print("foto niet te halen:", a["id"], type(e).__name__)
            klaar.add(a["id"])
            with uitslag.open("a") as fh:
                fh.write(json.dumps({"id": a["id"], "uid": a["uid"], "fout": "foto"}) + "\n")
            continue
        res = {}
        for model in MODELLEN:
            ai, status = vraag_model(model, foto, mime, sleutel)
            if status == "http429":
                print(f"{model}: daglimiet bereikt, morgen verder")
                return 0
            res[model] = ai if status == "ok" else {"fout": status}
            time.sleep(1)
        gt = {k: a.get(k) for k in ("title", "brand", "size", "color")}
        with uitslag.open("a") as fh:
            fh.write(json.dumps({"id": a["id"], "uid": a["uid"], "datum": str(date.today()), "gt": gt, "ai": res},
                                ensure_ascii=False) + "\n")
        gedaan += 1
    klaar_n = sum(1 for _ in uitslag.open()) if uitslag.exists() else 0
    print(f"vandaag {gedaan} artikelen, totaal {klaar_n} van {len(artikelen)}")
    if klaar_n >= len(artikelen):
        samenvatting()
    return 0


def samenvatting() -> int:
    manifest, uitslag = DIR / "steekproef.json", DIR / "resultaten.jsonl"
    if not uitslag.exists():
        print("nog geen resultaten")
        return 0
    artikelen = json.loads(manifest.read_text())
    winkel = winkelmerken(artikelen)
    rijen = [json.loads(r) for r in uitslag.read_text().splitlines()]
    regels = [f"Gemeten artikelen: {len(rijen)} van {len(artikelen)} (foto niet te halen: "
              f"{sum(1 for r in rijen if r.get('fout'))})"]
    for model in MODELLEN:
        tel: dict[str, list[int]] = {}
        antwoorden = 0
        for r in rijen:
            ai = (r.get("ai") or {}).get(model)
            if not ai or "fout" in ai:
                continue
            antwoorden += 1
            for veld, waarde in beoordeel(r["gt"], ai, winkel.get(r["uid"], set())).items():
                if waarde is not None:
                    tel.setdefault(veld, []).append(int(waarde))
        regels.append(f"\n{model}: {antwoorden} antwoorden")
        namen = {"kleur": "kleur gelijk aan verkoper", "merk": "merk gelijk (waar verkoper echt merk invulde)",
                 "merk_verzonnen": "merk genoemd terwijl verkoper geen had", "maat": "maat gelijk",
                 "maat_verzonnen": "maat genoemd terwijl verkoper geen echte had"}
        for veld, naam in namen.items():
            v = tel.get(veld, [])
            regels.append(f"  {naam}: {sum(v)}/{len(v)}" + (f" = {round(100 * sum(v) / len(v))}%" if v else ""))
    tekst = "\n".join(regels)
    (DIR / "samenvatting.txt").write_text(tekst)
    print(tekst)
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "samenvatting"
    sys.exit(dag() if cmd == "dag" else samenvatting())
