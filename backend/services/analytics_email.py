"""
Opmaak van het wekelijkse marketingrapport: één samenvatting, vier cijfers, het
verloop over acht weken, hooguit drie acties en daarna pas de details.

Waarom hier en niet in analytics_report: dat bestand meet, dit bestand vertelt.

Regels waar de opmaak zich aan houdt, omdat e-mail geen browser is:
  * Alles staat in tabellen met stijl-attributen op de elementen zelf. Gmail
    gooit <style>-blokken en externe css weg.
  * Geen svg en geen afbeeldingen voor de grafiek: Gmail toont svg niet en
    blokkeert afbeeldingen standaard. De balken zijn gewoon gekleurde cellen.
  * Er gaat altijd óók een platte tekstversie mee, zodat de mail leesbaar blijft
    zonder opmaak.
"""
from __future__ import annotations

from datetime import date

from backend.services.analytics_report import SITE_URL, nl_getal

BLAUW = "#2563eb"
BLAUW_LICHT = "#93c5fd"
INKT = "#0f172a"
GRIJS = "#64748b"
GRIJS_LICHT = "#94a3b8"
LIJN = "#e2e8f0"
VLAK = "#f8fafc"
GROEN = "#059669"
ROOD = "#dc2626"

MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"]


def _datum(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {MAANDEN[d.month - 1]}"


def _periode(this_s: str, this_e: str) -> str:
    a, b = date.fromisoformat(this_s), date.fromisoformat(this_e)
    if a.month == b.month:
        return f"{a.day} t/m {b.day} {MAANDEN[b.month - 1]}"
    return f"{_datum(this_s)} t/m {_datum(this_e)}"


# Merknamen schrijven zichzelf niet goed vanuit een url-slug.
_MERKEN = {"ebay": "eBay", "2dehands": "2dehands", "marktplaats": "Marktplaats",
           "vinted": "Vinted", "etsy": "Etsy", "shopify": "Shopify",
           "oneshop": "OneShop", "vendoo": "Vendoo", "crosslist": "Crosslist",
           "omnivaleur": "Omnivaleur", "facebook": "Facebook"}


def _woorden(tekst: str) -> str:
    return " ".join(_MERKEN.get(w, w) for w in tekst.split())


def _paginanaam(url: str) -> str:
    """Leesbare naam voor een pagina — een kaal pad zegt hem niets."""
    p = (url or "").replace(SITE_URL, "").split("?")[0].rstrip("/")
    for lang in ("/nl", "/fr", "/de"):
        if p.startswith(lang + "/"):
            p = p[len(lang):]
    if p in ("", "/"):
        return "Homepagina"
    if p == "/blog":
        return "Blog-overzicht"
    staart = p.rsplit("/", 1)[-1].replace("-", " ")
    if "/vergelijking/" in p or p.startswith("/vs/"):
        return "Vergelijking " + _woorden(staart.replace("omnivaleur vs ", "met "))
    if "/crosslisting/" in p or "/crosslisten/" in p:
        return _woorden(staart.replace(" to ", " → ")) + " (gids)"
    staart = _woorden(staart)
    return staart[:1].upper() + staart[1:]


# ---------------------------------------------------------------------------
# Bouwstenen
# ---------------------------------------------------------------------------
def _rij(inhoud: str, padding: str = "0 24px", rond: str = "") -> str:
    """Eén volle-breedte blok binnen de witte kaart."""
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
        f'style="background:#ffffff;border-left:1px solid {LIJN};border-right:1px solid {LIJN};{rond}">'
        f'<tr><td style="padding:{padding};">{inhoud}</td></tr></table>'
    )


def _kopje(tekst: str) -> str:
    return (f'<div style="font-size:13px;font-weight:800;color:{INKT};text-transform:uppercase;'
            f'letter-spacing:.6px;padding-bottom:10px;">{tekst}</div>')


def _verschil(nu: int, eerder: int | None, omhoog_is_goed: bool = True) -> str:
    """Absoluut verschil, niet procentueel: '+100%' op drie klikken is ruis."""
    if eerder is None:
        return f'<div style="font-size:12px;color:{GRIJS_LICHT};font-weight:600;">&nbsp;</div>'
    d = nu - eerder
    if d == 0:
        return (f'<div style="font-size:12px;color:{GRIJS_LICHT};font-weight:600;">'
                f'gelijk aan vorige week</div>')
    goed = (d > 0) == omhoog_is_goed
    kleur = GROEN if goed else ROOD
    pijl = "▲" if d > 0 else "▼"
    return (f'<div style="font-size:12px;color:{kleur};font-weight:700;">{pijl} {nl_getal(abs(d))} '
            f'<span style="color:{GRIJS_LICHT};font-weight:600;">was {nl_getal(eerder)}</span></div>')


