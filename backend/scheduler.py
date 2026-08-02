"""
APScheduler setup — runs polling jobs on a configurable interval.
Started automatically when the FastAPI app boots.
"""
from __future__ import annotations
import asyncio
import functools
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.config import settings

_scheduler: Optional[AsyncIOScheduler] = None


def _off_the_request_loop(coro_fn):
    """
    Draai een geplande taak in een eigen thread met een eigen event loop.

    De Supabase-client is synchroon: elke databaseaanroep blokkeert de loop
    waarop hij draait tot het antwoord binnen is. Deze taken deden dat op
    precies dezelfde loop die de website bedient, en doen tientallen tot
    honderden van die aanroepen achter elkaar. Zolang zo'n taak liep, stond
    de hele server stil en kreeg iedereen die op dat moment iets opsloeg een
    502 van de gateway — elke vijf minuten opnieuw, en dus schijnbaar
    willekeurig. In een eigen thread blokkeren ze alleen zichzelf.
    """
    @functools.wraps(coro_fn)
    async def runner():
        await asyncio.to_thread(lambda: asyncio.run(coro_fn()))
    return runner


def start_scheduler():
    global _scheduler
    from backend.services.polling import poll_platform_statuses
    from backend.services.crosslist import relist_expiring_marktplaats

    from backend.services.billing import expire_trials
    from backend.services.analytics_report import send_weekly_report
    from backend.content.evaluator import run_evaluation_cycle_sync

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _off_the_request_loop(poll_platform_statuses),
        "interval",
        seconds=settings.polling_interval,
        id="poll_platforms",
        replace_existing=True,
    )
    _scheduler.add_job(
        _off_the_request_loop(relist_expiring_marktplaats),
        "interval",
        hours=6,
        id="relist_marktplaats",
        replace_existing=True,
    )
    _scheduler.add_job(
        _off_the_request_loop(expire_trials),
        "interval",
        hours=1,
        id="expire_trials",
        replace_existing=True,
    )
    # Wekelijks marketingrapport — elke zondagochtend 08:00 (NL-tijd) per e-mail.
    _scheduler.add_job(
        _off_the_request_loop(send_weekly_report),
        "cron",
        day_of_week="sun",
        hour=8,
        minute=0,
        timezone="Europe/Amsterdam",
        id="weekly_marketing_report",
        replace_existing=True,
    )
    # Blog-evaluator — elke maandagochtend 07:00 (NL-tijd): beoordeelt alle
    # gepubliceerde content_pages op Search Console-data en herschrijft de
    # slechtst presterende pagina op dezelfde URL. Bewust vóór het wekelijkse
    # rapport in de week, zodat een refresh nog een volle week kan meetellen.
    _scheduler.add_job(
        run_evaluation_cycle_sync,
        "cron",
        day_of_week="mon",
        hour=7,
        minute=0,
        timezone="Europe/Amsterdam",
        id="weekly_content_evaluation",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler


def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown(wait=False)
