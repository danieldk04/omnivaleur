"""
Post-publicatie evaluator voor content_pages — de ontbrekende helft van de
contentpijplijn.

De pijplijn maakt elke pagina één keer en keek er daarna nooit meer naar om.
Deze module doet het omgekeerde: hij haalt voor elke gepubliceerde pagina de
échte Search Console-cijfers op (positie, impressies, CTR), vergelijkt die met
wat je op die positie zou mógen verwachten, en zet ondermaats presterende
pagina's in een refresh-wachtrij. De refresh draait de bestaande pijplijn
opnieuw op DEZELFDE slug — `intent_key` is UNIQUE, dus `_save_page_row` werkt de
bestaande rij bij i.p.v. een concurrent van jezelf te publiceren. De URL blijft
dus intact; alleen de inhoud wordt vernieuwd met verse SERP-research plus de
zoektermen die de pagina nú al binnenhaalt maar niet goed genoeg beantwoordt.

Faalt overal ZACHT: zonder Search Console-koppeling levert `evaluate_all()` een
lege lijst en gebeurt er niets. De snapshot-tabel `content_page_performance` is
optioneel — bestaat hij nog niet (handmatige migratie in Supabase), dan wordt
alleen het opslaan van de historie overgeslagen, niet de evaluatie zelf.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.database import get_db
from backend.services.search_console import get_queries_for_page, get_top_pages

logger = logging.getLogger(__name__)

SITE_URL = "https://omnivaleur.com"

# Een pagina heeft tijd nodig voordat GSC-data iets betekent. Onder deze leeftijd
# wordt niet geoordeeld — anders herschrijf je artikelen die simpelweg nog niet
# geïndexeerd/gerangschikt zijn.
MIN_AGE_DAYS = 45

# Boven deze leeftijd is "nog steeds geen enkele impressie" geen kwestie van
# geduld meer, maar van een onderwerp/uitvoering die niet aanslaat.
STALE_AGE_DAYS = 120

# Onder dit aantal impressies is de data te dun om een positie serieus te nemen.
MIN_IMPRESSIONS = 30

# Verwachte CTR per gemiddelde positie (afgeronde branche-benchmark). Gebruikt om
# "goede positie, maar niemand klikt" te onderscheiden van "slechte positie":
# het eerste is een titel-/meta-probleem, het tweede een inhoudsprobleem.
EXPECTED_CTR = [
    (1.5, 0.28),
    (2.5, 0.16),
    (3.5, 0.11),
    (5.0, 0.07),
    (7.0, 0.04),
    (10.0, 0.025),
]

# Haal je minder dan deze fractie van de verwachte CTR, dan telt het als
# onderpresterend op CTR. Bewust ruim (0.5) — CTR fluctueert sterk per keyword.
CTR_SHORTFALL_RATIO = 0.5


def _expected_ctr(position: float) -> float:
    for max_pos, ctr in EXPECTED_CTR:
        if position <= max_pos:
            return ctr
    return 0.01


def _page_age_days(page: dict) -> int | None:
    raw = page.get("published_at") or page.get("created_at")
    if not raw:
        return None
    try:
        published = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - published).days


def _classify(metrics: dict, age_days: int) -> tuple[str, float, str]:
    """
    Bepaalt verdict, prioriteitsscore en een leesbare reden voor één pagina.

    Verdicts:
      too_young  — te kort gepubliceerd om te beoordelen
      no_data    — nauwelijks impressies; refresh-waardig zodra de pagina oud genoeg is
      winning    — staat in de top 5, met rust laten
      striking   — positie 6-20: dichtbij, meeste winst te halen (hoogste prioriteit)
      low_ctr    — goede positie, maar de titel/meta trekt geen klikken
      buried     — positie >20: inhoudelijk niet competitief
    """
    if age_days < MIN_AGE_DAYS:
        return "too_young", 0.0, f"pas {age_days} dagen gepubliceerd"

    impressions = metrics["impressions"]
    position = metrics["position"]
    ctr = metrics["ctr"]

    if impressions < MIN_IMPRESSIONS:
        if age_days >= STALE_AGE_DAYS:
            return (
                "no_data",
                1.0,
                f"{age_days} dagen oud en nog maar {impressions} impressies — onderwerp of uitvoering slaat niet aan",
            )
        return "no_data", 0.0, f"nog te weinig data ({impressions} impressies)"

    if position <= 5.0:
        expected = _expected_ctr(position)
        if ctr < expected * CTR_SHORTFALL_RATIO:
            return (
                "low_ctr",
                impressions * 1.5,
                f"positie {position:.1f} maar CTR {ctr:.1%} tegen ~{expected:.0%} verwacht — titel/meta trekt niet",
            )
        return "winning", 0.0, f"positie {position:.1f}, CTR {ctr:.1%} — geen actie nodig"

    if position <= 20.0:
        return (
            "striking",
            impressions * 2.0,
            f"positie {position:.1f} met {impressions} impressies — binnen bereik van pagina 1",
        )

    return (
        "buried",
        impressions * 0.5,
        f"positie {position:.1f} met {impressions} impressies — inhoudelijk niet competitief",
    )


def _metrics_by_path(days: int) -> dict[str, dict]:
    """GSC-cijfers per URL-pad (zonder domein), zodat ze op content_pages matchen."""
    by_path: dict[str, dict] = {}
    for row in get_top_pages(days=days, row_limit=500):
        path = row["url"].replace(SITE_URL, "").split("?")[0].rstrip("/") or "/"
        by_path[path] = row
    return by_path


def _url_path_for(page: dict) -> str:
    # Hergebruikt bewust de pijplijn-logica: één definitie van hoe een pagina-URL
    # eruitziet, anders lopen evaluator en publicatie uiteen.
    from backend.content.pipeline import _url_path

    return _url_path(page.get("language", "en"), page["pillar"], page["slug"])


def evaluate_all(days: int = 90) -> list[dict]:
    """
    Beoordeelt elke gepubliceerde pagina en geeft de resultaten terug, gesorteerd
    op prioriteitsscore (hoogste eerst). Alleen-lezen: publiceert of wijzigt niets.
    """
    metrics_by_path = _metrics_by_path(days)
    if not metrics_by_path:
        logger.info("Geen Search Console-data beschikbaar — evaluatie overgeslagen")
        return []

    db = get_db()
    pages = (
        db.table("content_pages")
        .select("id,intent_key,pillar,region,slug,language,primary_keyword,title,published_at,created_at,translation_of")
        .eq("status", "published")
        .execute()
        .data
        or []
    )

    results = []
    for page in pages:
        age_days = _page_age_days(page)
        if age_days is None:
            continue

        url_path = _url_path_for(page)
        raw = metrics_by_path.get(url_path.rstrip("/") or "/")
        metrics = {
            "clicks": raw["clicks"] if raw else 0,
            "impressions": raw["impressions"] if raw else 0,
            "ctr": raw["ctr"] if raw else 0.0,
            "position": raw["position"] if raw else 0.0,
        }
        verdict, score, reason = _classify(metrics, age_days)
        results.append(
            {
                "id": page["id"],
                "intent_key": page["intent_key"],
                "url_path": url_path,
                "keyword": page["primary_keyword"],
                "title": page["title"],
                "language": page.get("language", "en"),
                "pillar": page["pillar"],
                "region": page["region"],
                "slug": page["slug"],
                "translation_of": page.get("translation_of"),
                "age_days": age_days,
                "verdict": verdict,
                "score": score,
                "reason": reason,
                **metrics,
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    _store_snapshots(results)
    return results


def _store_snapshots(results: list[dict]) -> None:
    """
    Schrijft één historie-rij per pagina per evaluatie, zodat je later kunt zien of
    een refresh de positie daadwerkelijk verbeterde. Ontbreekt de tabel nog (de
    migratie in schema.sql moet handmatig in Supabase gedraaid worden), dan wordt
    dit stil overgeslagen — de evaluatie zelf werkt gewoon.
    """
    if not results:
        return
    rows = [
        {
            "page_id": r["id"],
            "intent_key": r["intent_key"],
            "url_path": r["url_path"],
            "clicks": r["clicks"],
            "impressions": r["impressions"],
            "ctr": r["ctr"],
            "position": r["position"],
            "verdict": r["verdict"],
            "reason": r["reason"],
        }
        for r in results
    ]
    try:
        get_db().table("content_page_performance").insert(rows).execute()
    except Exception as e:
        logger.warning(f"Performance-snapshot niet opgeslagen (tabel ontbreekt?): {e}")


def refresh_candidates(results: list[dict]) -> list[dict]:
    """
    De pagina's die een herschrijving verdienen, hoogste prioriteit eerst.

    Vertaalde (NL-)rijen worden overgeslagen: die worden door de pijplijn altijd
    uit hun Engelse bron hergenereerd, dus refreshen doe je op het origineel —
    anders wordt de vertaling meteen daarna toch weer overschreven.
    """
    return [
        r
        for r in results
        if r["verdict"] in ("striking", "low_ctr", "buried", "no_data")
        and r["score"] > 0
        and not r["translation_of"]
    ]


def _refresh_context(candidate: dict) -> dict:
    """
    Bouwt de extra briefing voor de generator: waaróm deze pagina wordt herschreven,
    plus de zoektermen die hem nú al impressies opleveren. Die termen zijn het
    waardevolste signaal dat er is — het is letterlijk wat mensen zoeken als ze deze
    pagina te zien krijgen, en dus precies wat de tekst beter moet beantwoorden.
    """
    queries = get_queries_for_page(f"{SITE_URL}{candidate['url_path']}", days=90, row_limit=25)
    missed = [
        q
        for q in queries
        if q["impressions"] >= 5 and (q["clicks"] == 0 or q["position"] > 5.0)
    ][:15]
    return {
        "verdict": candidate["verdict"],
        "reason": candidate["reason"],
        "position": candidate["position"],
        "impressions": candidate["impressions"],
        "ctr": candidate["ctr"],
        "current_title": candidate["title"],
        "missed_queries": missed,
    }


def _nl_slug_for(intent_key: str) -> str | None:
    """
    Haalt de bestaande NL-slug op zodat een refresh de Nederlandse URL niet
    verandert. De DB-slug draagt een intern '-nl'-achtervoegsel dat de pijplijn er
    zelf weer aan plakt, dus dat wordt hier gestript.
    """
    try:
        rows = get_db().table("content_pages").select("slug").eq("translation_of", intent_key).limit(1).execute().data
    except Exception as e:
        logger.warning(f"NL-companion niet opgezocht voor {intent_key}: {e}")
        return None
    if not rows:
        return None
    slug = rows[0]["slug"]
    return slug[:-3] if slug.endswith("-nl") else slug


async def refresh_page(candidate: dict) -> dict:
    """Draait de volledige pijplijn opnieuw op dezelfde slug, met refresh-briefing."""
    from backend.content.pipeline import run_pipeline

    logger.info(f"Refresh van {candidate['url_path']} — {candidate['reason']}")
    return await run_pipeline(
        candidate["keyword"],
        candidate["region"],
        candidate["pillar"],
        candidate["slug"],
        nl_slug=_nl_slug_for(candidate["intent_key"]),
        refresh_context=_refresh_context(candidate),
    )


async def run_evaluation_cycle(limit: int = 1, dry_run: bool = False) -> dict:
    """
    Volledige cyclus: evalueer alles, refresh de `limit` slechtst presterende
    pagina's, mail een samenvatting. Dit is wat de wekelijkse cron aanroept.
    """
    results = evaluate_all()
    if not results:
        return {"evaluated": 0, "refreshed": [], "candidates": []}

    candidates = refresh_candidates(results)
    refreshed = []

    if not dry_run:
        for candidate in candidates[:limit]:
            try:
                result = await refresh_page(candidate)
                if result.get("success"):
                    refreshed.append({**candidate, "url_path": result["url_path"]})
                else:
                    logger.error(f"Refresh mislukt voor {candidate['url_path']}: {result.get('error')}")
            except Exception as e:
                logger.error(f"Refresh crashte voor {candidate['url_path']}: {e}")

    summary = {"evaluated": len(results), "refreshed": refreshed, "candidates": candidates}

    if not dry_run:
        try:
            from backend.services.email import notify_content_evaluation

            notify_content_evaluation(summary, results)
        except Exception as e:
            logger.error(f"Evaluatie-melding mislukt (niet-blokkerend): {e}")

    return summary


def run_evaluation_cycle_sync() -> None:
    """
    Sync-wrapper voor de scheduler. Bewust SYNC en niet als coroutine-job
    geregistreerd: APScheduler draait een sync-job in een threadpool-worker, en
    deze cyclus zit vol blokkerende Supabase-, GSC- en Anthropic-calls die de
    event loop van de webserver anders minutenlang zouden vastzetten. In die
    worker-thread draait geen loop, dus asyncio.run() is hier veilig.
    """
    import asyncio

    asyncio.run(run_evaluation_cycle(limit=1))
