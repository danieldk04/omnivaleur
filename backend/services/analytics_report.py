"""
Wekelijks marketingrapport voor CrossList EU.

Bundelt de signalen van alle primaire kanalen tot één beeld:
  * SEO/GEO  — Search Console: top-blogposts, stijgende zoektermen, deze week vs vorige week.
  * Kanalen  — GA4 (zodra gekoppeld): welk kanaal (organic / social / referral / direct)
               de meeste en meest waardevolle bezoekers levert.
  * Signups  — nieuwe accounts deze week vs vorige week.
  * Patronen — automatisch herkende inzichten (grootste stijger/daler, beste kanaal).

Alles faalt zacht: ontbrekende bron = die sectie leeg / 'nog niet gekoppeld', rapport
draait door. Week-over-week gebeurt door twee expliciete datumvensters op te vragen,
dus er is geen opslag nodig voor de basisvergelijking. Een optionele Supabase-tabel
`analytics_snapshots` geeft langere-termijn geheugen (maand-over-maand) — best effort.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from backend.services import search_console as gsc
from backend.services import ga4

logger = logging.getLogger(__name__)

SITE_URL = "https://crosslisteu.com"


# ---------------------------------------------------------------------------
# Datumvensters
# ---------------------------------------------------------------------------
def _windows(today: date | None = None) -> dict:
    """
    'Deze week' = de zojuist afgelopen ma..zo (t/m gisteren als het zondag is),
    'vorige week' = de 7 dagen daarvoor. GSC-data heeft ~2-3 dagen vertraging,
    dus we vergelijken volle, vergelijkbare 7-daagse blokken.
    """
    today = today or date.today()
    this_end = today - timedelta(days=1)
    this_start = this_end - timedelta(days=6)
    prev_end = this_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    return {
        "this": (this_start.isoformat(), this_end.isoformat()),
        "prev": (prev_start.isoformat(), prev_end.isoformat()),
    }


def _pct_delta(now: float, before: float) -> float | None:
    if before == 0:
        return None if now == 0 else 100.0
    return round((now - before) / before * 100.0, 1)


# ---------------------------------------------------------------------------
# Search Console
# ---------------------------------------------------------------------------
def _seo_section(win: dict) -> dict:
    this_s, this_e = win["this"]
    prev_s, prev_e = win["prev"]

    pages_now = {r["keys"][0]: r for r in gsc.query_window(["page"], this_s, this_e, row_limit=500)}
    pages_prev = {r["keys"][0]: r for r in gsc.query_window(["page"], prev_s, prev_e, row_limit=500)}
    queries_now = {r["keys"][0]: r for r in gsc.query_window(["query"], this_s, this_e, row_limit=500)}
    queries_prev = {r["keys"][0]: r for r in gsc.query_window(["query"], prev_s, prev_e, row_limit=500)}

    def _rows(now: dict, prev: dict, key_label: str):
        out = []
        for k, r in now.items():
            p = prev.get(k, {})
            out.append({
                key_label: k,
                "clicks": round(r["clicks"]),
                "impressions": round(r["impressions"]),
                "position": round(r["position"], 1),
                "clicks_prev": round(p.get("clicks", 0)),
                "clicks_delta": _pct_delta(r["clicks"], p.get("clicks", 0)),
            })
        return out

    top_pages = sorted(_rows(pages_now, pages_prev, "url"), key=lambda x: x["clicks"], reverse=True)
    top_queries = sorted(_rows(queries_now, queries_prev, "query"), key=lambda x: x["clicks"], reverse=True)

    # Stijgende zoektermen: grootste absolute clickwinst t.o.v. vorige week.
    risers = sorted(
        [q for q in top_queries if q["clicks"] > q["clicks_prev"]],
        key=lambda x: x["clicks"] - x["clicks_prev"],
        reverse=True,
    )

    tot_now = sum(p["clicks"] for p in top_pages)
    tot_prev = sum(p["clicks_prev"] for p in top_pages)
    imp_now = sum(p["impressions"] for p in top_pages)

    return {
        # 'connected' = koppeling werkt (creds aanwezig); data kan 0 zijn bij een nieuwe site.
        "connected": gsc.is_configured(),
        "has_data": bool(pages_now or pages_prev),
        "total_clicks": tot_now,
        "total_clicks_delta": _pct_delta(tot_now, tot_prev),
        "total_impressions": imp_now,
        "top_pages": top_pages[:10],
        "top_queries": top_queries[:10],
        "risers": risers[:8],
    }


# ---------------------------------------------------------------------------
# GA4
# ---------------------------------------------------------------------------
def _channels_section(win: dict) -> dict:
    if not ga4.is_configured():
        return {"connected": False}

    this_s, this_e = win["this"]
    prev_s, prev_e = win["prev"]

    now = ga4.channels(this_s, this_e)
    prev = {r["sessionDefaultChannelGroup"]: r for r in ga4.channels(prev_s, prev_e)}
    for r in now:
        p = prev.get(r["sessionDefaultChannelGroup"], {})
        r["sessions_delta"] = _pct_delta(r.get("sessions", 0), p.get("sessions", 0))

    return {
        "connected": True,
        "channels": now,
        "landing_pages": ga4.top_landing_pages(this_s, this_e, limit=12),
        "totals": ga4.totals(this_s, this_e),
    }


# ---------------------------------------------------------------------------
# Social media per platform (GA4-bron → platform) + post-niveau (UTM)
# ---------------------------------------------------------------------------
def _social_section(win: dict) -> dict:
    """Splitst het verkeer uit naar social platform (TikTok / Instagram / YouTube /
    Pinterest / Reddit / …) — iets wat GA4's default-kanaalgroep NIET doet — plus
    post-niveau attributie voor links die je met UTM's hebt getagd."""
    if not ga4.is_configured():
        return {"connected": False}

    this_s, this_e = win["this"]
    prev_s, prev_e = win["prev"]

    def _by_platform(rows: list[dict]) -> dict:
        agg: dict[str, dict] = {}
        for r in rows:
            plat = ga4.platform_of(r.get("sessionSource", ""))
            if not plat:
                continue
            a = agg.setdefault(plat, {"platform": plat, "sessions": 0, "newUsers": 0, "conversions": 0})
            a["sessions"] += r.get("sessions", 0)
            a["newUsers"] += r.get("newUsers", 0)
            a["conversions"] += r.get("conversions", 0)
        return agg

    now = _by_platform(ga4.traffic_sources(this_s, this_e))
    prev = _by_platform(ga4.traffic_sources(prev_s, prev_e))
    platforms = []
    for plat, a in now.items():
        a["sessions_delta"] = _pct_delta(a["sessions"], prev.get(plat, {}).get("sessions", 0))
        a["conv_rate"] = round(a["conversions"] / a["sessions"] * 100, 1) if a["sessions"] else 0.0
        platforms.append(a)
    platforms.sort(key=lambda x: x["sessions"], reverse=True)

    posts = ga4.social_posts(this_s, this_e)
    for p in posts:
        p["platform"] = ga4.platform_of(p.get("sessionSource", "")) or p.get("sessionSource", "")

    return {
        "connected": True,
        "platforms": platforms,
        "posts": posts[:15],
        "has_utm_data": bool(posts),
    }


