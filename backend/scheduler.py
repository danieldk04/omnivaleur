"""
APScheduler setup — runs polling jobs on a configurable interval.
Started automatically when the FastAPI app boots.
"""
from __future__ import annotations
import asyncio
import logging
import functools
import threading
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.config import settings

logger = logging.getLogger(__name__)
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

    Bewust een eigen thread en niet asyncio.to_thread: die deelt zijn threads
    met de inlogcontrole die op élk verzoek draait. Een taak die minuten duurt
    hield zo'n plek al die tijd bezet, waardoor inloggen ging staan wachten en
    de gateway alsnog 502 gaf — dezelfde storing, alleen verplaatst.
    """
    @functools.wraps(coro_fn)
    async def runner():
        klaar = asyncio.get_running_loop().create_future()

        def werk():
            try:
                asyncio.run(coro_fn())
                klaar.get_loop().call_soon_threadsafe(klaar.set_result, None)
            except BaseException as e:  # noqa: BLE001 - doorgeven aan APScheduler
                klaar.get_loop().call_soon_threadsafe(klaar.set_exception, e)

        threading.Thread(target=werk, name=f"job-{coro_fn.__name__}", daemon=True).start()
        await klaar
    return runner


def start_scheduler():
    global _scheduler
    from backend.services.polling import poll_platform_statuses
    from backend.services.crosslist import relist_expiring_marktplaats
    from backend.services.relist import herstel_vastgelopen_werk
    from backend.services.shopify_orders import controleer_shopify_verkopen

    from backend.services.billing import expire_trials, send_trial_reminders
    from backend.services.analytics_report import send_weekly_report
    from backend.content.evaluator import run_evaluation_cycle_sync
    from backend.content.pipeline import translate_missing_pages

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _off_the_request_loop(poll_platform_statuses),
        "interval",
        seconds=settings.polling_interval,
        id="poll_platforms",
        replace_existing=True,
    )
    # Verkopen op Shopify zelf nakijken. Bij een winkel die met een eigen sleutel
    # is gekoppeld komt er GEEN orders/paid-webhook binnen — die hoort bij onze
    # app, en die weg is dicht sinds Shopify geen marktplaats-apps meer toelaat.
    # Zonder deze ronde blijft iets dat in de eigen winkel verkocht is overal
    # anders gewoon te koop staan. Zie backend/services/shopify_orders.py.
    _scheduler.add_job(
        _off_the_request_loop(controleer_shopify_verkopen),
        "interval",
        minutes=5,
        id="shopify_verkopen",
        replace_existing=True,
    )
    _scheduler.add_job(
        _off_the_request_loop(relist_expiring_marktplaats),
        "interval",
        hours=6,
        id="relist_marktplaats",
        replace_existing=True,
    )
    # Werk dat halverwege bleef steken weer vlot trekken. Elke zes uur is vaak
    # genoeg: een advertentie die tussen verwijderen en terugplaatsen hangt is
    # weg bij het platform, dus dat mag geen dagen duren.
    _scheduler.add_job(
        _off_the_request_loop(herstel_vastgelopen_werk),
        "interval",
        hours=6,
        id="herstel_vastgelopen_werk",
        replace_existing=True,
    )
    _scheduler.add_job(
        _off_the_request_loop(expire_trials),
        "interval",
        hours=1,
        id="expire_trials",
        replace_existing=True,
    )
    # Herinneringsmail twee dagen voor het einde van de proefperiode — dagelijks
    # om 09:00 (NL-tijd), zodat de mail op een normaal moment binnenkomt en niet
    # midden in de nacht.
    _scheduler.add_job(
        _off_the_request_loop(send_trial_reminders),
        "cron",
        hour=9,
        minute=0,
        timezone="Europe/Amsterdam",
        id="trial_reminders",
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
    # NL-inhaalronde — dagelijks 11:00 (NL-tijd), ruim ná de publicatie van het
    # artikel van die dag. Elke Engelse pagina hoort een Nederlandse tweeling te
    # hebben; mislukte de vertaling bij het publiceren, dan bleef dat gat vroeger
    # voorgoed staan. Drie per ronde, zodat de Claude-kosten voorspelbaar blijven.
    # translate_missing_pages is synchroon (Supabase + Claude); _off_the_request_loop
    # verwacht een coroutine, vandaar dit dunne omhulsel.
    async def nl_backfill():
        translate_missing_pages(limit=3)

    _scheduler.add_job(
        _off_the_request_loop(nl_backfill),
        "cron",
        hour=11,
        minute=0,
        timezone="Europe/Amsterdam",
        id="daily_nl_backfill",
        replace_existing=True,
    )
    # ── De koude-mailmachine ──────────────────────────────────────────────
    #
    # Draaide tot 20-08-2026 op Daniels eigen Mac, via een LaunchAgent. Dat werkt
    # alleen zolang die Mac aan staat en wakker is; klapt hij zijn laptop dicht,
    # dan ligt de opvolging stil en blijven antwoorden onbeantwoord. Hier draait
    # hij dag en nacht.
    #
    # HIJ MAG NOOIT OP TWEE PLEKKEN TEGELIJK DRAAIEN: dan krijgt dezelfde
    # ontvanger twee keer dezelfde mail. Daarom staat hij uit tenzij LEADGEN_TICK
    # expliciet aan staat, en hoort de LaunchAgent op de Mac uit te staan zodra
    # dat zo is.
    if str(getattr(settings, "leadgen_tick", "") or "").strip() in ("1", "true", "True"):
        async def leadgen_beurt():
            import os
            import subprocess
            import sys
            from pathlib import Path
            script = Path(__file__).resolve().parent.parent / "scripts" / "leadgen_mail.py"
            omgeving = {**os.environ}
            # Resend is op de server de enige weg naar buiten; het script kiest
            # daarop. Zonder deze regel zou hij SMTP proberen en dat blokkeert
            # Railway, waarna er stilletjes niets verstuurd wordt.
            if settings.resend_api_key:
                omgeving["RESEND_API_KEY"] = settings.resend_api_key
            if settings.anthropic_api_key:
                omgeving["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
            if settings.supabase_url:
                omgeving["SUPABASE_URL"] = settings.supabase_url
            if settings.supabase_key:
                omgeving["SUPABASE_KEY"] = settings.supabase_key
            r = subprocess.run([sys.executable, str(script), "tick"],
                               capture_output=True, text=True, timeout=1500,
                               env=omgeving)
            uit = (r.stdout or "").strip()
            if uit:
                logger.info("leadgen tick:\n%s", uit[-2000:])
            if r.returncode != 0:
                logger.warning("leadgen tick eindigde met %s: %s",
                               r.returncode, (r.stderr or "")[-500:])

        _scheduler.add_job(
            _off_the_request_loop(leadgen_beurt),
            "interval",
            minutes=10,
            id="leadgen_tick",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    _scheduler.start()
    return _scheduler


def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown(wait=False)