def _tegel(label: str, waarde: str, onder: str) -> str:
    return (
        f'<td width="25%" style="padding:8px;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
        f'style="background:{VLAK};border:1px solid {LIJN};border-radius:10px;">'
        f'<tr><td style="padding:12px 10px;text-align:center;">'
        f'<div style="font-size:11px;color:{GRIJS};font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.5px;">{label}</div>'
        f'<div style="font-size:26px;font-weight:800;color:{INKT};padding:2px 0;">{waarde}</div>'
        f'{onder}</td></tr></table></td>'
    )


def _balken(trend: list[dict]) -> str:
    """De acht-wekengrafiek. Hoogte in pixels, want procenten doen het niet in mail."""
    gemeten = [w for w in trend if w["measured"]]
    top = max([w["clicks"] for w in gemeten] or [0]) or 1
    breedte = round(100 / len(trend), 2)

    cellen = []
    for i, w in enumerate(trend):
        laatste = i == len(trend) - 1
        if not w["measured"]:
            cellen.append(
                f'<td width="{breedte}%" style="padding:0 3px;vertical-align:bottom;">'
                f'<div style="height:14px;"></div>'
                f'<div style="height:6px;background:{LIJN};border-radius:3px 3px 0 0;font-size:0;">&nbsp;</div></td>')
            continue
        hoogte = max(6, round(w["clicks"] / top * 68))
        kleur = BLAUW if laatste else BLAUW_LICHT
        cellen.append(
            f'<td width="{breedte}%" style="padding:0 3px;vertical-align:bottom;">'
            f'<div style="height:14px;font-size:11px;text-align:center;'
            f'color:{INKT if laatste else GRIJS};font-weight:{800 if laatste else 700};">{w["clicks"]}</div>'
            f'<div style="height:{hoogte}px;background:{kleur};border-radius:4px 4px 0 0;font-size:0;">&nbsp;</div></td>')

    ongemeten = len(trend) - len(gemeten)
    links = (f'<td colspan="{ongemeten}" style="border-top:1px solid {LIJN};padding-top:6px;'
             f'font-size:11px;color:{GRIJS_LICHT};">← nog geen meting</td>') if ongemeten else ""
    rechts = (f'<td colspan="{len(trend) - ongemeten}" style="border-top:1px solid {LIJN};'
              f'padding-top:6px;font-size:11px;color:{GRIJS};text-align:right;">'
              f'{_datum(gemeten[0]["start"]) if gemeten else ""} → deze week</td>')

    return (
        _kopje("Acht weken terug")
        + f'<div style="font-size:12px;color:{GRIJS};padding:0 0 12px 0;margin-top:-8px;">'
          f'Bezoekers via Google per week</div>'
        + '<table width="100%" cellpadding="0" cellspacing="0" role="presentation">'
        + '<tr style="vertical-align:bottom;">' + "".join(cellen) + "</tr>"
        + "<tr>" + links + rechts + "</tr></table>"
    )


def _samenvatting(report: dict) -> str:
    """Eén zin die de week samenvat, in gevolgen."""
    seo = report.get("seo") or {}
    sc = report.get("social_content") or {}
    sg = report.get("signups") or {}
    views = sum(p["views"] for p in (sc.get("per_platform") or []))
    clicks = seo.get("total_clicks", 0)
    aanm = sg.get("this_week")

    staart = f"{nl_getal(clicks)} bezoeker{'s' if clicks != 1 else ''} via Google"
    if aanm is not None:
        staart += f" en {nl_getal(aanm)} nieuwe aanmelding{'en' if aanm != 1 else ''}"
    staart += "."

    if views >= 100 and clicks < 25:
        return (f"Je posts liepen goed ({nl_getal(views)} weergaven), maar dat bereik komt nog "
                f"niet op de site terecht: {staart}")
    if views >= 100:
        return f"{nl_getal(views)} weergaven op je posts, en op de site {staart}"
    return f"Deze week {staart}"


