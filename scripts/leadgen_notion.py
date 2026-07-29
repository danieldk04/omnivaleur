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


def _properties(lead: dict) -> dict:
    notes = " · ".join(x for x in [
        f"{lead.get('followers') or 0} volgers",
        lead.get("verkopertype"),
        f"gevonden via {lead.get('source') or lead.get('method')}",
        lead.get("website"), lead.get("email"), lead.get("reden"),
    ] if x)
    props = {
        "Name": {"title": [{"text": {"content": lead.get("full_name") or lead["handle"]}}]},
        "URL": {"url": lead["ig_url"]},
        "Platform": {"select": {"name": "IG"}},
        "Language": {"select": {"name": lead.get("language", "NL")}},
        "Status": {"status": {"name": "Reach out"}},
        "Je/Jullie": {"select": {"name": lead.get("je_jullie", "Je")}},
        "Notes (Optional)": {"rich_text": [{"text": {"content": notes[:1900]}}]},
    }
    for key, prop in (("verkoopt_vooral", "Verkoopt vooral..."),
                      ("verkoop_op", "Verkoop op...")):
        if lead.get(key):
            props[prop] = {"select": {"name": lead[key]}}
    return props


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
            print(f"  + @{lead['handle']}")
        except Exception as e:  # noqa: BLE001 — één afgekeurde lead mag de rest niet stoppen
            print(f"  ! @{lead['handle']}: {e}")
    return created, skipped
