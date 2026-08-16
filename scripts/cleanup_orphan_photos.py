#!/usr/bin/env python3
"""
One-off (and safely repeatable) cleanup: delete photos in the Supabase bucket
that no longer belong to anything.

Until now nothing ever removed a photo. Every import copied its pictures into
our bucket and every deleted item left them behind, which is how the bucket grew
to 346% of the free plan while the database itself sits at 9%.

SAFETY — this script is built to refuse rather than risk a photo:

  * Dry-run by default. Deleting requires an explicit --apply.
  * An object is only a candidate when its url appears in NO row of items or
    import_candidates, across ALL users.
  * If the database read comes back suspiciously empty (zero items with photos),
    it aborts. A failed query must never be read as "everything is orphaned".
  * Objects newer than --min-age-days (default 7) are skipped, so an import that
    is mid-flight — bytes uploaded, row not yet written — can never be caught.
  * Only paths under a user folder ({uuid}/...) are touched. That is the only
    shape the app ever writes; anything else in the bucket is left alone.

Usage:
    python3 scripts/cleanup_orphan_photos.py                # report only
    python3 scripts/cleanup_orphan_photos.py --apply        # actually delete
    python3 scripts/cleanup_orphan_photos.py --min-age-days 30
"""
import argparse
import re
import sys
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PAGE = 1000
LIST_PAGE = 1000
MAX_DEPTH = 4
DELETE_BATCH = 100


def _is_user_folder(name: str) -> bool:
    try:
        _uuid.UUID(name)
        return True
    except (ValueError, AttributeError):
        return False


def _paged(query_factory):
    """Read a whole table in pages — PostgREST caps a plain select at 1000 rows."""
    rows, start = [], 0
    while True:
        chunk = query_factory().range(start, start + PAGE - 1).execute().data or []
        rows.extend(chunk)
        if len(chunk) < PAGE:
            return rows
        start += PAGE


def collect_referenced_paths(db, marker: str) -> tuple[set, int]:
    """Every storage path still referenced anywhere in the database."""
    referenced = set()
    items_with_photos = 0

    def add(url):
        if isinstance(url, str) and marker in url:
            path = url.split(marker, 1)[1].split("?", 1)[0].split("#", 1)[0].strip("/")
            if path:
                referenced.add(path)

    for row in _paged(lambda: db.table("items").select("photo_urls")):
        urls = row.get("photo_urls") or []
        if urls:
            items_with_photos += 1
        for u in urls:
            add(u)

    for row in _paged(lambda: db.table("import_candidates").select("photo_url,photo_urls")):
        add(row.get("photo_url"))
        for u in (row.get("photo_urls") or []):
            add(u)

    # A queued publish carries its own copy of the photo urls. Delete those
    # objects and the job publishes an item without a single image — exactly the
    # failure this whole system exists to prevent. Anything not finished or
    # cancelled counts as live, including errored jobs: those get retried.
    for row in _paged(lambda: db.table("jobs").select("status,payload")):
        if row.get("status") in ("done", "cancelled"):
            continue
        for url in re.findall(r'https?://[^\s"\'\\,\]}]+', str(row.get("payload") or "")):
            add(url.rstrip("',\"" ))

    return referenced, items_with_photos


def list_bucket(storage, prefix: str = "", depth: int = 0) -> list[dict]:
    """Walk the bucket. Returns file entries with a full path, size and age."""
    if depth > MAX_DEPTH:
        return []
    out, offset = [], 0
    while True:
        try:
            entries = storage.list(
                path=prefix, options={"limit": LIST_PAGE, "offset": offset}
            ) or []
        except Exception as e:  # noqa: BLE001
            print(f"  ! could not list '{prefix}': {e}")
            return out
        for entry in entries:
            name = entry.get("name")
            if not name or name == ".emptyFolderPlaceholder":
                continue
            full = f"{prefix}/{name}" if prefix else name
            if entry.get("id") is None:          # a folder
                out.extend(list_bucket(storage, full, depth + 1))
            else:
                meta = entry.get("metadata") or {}
                out.append({
                    "path": full,
                    "size": int(meta.get("size") or 0),
                    "created_at": entry.get("created_at") or "",
                })
        if len(entries) < LIST_PAGE:
            return out
        offset += LIST_PAGE


