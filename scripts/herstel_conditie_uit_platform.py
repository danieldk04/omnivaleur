#!/usr/bin/env python3
"""
De staat ("Nieuw" / "Zo goed als nieuw" / "Gebruikt") van artikelen rechtzetten
aan de hand van de eigen, openbare advertenties van de verkoper.

WAAROM DIT BESTAAT (10-09-2026, Egbert Brouwer / Papa's Plectrums)
Zijn woorden: "Alle listings die gelukt zijn staan nu te boek als bijna nieuw,
dit klopt natuurlijk niet." Hij verkoopt nieuwe plectrums en miniatuurgitaren.

Wat er gebeurde: bij het importeren komt de staat mee van het platform. Kwam er
niets mee, dan vulde de import "good" in — en "good" is bij ons "Zo goed als
nieuw". Dat is geen leeg veld maar een verzonnen uitspraak over de goederen, en
juist daardoor zag niemand het: een gevuld veld wordt door elke verrijkronde
overgeslagen ("alleen aanvullen wat leeg is").

Het platform wéét het wel. De openbare zoek-API geeft bij elk zoekresultaat de
kenmerken mee, honderd advertenties per aanvraag:
    "attributes":[{"key":"condition","value":"Nieuw", ...}]
Die uitspraak is van de verkoper zelf. Onze "good" was een gok van ons. Daarom
wint het platform, maar ALLEEN van die gok: staat er bij ons iets anders dan de
standaardwaarde, dan heeft iemand hem bewust gezet en blijft hij staan.

Zonder --apply verandert dit script niets en laat het alleen zien wat het zou doen.

Gebruik:
    python3 scripts/herstel_conditie_uit_platform.py --user info@papas-plectrums.nl
    python3 scripts/herstel_conditie_uit_platform.py --user info@... --apply
    python3 scripts/herstel_conditie_uit_platform.py --user info@... --platform 2dehands
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx  # noqa: E402

BROK = 200


def _gebruiker_id(db, wie: str) -> str:
    """Een e-mailadres of een user-id naar het user-id van de verkoper."""
    if "@" not in wie:
        return wie
    pagina = 1
    while True:
        rij = db.auth.admin.list_users(page=pagina, per_page=200)
        if not rij:
            break
        for u in rij:
            if (u.email or "").lower() == wie.lower():
                return u.id
        if len(rij) < 200:
            break
        pagina += 1
    raise SystemExit(f"Geen account gevonden voor {wie}")


async def _hoofd(wie: str, platform: str, toepassen: bool) -> int:
    from backend.database import get_db, fetch_all
    from backend.services import mp_enrich as mp

    db = get_db()
    user_id = _gebruiker_id(db, wie)

    zoek_url, basis = mp.ZOEK_PER_PLATFORM[platform]
    items = fetch_all(lambda: db.table("items")
                      .select("id,title,condition").eq("user_id", user_id),
                      page_size=1000)
    print(f"{len(items)} artikelen van {wie} ({user_id})")
    print("staat nu:", dict(collections.Counter(i.get("condition") for i in items)))

    op_titel: dict[str, list[dict]] = collections.defaultdict(list)
    for i in items:
        op_titel[mp._sleutel(i.get("title") or "")].append(i)

    limiet = httpx.Limits(max_connections=mp.TEGELIJK, max_keepalive_connections=mp.TEGELIJK)
    async with httpx.AsyncClient(timeout=40, headers={"User-Agent": mp.UA},
                                 follow_redirects=True, limits=limiet) as client:
        titels = [i["title"] for i in items[:: max(1, len(items) // mp.MAX_TITELPOGINGEN)] if i.get("title")]
        vid = await mp.zoek_verkoper_id(client, titels, zoek_url=zoek_url)
        if not vid:
            raise SystemExit(f"Verkopersnummer op {platform} niet gevonden — staan de advertenties er nog?")
        print(f"verkopersnummer op {platform}: {vid}")
        # Geen tijdsbudget: dit is een reparatie die één keer draait, geen
        # verzoek waar iemand op wacht.
        adv = await mp.haal_advertenties(client, vid, deadline=None,
                                         zoek_url=zoek_url, basis=basis)
    print(f"{len(adv)} advertenties met een unieke titel opgehaald")

    plan: list[tuple[str, str, str, str]] = []   # id, titel, van, naar
    geen_advertentie = 0
    bewust_gezet = 0
    for sleutel, groep in op_titel.items():
        a = adv.get(sleutel)
        if not a:
            geen_advertentie += len(groep)
            continue
        for item in groep:
            patch = mp._conditie_correctie(item, a)
            if not patch:
                nu = str(item.get("condition") or "").strip().lower()
                if nu and nu != mp._CONDITIE_STANDAARD:
                    bewust_gezet += 1
                continue
            plan.append((item["id"], item.get("title") or "", item.get("condition") or "",
                         patch["condition"]))

    print(f"\n{len(plan)} artikelen krijgen een andere staat")
    print(f"{geen_advertentie} artikelen hebben geen advertentie op {platform} (met rust gelaten)")
    print(f"{bewust_gezet} artikelen staan al op iets anders dan de standaardwaarde (met rust gelaten)")
    print("verandering:", dict(collections.Counter(f"{v} -> {n}" for _, _, v, n in plan)))
    for _, titel, v, n in plan[:8]:
        print(f"   {v} -> {n}  {titel[:60]}")

    if not toepassen:
        print("\nNiets gewijzigd. Draai met --apply om het echt te doen.")
        return 0

    from backend.database import execute_with_retry
    per_doel: dict[str, list[str]] = collections.defaultdict(list)
    for iid, _, _, naar in plan:
        per_doel[naar].append(iid)
    gedaan = 0
    for naar, ids in per_doel.items():
        for i in range(0, len(ids), BROK):
            execute_with_retry(db.table("items").update({"condition": naar})
                               .eq("user_id", user_id).in_("id", ids[i:i + BROK]))
            gedaan += len(ids[i:i + BROK])
    print(f"\n{gedaan} artikelen bijgewerkt.")
    na = fetch_all(lambda: db.table("items").select("condition").eq("user_id", user_id),
                   page_size=1000)
    print("staat nu:", dict(collections.Counter(i.get("condition") for i in na)))
    return gedaan


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True, help="e-mailadres of user-id van de verkoper")
    p.add_argument("--platform", default="marktplaats", choices=["marktplaats", "2dehands"])
    p.add_argument("--apply", action="store_true", help="de wijzigingen echt wegschrijven")
    a = p.parse_args()
    if not os.environ.get("SUPABASE_KEY"):
        raise SystemExit("SUPABASE_KEY ontbreekt — draai dit met de service-sleutel.")
    asyncio.run(_hoofd(a.user, a.platform, a.apply))


if __name__ == "__main__":
    main()
