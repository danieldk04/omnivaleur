"""
Aggregated activity notifications — unread messages + open bids/offers across
the marketplaces, shown in one place on the dashboard.

The platforms we automate (Marktplaats, 2dehands, Vinted) have no seller API for
messages/bids, so the desktop extension reads the unread badge counts from the
user's own logged-in session and reports them here. We keep ONLY counts and a
deep link — never message contents. Replying / accepting a bid still happens on
the platform itself via the deep link; this endpoint just centralises "where is
something waiting for me".
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from backend.database import get_db
from backend.api.deps import get_current_user
from backend.models import NotificationReport

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Fallback deep links per platform if the extension doesn't supply one.
DEFAULT_DEEP_LINKS = {
    "marktplaats": "https://www.marktplaats.nl/messages",
    "2dehands": "https://www.2dehands.be/messages",
    "vinted": "https://www.vinted.nl/inbox",
}


@router.get("/")
async def list_notifications(user_id: str = Depends(get_current_user)):
    """Current snapshot of unread messages / open bids per platform for this user."""
    db = get_db()
    rows = (
        db.table("platform_notifications")
        .select("*")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    total = sum((r.get("messages") or 0) + (r.get("offers") or 0) for r in rows)
    return {"total": total, "platforms": rows}


@router.post("/report")
async def report_notifications(
    body: NotificationReport, user_id: str = Depends(get_current_user)
):
    """
    Extension reports the CURRENT counts for one platform (overwrites the prior
    snapshot for that platform). Counts are clamped to >= 0; negative/garbage is
    treated as 0 so a bad scrape can never show a nonsense number.
    """
    messages = max(0, int(body.messages or 0))
    offers = max(0, int(body.offers or 0))
    deep_link = body.deep_link or DEFAULT_DEEP_LINKS.get(body.platform)

    db = get_db()
    db.table("platform_notifications").upsert(
        {
            "user_id": user_id,
            "platform": body.platform,
            "messages": messages,
            "offers": offers,
            "deep_link": deep_link,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()
    return {"ok": True, "platform": body.platform, "messages": messages, "offers": offers}
