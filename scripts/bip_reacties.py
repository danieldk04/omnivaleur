#!/usr/bin/env python3
"""Build in public: reacties onder Daniels eigen posts en beloften met een terugkomdatum.

Daniel schrijft elke dag een build-in-public post op X, Bluesky en Indie Hackers
(17-11-2026). Dit script doet het deel dat zonder browser kan en onthoudt wat al
gezien is, zodat dezelfde reactie niet twee keer wordt beantwoord of gemeld.

  bluesky [--posts 5]   onbeantwoorde reacties van anderen onder zijn laatste posts
  gezien SLEUTEL...     markeer reacties als afgehandeld (ook voor X en Indie Hackers)
  is-gezien SLEUTEL     afsluitcode 0 als al afgehandeld, anders 1
  due [--dagen 0]       beloften in docs/build-in-public-ideeen.md waarvan de
                        terugkomdatum is bereikt (of binnen --dagen dagen komt)

X en Indie Hackers leest Claude in Daniels ingelogde Chrome (zie data/social/ronde-prompt.txt);
daarvoor gebruikt hij `gezien` en `is-gezien` met een eigen sleutel, bijvoorbeeld
"x:<status-id>" of "ih:<post-slug>:<auteur>:<eerste 30 tekens>".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEZIEN = ROOT / "data" / "social" / "bip-gezien.json"
IDEEEN = ROOT / "docs" / "build-in-public-ideeen.md"
API = "https://public.api.bsky.app/xrpc/"
HANDLE = "danieldekoning.bsky.social"
UITGEWERKT = ("gemeld", "klaar", "vervallen")


# ── Wat al gezien is ───────────────────────────────────────────────────────────
def lees_gezien(pad: Path = GEZIEN) -> dict:
    try:
        d = json.loads(pad.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def zet_gezien(sleutels, pad: Path = GEZIEN, nu: date | None = None) -> int:
    d = lees_gezien(pad)
    dag = (nu or date.today()).isoformat()
    nieuw = 0
    for s in sleutels:
        if s and s not in d:
            d[s] = dag
            nieuw += 1
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(json.dumps(d, indent=1, sort_keys=True) + "\n")
    return nieuw


# ── Bluesky ────────────────────────────────────────────────────────────────────
def _haal(pad: str, **params) -> dict:
    url = API + pad + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def onbeantwoord(draad: dict, eigen_did: str) -> list[dict]:
    """Alle reacties van anderen in een draad waar Daniel nog niet op antwoordde.

    Een reactie telt als beantwoord zodra een directe reactie eronder van Daniel zelf is.
    Reacties van Daniel zelf worden nooit teruggegeven."""
    uit: list[dict] = []

    def loop(knoop: dict) -> None:
        for r in knoop.get("replies") or []:
            post = r.get("post") or {}
            auteur = post.get("author") or {}
            if auteur.get("did") != eigen_did:
                eronder = [x for x in (r.get("replies") or [])
                           if ((x.get("post") or {}).get("author") or {}).get("did") == eigen_did]
                if not eronder:
                    uit.append({
                        "sleutel": "bsky:" + post.get("uri", "").rsplit("/", 1)[-1],
                        "uri": post.get("uri"),
                        "cid": post.get("cid"),
                        "auteur": auteur.get("handle"),
                        "tijd": (post.get("indexedAt") or "")[:16],
                        "tekst": (post.get("record") or {}).get("text", ""),
                    })
            loop(r)

    loop(draad.get("thread") or {})
    return uit


def bluesky(aantal: int = 5, gezien: dict | None = None, haal=_haal) -> list[dict]:
    gezien = lees_gezien() if gezien is None else gezien
    feed = haal("app.bsky.feed.getAuthorFeed", actor=HANDLE, limit=aantal,
                filter="posts_no_replies").get("feed") or []
    uit: list[dict] = []
    for item in feed:
        post = item.get("post") or {}
        eigen = (post.get("author") or {}).get("did")
        if not post.get("uri") or not eigen:
            continue
        draad = haal("app.bsky.feed.getPostThread", uri=post["uri"], depth=8)
        for r in onbeantwoord(draad, eigen):
            if r["sleutel"] in gezien:
                continue
            r["post"] = post["uri"].rsplit("/", 1)[-1]
            r["post_tekst"] = (post.get("record") or {}).get("text", "")[:80]
            uit.append(r)
    return uit


# ── Beloften met een terugkomdatum ─────────────────────────────────────────────
_DATUM = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")


def _cellen(regel: str) -> list[str]:
    return [c.strip() for c in regel.strip().strip("|").split("|")]


def beloften(tekst: str) -> list[dict]:
    """Rijen uit de tabel 'Open beloften aan de lezers' met hun terugkomdatum."""
    uit: list[dict] = []
    in_sectie, kop = False, None
    for regel in tekst.splitlines():
        if regel.startswith("## "):
            in_sectie = "beloften" in regel.lower()
            kop = None
            continue
        if not in_sectie or not regel.strip().startswith("|"):
            continue
        cellen = _cellen(regel)
        if kop is None:
            kop = [c.lower() for c in cellen]
            continue
        if set("".join(cellen)) <= set("-: "):
            continue
        rij = dict(zip(kop, cellen))
        terug = next((v for k, v in rij.items() if k.startswith("terugkom")), "")
        m = _DATUM.search(terug)
        datum = None
        if m:
            try:
                datum = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                datum = None
        status = next((v for k, v in rij.items() if k.startswith("status")), "")
        uit.append({"belofte": next((v for k, v in rij.items() if k.startswith("wat")), ""),
                    "post": next((v for k, v in rij.items() if k.startswith("post")), ""),
                    "meting": next((v for k, v in rij.items() if k.startswith("meting")), ""),
                    "terugkom": datum, "status": status})
    return uit


def due(tekst: str, vandaag: date | None = None, dagen: int = 0) -> list[dict]:
    """Beloften waarvan de terugkomdatum is bereikt (of binnen `dagen` dagen komt)
    en die nog niet zijn gemeld."""
    grens = (vandaag or date.today()) + timedelta(days=dagen)
    return [b for b in beloften(tekst)
            if b["terugkom"] and b["terugkom"] <= grens
            and not b["status"].lower().startswith(UITGEWERKT)]


# ── Opdrachtregel ──────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bluesky"); b.add_argument("--posts", type=int, default=5)
    g = sub.add_parser("gezien"); g.add_argument("sleutels", nargs="+")
    i = sub.add_parser("is-gezien"); i.add_argument("sleutel")
    d = sub.add_parser("due"); d.add_argument("--dagen", type=int, default=0)
    a = p.parse_args(argv)

    if a.cmd == "bluesky":
        try:
            rijen = bluesky(a.posts)
        except Exception as e:  # noqa: BLE001
            print(f"Bluesky niet bereikbaar: {e}", file=sys.stderr)
            return 2
        print(json.dumps(rijen, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "gezien":
        print(f"{zet_gezien(a.sleutels)} nieuw als gezien gemarkeerd")
        return 0
    if a.cmd == "is-gezien":
        return 0 if a.sleutel in lees_gezien() else 1
    if a.cmd == "due":
        rijen = due(IDEEEN.read_text(), dagen=a.dagen)
        for r in rijen:
            print(f"{r['terugkom'].strftime('%d-%m-%Y')} | {r['post']} | {r['belofte']} | meting: {r['meting']}")
        if not rijen:
            print("Geen beloften die nu aan de beurt zijn.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
