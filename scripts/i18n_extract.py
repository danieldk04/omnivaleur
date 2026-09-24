"""Haalt elke zichtbare Engelse zin uit het dashboard, voor de vertaallaag.

De vertaallaag (frontend/i18n.js) vertaalt op het scherm: elke tekst die in de
pagina verschijnt wordt opgezocht in frontend/i18n/nl.json. Dit script vindt de
zinnen die daar in moeten staan, op dezelfde manier waarop de browser ze later
ziet: tekstknopen uit HTML, ook uit HTML die JavaScript in elkaar zet, plus losse
teksten in JavaScript (meldingen, knopteksten, alert/confirm).

Gebruik:
    python3 scripts/i18n_extract.py            # toont wat nog geen vertaling heeft
    python3 scripts/i18n_extract.py --alles    # toont alles wat gevonden is
    python3 scripts/i18n_extract.py --json     # hetzelfde als JSON (voor hulpmiddelen)
    python3 scripts/i18n_extract.py --versie   # zet ?v= in de pagina's gelijk aan nl.json
    python3 scripts/i18n_extract.py --live     # wat klanten nog Engels zagen (meldpunt)

Wat geen zin voor de gebruiker is (een klassenaam, een kanaalnaam, een API-veld)
en toch als kandidaat opduikt, zet je in frontend/i18n/negeer.txt.
tests/test_i18n_compleet.py faalt zolang er iets in geen van beide staat.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
WOORDENBOEK = FRONTEND / "i18n" / "nl.json"
NEGEER = FRONTEND / "i18n" / "negeer.txt"

# Pagina's die de vertaallaag laden. beheer.html is alleen voor Daniel en blijft
# Engels; de openbare site heeft zijn eigen Nederlandse kopieën (nl.html, blog).
PAGINAS = [
    "app.html",
    "login.html",
    "register.html",
    "forgot-password.html",
    "reset-password.html",
    "ebay-callback.html",
    "shopify-callback.html",
]
SCRIPTS = ["onboarding.js"]
# Foutteksten die de extensie naar het dashboard stuurt. Die komen daar als
# gewone tekst op het scherm en worden dus ook in het dashboard vertaald.
EXTENSIE = [
    "extension/background.js",
    "extension/content/shared.js",
    "extension/content/vinted.js",
    "extension/content/marktplaats.js",
    "extension/content/tweedehands.js",
    "extension/content/facebook.js",
]

# Meldingen van de server die het dashboard letterlijk toont: HTTPException-
# details en de fout-/berichtvelden van opdrachten en antwoorden.
SERVER = sorted(
    str(p.relative_to(ROOT)) for p in (ROOT / "backend").rglob("*.py")
    if "content" not in p.parts
)

ATTRIBUTEN = ("title", "placeholder", "aria-label", "data-tip")
PLEK = "\x00"  # tijdelijk teken voor ${...} tot de tekst genummerd wordt


# ── JavaScript in stukjes ──────────────────────────────────────────────────

_REGEX_VOOR = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_WOORDEN = {"return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "else", "do"}


def _escape(src, j):
    """src[j] is een backslash. Geeft (teken, nieuwe positie)."""
    nxt = src[j + 1]
    if nxt == "u":
        if src[j + 2:j + 3] == "{":
            e = src.index("}", j + 3)
            return chr(int(src[j + 3:e], 16)), e + 1
        try:
            return chr(int(src[j + 2:j + 6], 16)), j + 6
        except ValueError:
            return "u", j + 2
    if nxt == "x":
        try:
            return chr(int(src[j + 2:j + 4], 16)), j + 4
        except ValueError:
            return "x", j + 2
    return {"n": "\n", "t": "\t", "r": "", "b": "", "0": ""}.get(nxt, nxt), j + 2


def js_teksten(src: str, start_regel: int = 1):
    """Geeft (regel, soort, tekst, naast_plus) voor elke tekst in JavaScript.

    soort is "q" voor '...' en "...", "t" voor `...`. In een `...` wordt elke
    ${...} vervangen door PLEK; teksten binnen die ${...} komen los mee.
    naast_plus is True als er een + direct voor of na staat (aan elkaar geplakt).
    """
    uit = []
    i, n = 0, len(src)
    regel = start_regel
    vorige = ""  # laatste betekenisvolle teken of woord, voor regex-herkenning

    def lees_string(i, q):
        nonlocal regel
        j = i + 1
        buf = []
        while j < n:
            c = src[j]
            if c == "\\" and j + 1 < n:
                teken, j = _escape(src, j)
                if teken == "\n" and src[j - 1] == "\n":
                    regel += 1
                    teken = ""
                buf.append(teken)
                continue
            if c == q:
                return j + 1, "".join(buf)
            if c == "\n":
                regel += 1
            buf.append(c)
            j += 1
        return j, "".join(buf)

    def lees_template(i):
        """i wijst naar de openende backtick. Geeft (einde, tekst, binnenteksten)."""
        nonlocal regel
        j = i + 1
        buf = []
        binnen = []
        while j < n:
            c = src[j]
            if c == "\\" and j + 1 < n:
                teken, j = _escape(src, j)
                buf.append(teken)
                continue
            if c == "`":
                return j + 1, "".join(buf), binnen
            if c == "$" and j + 1 < n and src[j + 1] == "{":
                # zoek de bijbehorende }
                diepte = 1
                k = j + 2
                expr_start = k
                while k < n and diepte:
                    ck = src[k]
                    if src.startswith("//", k):
                        e = src.find("\n", k)
                        k = n if e < 0 else e
                        continue
                    if src.startswith("/*", k):
                        e = src.find("*/", k + 2)
                        k = n if e < 0 else e + 2
                        continue
                    if ck in "'\"":
                        k, _ = lees_string(k, ck)
                        continue
                    if ck == "`":
                        k, _, _ = lees_template(k)
                        continue
                    if ck == "{":
                        diepte += 1
                    elif ck == "}":
                        diepte -= 1
                    elif ck == "\n":
                        regel += 1
                    k += 1
                expr = src[expr_start:k - 1]
                binnen.append((regel, expr))
                buf.append(PLEK)
                j = k
                continue
            if c == "\n":
                regel += 1
            buf.append(c)
            j += 1
        return j, "".join(buf), binnen

    def plus_ervoor(pos):
        k = pos - 1
        while k >= 0 and src[k] in " \t\r\n":
            k -= 1
        return k >= 0 and src[k] == "+" and (k == 0 or src[k - 1] != "+")

    def plus_erna(pos):
        k = pos
        while k < n and src[k] in " \t\r\n":
            k += 1
        return k < n and src[k] == "+" and (k + 1 >= n or src[k + 1] != "+")

    while i < n:
        c = src[i]
        if c == "\n":
            regel += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            e = src.find("*/", i + 2)
            e = n if e < 0 else e + 2
            regel += src.count("\n", i, e)
            i = e
            continue
        if c == "/" and (vorige == "" or vorige in _REGEX_VOOR or vorige in _REGEX_WOORDEN):
            # regex-literal overslaan
            j = i + 1
            in_klasse = False
            while j < n and src[j] != "\n":
                cj = src[j]
                if cj == "\\":
                    j += 2
                    continue
                if cj == "[":
                    in_klasse = True
                elif cj == "]":
                    in_klasse = False
                elif cj == "/" and not in_klasse:
                    break
                j += 1
            j += 1
            while j < n and src[j].isalpha():
                j += 1
            i = j
            vorige = ")"
            continue
        if c in "'\"":
            r = regel
            e, tekst = lees_string(i, c)
            uit.append((r, "q", tekst, plus_ervoor(i) or plus_erna(e)))
            i = e
            vorige = ")"
            continue
        if c == "`":
            r = regel
            e, tekst, binnen = lees_template(i)
            uit.append((r, "t", tekst, plus_ervoor(i) or plus_erna(e)))
            for br, expr in binnen:
                uit.extend(js_teksten(expr, br))
            i = e
            vorige = ")"
            continue
        if c.isalnum() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            vorige = src[i:j]
            i = j
            continue
        vorige = c
        i += 1
    return uit


# ── HTML in stukjes ────────────────────────────────────────────────────────

class _Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stapel = []
        self.teksten = []  # (regel_offset, tekst, soort)
        self.scripts = []  # (regel, inhoud)
        self._script_start = None
        self._stil = 0  # binnen translate="no"

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        stil = a.get("translate") == "no" or "notranslate" in (a.get("class") or "").split()
        if tag not in ("br", "img", "input", "hr", "meta", "link", "source", "wbr", "col", "area", "base", "embed", "param", "track"):
            self.stapel.append((tag, stil))
            if stil:
                self._stil += 1
        if tag == "script" and not a.get("src"):
            self._script_start = (self.getpos()[0], len(self.rawdata))
        if self._stil and not stil:
            return
        for naam in ATTRIBUTEN:
            if a.get(naam):
                self.teksten.append((self.getpos()[0], a[naam], "attr"))
        if tag == "input" and (a.get("type") or "").lower() in ("button", "submit", "reset") and a.get("value"):
            self.teksten.append((self.getpos()[0], a["value"], "attr"))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        while self.stapel:
            t, stil = self.stapel.pop()
            if stil:
                self._stil -= 1
            if t == tag:
                break

    def huidige(self):
        return self.stapel[-1][0] if self.stapel else ""

    def handle_data(self, data):
        tag = self.huidige()
        if tag == "script":
            self.scripts.append((self.getpos()[0], data))
            return
        if tag == "style" or self._stil:
            return
        self.teksten.append((self.getpos()[0], data, "text"))


def html_teksten(html: str, regel0: int = 1):
    p = _Html()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass
    teksten = [(regel0 + r - 1, t, s) for r, t, s in p.teksten]
    scripts = [(regel0 + r - 1, s) for r, s in p.scripts]
    return teksten, scripts


# ── Wat telt als zin voor de gebruiker ─────────────────────────────────────

def normaliseer(tekst: str) -> str:
    """Witruimte samenvouwen zoals de browser het op het scherm toont.

    Plekken worden {0}, {1}, ... op volgorde. Staat de tekst helemaal uit een
    plek, dan is er niets te vertalen.
    """
    t = re.sub(r"\s+", " ", tekst.replace("\xa0", " ")).strip()
    teller = iter(range(100))
    t = re.sub(PLEK + "+", lambda m: "{" + str(next(teller)) + "}", t)
    return t


_GEEN_ZIN = [
    re.compile(r"^https?://|^/|^\.{0,2}/|^mailto:|^data:|^#[\w-]+$|^\.[\w-]+"),
    re.compile(r"^[\w.-]+@[\w.-]+$"),
    re.compile(r"^[a-z0-9_$.:\-/\[\]{}()=]+$"),  # klassen, sleutels, paden, selectors
    re.compile(r"^[A-Z0-9_]+$"),  # CONSTANTEN, GET, POST
    re.compile(r"^[\d\s.,:%€$+\-×x/()]+$"),
    re.compile(r"^[\w-]+\s*:\s*[^.!?]*;"),  # css
    re.compile(r"^;?[\w-]*\s*:?\s*var\(--"),  # css-variabelen
    re.compile(r"[{}<>;]\s*$"),
]


_NL = re.compile(
    r"\b(het|een|niet|geen|je|jouw|jij|van|voor|zijn|wordt|werd|naar|bij|deze|moet|maar|nog|ook|dat|die|met|"
    r"op|de|er|mislukt|ongeldig|opdracht|advertentie|zoekertje|staat|kan|nodig|alleen|wat|wij|we|ons|"
    r"onze|hij|zij|zelf|eerst|daarna|omdat|terwijl)\b", re.I)
_EN = re.compile(
    r"\b(the|you|your|to|is|are|not|could|and|of|for|this|was|has|have|be|with|on|no|please|try|"
    r"again|will|it|in|from|here|what|when|failed|click|item|items|listing|listings)\b", re.I)


_KLEIN_ENGELS = re.compile(
    r"\b(the|a|an|to|of|and|in|on|as|for|with|is|are|you|your|it|this|that|not|no|by|from|at|or|be|"
    r"was|will|can|all|still|yet|more|here|there|now|again|nothing|never|already|waiting|queued|done|"
    r"failed|until|left|ago|selected|found|items?|listings?)\b")


def lijkt_nederlands(t: str) -> bool:
    nl = len(_NL.findall(t))
    return nl >= 2 and nl > len(_EN.findall(t))


_NOOIT_TEKST = [
    re.compile(r"^https?://|^mailto:|^data:|^chrome://|://|^[\w.+-]+@[\w.-]+$|^\.?[\w-]+\.(com|nl|be)$"),
    re.compile(r"^[\d\s.,:%€$+\-×x/()]+$"),
    re.compile(r"^\d*X{0,2}[SML]$|^\d*XL$|^XX?S$"),  # maten
    re.compile(r"^[a-z]+_[a-z_]+$"),  # read_orders
]


def is_kandidaat(t: str, html_tekst: bool = False) -> bool:
    """html_tekst: de tekst staat als tekstknoop in HTML en is dus zichtbaar.
    Dan telt ook een los woordje in kleine letters ("days", "hidden")."""
    if html_tekst:
        kaal = re.sub(r"\{\d+\}", "", t).strip()
        return bool(re.search(r"[A-Za-z]{2}", kaal)) and not any(p.search(kaal) for p in _NOOIT_TEKST) \
            and not lijkt_nederlands(t)
    if not t or not re.search(r"[A-Za-z]{2}", t):
        return False
    # zonder de plekken moet er nog iets overblijven om te vertalen
    kaal = re.sub(r"\{\d+\}", "", t)
    if not re.search(r"[A-Za-z]{2}", kaal):
        return False
    if any(p.search(kaal.strip() or t) for p in _GEEN_ZIN):
        return False
    # Alles in kleine letters: meestal klassen of sleutels ("btn btn-primary",
    # "heren polo's"), maar een zinsdeel als "as the extension" is tekst.
    if re.fullmatch(r"[a-z][\w'-]*(\s+[a-z0-9][\w'-]*)*", t) and not _KLEIN_ENGELS.search(t):
        return False
    if lijkt_nederlands(t):
        return False
    if re.search(r"[a-z][A-Z]", t) and " " not in t:  # camelCase
        return False
    if re.search(r"=>|===|&&|\|\||\bfunction\s*\(|\bconst \w+ =|\breturn [\w(]+;|document\.|\bvar \w+ =|\w\(\)", t):
        return False
    return True


def bevat_html(t: str) -> bool:
    return bool(re.search(r"<\s*/?\s*[a-zA-Z][\w-]*[^<>]*>", t))


def _bron_lezen(pad: Path):
    return pad.read_text(encoding="utf-8")


def _uit_js(src, regel0, bron, kand):
    for r, soort, tekst, plus in js_teksten(src, regel0):
        if bevat_html(tekst):
            teksten, _ = html_teksten(tekst, r)
            for rr, tt, s in teksten:
                _voeg(kand, tt, bron, rr, plus, s == "text")
        else:
            _voeg(kand, tekst, bron, r, plus)


def _voeg(kand, ruw, bron, regel, plus, html_tekst=False):
    if re.search(r"&(#\d+|[a-zA-Z]+);", ruw):
        ruw = html.unescape(ruw)
    t = normaliseer(ruw)
    if PLEK in t:
        return
    if not is_kandidaat(t, html_tekst):
        return
    k = kand.setdefault(t, {"plekken": [], "plus": False})
    k["plekken"].append(f"{bron}:{regel}")
    k["plus"] = k["plus"] or plus


_EXT_FOUT = re.compile(r"(throw new Error\(|\berror:\s*|reason:\s*|message:\s*)")


def _uit_extensie(src, bron, kand):
    """Alleen wat de extensie als fout of reden doorstuurt telt; de rest
    (logregels, selectors, formulierteksten van de sites zelf) niet."""
    for m in _EXT_FOUT.finditer(src):
        start = m.end()
        # pak het stuk tot het einde van de uitdrukking (; of een regel met ,)
        stuk = src[start:start + 600]
        e = re.search(r";|\n\s*[}\]]|,\s*\n\s*\w+:", stuk)
        stuk = stuk[: e.start()] if e else stuk
        regel0 = src.count("\n", 0, start) + 1
        for r, soort, tekst, plus in js_teksten(stuk, regel0):
            _voeg(kand, tekst, bron, r, plus)


_PY_CONTEXT = re.compile(
    r"""(\bdetail\s*=\s*|["'](?:error|message|error_message|reason|hint|melding)["']\s*:\s*)"""
)
_PY_STRING = re.compile(
    r"""\s*(?:\(\s*)?([rRbBuUfF]{0,2})("{3}|'{3}|"|')"""
)


def _py_string(src, i):
    """Leest opeenvolgende Python-strings vanaf i (impliciet aan elkaar geplakt).
    Geeft de tekst terug met {..} uit f-strings als PLEK, of None."""
    delen = []
    while True:
        m = _PY_STRING.match(src, i)
        if not m:
            break
        prefix, q = m.group(1).lower(), m.group(2)
        j = m.end()
        buf = []
        while j < len(src):
            if src.startswith(q, j):
                break
            c = src[j]
            if c == "\\" and j + 1 < len(src):
                nxt = src[j + 1]
                buf.append({"n": "\n", "t": "\t"}.get(nxt, "" if nxt == "\n" else nxt))
                j += 2
                continue
            if c == "\n" and len(q) == 1:
                return None
            if "f" in prefix and c == "{":
                if src.startswith("{{", j):
                    buf.append("{")
                    j += 2
                    continue
                diepte, k = 1, j + 1
                while k < len(src) and diepte:
                    diepte += {"{": 1, "}": -1}.get(src[k], 0)
                    k += 1
                buf.append(PLEK)
                j = k
                continue
            if "f" in prefix and src.startswith("}}", j):
                buf.append("}")
                j += 2
                continue
            buf.append(c)
            j += 1
        delen.append("".join(buf))
        i = j + len(q)
    return "".join(delen) if delen else None


def _uit_server(src, bron, kand):
    for m in _PY_CONTEXT.finditer(src):
        tekst = _py_string(src, m.end())
        if tekst is None:
            continue
        regel = src.count("\n", 0, m.start()) + 1
        # PLEK blijft staan: normaliseer() maakt er {0}, {1} van
        _voeg(kand, tekst, bron, regel, False)


def kandidaten() -> dict:
    kand: dict = {}
    for naam in PAGINAS:
        src = _bron_lezen(FRONTEND / naam)
        teksten, scripts = html_teksten(src)
        for r, t, s in teksten:
            _voeg(kand, t, naam, r, False, s == "text")
        for r, s in scripts:
            _uit_js(s, r, naam, kand)
    for naam in SCRIPTS:
        _uit_js(_bron_lezen(FRONTEND / naam), 1, naam, kand)
    for naam in EXTENSIE:
        _uit_extensie(_bron_lezen(ROOT / naam), naam, kand)
    for naam in SERVER:
        _uit_server(_bron_lezen(ROOT / naam), naam, kand)
    return kand


def woordenboek() -> dict:
    return json.loads(WOORDENBOEK.read_text(encoding="utf-8")) if WOORDENBOEK.exists() else {}


def negeerlijst() -> set:
    if not NEGEER.exists():
        return set()
    return {
        r.rstrip("\n") for r in NEGEER.read_text(encoding="utf-8").splitlines()
        if r.strip() and not r.startswith("# ")
    }


def _lijkt_engels_zin(t: str) -> bool:
    return len(_EN.findall(t)) >= 2 and len(_EN.findall(t)) > len(_NL.findall(t))


class Vertaler:
    """Dezelfde regels als frontend/i18n.js, om te controleren of een tekst op
    het scherm vertaald wordt: letterlijk, via een patroon met {0}, zin voor
    zin, of na een voorvoegsel als "Vinted: "."""

    def __init__(self, wb: dict):
        self.exact = {k: v for k, v in wb.items() if not re.search(r"\{\d+\}", k)}
        self.patronen = []
        self.meervoud = {}
        for k, v in wb.items():
            if not re.search(r"\{\d+\}", k):
                continue
            delen = re.split(r"(\{\d+\})", k)
            bron = "".join("(.*?)" if re.fullmatch(r"\{\d+\}", d) else re.escape(d).replace(r"\ ", r"\s+") for d in delen)
            self.patronen.append((re.compile("^" + bron + "$"), k, v))
            self.meervoud[k] = {int(n) for n in re.findall(r"\{(\d+)\|", v)}
        # Specifiekste patroon eerst, net als in de browser.
        self.patronen.sort(key=lambda p: -len(re.sub(r"\{\d+\}", "", p[1])))

    def _past(self, rx, s):
        """Past het patroon, zonder dat een lang Engels stuk als invulling meelift?"""
        m = rx.match(s)
        if not m:
            return False
        sleutel = next(k for r, k, _ in self.patronen if r is rx)
        volgorde = [int(n) for n in re.findall(r"\{(\d+)\}", sleutel)]
        for nr, g in zip(volgorde, m.groups()):
            if nr in self.meervoud.get(sleutel, ()) and g not in ("", "s", "es") and not re.fullmatch(r"\{\d+\}", g):
                return False
        for g in m.groups():
            if len(g) > 30 and _lijkt_engels_zin(g) and self.vertaal(g.strip()) is None:
                return False
        return True

    def vertaal(self, s: str):
        if s in self.exact:
            return self.exact[s]
        for rx, k, v in self.patronen:
            if self._past(rx, s):
                return v
        slot = re.match(r"^(.*[^.:])(\.\.?|:)$", s)
        if slot and len(slot.group(1)) > 2 and self.vertaal_zin(slot.group(1)) is not None:
            return self.vertaal_zin(slot.group(1))
        delen = re.split(r"(?<=[.!?…])\s+(?=[A-Z\"'(“‘0-9])", s)
        if len(delen) > 1:
            los = [self.vertaal(z) for z in delen]
            if all(z is not None for z in los):
                return " ".join(los)
        if " | " in s:
            kop = self.vertaal(s.split(" | ", 1)[0])
            if kop is not None:
                return kop + " | " + s.split(" | ", 1)[1]
        m = re.match(r"^(\d{1,2}\.\s+|[^:]{1,30}:\s+|[^\w\s\"'(]{1,4}\s*)(.+)$", s)
        if m:
            rest = self.vertaal(m.group(2))
            if rest is not None:
                return m.group(1) + rest
        return None

    def deel_van_patroon(self, t: str) -> bool:
        kaal = re.sub(r"\{\d+\}", "{}", t)
        return any(kaal in re.sub(r"\{\d+\}", "{}", k) for _, k, _ in self.patronen)

    def vertaal_zin(self, z):
        if z in self.exact:
            return self.exact[z]
        for rx, k, v in self.patronen:
            if self._past(rx, z):
                return v
        return None


def gedekt(t: str, vt: "Vertaler", negeer: set, plus: bool = False) -> bool:
    """Een kandidaat is gedekt als de vertaallaag hem op het scherm vertaalt,
    als hij op de negeerlijst staat, of als hij een stuk is van een patroon met
    {0}: de tekst 'Failed on ' + kanaal wordt op het scherm 'Failed on Vinted'
    en valt onder het patroon 'Failed on {0}'."""
    if t in negeer or vt.vertaal(t) is not None:
        return True
    if " | " in t:  # technische staart van een extensiemelding blijft staan
        return gedekt(t.split(" | ", 1)[0], vt, negeer, plus)
    # Een los woord ("Close") moet zelf in het woordenboek; alleen een echt stuk
    # van een samengestelde zin mag onder een patroon vallen.
    stuk = plus or len(t) >= 12
    if stuk and vt.deel_van_patroon(t):
        return True
    zinnen = re.split(r"(?<=[.!?…])\s+", t)
    return len(zinnen) > 1 and all(
        vt.vertaal(z) is not None or (stuk and vt.deel_van_patroon(z)) for z in zinnen if re.search(r"[A-Za-z]{2}", z)
    )


def ontbrekend():
    vt, neg = Vertaler(woordenboek()), negeerlijst()
    return {t: v for t, v in kandidaten().items() if not gedekt(t, vt, neg, v["plus"])}


def versie() -> str:
    """Hash van woordenboek én vertaler. De service worker (frontend/sw.js) geeft
    statische bestanden eerst uit zijn cache; een nieuw ?v= is de enige manier
    waarop een browser de nieuwe versie ophaalt."""
    h = hashlib.sha1(WOORDENBOEK.read_bytes())
    h.update((FRONTEND / "i18n.js").read_bytes())
    return h.hexdigest()[:10]


_VERSIE_RE = re.compile(r'(/i18n\.js\?v=)[0-9a-f]+')


def zet_versie():
    v = versie()
    for naam in PAGINAS:
        pad = FRONTEND / naam
        src = pad.read_text(encoding="utf-8")
        nieuw = _VERSIE_RE.sub(lambda m: m.group(1) + v, src)
        if nieuw != src:
            pad.write_text(nieuw, encoding="utf-8")
            print(f"{naam}: ?v={v}")


def live():
    """Wat browsers in het Nederlands op het scherm zagen en niet konden vertalen
    (gemeld via /api/i18n/ontbrekend). Nodig: SUPABASE_URL en de service-sleutel."""
    sys.path.insert(0, str(ROOT))
    from backend.database import get_admin_db  # noqa: PLC0415

    rijen = get_admin_db().table("leadgen_opslag").select("inhoud").eq("naam", "i18n_ontbrekend").execute().data
    lijst = rijen[0]["inhoud"] if rijen else {}
    vt = Vertaler(woordenboek())
    for zin, rij in sorted(lijst.items(), key=lambda kv: -int(kv[1].get("aantal", 0))):
        status = "nu vertaald" if vt.vertaal(zin) is not None else "ONTBREEKT"
        print(f"{rij.get('aantal', 0):>4}x  {status:<11} {rij.get('pagina', '')} {rij.get('plek', '')[:30]}\n      {zin}")


if __name__ == "__main__":
    if "--live" in sys.argv:
        live()
        sys.exit(0)
    if "--versie" in sys.argv:
        zet_versie()
        sys.exit(0)
    data = kandidaten() if "--alles" in sys.argv else ontbrekend()
    if "--json" in sys.argv:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        def _volgorde(kv):
            bron, _, regel = kv[1]["plekken"][0].rpartition(":")
            return bron, int(regel)
        for t, v in sorted(data.items(), key=_volgorde):
            vlag = " [+]" if v["plus"] else ""
            print(f"{v['plekken'][0]}{vlag}\t{t}")
        print(f"\n{len(data)} teksten", file=sys.stderr)
