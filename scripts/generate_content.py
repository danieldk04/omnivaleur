#!/usr/bin/env python3
"""
Draait de content-pijplijn voor het eerstvolgende pending keyword in
scripts/content_keywords.json en publiceert direct naar de database
(geen draaiende server nodig — roept backend.content.pipeline rechtstreeks aan).

Gebruik:
    python3 scripts/generate_content.py            # 1 pending item
    python3 scripts/generate_content.py --all       # alle pending items
    DRY_RUN=1 python3 scripts/generate_content.py    # research+generatie, niet opslaan

Env: vereist dezelfde .env als de backend (ANTHROPIC_API_KEY, SUPABASE_*, optioneel GOOGLE_API_KEY).
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

QUEUE_FILE = Path(__file__).parent / "content_keywords.json"


def load_queue() -> dict:
    return json.loads(QUEUE_FILE.read_text())


def save_queue(data: dict) -> None:
    QUEUE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def next_pending(data: dict) -> dict | None:
    pending = [item for item in data["queue"] if item["status"] == "pending"]
    return sorted(pending, key=lambda i: i["priority"])[0] if pending else None


async def process_item(item: dict) -> dict:
    from backend.content.pipeline import run_pipeline

    print(f"→ {item['keyword']} ({item['region']}, pillar {item['pillar']})")
    result = await run_pipeline(item["keyword"], item["region"], item["pillar"], item["slug"])
    return result


async def main():
    data = load_queue()
    run_all = "--all" in sys.argv
    dry_run = bool(os.environ.get("DRY_RUN"))

    items = [i for i in data["queue"] if i["status"] == "pending"]
    items.sort(key=lambda i: i["priority"])
    if not run_all:
        items = items[:1] if items else []

    if not items:
        print("Geen pending keywords in de wachtrij.")
        return

    for item in items:
        if dry_run:
            print(f"[DRY RUN] zou verwerken: {item['keyword']} → /{item['region']}/{'crosslisten' if item['pillar'] == 'A' else 'reseller-tools'}/{item['slug']}")
            continue

        result = await process_item(item)
        if result.get("success"):
            item["status"] = "published"
            data["published"].append({
                "keyword": item["keyword"],
                "slug": item["slug"],
                "region": item["region"],
                "pillar": item["pillar"],
                "action": result["action"],
                "url_path": result["url_path"],
                "published_at": datetime.now(timezone.utc).isoformat(),
            })
            save_queue(data)
            print(f"  ✅ {result['action']}: {result['url_path']} (interne links: {len(result.get('linked', []))})")
        else:
            print(f"  ❌ mislukt: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
