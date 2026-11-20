"""Producten uit een webshop lezen via de openbare pagina's (sitemap + schema.org).

Voor webshops waar wij geen koppeling mee hebben (JouwWeb, en straks andere). Er is
geen inlog nodig en niets wordt in de winkel gewijzigd: alleen lezen.

Gemeten op een echte JouwWeb-winkel (19-11-2026): de sitemap noemt de productpagina's
als /product/<nummer>/<naam>, en elke pagina heeft schema.org Product-gegevens
(prijs, beschikbaarheid, artikelnummer, omschrijving) plus de foto's als og:image.

Het resultaat heeft dezelfde vorm als een scanregel van WooCommerce
(woocommerce_scan.naar_scanregel), zodat het later op dezelfde rails kan.
"""
from __future__ import annotations

import html
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import httpx

UA = "Mozilla/5.0 (compatible; OmnivaleurBot/1.0; +https://omnivaleur.com)"
PRODUCT_PAD = re.compile(r"/product/(\d+)/")


class WinkelFout(Exception):
    pass


def normaliseer(adres: str) -> str:
    adres = (adres or "").strip()
    if not adres:
        raise WinkelFout("Enter your shop's address, for example yourshop.nl.")
    if not adres.startswith(("http://", "https://")):
        adres = "https://" + adres
    p = urlparse(adres)
    if not p.netloc or "." not in p.netloc:
        raise WinkelFout("That doesn't look like a web address.")
    return f"{p.scheme}://{p.netloc}"


def _tekst(fragment: str) -> str:
    fragment = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    fragment = html.unescape(fragment)
    regels = [re.sub(r"[ \t ]+", " ", r).strip() for r in fragment.split("\n")]
    return "\n".join(r for r in regels if r).strip()


def productadressen(client: httpx.Client, basis: str) -> list[str]:
    """Alle productpagina's uit de sitemap (ook een sitemap van sitemaps)."""
    gezien: set[str] = set()
    uit: list[str] = []

    def lees(url: str, diepte: int = 0) -> None:
        if url in gezien or diepte > 2:
            return
        gezien.add(url)
        r = client.get(url)
        if r.status_code != 200:
            return
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text):
            loc = html.unescape(loc)
            if loc.endswith(".xml") or "sitemap" in loc.rsplit("/", 1)[-1]:
                lees(loc, diepte + 1)
            elif PRODUCT_PAD.search(loc) and loc not in uit:
                uit.append(loc)

    lees(basis + "/sitemap.xml")
    return uit


def _meta(h: str, naam: str) -> str | None:
    m = re.search(r'<meta[^>]+itemprop="%s"[^>]+content="([^"]*)"' % naam, h)
    return html.unescape(m.group(1)).strip() if m else None


def lees_product(h: str, url: str) -> dict | None:
    """Eén productpagina naar een scanregel. None als het geen productpagina is."""
    if "schema.org/Product" not in h:
        return None
    nr = PRODUCT_PAD.search(url)
    prijs_tekst = _meta(h, "price")
    try:
        prijs = float(prijs_tekst) if prijs_tekst else None
    except ValueError:
        prijs = None

    titel = None
    m = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S)
    if m:
        titel = _tekst(m.group(1)) or None
    if not titel:
        m = re.search(r'<meta property="og:title" content="([^"]*)"', h)
        titel = html.unescape(m.group(1)).split(" | ")[0].strip() if m else None

    omschrijving = None
    m = re.search(r'itemprop="description"[^>]*>(.*?)</div>\s*</div>', h, re.S)
    if m:
        omschrijving = _tekst(m.group(1)) or None
    if not omschrijving:
        m = re.search(r'<meta property="og:description" content="([^"]*)"', h)
        omschrijving = html.unescape(m.group(1)).strip() if m else None

    fotos: list[str] = []
    for f in re.findall(r'<meta property="og:image" content="([^"]+)"', h):
        f = html.unescape(f)
        if f not in fotos:
            fotos.append(f)

    beschikbaar = (_meta(h, "availability") or "").rsplit("/", 1)[-1]
    sku = _meta(h, "sku") or _meta(h, "productID")
    return {
        "platform_listing_id": nr.group(1) if nr else (sku or url),
        "platform_listing_url": url,
        "title": titel or "",
        "price": prijs,
        "photo_url": fotos[0] if fotos else None,
        "photo_urls": fotos,
        "description": omschrijving,
        "is_closed": beschikbaar in ("OutOfStock", "SoldOut", "Discontinued"),
        "sku": sku,
    }


def lees_winkel(adres: str, tempo: int = 4, max_producten: int | None = None) -> tuple[list[dict], list[str]]:
    """Leest alle producten. Geeft (producten, mislukte adressen)."""
    basis = normaliseer(adres)
    with httpx.Client(headers={"User-Agent": UA}, timeout=20.0, follow_redirects=True) as client:
        try:
            adressen = productadressen(client, basis)
        except httpx.HTTPError as e:
            raise WinkelFout(f"Couldn't reach {basis} ({type(e).__name__}).") from e
        if not adressen:
            raise WinkelFout("No product pages found in that shop's sitemap.")
        if max_producten:
            adressen = adressen[:max_producten]

        def een(url: str) -> dict | None:
            for _ in range(2):
                try:
                    r = client.get(url)
                    if r.status_code == 200:
                        return lees_product(r.text, url)
                except httpx.HTTPError:
                    pass
            raise WinkelFout(url)

        producten: list[dict] = []
        mislukt: list[str] = []
        with ThreadPoolExecutor(max_workers=tempo) as pool:
            futures = [(u, pool.submit(een, u)) for u in adressen]
            for u, f in futures:
                try:
                    p = f.result()
                except WinkelFout:
                    mislukt.append(u)
                    continue
                if p:
                    producten.append(p)
    return producten, mislukt