# ---------------------------------------------------------------------------
# Blog-prestaties per categorie (contentpijler uit de URL)
# ---------------------------------------------------------------------------
def _category_of(url_or_path: str) -> str:
    """Leidt de contentcategorie af uit het URL-pad, zodat we per soort content
    (niet per losse pagina) kunnen zien wat aanslaat — beslissingswaardig voor
    'welke soort artikelen moet ik meer maken'."""
    p = (url_or_path or "").replace(SITE_URL, "")
    # taalprefix wegstrippen (/nl/…, /fr/…, /de/…)
    for lang in ("/nl/", "/fr/", "/de/"):
        if p.startswith(lang):
            p = "/" + p[len(lang):]
            break
    if p in ("", "/"):
        return "Homepage"
    if p.startswith("/vs/") or "/vergelijking/" in p:
        return "Vergelijkingen"
    if "/reseller-tools/" in p:
        return "Reseller-tools"
    if "/crosslisting/" in p or "/crosslisten/" in p:
        return "Crosslisting-guides"
    if p.startswith("/blog"):
        return "Blog-index"
    return "Overig"


def _blog_categories(seo: dict) -> list[dict]:
    """Groepeert de GSC-pagina's per categorie: clicks/impressies + week-over-week."""
    agg: dict[str, dict] = {}
    for p in seo.get("top_pages", []):
        cat = _category_of(p["url"])
        a = agg.setdefault(cat, {"category": cat, "clicks": 0, "impressions": 0,
                                 "clicks_prev": 0, "pages": 0})
        a["clicks"] += p["clicks"]
        a["impressions"] += p["impressions"]
        a["clicks_prev"] += p.get("clicks_prev", 0)
        a["pages"] += 1
    out = []
    for a in agg.values():
        a["clicks_delta"] = _pct_delta(a["clicks"], a["clicks_prev"])
        a["ctr"] = round(a["clicks"] / a["impressions"] * 100, 1) if a["impressions"] else 0.0
        out.append(a)
    out.sort(key=lambda x: x["clicks"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Signups
# ---------------------------------------------------------------------------
def _signups_section(win: dict) -> dict:
    from backend.database import get_db

    this_s, this_e = win["this"]
    prev_s, _ = win["prev"]
    try:
        db = get_db()
        # Supabase auth admin: haal recente gebruikers en tel per venster.
        users = db.auth.admin.list_users()
        rows = users if isinstance(users, list) else getattr(users, "users", []) or []
        this_n = prev_n = 0
        for u in rows:
            created = getattr(u, "created_at", None) or (u.get("created_at") if isinstance(u, dict) else None)
            if not created:
                continue
            d = str(created)[:10]
            if this_s <= d <= this_e:
                this_n += 1
            elif prev_s <= d < this_s:
                prev_n += 1
        return {"available": True, "this_week": this_n, "prev_week": prev_n,
                "delta": _pct_delta(this_n, prev_n)}
    except Exception as e:
        logger.info(f"Signup-telling niet beschikbaar (best effort): {e}")
        return {"available": False}


# ---------------------------------------------------------------------------
# Patroonherkenning
# ---------------------------------------------------------------------------
def _patterns(seo: dict, channels: dict, signups: dict, social: dict, categories: list[dict]) -> list[str]:
    out: list[str] = []

    if seo.get("connected"):
        d = seo.get("total_clicks_delta")
        if d is not None:
            arrow = "📈" if d >= 0 else "📉"
            out.append(f"{arrow} SEO-clicks {'+' if d >= 0 else ''}{d}% vs vorige week ({seo['total_clicks']} clicks).")
        if seo.get("risers"):
            r = seo["risers"][0]
            out.append(f"🔎 Snelst stijgende zoekterm: “{r['query']}” ({r['clicks_prev']}→{r['clicks']} clicks).")
        if seo.get("top_pages"):
            best = seo["top_pages"][0]
            slug = best["url"].replace(SITE_URL, "") or "/"
            out.append(f"🏆 Best presterende pagina: {slug} ({best['clicks']} clicks).")

    if channels.get("connected") and channels.get("channels"):
        top = channels["channels"][0]
        out.append(
            f"🚀 Meeste verkeer via {top['sessionDefaultChannelGroup']} "
            f"({top.get('sessions', 0)} sessies, {top.get('conversions', 0)} conversies)."
        )
        # Kanaal met de hoogste conversie-ratio = 'meest waardevolle' bron.
        valued = [c for c in channels["channels"] if c.get("sessions")]
        if valued:
            best_val = max(valued, key=lambda c: (c.get("conversions", 0) / c["sessions"]))
            if best_val.get("conversions"):
                out.append(
                    f"💎 Meest waardevolle kanaal (hoogste conversie): "
                    f"{best_val['sessionDefaultChannelGroup']}."
                )
    elif not channels.get("connected"):
        out.append("ℹ️ GA4 nog niet gekoppeld — kanaal- en conversiedata ontbreekt nog.")

    # Social per platform — welk kanaal levert bezoek, en welk converteert het best.
    if social.get("connected") and social.get("platforms"):
        top = social["platforms"][0]
        out.append(
            f"📱 Beste social-platform: {top['platform']} "
            f"({top['sessions']} sessies, {top['newUsers']} nieuwe bezoekers)."
        )
        converters = [p for p in social["platforms"] if p.get("conversions")]
        if converters:
            best = max(converters, key=lambda p: p["conv_rate"])
            out.append(
                f"💎 Meest waardevolle social-platform (hoogste conversie): "
                f"{best['platform']} — {best['conv_rate']}% conversie."
            )
        if not social.get("has_utm_data"):
            out.append("🏷️ Tip: tag je post-links met UTM's (zie de linkbouwer in het dashboard) "
                       "om per TikTok/Reel/Pin te zien wat bezoek én signups oplevert.")
    elif social.get("connected"):
        out.append("📱 Nog geen herkend social-verkeer deze week — begin met UTM-links te delen.")

    # Beste contentcategorie — beslissingswaardig: hier zit je meeste organische bereik.
    if categories:
        best_cat = categories[0]
        if best_cat["clicks"]:
            out.append(
                f"🗂️ Sterkste contentcategorie: {best_cat['category']} "
                f"({best_cat['clicks']} clicks over {best_cat['pages']} pagina's) → "
                f"hier lonen méér artikelen."
            )
        # Categorie met veel impressies maar lage CTR = kans (betere titels/snippets).
        opportunity = [c for c in categories if c["impressions"] >= 20 and c["ctr"] < 2.0]
        if opportunity:
            o = max(opportunity, key=lambda c: c["impressions"])
            out.append(
                f"🎯 Kans: {o['category']} krijgt {o['impressions']} impressies maar "
                f"{o['ctr']}% CTR — scherpere titels/meta kunnen hier clicks winnen."
            )

    if signups.get("available"):
        d = signups.get("delta")
        dtxt = f"{'+' if (d or 0) >= 0 else ''}{d}%" if d is not None else "n.v.t."
        out.append(f"👤 Nieuwe signups: {signups['this_week']} (vorige week {signups['prev_week']}, {dtxt}).")

    return out


# ---------------------------------------------------------------------------
# Publieke API
# ---------------------------------------------------------------------------
def build_report(today: date | None = None) -> dict:
    win = _windows(today)
    seo = _seo_section(win)
    channels = _channels_section(win)
    social = _social_section(win)
    categories = _blog_categories(seo)
    signups = _signups_section(win)
    patterns = _patterns(seo, channels, signups, social, categories)

    report = {
        "period": {"this": win["this"], "prev": win["prev"]},
        "seo": seo,
        "channels": channels,
        "social": social,
        "categories": categories,
        "signups": signups,
        "patterns": patterns,
    }
    _store_snapshot(report)
    return report


def _store_snapshot(report: dict) -> None:
    """Best-effort langetermijngeheugen. Vereist eenmalig een `analytics_snapshots`
    tabel (zie setup-instructies). Faalt stil als die er niet is."""
    try:
        from backend.database import get_db
        get_db().table("analytics_snapshots").insert({
            "week_start": report["period"]["this"][0],
            "week_end": report["period"]["this"][1],
            "seo_clicks": report["seo"].get("total_clicks", 0),
            "seo_impressions": report["seo"].get("total_impressions", 0),
            "signups": report["signups"].get("this_week"),
            "payload": report,
        }).execute()
    except Exception as e:
        logger.info(f"analytics_snapshots niet opgeslagen (tabel ontbreekt?): {e}")


def render_email(report: dict) -> tuple[str, str]:
    """Geeft (subject, plaintext body) voor de wekelijkse e-mail."""
    this_s, this_e = report["period"]["this"]
    lines = [
        f"CrossList EU — wekelijks marketingrapport",
        f"Week {this_s} t/m {this_e}",
        f"Dashboard: {SITE_URL}/analytics",
        "",
        "── Belangrijkste inzichten ──",
    ]
    lines += [f"  {p}" for p in report["patterns"]] or ["  (geen data)"]

    seo = report["seo"]
    if seo.get("connected"):
        lines += ["", "── SEO / Blog (Search Console) ──",
                  f"  Totaal clicks: {seo['total_clicks']} "
                  f"({seo['total_clicks_delta']}% vs vorige week) | "
                  f"impressies: {seo['total_impressions']}",
                  "  Top pagina's:"]
        for p in seo["top_pages"][:5]:
            slug = p["url"].replace(SITE_URL, "") or "/"
            dtxt = f"{p['clicks_delta']:+}%" if p["clicks_delta"] is not None else "nieuw"
            lines.append(f"    • {slug} — {p['clicks']} clicks ({dtxt}), pos {p['position']}")
        if seo["risers"]:
            lines.append("  Stijgende zoektermen:")
            for q in seo["risers"][:5]:
                lines.append(f"    • {q['query']} — {q['clicks_prev']}→{q['clicks']} clicks")
    else:
        lines += ["", "── SEO / Blog ──", "  Search Console nog niet gekoppeld."]

    ch = report["channels"]
    lines += ["", "── Kanalen (GA4) ──"]
    if ch.get("connected"):
        for c in ch["channels"][:8]:
            dtxt = f"{c['sessions_delta']:+}%" if c.get("sessions_delta") is not None else "nieuw"
            lines.append(
                f"    • {c['sessionDefaultChannelGroup']}: {c.get('sessions', 0)} sessies "
                f"({dtxt}), {c.get('conversions', 0)} conversies")
    else:
        lines.append("  GA4 nog niet gekoppeld — zie setup-instructies om social/Reddit/"
                     "referral-verkeer te meten.")

    sg = report["signups"]
    if sg.get("available"):
        lines += ["", "── Signups ──",
                  f"  Deze week: {sg['this_week']} | vorige week: {sg['prev_week']} "
                  f"({sg['delta']}%)"]

    lines += ["", "— Automatisch gegenereerd, elke zondagochtend."]
    subject = f"📊 Wekelijks marketingrapport — {this_s} t/m {this_e}"
    return subject, "\n".join(lines)


def send_weekly_report() -> None:
    """Scheduler-entrypoint: bouw + mail het rapport. Non-blocking, logt fouten."""
    try:
        report = build_report()
        subject, body = render_email(report)
        from backend.services.email import send_email
        send_email(subject, body)
        logger.info("Wekelijks marketingrapport verzonden.")
    except Exception as e:
        logger.error(f"Wekelijks marketingrapport mislukt: {e}")
