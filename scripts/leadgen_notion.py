"""
Wegschrijven van gekwalificeerde leads naar de Notion-Leadlist.

Losgetrokken van de pijplijn omdat het een andere zorg is: de trechter beslist WIE
een lead is, dit bestand alleen HOE die in Notion terechtkomt. De AI-autofill in
Notion schrijft daarna zelf de outreach-tekst.

Vereist NOTION_TOKEN, en de integratie moet aan de Leadlist gekoppeld zijn
(database → ··· → Connections). Zonder die tweede stap geeft de API "not found"
terwijl de token gewoon geldig is.
"""
from __future__ import annotations

NOTION_DB = "399b0954-fb72-8053-a8fc-fa7c21616371"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def call(method: str, path: str, token: str, body: dict | None = None) -> dict:
    import httpx

    r = httpx.request(
        method, f"{NOTION_API}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        json=body, timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def existing_urls(token: str) -> set[str]:
    """Wat al in de Leadlist staat, ook handmatig toegevoegd. Zonder deze check
    krijgt iemand bij een tweede run een tweede DM."""
    urls: set[str] = set()
    cursor = None
    while True:
        body: dict = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = call("POST", f"/databases/{NOTION_DB}/query", token, body)
        for page in data.get("results", []):
            url = (page.get("properties", {}).get("URL") or {}).get("url")
            if url:
                urls.add(url.rstrip("/").lower())
        if not data.get("has_more"):
            return urls
        cursor = data["next_cursor"]


# De namen hieronder zijn overgenomen uit de LIVE database (2026-08-10). Notion
# weigert een hele pagina zodra er één onbekende kolomnaam in staat, dus een
# hernoemde kolom betekent niet "dat veld blijft leeg" maar "er komt niets binnen".
# De vorige versie schreef naar "Notes (Optional)", "Verkoopt vooral..." en
# "Verkoop op..." — geen van drieën bestaat nog.
MULTI = {
    "Verkoopt": {"Kleding", "Vintage kleding", "Hoogwaardige vintage",
                 "Antieke vintage", "Vintage interieur", "Meubilair", "Sieraden",
                 "Knutselmaterialen", "Alles"},
    "Verkoopt op": {"Vinted", "Marktplaats", "Instagram", "Etsy", "Eigen website",
                    "Fysieke winkel", "Onbekend"},
}


def _multi(prop: str, value: str) -> dict | None:
    """"Vinted en eigen website" is één antwoord maar twee opties. Alles wat niet
    in de database bestaat laten we weg in plaats van het aan te maken — anders
    groeit de kolom vol met varianten van hetzelfde."""
    parts = [p.strip() for p in str(value).replace(" en ", ",").split(",")]
    names = [{"name": p} for p in parts if p in MULTI[prop]]
    return {"multi_select": names} if names else None


def _properties(lead: dict) -> dict:
    notes = " · ".join(str(x) for x in [
        f"{lead['followers']} volgers" if lead.get("followers") else "",
        f"{lead['ads']} advertenties" if lead.get("ads") else "",
        lead.get("verkopertype"),
        f"gevonden via {lead.get('source') or lead.get('method')}",
        lead.get("website"), lead.get("email"), lead.get("tel"),
        f"KvK {lead['kvk']}" if lead.get("kvk") else "",
        lead.get("reden"),
    ] if x)
    props = {
        "Name": {"title": [{"text": {"content":
                 lead.get("full_name") or lead.get("handle") or "?"}}]},
        "URL": {"url": lead["ig_url"]},
        "Platform": {"select": {"name": lead.get("platform", "IG")}},
        "Language": {"select": {"name": lead.get("language", "NL")}},
        "Status": {"status": {"name": "Reach out"}},
        "Fase": {"select": {"name": "1. Te benaderen"}},
        "Je/Jullie": {"select": {"name": lead.get("je_jullie", "Je")}},
        "Notities": {"rich_text": [{"text": {"content": notes[:1900]}}]},
        "Bron / hashtag": {"rich_text": [{"text": {"content":
                           str(lead.get("source") or lead.get("method") or "")[:200]}}]},
    }
    for key, prop in (("verkoopt_vooral", "Verkoopt"), ("verkoop_op", "Verkoopt op")):
        if lead.get(key):
            val = _multi(prop, lead[key])
            if val:
                props[prop] = val
    return props


def _label(lead: dict) -> str:
    """Instagram-leads hebben een handle, Marktplaats-leads een handelsnaam."""
    handle = lead.get("handle")
    return f"@{handle}" if handle else (lead.get("full_name") or lead.get("name") or "?")


def push_leads(leads: list[dict], token: str) -> tuple[int, int]:
    """Maak een Notion-pagina per lead. Geeft (aangemaakt, overgeslagen) terug."""
    seen = existing_urls(token)
    print(f"{len(seen)} bestaande leads in Notion, die sla ik over")

    created = skipped = 0
    for lead in leads:
        if lead["ig_url"].rstrip("/").lower() in seen:
            skipped += 1
            continue
        try:
            call("POST", "/pages", token,
                 {"parent": {"database_id": NOTION_DB}, "properties": _properties(lead)})
            created += 1
            print(f"  + {_label(lead)}")
        except Exception as e:  # noqa: BLE001 — één afgekeurde lead mag de rest niet stoppen
            print(f"  ! {_label(lead)}: {e}")
    return created, skipped