# ---------------------------------------------------------------------------
# Opmaak
# ---------------------------------------------------------------------------
def render_html(report: dict) -> str:
    this_s, this_e = report["period"]["this"]
    seo = report.get("seo") or {}
    sg = report.get("signups") or {}
    sc = report.get("social_content") or {}
    trend = report.get("trend") or []
    per_platform = [p for p in (sc.get("per_platform") or []) if p["posts_count"]]
    views = sum(p["views"] for p in per_platform)

    delen = []

    # Kop
    delen.append(
        f'<table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
        f'style="background:{BLAUW};border-radius:14px 14px 0 0;"><tr>'
        f'<td style="padding:22px 24px;">'
        f'<div style="color:#bfdbfe;font-size:12px;letter-spacing:1.2px;text-transform:uppercase;'
        f'font-weight:700;">Omnivaleur — weekrapport</div>'
        f'<div style="color:#ffffff;font-size:22px;font-weight:800;padding-top:4px;">'
        f'{_periode(this_s, this_e)}</div></td></tr></table>'
    )

    # Samenvatting
    delen.append(_rij(
        f'<div style="font-size:17px;line-height:1.5;color:{INKT};font-weight:600;">'
        f'{_samenvatting(report)}</div>', padding="20px 24px 4px 24px"))

    # Vier cijfers
    tegels = []
    if sg.get("available"):
        tegels.append(_tegel("Aanmeldingen", nl_getal(sg["this_week"]),
                             _verschil(sg["this_week"], sg["prev_week"])))
    if seo.get("connected"):
        tegels.append(_tegel("Bezoekers", nl_getal(seo["total_clicks"]),
                             _verschil(seo["total_clicks"], seo.get("total_clicks_prev"))))
        tegels.append(_tegel("Vertoond", nl_getal(seo["total_impressions"]),
                             f'<div style="font-size:12px;color:{GRIJS_LICHT};font-weight:600;">'
                             f'in Google</div>'))
    if per_platform:
        tegels.append(_tegel(
            "Weergaven", nl_getal(views),
            _verschil(views, sc.get("prev_views")) if sc.get("prev_views") else
            f'<div style="font-size:12px;color:{GRIJS_LICHT};font-weight:600;">'
            f'{sum(p["posts_count"] for p in per_platform)} posts</div>'))
    if tegels:
        delen.append(_rij(
            '<table width="100%" cellpadding="0" cellspacing="0" role="presentation"><tr>'
            + "".join(tegels[:4]) + "</tr></table>", padding="16px 16px 4px 16px"))

    # Verloop
    if any(w["measured"] for w in trend):
        delen.append(_rij(_balken(trend), padding="14px 24px 20px 24px"))

    # Acties
    acties = report.get("actions") or []
    if acties:
        regels = "<br>".join(
            f'<b>{i}.</b> {a}' for i, a in enumerate(acties, 1))
        delen.append(_rij(
            f'<table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
            f'style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:10px;">'
            f'<tr><td style="padding:16px 18px;">'
            f'<div style="font-size:13px;font-weight:800;color:#065f46;text-transform:uppercase;'
            f'letter-spacing:.6px;padding-bottom:8px;">Wat ik deze week zou doen</div>'
            f'<div style="font-size:14px;line-height:1.6;color:#064e3b;">{regels}</div>'
            f'</td></tr></table>', padding="6px 24px 20px 24px"))

    # Best bezochte pagina's
    paginas = [p for p in (seo.get("top_pages") or []) if p["clicks"]][:5]
    if paginas:
        koppen = "".join(
            f'<td style="padding:8px 10px;color:{GRIJS};font-size:11px;font-weight:700;'
            f'text-transform:uppercase;{stijl}">{tekst}</td>'
            for tekst, stijl in (("Pagina", "border-radius:6px 0 0 6px;"),
                                 ("Bezoek", "text-align:right;"),
                                 ("Plek in Google", "text-align:right;border-radius:0 6px 6px 0;")))
        regels = []
        for i, p in enumerate(paginas):
            rand = "" if i == len(paginas) - 1 else "border-bottom:1px solid #f1f5f9;"
            pos = p["position"]
            kleur = GROEN if pos <= 10 else (GRIJS if pos <= 20 else ROOD)
            regels.append(
                f'<tr><td style="padding:10px;{rand}color:{INKT};">{_paginanaam(p["url"])}</td>'
                f'<td style="padding:10px;{rand}text-align:right;font-weight:700;">{p["clicks"]}</td>'
                f'<td style="padding:10px;{rand}text-align:right;color:{kleur};font-weight:700;">'
                f'{round(pos)}</td></tr>')
        delen.append(_rij(
            _kopje("Best bezochte pagina's")
            + f'<table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
              f'style="font-size:14px;"><tr style="background:{VLAK};">{koppen}</tr>'
            + "".join(regels) + "</table>", padding="0 24px 18px 24px"))

    # Posts per platform
    if per_platform:
        top = max(p["views"] for p in per_platform) or 1
        regels = []
        for p in per_platform:
            aandeel = max(2, round(p["views"] / top * 100)) if p["views"] else 100
            balk = (f'<table width="{aandeel}%" cellpadding="0" cellspacing="0" role="presentation">'
                    f'<tr><td style="background:{BLAUW if p["views"] else "#f1f5f9"};height:10px;'
                    f'border-radius:5px;font-size:0;line-height:0;">&nbsp;</td></tr></table>')
            kleur = INKT if p["views"] else GRIJS_LICHT
            regels.append(
                f'<tr><td style="padding:6px 0;color:{kleur};width:90px;font-weight:600;">'
                f'{p["platform"]}</td>'
                f'<td style="padding:6px 0;">{balk}</td>'
                f'<td style="padding:6px 0 6px 10px;text-align:right;font-weight:800;color:{kleur};'
                f'width:110px;">{nl_getal(p["views"])}'
                f'<span style="color:{GRIJS_LICHT};font-weight:600;"> · {p["posts_count"]} posts</span>'
                f'</td></tr>')
        beste = ""
        if sc.get("by_content"):
            g = sc["by_content"][0]
            if g["total_views"]:
                titel = (g["text"][:70] + "…") if len(g["text"]) > 70 else g["text"]
                beste = (f'<div style="font-size:13px;color:{GRIJS};padding-top:14px;">'
                         f'<b style="color:{INKT};">Beste post:</b> “{titel}” — '
                         f'<b style="color:{INKT};">{nl_getal(g["total_views"])}</b> weergaven.</div>')
        delen.append(_rij(
            _kopje("Je posts")
            + '<table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
              'style="font-size:13px;">' + "".join(regels) + "</table>" + beste,
            padding="0 24px 20px 24px"))

    # Knop + voet
    delen.append(
        f'<table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
        f'style="background:#ffffff;border:1px solid {LIJN};border-top:0;border-radius:0 0 14px 14px;">'
        f'<tr><td style="padding:4px 24px 26px 24px;text-align:center;">'
        f'<a href="{SITE_URL}/analytics" style="display:inline-block;background:{BLAUW};'
        f'color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 26px;'
        f'border-radius:9px;">Alle cijfers bekijken →</a></td></tr></table>'
        f'<div style="text-align:center;font-size:11px;color:{GRIJS_LICHT};padding:14px 0 0 0;">'
        f'Elke zondagochtend automatisch. Alleen wat veranderd is.</div>'
    )

    return (
        '<div style="background:#f0f9ff;padding:24px 12px;font-family:-apple-system,'
        'BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif;">'
        '<div style="max-width:640px;margin:0 auto;">' + "".join(delen) + "</div></div>"
    )


