#!/usr/bin/env python3
"""
One-off backfill: copy every item photo that still points at a marketplace CDN
into our own Supabase Storage bucket.

Items imported before the mirror existed kept urls like images1.vinted.net.
The extension downloads photos from the MARKETPLACE page's origin, and Vinted's
CDN refuses that origin, so those items publish to Marktplaats/2dehands without
a single photo. New imports are mirrored automatically (see
backend/services/photo_mirror.py); this fixes the ones already in the database.

Safe to re-run: an already-mirrored url is skipped, and a photo that can't be
copied keeps its original url.

Usage:
    python3 scripts/backfill_mirror_photos.py            # every user
    python3 scripts/backfill_mirror_photos.py --dry-run  # show what would change
    python3 scripts/backfill_mirror_photos.py --user <user_id>
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--user", default=None, help="Only this user_id")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N items (0 = all)")
    args = ap.parse_args()

    from backend.database import get_db
    from backend.services.photo_mirror import mirror_photos, is_mirrored

    db = get_db()
    q = db.table("items").select("id,user_id,title,photo_urls")
    if args.user:
        q = q.eq("user_id", args.user)
    items = q.execute().data or []

    todo = [
        it for it in items
        if any(isinstance(u, str) and u.startswith("http") and not is_mirrored(u)
               for u in (it.get("photo_urls") or []))
    ]
    if args.limit:
        todo = todo[: args.limit]

    print(f"{len(items)} items, {len(todo)} with photos still on an external CDN")
    if args.dry_run:
        for it in todo[:20]:
            external = [u for u in it["photo_urls"] if not is_mirrored(u)]
            print(f"  {it['id']}  {(it.get('title') or '')[:50]:50s}  {len(external)} photo(s)")
        if len(todo) > 20:
            print(f"  … and {len(todo) - 20} more")
        return

    moved = failed = 0
    for i, it in enumerate(todo, 1):
        before = it.get("photo_urls") or []
        after = await mirror_photos(before, it["user_id"])
        changed = sum(1 for a, b in zip(before, after) if a != b)
        if changed:
            db.table("items").update({"photo_urls": after}).eq("id", it["id"]).execute()
            moved += changed
        failed += sum(1 for u in after if not is_mirrored(u) and u.startswith("http"))
        print(f"[{i}/{len(todo)}] {it['id']}: {changed}/{len(before)} photo(s) mirrored")

    print(f"\nDone. {moved} photo(s) copied to our storage, {failed} still external "
          f"(source refused the download — those items need their photos re-added by hand).")


if __name__ == "__main__":
    asyncio.run(main())