def _older_than(created_at: str, cutoff: datetime) -> bool:
    """Unparseable timestamp counts as NEW, i.e. keep it."""
    if not created_at:
        return False
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00")) < cutoff
    except ValueError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default: report only)")
    ap.add_argument("--min-age-days", type=int, default=7,
                    help="never touch objects younger than this (default 7)")
    ap.add_argument("--include-root", action="store_true",
                    help="also clean unreferenced objects lying loose in the bucket root "
                         "(uploads from before photos were stored per user)")
    args = ap.parse_args()

    from backend.database import get_db
    from backend.services.image_upload import BUCKET

    db = get_db()
    marker = f"/storage/v1/object/public/{BUCKET}/"

    print("Reading the database…")
    referenced, items_with_photos = collect_referenced_paths(db, marker)
    print(f"  {items_with_photos} items with photos, {len(referenced)} referenced objects")

    # The guard is about a FAILED read looking like "everything is orphaned".
    # Reading items that have photos proves the query worked. Zero of those urls
    # pointing at Supabase is a different thing entirely — it is what a finished
    # migration to R2 looks like, and then the whole bucket is genuinely stale.
    if items_with_photos == 0:
        print("\nABORT: the database returned no items with photos at all. That is almost\n"
              "certainly a failed or unauthorised read, not an empty account.\n"
              "Nothing was deleted.")
        return 1
    if not referenced:
        print("  none of them still point at Supabase — the migration to R2 is complete,\n"
              "  so everything left in this bucket is a leftover")

    print(f"Listing bucket '{BUCKET}'… (this takes a moment)")
    files = list_bucket(db.storage.from_(BUCKET))
    total_bytes = sum(f["size"] for f in files)
    print(f"  {len(files)} objects, {total_bytes / 1e9:.2f} GB")

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.min_age_days)
    orphans, too_new, skipped_shape = [], 0, 0
    for f in files:
        if f["path"] in referenced:
            continue
        top = f["path"].split("/", 1)[0]
        if not _is_user_folder(top):
            # Loose objects in the bucket root are the old upload scheme: a bare
            # {uuid}.jpg. They are only touched on request, and only when the
            # name is a plain uuid image — never a folder like content/ or a
            # stray file we did not write.
            root_object = "/" not in f["path"] and _is_user_folder(top.rsplit(".", 1)[0])
            if not (args.include_root and root_object):
                skipped_shape += 1
                continue
        if not _older_than(f["created_at"], cutoff):
            too_new += 1
            continue
        orphans.append(f)

    orphan_bytes = sum(f["size"] for f in orphans)
    print(f"\n  in use            : {len(files) - len(orphans) - too_new - skipped_shape}")
    print(f"  too new to touch  : {too_new}")
    print(f"  outside user dirs : {skipped_shape} (left alone)")
    print(f"  ORPHANED          : {len(orphans)}  ->  {orphan_bytes / 1e9:.2f} GB reclaimable")

    if not orphans:
        print("\nNothing to clean up.")
        return 0

    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)
    report = out_dir / "orphan_photos.txt"
    report.write_text("\n".join(f["path"] for f in orphans))
    print(f"  full list written to {report}")

    if not args.apply:
        print("\nDry run — nothing deleted. Re-run with --apply to remove them.")
        return 0

    print(f"\nDeleting {len(orphans)} objects…")
    storage = db.storage.from_(BUCKET)
    done = 0
    for i in range(0, len(orphans), DELETE_BATCH):
        batch = [f["path"] for f in orphans[i:i + DELETE_BATCH]]
        try:
            verwijderd = storage.remove(batch) or []
        except Exception as e:  # noqa: BLE001
            print(f"  ! batch failed ({e}) — stopping here, {done} removed so far")
            return 1
        # Storage does NOT raise when row-level security refuses the delete: it
        # answers 200 with an empty list. Counting the request as a success is
        # how this script once reported "3.04 GB freed" while every single file
        # was still there. Only objects it hands back were actually removed.
        if len(verwijderd) != len(batch):
            print(f"  ! storage removed {len(verwijderd)} of {len(batch)} objects and did "
                  f"not say why — stopping, {done} removed so far.")
            print("    Vrijwel altijd de sleutel: verwijderen mag niet met de anon-sleutel.")
            print("    Zet SUPABASE_SERVICE_KEY in .env (Supabase > Project Settings >")
            print("    API > service_role) en draai dit opnieuw.")
            return 1
        done += len(verwijderd)
        print(f"  {done}/{len(orphans)}")
    print(f"\nDone. {done} objects removed, {orphan_bytes / 1e9:.2f} GB freed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