def render_text(report: dict) -> str:
    """Terugvalversie zonder opmaak — zelfde volgorde, zelfde cijfers."""
    this_s, this_e = report["period"]["this"]
    seo = report.get("seo") or {}
    sg = report.get("signups") or {}
    sc = report.get("social_content") or {}
    per_platform = [p for p in (sc.get("per_platform") or []) if p["posts_count"]]

    r = [f"Omnivaleur — weekrapport {_periode(this_s, this_e)}", "", _samenvatting(report), ""]

    if sg.get("available"):
        r.append(f"Aanmeldingen: {sg['this_week']} (vorige week {sg['prev_week']})")
    if seo.get("connected"):
        r.append(f"Bezoekers via Google: {seo['total_clicks']} | vertoond: {seo['total_impressions']}")
    if per_platform:
        r.append("Weergaven op je posts: "
                 + nl_getal(sum(p["views"] for p in per_platform))
                 + " (" + ", ".join(f"{p['platform']} {nl_getal(p['views'])}" for p in per_platform) + ")")

    if report.get("actions"):
        r += ["", "Wat ik deze week zou doen:"]
        r += [f"  {i}. {a}" for i, a in enumerate(report["actions"], 1)]

    paginas = [p for p in (seo.get("top_pages") or []) if p["clicks"]][:5]
    if paginas:
        r += ["", "Best bezochte pagina's:"]
        r += [f"  • {_paginanaam(p['url'])} — {p['clicks']} bezoekers, plek {round(p['position'])}"
              for p in paginas]

    r += ["", f"Alle cijfers: {SITE_URL}/analytics",
          "Elke zondagochtend automatisch."]
    return "\n".join(r)


def render(report: dict) -> tuple[str, str, str]:
    """(onderwerp, platte tekst, opmaak)."""
    this_s, this_e = report["period"]["this"]
    return (f"📊 Weekrapport Omnivaleur — {_periode(this_s, this_e)}",
            render_text(report), render_html(report))
