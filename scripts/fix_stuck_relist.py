#!/usr/bin/env python3
"""
One-off: repair a single Vinted relist record that was marked "Relist failed —
still live" while the item had actually been recreated (Vinted's "check in
progress" review delayed the redirect, so the extension timed out). The new
listing is live under a known Vinted id; this reconciles the dashboard record to
it so future sold-detection/delete targets the right listing, clears the error,
and cancels any leftover create/delete jobs so nothing later duplicates it.

Read-only unless --apply is passed.

Usage:
    python3 scripts/fix_stuck_relist.py                 # show what it would do
    python3 scripts/fix_stuck_relist.py --apply         # actually fix it
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# The specific item this repair targets, confirmed live on Vinted (2026-07).
TITLE_MATCH = "998"                 # unique prefix in the item title
TITLE_MATCH_2 = "ralph lauren"
NEW_VINTED_ID = "9410808567"
NEW_VINTED_URL = "https://www.vinted.nl/items/9410808567"
PLATFORM = "vinted"


def main(apply: bool):
    from backend.database import get_db

    db = get_db()

    # Find the item by title (case-insensitive, both fragments must be present).
    items = db.table("items").select("id,title,user_id").execute().data or []
    matches = [
        it for it in items
        if TITLE_MATCH in (it.get("title") or "")
        and TITLE_MATCH_2 in (it.get("title") or "").lower()
    ]
    if not matches:
        print(f"No item found whose title contains '{TITLE_MATCH}' and '{TITLE_MATCH_2}'.")
        return
    if len(matches) > 1:
        print("Multiple items matched — refusing to guess. Matches:")
        for it in matches:
            print(f"  {it['id']}  {it['title']!r}")
        return

    item = matches[0]
    item_id = item["id"]
    print(f"Item: {item_id}  {item['title']!r}")

    # The Vinted listing row for this item.
    listings = (
        db.table("listings")
        .select("*")
        .eq("item_id", item_id)
        .eq("platform", PLATFORM)
        .execute()
        .data
        or []
    )
    if not listings:
        print("No Vinted listing row for this item — nothing to reconcile.")
        return
    for l in listings:
        print(f"  listing {l['id']}: status={l.get('status')} "
              f"vinted_id={l.get('platform_listing_id')} err={(l.get('error_message') or '')[:60]!r}")

    # Leftover jobs that could still act on this item (create would duplicate,
    # delete would remove the now-live listing).
    jobs = (
        db.table("jobs")
        .select("id,action,status,scheduled_for")
        .eq("item_id", item_id)
        .eq("platform", PLATFORM)
        .in_("status", ["pending", "claimed", "error"])
        .execute()
        .data
        or []
    )
    for j in jobs:
        print(f"  job {j['id']}: {j['action']} status={j['status']}")

    if not apply:
        print("\n(dry-run) Would set the listing to active, link it to "
              f"{NEW_VINTED_ID}, clear the error, and cancel {len(jobs)} job(s). "
              "Re-run with --apply.")
        return

    for l in listings:
        db.table("listings").update({
            "status": "active",
            "platform_listing_id": NEW_VINTED_ID,
            "platform_listing_url": NEW_VINTED_URL,
            "error_message": None,
        }).eq("id", l["id"]).execute()
        print(f"  ✓ listing {l['id']} reconciled → {NEW_VINTED_ID}, active, error cleared")

    for j in jobs:
        db.table("jobs").update({"status": "cancelled"}).eq("id", j["id"]).execute()
        print(f"  ✓ job {j['id']} ({j['action']}) cancelled")

    print("\nDone.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
