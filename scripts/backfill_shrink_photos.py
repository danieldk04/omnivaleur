#!/usr/bin/env python3
"""
Backfill: re-save the photos already in the bucket at a sane size.

New photos are shrunk on the way in (backend/services/image_optimize.py), but
the 3400 photos already stored average 724 KB — together 2.5 GB against a 1 GB
free plan. This walks the existing items and replaces each photo with its
optimised version.

SAFETY — the old photo is never destroyed by this script:

  * A photo is only swapped after its optimised copy is uploaded AND the item
    row points at the new url. Any failure at any step leaves the item exactly
    as it was, still pointing at the original.
  * The old object stays in the bucket. It simply becomes unreferenced, so
    cleanup_orphan_photos.py removes it on a later run — which means there is a
    window in which you can still roll back.
  * One item is written at a time. An interrupted run leaves finished items done
    and untouched items untouched; re-running continues where it left off.
  * Dry-run by default.

TRAFFIC — reading a photo back out of Supabase counts as egress, and egress is
part of what is already over quota. --budget-mb caps how much this run may
download (default 400 MB) so the job can be spread over several days or run
after the billing cycle resets.

Usage:
    python3 scripts/backfill_shrink_photos.py                     # report only
    python3 scripts/backfill_shrink_photos.py --apply
    python3 scripts/backfill_shrink_photos.py --apply --budget-mb 1000
    python3 scripts/backfill_shrink_photos.py --apply --user <user_id>
"""
import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PAGE = 1000
TIMEOUT = 60.0


def _paged(query_factory):
    rows, start = [], 0
    while True:
        chunk = query_factory().range(start, start + PAGE - 1).execute().data or []
        rows.extend(chunk)
        if len(chunk) < PAGE:
            return rows
        start += PAGE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually rewrite (default: report only)")
    ap.add_argument("--user", default=None, help="only this user_id")
    ap.add_argument("--budget-mb", type=int, default=400,
                    help="stop after downloading this many MB (default 400)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N items (0 = all)")
    args = ap.parse_args()

    import httpx
    from backend.database import get_db
    from backend.services.image_optimize import optimize_image
    from backend.services.image_upload import BUCKET, upload_image_sync, storage_path_from_url

    db = get_db()
    budget = args.budget_mb * 1024 * 1024

    q = (lambda: db.table("items").select("id,user_id,title,photo_urls")) if not args.user else \
        (lambda: db.table("items").select("id,user_id,title,photo_urls").eq("user_id", args.user))
    items = [it for it in _paged(q) if it.get("photo_urls")]
    if args.limit:
        items = items[: args.limit]

    print(f"{len(items)} items with photos"
          + (f" (user {args.user})" if args.user else "")
          + f", download budget {args.budget_mb} MB"
          + ("" if args.apply else "  — DRY RUN, nothing is written"))

    gelezen = bespaard = 0
    aangepast = fotos = mislukt = 0

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        for it in items:
            if gelezen >= budget:
                print(f"\nBudget of {args.budget_mb} MB reached — stopping here. "
                      f"Re-run later to continue.")
                break

            oud = list(it["photo_urls"])
            nieuw = list(oud)
            veranderd = False

            for i, url in enumerate(oud):
                if gelezen >= budget:
                    break
                if not storage_path_from_url(url):
                    continue  # external CDN url — leave it to the mirror
                try:
                    r = client.get(url)
                    if r.status_code != 200 or not r.content:
                        continue
                    data = r.content
                    gelezen += len(data)

                    ext = (url.rsplit(".", 1)[-1].split("?")[0] or "jpg").lower()
                    klein, ext_uit = optimize_image(data, ext)
                    if len(klein) >= len(data) * 0.9:
                        continue  # not worth a rewrite

                    if args.apply:
                        digest = hashlib.sha256(klein).hexdigest()[:32]
                        pad = f"{it['user_id']}/shrunk/{digest}.{ext_uit}"
                        nieuw[i] = upload_image_sync(klein, pad)
                    bespaard += len(data) - len(klein)
                    fotos += 1
                    veranderd = True
                except Exception as e:  # noqa: BLE001 - keep the original url
                    mislukt += 1
                    print(f"  ! {it['id']} photo {i}: {e}")

            if veranderd and args.apply:
                try:
                    # Only now does the item start pointing at the new photos.
                    # Until this line lands, nothing about the item has changed.
                    db.table("items").update({"photo_urls": nieuw}).eq("id", it["id"]).execute()
                    aangepast += 1
                except Exception as e:  # noqa: BLE001
                    mislukt += 1
                    print(f"  ! could not update item {it['id']}: {e} — photos left as they were")
            elif veranderd:
                aangepast += 1

            if aangepast and aangepast % 25 == 0:
                print(f"  {aangepast} items, {bespaard / 1e9:.2f} GB saved so far "
                      f"({gelezen / 1e6:.0f} MB downloaded)")

    print(f"\n{'Rewrote' if args.apply else 'Would rewrite'} {fotos} photos across {aangepast} items")
    print(f"  downloaded : {gelezen / 1e6:.0f} MB")
    print(f"  storage    : {bespaard / 1e9:.2f} GB {'freed' if args.apply else 'reclaimable'}")
    if mislukt:
        print(f"  failures   : {mislukt} (those photos were left untouched)")
    if args.apply:
        print("\nThe old objects are still in the bucket, now unreferenced. Run\n"
              "  python3 scripts/cleanup_orphan_photos.py --apply\n"
              "in a few days to actually reclaim the space.")
    else:
        print("\nDry run — re-run with --apply to write the changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
