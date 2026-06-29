"""
APScheduler setup — runs polling jobs on a configurable interval.
Started automatically when the FastAPI app boots.
"""
from __future__ import annotations
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.config import settings

_scheduler: Optional[AsyncIOScheduler] = None


def start_scheduler():
    global _scheduler
    from backend.services.polling import poll_platform_statuses
    from backend.services.crosslist import relist_expiring_marktplaats

    from backend.services.billing import expire_trials

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        poll_platform_statuses,
        "interval",
        seconds=settings.polling_interval,
        id="poll_platforms",
        replace_existing=True,
    )
    _scheduler.add_job(
        relist_expiring_marktplaats,
        "interval",
        hours=6,
        id="relist_marktplaats",
        replace_existing=True,
    )
    _scheduler.add_job(
        expire_trials,
        "interval",
        hours=1,
        id="expire_trials",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler


def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown(wait=False)
