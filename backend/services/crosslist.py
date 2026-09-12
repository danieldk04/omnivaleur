"""
Core crosslisting orchestration.
Handles: publish to multiple platforms, auto-delist on sale.
"""
from __future__ import annotations
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
import uuid

from backend.database import execute_with_retry, fetch_all, get_db, naast_de_lus, eerste_rij
from backend.platforms import get_platform

_ENGLISH_PLATFORMS = {"vinted", "shopify", "ebay", "etsy"}
# marktplaats/2dehands require Dutch — user now enters English, so translate EN→NL.
_DUTCH_PLATFORMS: set[str] = {"marktplaats", "2dehands"}

logger = logging.getLogger(__name__)

# Hoe lang een geclaimde publicatieopdracht zonder teken van leven nog als "echt
# bezig" telt. Klikt de gebruiker binnen die tijd nóg eens op publiceren, dan is
# de extensie waarschijnlijk gewoon aan het werk; daarna niet meer.
STALE_CLAIM_SECONDS = 60


# ── Geen webadres in een Marktplaats- of 2dehands-advertentie ──────────────
#
# WAAROM DIT ER IS (09-09-2026, Egbert Brouwer / papas-plectrums), en dit is de
# echte oorzaak achter drie weken "2dehands doet het niet".
#
# In zijn advertentietekst staat, onder elk artikel:
#     https://www.papas-plectrums.nl
#     info@papas-plectrums.nl
# 2dehands.be herkent dat webadres en verkoopt de advertentie dan als
# "Websitevermelding" van EUR 9,00 in plaats van haar te plaatsen. Gemeten in
# zijn opdrachten: na de plaatsklik sprong het tabblad naar
# /payments/orderOverview/index.html, en zijn winkelmandje liep op tot 17 regels
# en EUR 153,00. Nul van zijn 787 plaatsopdrachten is ooit online gekomen.
#
# 2dehands zegt het zelf ook: een link in het URL-veld kost geld, en zet je hem
# in de omschrijving, dan meldt de site "er is een URL gevonden" en wil ze
# alsnog betaald worden. Op Marktplaats geldt dezelfde regel; het is dezelfde
# site met dezelfde voorwaarden.
#
# Een advertentie die geld kost is geen advertentie die wij namens iemand mogen
# plaatsen. Dus halen we het webadres eruit voordat we hem versturen, en alleen
# op die twee kanalen: op Vinted, eBay en Shopify hoort de tekst gewoon heel te
# blijven.
_EMAIL_IN_TEKST = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.I)
_URL_IN_TEKST = re.compile(r"(?:https?://|www\.)\S+", re.I)
# Een kaal webadres zonder http of www: papas-plectrums.nl. Bewust een vaste
# lijst met eindes, en het stuk ervoor moet minstens twee tekens zijn en niet
# alleen cijfers. Zo blijven "z.o.z.", "t.w.v." en "€ 35,00" met rust.
#
# TWEE LETTERS MOETEN KLEIN, LANGERE EINDES NIET, en dat is geen
# schoonheidsfoutje. Gemeten over 5.009 advertenties: met een volledig
# hoofdletter-ongevoelige lijst sneuvelde "...zie later.De maat is..." — een zin
# zonder spatie na de punt, waarin "De" toevallig ook een landcode is. Datzelfde
# geldt voor "nu", "be" en "fr". Bij ".com" of ".shop" speelt dat niet, want dat
# zijn geen Nederlandse woorden; die mogen dus wél in hoofdletters.
#
# EN DAN DE SCHREEUWERS. Nagemeten 10-09-2026 over 1.000 echte advertenties van
# willekeurige verkopers: twee schrijven hun domein voluit in hoofdletters
# (SOUMAN.NL, WEAR2WORK.NL) en glipten er zo langs. Dat is 0,2%, oftewel bij
# Egberts 5.533 advertenties zo'n elf keer EUR 9,00. Daarom mag een kort einde
# tóch in hoofdletters, mits het stuk ervoor overduidelijk een domeinnaam is:
# met een streepje of cijfer erin, of zelf helemaal in hoofdletters. "later.De"
# valt daar niet onder en blijft dus staan. Diezelfde proef: de oude lijst zag
# 38 adressen, deze ziet er 40, en die twee extra zijn allebei echt.
_LABEL = r"(?![0-9]+\.)[A-Za-z0-9][A-Za-z0-9-]{1,}(?:\.[A-Za-z0-9-]{2,})*"
# MINSTENS DRIE LETTERS, anders is het een maat en geen merk. Zonder die eis
# sloopte de streepje-tak "Maat 38-40.Nu voor 20 euro" tot "Maat voor 20 euro",
# en "S-M.Nu" idem: precies de zin-zonder-spatie waar de regel hierboven voor
# waarschuwt, via de achterdeur terug.
_LABEL_DUIDELIJK = (r"(?![0-9]+\.)(?=(?:[A-Za-z0-9-]*[A-Za-z]){3})"
                    r"(?:[A-Za-z0-9][A-Za-z0-9-]*[-0-9][A-Za-z0-9-]*"
                    r"|[A-Z][A-Z0-9-]+)")
_EINDE_LANG = (r"(?:com|net|org|shop|store|info|biz|online|site|club|link|art"
               r"|today|webshop|company)")
_EINDE_KORT = (r"(?:nl|be|de|fr|uk|eu|nu|io|co|es|it|pl|dk|se|no|fi|at|ch|pt"
               r"|ie|lu|cz)")
_KAAL_DOMEIN = re.compile(
    rf"\b{_LABEL}\.(?:(?i:{_EINDE_LANG})|{_EINDE_KORT})\b(?:/\S*)?"
    rf"|\b{_LABEL_DUIDELIJK}\.(?i:{_EINDE_KORT})\b(?:/\S*)?"
)


def _zonder_links(tekst: str) -> str:
    """Webadressen en e-mailadressen uit een advertentietekst halen.

    Zie de toelichting hierboven. E-mailadressen gaan mee omdat het domein
    daarin (papas-plectrums.nl) precies hetzelfde is als het webadres, en omdat
    een marktplaats sowieso niet wil dat je kopers buiten de site om benadert.

    ZONDER RUINE. Blijft er na het schrappen bijna niets over, dan is het geen
    advertentietekst met een link erin maar een link met wat woorden eromheen.
    Dan laten we hem staan: een lege omschrijving laat het formulier hangen, en
    de betaalmuur-detectie in de extensie vangt zo'n geval alsnog op.
    """
    if not tekst:
        return tekst
    # ZIT ER GEEN ADRES IN, DAN BLIJFT DE TEKST LETTERLIJK ZOALS HIJ IS.
    #
    # Zonder deze regel liep elke advertentie door de molen en verloor ze
    # onderweg haar spaties aan het eind van een regel. Onschuldig, maar het
    # veranderde de tekst van 18% van alle klanten zonder dat er iets te halen
    # viel. Wat niets te maken heeft met een link, raken we niet aan.
    if not (_EMAIL_IN_TEKST.search(tekst) or _URL_IN_TEKST.search(tekst)
            or _KAAL_DOMEIN.search(tekst)):
        return tekst
    # REGEL VOOR REGEL, EN ALLEEN WEGGOOIEN WAT WIJ ZELF LEEG MAAKTEN.
    #
    # De eerste versie hiervan haalde in één keer alle lege regels uit de tekst.
    # Nagemeten over 5.009 advertenties van andere klanten: 55% werd daardoor
    # aangeraakt, vrijwel allemaal alinea-indeling die niets met een link te
    # maken had. Een filter dat de advertentie van iedereen verbouwt om er bij
    # één klant een link uit te halen is erger dan de kwaal.
    geschrapt = False
    uit: list[str] = []
    for regel in tekst.split("\n"):
        schoon = _EMAIL_IN_TEKST.sub("", regel)
        schoon = _URL_IN_TEKST.sub("", schoon)
        schoon = _KAAL_DOMEIN.sub("", schoon)
        schoon = re.sub(r"[ \t]{2,}", " ", schoon).rstrip()
        if regel.strip() and not schoon.strip():
            geschrapt = True       # deze regel was alleen het adres
            continue
        if schoon != regel.rstrip():
            geschrapt = True
        uit.append(schoon)
    # Een aankondiging die nergens meer heen wijst: "... met onderstaande link:"
    # gevolgd door niets. Alleen als er echt iets is weggehaald, en alleen als
    # de zin zelf naar die link verwijst — anders sneuvelt een onschuldige
    # "Afmetingen:" onderaan iemands advertentie.
    _WIJST_NAAR_LINK = re.compile(
        r"link|website|webshop|site|url|bestel|klik|volg ons|shop", re.I)
    while geschrapt and uit:
        laatste = uit[-1].rstrip()
        if not laatste:
            uit.pop()
            continue
        if laatste.endswith(":") and _WIJST_NAAR_LINK.search(laatste):
            uit.pop()
            continue
        break
    schoon = "\n".join(uit).strip()
    if len(schoon) < 10 < len(tekst.strip()):
        return tekst
    return schoon


def _strip_text_tags(result: str) -> str:
    """
    Haal de <text>-omhulling weg die het model soms meeteruggeeft.

    De vertaalopdracht zet de brontekst tussen <text>…</text>. Het model kopieert
    die tags af en toe mee, en dan stond er letterlijk "<text>B'TWIN short-sleeve
    cycling set …</text>" in de advertentie op Vinted. Alleen de buitenste
    omhulling weghalen — tekens < en > midden in een beschrijving (maten,
    pijltjes) blijven staan.
    """
    s = (result or "").strip()
    if not s:
        return ""
    s = re.sub(r"^<\s*text\s*>", "", s, flags=re.I).strip()
    s = re.sub(r"<\s*/\s*text\s*>\s*$", "", s, flags=re.I).strip()
    return s


def _republish_job_update(open_job: dict, payload: dict, now: datetime | None = None) -> dict:
    """
    Wat er met een al openstaande publicatieopdracht moet gebeuren als de
    gebruiker nóg eens op publiceren drukt.

    Een opdracht die "claimed" staat maar al een tijd niets van zich laat horen,
    hoort bij een tabblad dat weg is (gesloten, gecrasht, Chrome afgesloten).
    Die overnemen zonder hem los te maken betekende dat opnieuw crosslisten
    precies niets deed: de extensie krijgt alleen "pending" werk, dus bleef het
    item eindeloos "publishing…" staan tot de opruiming na vijf minuten. Klikt de
    gebruiker zelf opnieuw op publiceren, dan is dat het duidelijkste signaal dat
    de vorige poging dood is — dus zetten we hem terug op de wachtrij. Is de claim
    nog vers, dan is de extensie gewoon bezig en laten we hem met rust.
    """
    update: dict = {"payload": payload}
    if (open_job or {}).get("status") != "claimed":
        return update
    claimed_at = _parse_iso(open_job.get("claimed_at"))
    now = now or datetime.now(timezone.utc)
    if claimed_at is None or (now - claimed_at) > timedelta(seconds=STALE_CLAIM_SECONDS):
        update["status"] = "pending"
        update["claimed_at"] = None
    return update


def _parse_iso(ts):
    """Tijdstempel uit de database naar datetime (altijd met tijdzone), of None."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# De Supabase-client is synchroon: elke .execute() legt de héle server stil tot
# het antwoord binnen is. Publiceren doet er een handvol per platform, boven op
# de vertalingen en de Shopify-upload. Zolang één verkoper op "Opslaan" wachtte,
# stond iedereen anders dus ook te wachten — en gaf de gateway 502. Alleen
# .execute() doet netwerkwerk; de rest van de keten bouwt enkel de query op.
async def _exec(query, dubbel_is_ok: bool = False):
    """Voer een query uit, en probeer opnieuw als de verbinding wegviel.

    Zonder die herhaling brak één weggevallen verbinding de héle publicatie af:
    Marktplaats en 2dehands stonden er al op, Vinted kwam niet eens in de
    wachtrij, en de gebruiker kreeg alleen "HTTP 500". Precies dat is gebeurd.
    """
    return await asyncio.to_thread(execute_with_retry, query, 3, dubbel_is_ok)


# Eén gedeelde client in plaats van een nieuwe per vertaling: die zette elke keer
# een verse beveiligde verbinding op (vier keer per publicatie). Hergebruik scheelt
# die opzet-tijd. De client is draadveilig, dus to_thread mag hem delen.
_CLAUDE_CLIENT = None


def _claude_client():
    global _CLAUDE_CLIENT
    if _CLAUDE_CLIENT is None:
        import anthropic as _anthropic
        from backend.config import settings as _settings
        _CLAUDE_CLIENT = _anthropic.Anthropic(api_key=_settings.anthropic_api_key)
    return _CLAUDE_CLIENT


# Wat de verkoper leest als hij zelf op Publish drukt en de vertaling plat ligt.
#
# De tekst van VertalingOnbeschikbaar zelf ("gaat deze advertentie vanzelf
# alsnog de deur uit") klopt alleen op het uitgiftepad, waar de opdracht al in
# de wachtrij staat en vanzelf opnieuw wordt aangeboden. Bij een verse
# publicatie is er nog geen opdracht: het vertalen gebeurt vóór het aanmaken
# ervan. Wie dan leest dat het vanzelf goedkomt, zit voor niets te wachten.
NIETS_GEPLAATST_VERTALING = (
    "Publishing is on hold: we couldn't translate this listing, so nothing was "
    "published and nothing is waiting in the queue. That keeps your ad from "
    "going out in the wrong language. Please try again later."
)


class VertalingOnbeschikbaar(RuntimeError):
    """De vertaaldienst deed het niet. Dit is GEEN reden om de tekst maar te plaatsen.

    WAAROM DIT ER IS (08-09-2026, Daniel). `_vertaal` ving elke fout op en gaf de
    brontekst terug. Bij een lege API-rekening betekende dat: de Engelse tekst
    ging ongewijzigd naar Marktplaats en 2dehands, de opdracht werd gestempeld
    als "vertaald" (TAAL_VELD) en werd dus ook nooit meer opnieuw vertaald.
    Niemand kreeg een foutmelding, want er ging technisch niets mis.

    Gemeten op 08-09-2026: "(1346) Black MyProtein Shorts - Men XL - New" met een
    Engelse omschrijving stond op marktplaats.nl, en "(1071) Light Blue Massimo
    Dutti Turtleneck - Women XS - Very Good" op 2dehands.be, allebei met
    `_taal: nl` in de opdracht.

    Een storing hoort de advertentie te laten wachten, niet verkeerd te plaatsen.
    """


# ── STAAT DEZE TEKST AL IN DE DOELTAAL? ──────────────────────────────────────
#
# Alleen nodig als de vertaaldienst plat ligt. Dan moeten we kiezen tussen
# "plaatsen zoals het er staat" en "laten wachten", en dat mag geen gok zijn.
#
# Bewust streng: bij twijfel luidt het antwoord False. Een onterechte False kost
# uitstel tot de dienst weer draait; een onterechte True zet een Engelse
# advertentie op een Nederlandse site, en dat is precies de fout die dit hoort te
# voorkomen.
#
# Gemeten op 1.350 echt gepubliceerde Marktplaats- en 2dehands-teksten van de
# laatste drie weken: 1.296 (96%) worden als Nederlands herkend en zouden dus
# ook tijdens een storing gewoon doorgaan. De 54 die blijven wachten zijn korte
# trefwoordteksten zonder stopwoorden ("Kelim kleedje rood 73/40 cm") plus de
# echt Engelse teksten, en dat is precies de bedoeling.
_STOPWOORDEN_NL = {
    "de", "het", "een", "van", "voor", "met", "niet", "zijn", "deze", "dit", "wordt",
    "goede", "staat", "maat", "kleur", "nieuw", "gebruikt", "aan", "naar", "zeer",
    "mooi", "ook", "bij", "uit", "door", "tot", "zonder", "nog", "geen", "heeft",
    "kan", "je", "u", "we", "wij", "er", "hij", "ze", "om", "dat", "als", "maar",
    "want", "dus", "al", "onze", "mijn", "hun", "waar",
}
_STOPWOORDEN_EN = {
    "the", "and", "with", "for", "this", "from", "size", "colour", "color",
    "condition", "great", "brand", "are", "was", "were", "have", "has", "been",
    "you", "your", "our", "their", "please", "shipping", "item", "items",
    "measurements", "available", "authentic", "designer", "very", "without",
    "because", "which", "that", "they", "them", "some", "more", "only", "also",
}


def lijkt_al_in_taal(text: str, taal: str) -> bool:
    """True als de tekst overtuigend al in `taal` staat. Bij twijfel False."""
    woorden = re.findall(r"[a-z\u00e0-\u00ff']+", (text or "").lower())
    if len(woorden) < 6:
        return False
    nl = sum(1 for w in woorden if w in _STOPWOORDEN_NL)
    en = sum(1 for w in woorden if w in _STOPWOORDEN_EN)
    doel, ander = (nl, en) if taal == "nl" else (en, nl)
    return doel >= 3 and doel >= ander * 2


def _vertaal(text: str, target_lang: str, brand: str | None = None) -> str:
    """Translate text using Claude. Preserves brand names, formatting and paragraph structure.

    Synchroon met opzet. Het vertalen zelf is één netwerkgesprek met een
    synchrone client, en het wordt vanaf twee kanten aangeroepen: de
    publicatiestroom (async, zie _translate_with_claude hieronder, die hem in een
    draad zet zodat vier vertalingen echt naast elkaar lopen) en de uitgifte van
    werk aan de extensie (backend/api/jobs.py, een gewone def). Eén keer
    opschrijven, twee kanten bediend — anders drijft de ene kopie weg van de
    andere en vertaalt het ene pad net iets anders dan het andere.
    """
    if not text or not text.strip():
        return text
    # STAAT DE TEKST AL IN DE DOELTAAL, DAN GAAT HIJ NIET NAAR HET MODEL.
    #
    # GEMETEN (12-09-2026, Toon van De Juiste Toon). Zijn Nederlandse
    # omschrijving ging bij het herplaatsen opnieuw door "vertaal naar het
    # Nederlands", en kwam er in 3 van de 6 pogingen in het ENGELS uit — het
    # model draait de richting om als de opdracht zelf in het Engels staat en de
    # tekst al Nederlands is. Zo stond er een Engelse advertentie op Marktplaats
    # ("Characterized by geometric patterns and vibrant colors") terwijl de
    # database gewoon Nederlands bevatte, en gold hij intern als vertaald.
    #
    # Een tekst die al in de doeltaal staat heeft niets aan een vertaling: het
    # beste resultaat is letterlijk dezelfde tekst. Niet sturen is dus niet
    # alleen veiliger maar ook gratis.
    if lijkt_al_in_taal(text, target_lang):
        logger.info("translate→%s: tekst staat al in de doeltaal, ongewijzigd gelaten", target_lang)
        return text
    try:
        _client = _claude_client()

        lang_name = "Dutch" if target_lang == "nl" else "English"
        brand_note = f' The word "{brand}" is a brand name — never translate it, keep it exactly as-is.' if brand else ""

        # Models routinely collapse paragraph breaks into one blob even when asked
        # in prose to "preserve line breaks" — instructing to keep a literal marker
        # is much more reliable than instructing about whitespace, since the model
        # can't quietly normalize a token it's told to reproduce verbatim.
        has_breaks = "\n" in text
        # Diagnostic (ISSUE 2): the MP/2dehands description was rendering as one
        # glued block ("Wol" + "Pasvorm" → "WolPasvorm"), which only happens when
        # the text reaching translation has NO "\n" — so has_breaks is False and
        # the §BR§ preservation path never runs. Log the repr of the incoming text
        # so the next real publish shows in the server logs whether newlines are
        # actually present at this point (and are therefore lost upstream, at
        # storage/generation, rather than in translation).
        logger.info(
            "translate→%s in: has_breaks=%s repr=%r",
            target_lang, has_breaks, text[:200],
        )
        marked_text = text.replace("\n", " §BR§ ") if has_breaks else text
        break_note = (
            " The text contains literal §BR§ tokens marking line/paragraph breaks in the"
            " original — keep every single §BR§ token exactly where it is, in the same order,"
            " never remove, add, merge or translate them; translate only the words around them."
            if has_breaks else ""
        )

        prompt = (
            f"Translate the listing text between the <text> tags to {lang_name}."
            f"{brand_note}"
            f"{break_note}"
            " Preserve bullet points and formatting."
            " Keep numbers, sizes, measurements and condition scores (e.g. 7-8/10) unchanged."
            f" If the text is already in {lang_name}, return it exactly as-is."
            " Never ask questions or add commentary — the text between the tags is always"
            " the text to translate, even if it looks like an example or is very short."
            " Return only the translated text, nothing else.\n\n"
            f"<text>{marked_text}</text>"
        )
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        result = _strip_text_tags(response.content[0].text)
        if not result:
            return text
        if has_breaks:
            if "§BR§" in result:
                result = "\n".join(p.strip() for p in result.split("§BR§"))
            else:
                # Model dropped the markers entirely — better to keep the original
                # (with its correct paragraph structure) than publish one solid blob.
                logger.warning(
                    f"Claude {target_lang} translation dropped §BR§ markers — keeping original text"
                )
                return text
        # Guard against the model answering *about* the text instead of
        # translating it — a short title that's already in the target language
        # used to come back as "I notice you haven't included any text…", which
        # was then published verbatim as the listing title. A translation is
        # never several times longer than its source, so treat that as a failure
        # and keep the original.
        if len(result) > max(120, len(text) * 3):
            logger.warning(
                f"Discarding suspicious {target_lang} translation "
                f"({len(text)} chars in, {len(result)} out) — keeping original text"
            )
            return text
        # DE VERTALING KWAM IN DE VERKEERDE TAAL TERUG.
        #
        # Zelfde meting als hierboven: het model draait de richting soms om. De
        # voorcontrole vangt teksten die al in de doeltaal staan; dit vangt het
        # geval waarin het model een Nederlandse zin alsnog naar het Engels
        # omzet. Dan is de brontekst beter dan het antwoord.
        andere = "en" if target_lang == "nl" else "nl"
        if lijkt_al_in_taal(result, andere) and not lijkt_al_in_taal(result, target_lang):
            logger.warning(
                "Vertaling naar %s kwam in de andere taal terug — brontekst behouden", target_lang)
            return text
        logger.info("translate→%s out: repr=%r", target_lang, result[:200])
        return result
    except Exception as e:
        # De vertaaldienst zelf deed het niet (lege rekening, storing, tijdslimiet).
        # Wel of niet toch plaatsen wordt NIET hier beslist. Dit is één veld —
        # een titel van drie woorden is te weinig tekst om een taal aan af te
        # lezen. De afweging staat in localiseer_sync / localize_item_for_platform,
        # die titel en omschrijving samen kunnen wegen.
        logger.error("Vertaling naar %s mislukt: %s", target_lang, e)
        raise VertalingOnbeschikbaar(
            "De vertaling naar het "
            + ("Nederlands" if target_lang == "nl" else "Engels")
            + " lukte niet, dus er is niets geplaatst. Zodra de vertaling weer "
              "werkt gaat deze advertentie vanzelf alsnog de deur uit."
        ) from e


async def _translate_with_claude(text: str, target_lang: str, brand: str | None = None) -> str:
    """`_vertaal` in een draad, zodat vier vertalingen echt naast elkaar lopen.

    De Anthropic-client is synchroon. Zonder to_thread stond dit `await`-loze
    netwerkgesprek middenin een async-functie, waardoor de vier vertalingen
    (titel+tekst, Engels+Nederlands) NIET naast elkaar liepen maar netjes op
    elkaar wachtten — en de rest van de server ondertussen ook stilstond. Met
    to_thread vertalen ze echt tegelijk: de wachttijd is die van één vertaling in
    plaats van de som van vier.
    """
    return await asyncio.to_thread(_vertaal, text, target_lang, brand)


async def _translate_to_english(text: str, brand: str | None = None) -> str:
    return await _translate_with_claude(text, "en", brand)


async def _translate_to_dutch(text: str, brand: str | None = None) -> str:
    return await _translate_with_claude(text, "nl", brand)


# IN WELKE TAAL STAAT DEZE OPDRACHT AL?
#
# Aan een opdracht in de wachtrij was niet te zien of de titel en de omschrijving
# de vertaling al hadden gehad. Elk pad dat zelf een payload in elkaar zette
# moest er dus zelf aan denken — en één pad deed dat niet (de reddingsronde in
# services/relist.py). Gevolg: een Marktplaats-advertentie in het Engels, precies
# wat de vertaling had moeten voorkomen, zonder dat er ergens iets rood werd.
#
# Vanaf nu zet elke localisatie dit veld in de payload. Wie een opdracht uitdeelt
# kan daaraan zien of hij nog vertaald moet worden (zie _zet_taal_goed in
# backend/api/jobs.py). Het is een onderstreept veld, net als _refresh_rollback
# en _price_update: de extensie kijkt er niet naar en struikelt er niet over.
TAAL_VELD = "_taal"

_PLATFORM_TAAL = {
    **{p: "nl" for p in _DUTCH_PLATFORMS},
    **{p: "en" for p in _ENGLISH_PLATFORMS},
}


def taal_van_platform(platform: str) -> str | None:
    """De taal waarin dit platform zijn advertenties verwacht, of None."""
    return _PLATFORM_TAAL.get(platform)


def _al_in_doeltaal(item: dict, taal: str) -> bool:
    """Staan titel en omschrijving van dit artikel samen al in `taal`?

    Samen wegen, niet los: een titel als "Handgeknoopt Perzisch Shiraz wollen
    tapijt 135/80 cm" is te kort om een taal aan af te lezen, terwijl de
    omschrijving eronder glashelder Nederlands is. Staat het geheel al goed, dan
    hoeft er niets vertaald te worden — en dat is precies wat de fout van
    12-09-2026 voorkomt: het model draaide de richting om en zette een
    Nederlandse advertentie alsnog in het Engels op Marktplaats.
    """
    samen = f"{item.get('title') or ''}\n{item.get('description') or ''}"
    return lijkt_al_in_taal(samen, taal)


def localiseer_sync(item: dict, platform: str) -> dict:
    """`localize_item_for_platform` zonder event-lus.

    Het uitdelen van werk aan de extensie (backend/api/jobs.py) is een gewone
    def en kan dus niet awaiten. Titel en omschrijving gaan hier achter elkaar in
    plaats van naast elkaar: het gaat om hooguit één opdracht per keer, en die
    twee vertalingen samen duren nog altijd korter dan de klik waar de verkoper
    op wacht.
    """
    taal = taal_van_platform(platform)
    if not taal:
        return item
    if _al_in_doeltaal(item, taal) and platform != "shopify":
        return {**item, TAAL_VELD: taal}
    brand = item.get("brand") or None
    # Shopify-only override — Vinted/eBay keep the item's own translated title.
    manual_title = (item.get("shopify_title") or "").strip() if platform == "shopify" else ""
    try:
        title = manual_title or _vertaal(item.get("title", ""), taal, brand)
        desc = _vertaal(item.get("description", ""), taal, brand)
    except VertalingOnbeschikbaar:
        return _zonder_vertaling(item, taal)
    return {**item, "title": title, "description": desc, TAAL_VELD: taal}


def _zonder_vertaling(item: dict, taal: str) -> dict:
    """De vertaaldienst ligt plat. Mag deze advertentie tóch de deur uit?

    Alleen als titel en omschrijving SAMEN al overtuigend in de doeltaal staan;
    dan valt er niets te vertalen en verandert een werkende vertaling er ook
    niets aan. Anders gaat de fout door naar boven en blijft de opdracht wachten.

    Titel en omschrijving worden samen gewogen en niet los: "Vintage tafellamp
    hoogte 44 cm" is te kort om een taal aan af te lezen, terwijl de omschrijving
    eronder glashelder Nederlands is.
    """
    samen = f"{item.get('title') or ''}\n{item.get('description') or ''}"
    if lijkt_al_in_taal(samen, taal):
        logger.warning("Vertaling ligt plat, maar deze advertentie staat al in het %s "
                       "— ongewijzigd doorgelaten.", taal)
        return {**item, TAAL_VELD: taal}
    raise VertalingOnbeschikbaar(
        "De vertaling naar het " + ("Nederlands" if taal == "nl" else "Engels")
        + " lukte niet, dus er is niets geplaatst. Zodra de vertaling weer werkt "
          "gaat deze advertentie vanzelf alsnog de deur uit."
    )


async def localize_item_for_platform(item: dict, platform: str) -> dict:
    """
    Return `item` with title/description in the language `platform` expects.

    Every path that publishes a listing must go through this. The relist recreate
    used to build its create payload straight from the DB row, so a refreshed
    marktplaats/2dehands listing came back in English while the original had been
    published in Dutch — the item reads as translated on first publish and
    untranslated after every relist.

    Non-localized platforms return the item unchanged. Ligt de vertaaldienst plat,
    dan komt er een VertalingOnbeschikbaar naar boven, tenzij de advertentie al in
    de doeltaal staat — zie _zonder_vertaling.
    """
    taal = taal_van_platform(platform)
    if not taal:
        return item
    if _al_in_doeltaal(item, taal) and platform != "shopify":
        return {**item, TAAL_VELD: taal}
    brand = item.get("brand") or None
    # Shopify-only override — Vinted/eBay keep the item's own translated title.
    manual_title = (item.get("shopify_title") or "").strip() if platform == "shopify" else ""
    try:
        if manual_title:
            title = manual_title
            desc = await _translate_with_claude(item.get("description", ""), taal, brand)
        else:
            title, desc = await asyncio.gather(
                _translate_with_claude(item.get("title", ""), taal, brand),
                _translate_with_claude(item.get("description", ""), taal, brand),
            )
    except VertalingOnbeschikbaar:
        return _zonder_vertaling(item, taal)
    return {**item, "title": title, "description": desc, TAAL_VELD: taal}


# Platforms handled by the Chrome extension (form automation in real browser)
# NOTE: "facebook" (Facebook Marketplace) is a BETA happy-path integration. Facebook
# obfuscates its form markup and actively detects automation, so this path is
# best-effort and carries an account-ban risk — surfaced to the user in the UI.
EXTENSION_PLATFORMS = {"marktplaats", "2dehands", "vinted", "facebook"}
# Platforms handled server-side via official API
API_PLATFORMS = {"ebay", "shopify"}
# Built in the backend but NOT yet released — surfaced as "Coming soon" in the UI
# and refused by publish_to_platforms so nothing half-lists. Etsy's platform code
# exists (backend/platforms/etsy.py) but the flow isn't finished/tested.
NOT_YET_AVAILABLE = {"etsy"}

# Wat het scherm laat zien als een kanaal wordt overgeslagen omdat het artikel er
# al op staat. Eén zin die zegt dat er NIETS is gebeurd, en wat de weg vooruit is.
ALREADY_LIVE_MESSAGE = (
    "Already live on this channel, so nothing was published and nothing was queued. "
    "Use Relist if you want to replace the existing advert with a fresh one."
)

# Required on every platform — an empty description or zero photos means the
# extension has nothing to type/upload, so the listing goes out looking broken
# rather than just "safely bare".
# Prijs hoort hier bij, en ontbrak. Een item zonder prijs (of met 0) kon daardoor
# gewoon gepubliceerd worden en ging voor niets online. Dat is geen theoretisch
# risico: een Admarkt-import levert nooit een prijs mee, en er stonden 240 items
# op 0 klaar om te publiceren. `not value` vangt 0, None en "" allemaal, dus
# hieronder is geen extra controle nodig.
_UNIVERSAL_REQUIRED = ["price", "description", "photo_urls"]
# Marktplaats/2dehands render category-specific attribute dropdowns (maat,
# merk, kleur...) and pick the category itself from `category`/`gender` — those
# are the fields that silently produced a wrong-category, everything-empty
# listing before (see extension/background.js MP_CATEGORIES fallback).
_PLATFORM_REQUIRED = {
    "marktplaats": ["category", "gender", "brand", "size", "color"],
    "2dehands": ["category", "gender", "brand", "size", "color"],
    # Facebook Marketplace (beta): the create form requires a category — the
    # content script types it into Facebook's category picker. Brand/size/colour
    # are optional on Marketplace, so we don't demand them for the happy path.
    "facebook": ["category"],
    # Vinted's create form blocks on "Fill in colour/size to continue" — without
    # these the extension leaves the form half-filled and the user has to finish
    # it by hand. Demand them up front instead (colour is auto-inferred from the
    # title first, so this rarely trips).
    "vinted": ["category", "gender", "size", "color"],
}
# Non-clothing items (games, consoles, ...) live in a different Marktplaats
# category tree that has no gender/maat/kleur attributes, so demanding those
# fields would make an otherwise-complete game listing un-publishable. Such items
# are recognised by their category prefix (mirrors the "games ..." keys in the
# extension's MP_CATEGORIES and the frontend CATEGORIES.games group). For them
# only the category itself is platform-required.
_NON_CLOTHING_PREFIXES = ("games ", "electronics ", "sieraden ", "muziek ",
                          "antiek ", "kunst ", "wonen ", "audio ")
# Accessoires staan in de kledingboom, maar een bandana, een patch, een speld of
# een sleutelhanger heeft geen maat en geen merk.
#
# GEMETEN OP 07-09-2026, NIET AANGENOMEN. Van de geslaagde plaatsingen in
# "unisex accessoires" hadden er 13 van de 14 GEEN maat, en in "kinderen
# accessoires" 16 van de 21. Marktplaats accepteert ze dus gewoon; de eis kwam
# van ons. Bij Egbert Brouwer (papas-plectrums) staan 2.343 van zijn 5.533
# artikelen in "unisex accessoires", en die kregen daardoor allemaal de
# waarschuwing "voeg merk, maat, kleur toe" en waren niet te publiceren. Dat is
# wat hij "gaten in mijn listings" noemt, en het is de tweede keer: op
# 03-09-2026 is dezelfde fout al uit de knopteller gehaald (zie _mist_iets in
# mp_enrich.py), maar niet uit de eis zelf.
_GEEN_MAAT_CATEGORIEEN = ("unisex accessoires", "accessoires dames", "kinderen accessoires")
_NON_CLOTHING_PLATFORM_REQUIRED = ["category"]


def _is_non_clothing(item: dict) -> bool:
    cat = str(item.get("category") or "").strip().lower()
    return cat.startswith(_NON_CLOTHING_PREFIXES) or cat in _GEEN_MAAT_CATEGORIEEN


async def _fill_inferred_gaps(db, item: dict) -> dict:
    """Fill empty colour/gender/category from the listing text, and persist it.

    Only fills fields that are actually empty, and the inference is conservative
    (see api/imports._infer_attributes), so a wrong guess is never written over
    real data. Failure here is never fatal — worst case the field stays empty
    and validation tells the user to fill it in.
    """
    try:
        from backend.api.imports import _infer_attributes, _infer_attributes_smart
        inferred = _infer_attributes(item.get("title"), item.get("description"))
        # DE WOORDENLIJST ALLEEN IS HIER NIET GENOEG (07-09-2026).
        #
        # De woordenlijst leest de omschrijving, en juist die ontbreekt bij een
        # pas geïmporteerde advertentie: Marktplaats en 2dehands leveren hem pas
        # in een tweede ronde na. Gemeten bij Toon: op alleen de titel vindt de
        # woordenlijst 0 van de 114 rubrieken, het model 20 van de 20. Zonder
        # rubriek weigert de controle hieronder te publiceren, dus dan staat de
        # verkoper stil bij een artikel dat prima in te delen was.
        #
        # Alleen bij een lege rubriek, alleen op dit moment (hij drukt op
        # publiceren, dus één modelvraag mag), en het antwoord wordt opgeslagen.
        if not (item.get("category") or "").strip() and not inferred.get("category"):
            inferred = {**inferred, **(await _infer_attributes_smart(
                item.get("title"), item.get("description"), item.get("brand")) or {})}
    except Exception as e:
        logger.warning(f"Attribute inference failed for item {item.get('id')}: {e}")
        return item
    patch = {
        k: v for k, v in inferred.items()
        if k in ("color", "gender", "category") and v and not (item.get(k) or "").strip()
    }
    if not patch:
        return item
    try:
        await _exec(db.table("items").update(patch).eq("id", item["id"]))
    except Exception as e:
        logger.warning(f"Could not persist inferred attributes for {item.get('id')}: {e}")
    return {**item, **patch}


class CrosslistValidationError(Exception):
    """Raised when an item is missing data a platform needs — caller should
    show `missing` to the user and require them to fill it in rather than
    silently publishing an incomplete listing."""
    def __init__(self, missing: dict[str, list[str]]):
        self.missing = missing
        super().__init__(f"Item is missing required fields: {missing}")


def _missing_fields_per_platform(item: dict, platforms: list[str]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    # ZONDER CATEGORIE WETEN WE NIET WELKE TAK HET IS, DUS VRAGEN WE ALLEEN DIE.
    # Anders viel een item zonder categorie terug op kleding en kreeg de verkoper
    # "voeg categorie, geslacht, merk, maat, kleur toe" te zien terwijl vier van
    # die vijf misschien helemaal niet nodig zijn. Vul hij de categorie in, dan
    # vertelt de volgende ronde vanzelf wat er dán nog ontbreekt.
    geen_categorie = not str(item.get("category") or "").strip()
    non_clothing = _is_non_clothing(item)
    for platform in platforms:
        platform_required = (
            _NON_CLOTHING_PLATFORM_REQUIRED
            if (non_clothing or geen_categorie) and platform in _PLATFORM_REQUIRED
            else _PLATFORM_REQUIRED.get(platform, [])
        )
        required = _UNIVERSAL_REQUIRED + platform_required
        gaps = []
        for field in required:
            value = item.get(field)
            if field == "photo_urls":
                if not value or len(value) == 0:
                    gaps.append("photos")
            elif not value or not str(value).strip():
                gaps.append(field)
        if gaps:
            missing[platform] = gaps
    return missing


def slottekst_van(user_id: str) -> str:
    """De vaste tekst die deze verkoper onder élke advertentie wil hebben."""
    try:
        from backend.services.instellingen import lees as _lees_instellingen
        return (_lees_instellingen(user_id) or {}).get("slottekst") or ""
    except Exception as e:  # noqa: BLE001 — geen slottekst is vervelend, niet fataal
        logger.warning("Kon de vaste slottekst niet lezen voor %s: %s", user_id, e)
        return ""


def _met_slot(tekst: str, slot: str) -> str:
    """De omschrijving met de vaste slottekst eronder.

    Stond als hulpfunctie binnen publish_to_platforms, en dus kon elk ánder pad
    dat zelf een payload bouwt hem missen — wat de reddingsronde in
    services/relist.py ook deed. Hier staat hij één keer, voor iedereen.
    """
    schoon = str(tekst or "").rstrip()
    if not slot:
        return schoon
    # Al aanwezig? Dan niet nog een keer. Dat gebeurt zodra een advertentie
    # met slottekst en al weer wordt ingelezen bij een scan.
    if slot.strip() and slot.strip() in schoon:
        return schoon
    return (schoon + "\n\n" + slot).strip() if schoon else slot


# Een bulk-crosslist roept publish_to_platforms per artikel aan. Zonder cache zou
# de kansloos-check bij 5.533 aangevinkte artikelen 5.533 keer drie databasevragen
# doen. De uitkomst verandert binnen zo'n ronde niet, dus twee minuten vasthouden.
_KANSLOOS_CACHE: dict[tuple, tuple] = {}
_KANSLOOS_CACHE_TTL = 120  # seconden


def _kanaal_kansloos_gecached(db, user_id: str, platform: str) -> bool:
    """Kansloos volgens de rem, maar altijd één proefopdracht per ronde.

    WAAROM DIE PROEF ER IS (08-09-2026, Egbert Brouwer). De rem hield zijn hele
    2dehands tegen zolang er nog nooit één plaatsing was geslaagd — en hield
    daarmee ook de enige poging tegen die dat had kunnen veranderen. Vanaf
    06-09 21:14 is er voor hem geen enkele 2dehands-opdracht meer aangemaakt;
    elke klik op publiceren gaf de foutmelding van dagen eerder terug. Zonder
    uitweg is een pauze een muur.

    De eerste vraag in een ronde krijgt daarom altijd groen licht, ook als het
    kanaal kansloos is; de rest van diezelfde ronde niet. Dat is precies één
    advertentie in plaats van vijfhonderd, en het is genoeg: lukt hij, dan is
    `_nooit_gelukt_op` voorgoed onwaar en valt de rem vanzelf weg. Lukt hij
    niet, dan neemt de extensie de rij zelf weer terug (stopPlatformWachtrij)
    en staat er één nieuwe foutmelding in plaats van honderden.
    """
    import time
    from backend.api.jobs import _kanaal_kansloos
    sleutel = (user_id, platform)
    nu = time.monotonic()
    trof = _KANSLOOS_CACHE.get(sleutel)
    if trof and nu - trof[1] < _KANSLOOS_CACHE_TTL:
        return trof[0]
    uit = bool(_kanaal_kansloos(db, user_id, platform))
    # Het antwoord dat we ONTHOUDEN is het echte oordeel; het antwoord dat we
    # NU teruggeven laat de proef door. Zo blijft het bij één.
    _KANSLOOS_CACHE[sleutel] = (uit, nu)
    return False if uit else uit


_HARD_DICHT_CACHE: dict[tuple, tuple] = {}


def _kanaal_hard_dicht_gecached(db, user_id: str, platform: str) -> bool:
    """Vraagt dit kanaal geld voor elke advertentie? Dan géén proefopdracht.

    HET VERSCHIL MET DE PAUZE HIERBOVEN (09-09-2026, Egbert Brouwer). Die laat
    per ronde bewust één advertentie door, want een pauze zonder uitweg is een
    muur. Dat klopt zolang een mislukte poging alleen tijd kost.

    Bij een betaalmuur kost ze geld. Gemeten: 2dehands.be stuurde zijn tabblad
    na de plaatsklik naar /payments/orderOverview en zette de advertentie als
    bestelregel van EUR 9,00 klaar. Elke proefadvertentie die wij er daarna nog
    doorheen lieten was dus opnieuw EUR 9,00. Hij mailde een winkelmandje met 17
    regels, EUR 153,00 in totaal. Hier hoort de deur dus wél helemaal dicht.
    """
    import time
    from backend.api.jobs import _kanaal_hard_dicht
    sleutel = (user_id, platform)
    nu = time.monotonic()
    trof = _HARD_DICHT_CACHE.get(sleutel)
    if trof and nu - trof[1] < _KANSLOOS_CACHE_TTL:
        return trof[0]
    uit = bool(_kanaal_hard_dicht(db, user_id, platform))
    _HARD_DICHT_CACHE[sleutel] = (uit, nu)
    return uit


# De statussen waarin een advertentierij "staat er nog" betekent. `delisted` en
# `sold` horen er bewust niet bij: dan is de advertentie juist weg.
_LEVENDE_STATUS = ["active", "hidden", "pending", "relisting"]


FOTO_OVERLAP_DREMPEL = 0.6


def _zelfde_fotos(a: set, b: set) -> bool:
    """Wijzen deze twee fotosets op hetzelfde voorwerp?

    ÉÉN GEDEELDE FOTO IS GEEN BEWIJS (12-09-2026, De Juiste Toon).

    Hij zette het hele weekend lederhosen klaar voor oktober en kreeg bij elke
    poging "Already listed here under a duplicate copy of this item. Merge them
    first." Ze waren geen dubbelen. Vier artikelen die allemaal "Lederhosen
    Dames" heten zijn vier verschillende broeken: 40 cm, 35 cm, 47 cm en een
    groene suède, elk met eigen prijs, eigen tekst en negen tot elf eigen
    foto's. Wat ze delen is één plaatje: zijn eigen info-/maatfoto, die in 17
    van zijn artikelen zit. Op "minstens één gedeelde foto" gold dat als bewijs
    en kon hij ze niet publiceren, terwijl samenvoegen (wat de melding hem
    opdroeg) twee echte broeken tot één zou hebben geplakt.

    GEMETEN op zijn 1.318 artikelen, alle 43 paren met dezelfde titel én een
    gedeelde foto. De scheiding is scherp, zonder twijfelgevallen ertussen:

      * 26 echte dubbelen — de kleinere fotoset zit hélemaal in de grotere
        (4 van 4, 5 van 5, 9 van 9, 10 van 10, 11 van 11, en twee paren van
        1 van 1 die allebei dezelfde enige foto dragen). Twee imports van
        dezelfde advertentie leveren immers dezelfde foto's op.
      * 17 valse — precies één gedeelde foto van de zeven tot elf, telkens zijn
        info-plaatje, telkens verschillende prijzen en teksten.

    Vandaar een aandeel en geen aantal: een dubbele deelt vrijwel al zijn
    foto's, een sjabloonplaatje deelt er één van de tien. De drempel ligt op
    0,6 en niet op 1,0 zodat een import die één foto meer of minder ophaalde er
    nog steeds onder valt.
    """
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= FOTO_OVERLAP_DREMPEL


def _zelfde_artikel_al_online(db, item: dict, platforms: list[str],
                              al_bekeken: list[str] | None = None) -> dict[str, dict]:
    """Kanalen waar dit artikel al staat onder een ANDER artikel met dezelfde
    titel en minstens één gedeelde foto.

    Synchroon en zonder eigen foutafvang: de aanroeper draait hem naast de lus en
    laat publiceren gewoon doorgaan als het lezen mislukt. Een dubbele advertentie
    is vervelend; niets kunnen publiceren is erger.

    Waarom foto's en niet alleen de titel: zie de uitleg bij de aanroep. Een
    gedeeld foto-adres is letterlijk hetzelfde bestand bij dezelfde verkoper, dus
    hetzelfde voorwerp. Verschillende foto's bij dezelfde titel zijn losse
    artikelen die allebei te koop horen te kunnen staan.
    """
    titel = (item or {}).get("title")
    fotos = {u for u in ((item or {}).get("photo_urls") or []) if u}
    eigen = (item or {}).get("id")
    user_id = (item or {}).get("user_id")
    if not (titel and fotos and eigen and user_id and platforms):
        return {}

    overslaan = set(al_bekeken or []) | {eigen}
    # Exacte titel. Twee imports van dezelfde advertentie leveren letterlijk
    # dezelfde tekst op (nagemeten), dus hier is geen patroon nodig — en een
    # patroon met haakjes of procenttekens erin is precies waar PostgREST stil
    # een lege lijst op teruggeeft. Zie de opmerking in tweelingen.familie_ids.
    rijen = (db.table("items").select("id,photo_urls")
             .eq("user_id", user_id).eq("title", titel)
             .limit(50).execute().data or [])
    zelfde = [r["id"] for r in rijen
              if r.get("id") and r["id"] not in overslaan
              and _zelfde_fotos(fotos, {u for u in (r.get("photo_urls") or []) if u})]
    if not zelfde:
        return {}

    listings = (db.table("listings")
                .select("item_id,platform,status,platform_listing_id,platform_listing_url")
                .in_("item_id", zelfde)
                .in_("status", _LEVENDE_STATUS)
                .execute().data or [])
    uit: dict[str, dict] = {}
    for rij in listings:
        if rij.get("platform") in platforms:
            uit.setdefault(rij["platform"], rij)
    return uit


async def publish_to_platforms(item_id: str, platforms: list[str], user_id: str) -> list[dict]:
    """
    Route each platform to the right handler:
    - Extension platforms → create a job, extension picks it up
    - API platforms → call directly server-side

    Raises CrosslistValidationError instead of publishing if the item is
    missing data a platform needs — never silently ships a half-empty listing.
    """
    db = get_db()
    # Op naam van de eigenaar opvragen. Zonder die voorwaarde kon /listings/publish
    # met een willekeurig item-id andermans item publiceren, op jouw gekoppelde
    # accounts.
    item_resp = await _exec(
        db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).limit(1)
    )
    item = (item_resp.data or [None])[0]
    if not item:
        raise CrosslistValidationError({"item": ["This item does not exist (or is not yours)."]})

    # Etsy isn't built yet (shown only as "Coming soon"). Refuse it explicitly so a
    # stray request can never half-publish or fall through to the extension path.
    # Any not-yet-available platform is returned as a clear error result.
    results = [
        {"platform": p, "status": "error",
         "error": f"{p.capitalize()} is coming soon — you can't publish to it yet."}
        for p in platforms if p in NOT_YET_AVAILABLE
    ]
    platforms = [p for p in platforms if p not in NOT_YET_AVAILABLE]

    # Vul lege kleur/gender/categorie alsnog uit de titel voordat we valideren.
    # Zonder deze stap stond de kolom leeg, sloeg de extensie het veld over en
    # moest de gebruiker kleur en maat zelf in het Vinted-formulier typen.
    item = await _fill_inferred_gaps(db, item)

    # EÉN FOTO IS BIJNA NOOIT DE HELE ADVERTENTIE.
    #
    # Een geïmporteerde Marktplaats-advertentie komt binnen via de zoeklijst, en
    # die geeft alleen het omslagplaatje en een ingekorte tekst. De rest — alle
    # foto's, de volledige tekst — staat op de advertentiepagina zelf. Tot nu toe
    # moest de verkoper daarvoor zelf op "Fill from Marktplaats" klikken; deed
    # hij dat niet, dan werd de advertentie elders gepubliceerd met één foto en
    # een halve tekst. Jaap (Zilverwebsite, 28-08-2026) publiceerde zo veertien
    # advertenties: alle veertien met precies één foto.
    #
    # Dus halen we het hier alsnog op, op het moment dat het ertoe doet, en
    # alleen als er iets te halen valt. Bestaande waarden blijven staan.
    if len(item.get("photo_urls") or []) <= 1:
        try:
            bron = (await _exec(
                db.table("listings").select("platform_listing_url")
                .eq("item_id", item_id)
                .in_("platform", ["marktplaats", "2dehands"])
                .not_.is_("platform_listing_url", "null")
                .limit(1)
            )).data
            if bron and bron[0].get("platform_listing_url"):
                from backend.services.mp_enrich import vul_item_aan_uit_advertentie
                item = await vul_item_aan_uit_advertentie(
                    db, item, bron[0]["platform_listing_url"])
        except Exception as e:  # noqa: BLE001
            # Lukt het niet, dan publiceren we met wat we hebben. Een advertentie
            # met één foto is beter dan geen advertentie.
            logger.warning("Kon item %s niet aanvullen uit de advertentiepagina: %s", item_id, e)

    missing = _missing_fields_per_platform(item, platforms)
    # De EU-verplichte "verantwoordelijke partij" hoort bij de verkoper, niet bij
    # het artikel: hij staat één keer in zijn instellingen. Ontbreekt hij, dan
    # markeert Marktplaats de drie velden rood en gebeurt er verder niets — een
    # publicatie die stilstaat op een scherm dat de gebruiker niet ziet. Hier
    # gevangen, zodat hij een zin te lezen krijgt in plaats van een dood tabblad.
    # ... maar alleen als de verkoper hem ook wíl meesturen. Staat die
    # schakelaar uit, dan is een leeg blok een keuze en geen gebrek — dan houden
    # we het publiceren niet tegen en vullen we op het formulier niets in.
    # Amanda, 30-08-2026: haar bedrijfsgegevens kwamen onder elke advertentie te
    # staan omdat ze anders niet kón publiceren.
    from backend.services.instellingen import (fabrikant as _fabrikant,
                                               fabrikant_verplicht as _fab_verplicht)
    fab = _fabrikant(user_id)
    if _fab_verplicht(user_id) and not all(fab.values()):
        for platform in ("marktplaats", "2dehands"):
            if platform in platforms:
                missing.setdefault(platform, []).append("manufacturer_details")
    if missing:
        raise CrosslistValidationError(missing)

    # STAAT DIT ARTIKEL ER AL OP, ONDER EEN ANDERE RIJ? (30-08-2026)
    #
    # Dezelfde trui staat vaak meerdere keren in de voorraad: één rij per
    # importbron, met dezelfde nummering voor de titel — "(1032) Grijs Ralph
    # Lauren Zip Vest" naast "(1032) Grey Ralph Lauren Zip Vest". Het dashboard
    # keek alleen naar de eigen rij, zag daar geen Vinted-advertentie en zei
    # "staat niet op Vinted". Wie dan op Publish drukte zette de trui een TWEEDE
    # keer op Vinted — met twee kopers voor één trui als afloop.
    #
    # Dus kijken we naar de hele familie. Staat er al een levende advertentie op
    # dit kanaal, dan publiceren we niet en zeggen we waaróm niet.
    bezet: dict[str, dict] = {}
    familie: list[str] = []   # ook nodig als het lezen hieronder mislukt
    try:
        from backend.services.tweelingen import familie_ids
        familie = [i for i in await naast_de_lus(lambda: familie_ids(db, item))
                   if i != item_id]
        if familie:
            zuster_rijen = (await _exec(
                db.table("listings")
                .select("item_id,platform,status,platform_listing_id,platform_listing_url")
                .in_("item_id", familie)
                .in_("status", ["active", "hidden", "pending", "relisting"])
            )).data or []
            for rij in zuster_rijen:
                if rij.get("platform") in platforms:
                    bezet.setdefault(rij["platform"], rij)
    except Exception as e:  # noqa: BLE001
        # Kunnen we de familie niet lezen, dan publiceren we gewoon. Een
        # dubbele advertentie is vervelend; niets kunnen publiceren is erger.
        logger.warning("Kon de zusterrijen van %s niet lezen: %s", item_id, e)

    # ...EN ONDER EEN ARTIKEL DAT NIET DEZELFDE NUMMERING DRAAGT (07-09-2026).
    #
    # GEMETEN bij De Juiste Toon. De familiecontrole hierboven herkent tweelingen
    # aan het nummer dat de verkoper zelf voor de titel zet — "(1032) …" — of aan
    # een gedeelde sku. Zijn artikelen hebben geen van beide: elke import geeft
    # een eigen sku (IMP-3D1EC8DB, IMP-6CB890D8) en de titels zijn kaal. Twee
    # imports van dezelfde advertentie werden daardoor twee losse artikelen, en
    # allebei publiceren gaf twee advertenties voor één voorwerp. Op zijn
    # openbare verkoperspagina stonden zo elf titels dubbel, waarvan één die
    # dezelfde dag nog was bijgekomen.
    #
    # WAAROM TITEL ÉN FOTO, EN NIET DE TITEL ALLEEN. Hij heeft acht verschillende
    # dameslederhosen die allemaal "Lederhosen dames" heten; die MOETEN los te
    # koop kunnen staan. Op de titel alleen hadden we er zeven geblokkeerd. Alle
    # acht hebben hun eigen foto's. De echte dubbelen delen juist een foto-adres
    # letterlijk, want ze komen uit dezelfde bron. Gemeten op zijn 1.319
    # artikelen: 45 paren met dezelfde titel én een gedeelde foto, en geen enkel
    # van de acht lederhosen erbij.
    if platforms:
        try:
            zelfde = await naast_de_lus(
                lambda: _zelfde_artikel_al_online(db, item, platforms, familie))
            for p, rij in zelfde.items():
                bezet.setdefault(p, rij)
        except Exception as e:  # noqa: BLE001 — zelfde afweging als hierboven
            logger.warning("Kon de dubbelcontrole op titel+foto niet doen voor %s: %s",
                           item_id, e)

    if bezet:
        results.extend([
            {"platform": p, "status": "duplicate",
             "platform_listing_id": rij.get("platform_listing_id"),
             "platform_listing_url": rij.get("platform_listing_url"),
             "duplicate_of": rij.get("item_id"),
             "message": ("This exact article is already listed here under a duplicate copy"
                         " of this item — merge the two instead of publishing again."),
             "error": ("Already listed here under a duplicate copy of this item."
                       " Merge them first, otherwise you get two adverts for one article.")}
            for p, rij in bezet.items()
        ])
        platforms = [p for p in platforms if p not in bezet]

    api_platforms = [p for p in platforms if p in API_PLATFORMS]
    ext_platforms = [p for p in platforms if p in EXTENSION_PLATFORMS]

    # EEN KANAAL DAT NOG NOOIT HEEFT GEWERKT, NIET OPNIEUW VOLPROPPEN.
    #
    # GEMETEN (07-09-2026, Egbert Brouwer). 671 plaatsopdrachten voor 2dehands,
    # nul geslaagd, drie weken lang. 2dehands.be laat dit account niet plaatsen
    # via /plaats. Elke nieuwe poging is drie minuten stilte en een rode balk
    # erbij. Zolang er niet één 2dehands-advertentie door is, zetten we hier geen
    # nieuwe opdracht meer klaar en zeggen we in één zin waaróm niet. Zodra één
    # plaatsing lukt is `_kanaal_kansloos` weer False en loopt alles gewoon.
    kansloos_geblokkeerd: dict[str, str] = {}
    if ext_platforms:
        from backend.api.jobs import (_kanaal_kansloos, _melding_kanaal_op_pauze,
                                      _melding_kanaal_vraagt_geld)
        for p in ext_platforms:
            try:
                # Eerst de betaalmuur: die kent geen proefadvertentie, want die
                # is niet gratis. Zie _kanaal_hard_dicht_gecached.
                if await naast_de_lus(lambda p=p: _kanaal_hard_dicht_gecached(db, user_id, p)):
                    kansloos_geblokkeerd[p] = _melding_kanaal_vraagt_geld(p)
                elif await naast_de_lus(lambda p=p: _kanaal_kansloos_gecached(db, user_id, p)):
                    kansloos_geblokkeerd[p] = _melding_kanaal_op_pauze(p)
            except Exception as e:  # noqa: BLE001 — een rem mag nooit publiceren blokkeren op een fout
                logger.warning("kansloos-check mislukt voor %s/%s: %s", user_id, p, e)
    if kansloos_geblokkeerd:
        results.extend([
            {"platform": p, "status": "blocked", "error": reden}
            for p, reden in kansloos_geblokkeerd.items()
        ])
        ext_platforms = [p for p in ext_platforms if p not in kansloos_geblokkeerd]
        platforms = [p for p in platforms if p not in kansloos_geblokkeerd]

    # Pre-translate concurrently for platforms that need a different language
    english_item = None
    dutch_item = None
    need_en = any(p in _ENGLISH_PLATFORMS for p in platforms)
    need_nl = any(p in _DUTCH_PLATFORMS for p in platforms)

    brand = item.get("brand") or None

    # Ligt de vertaaldienst plat, dan gaat de advertentie alleen door als hij al
    # in de doeltaal staat (_zonder_vertaling weegt titel en omschrijving samen).
    # Zo niet, dan komt er een VertalingOnbeschikbaar naar boven en zegt het
    # scherm dat er níéts is geplaatst — in plaats van een Engelse advertentie op
    # Marktplaats te zetten en dat "gelukt" te noemen.
    # Staat het artikel al in de doeltaal, dan gaat er niets naar het model —
    # zie _al_in_doeltaal voor het waarom (een "vertaling" van nl naar nl kwam
    # in 3 van de 6 gevallen in het Engels terug).
    async def _build_english():
        if _al_in_doeltaal(item, "en"):
            return {**item, TAAL_VELD: "en"}
        # Always the item's OWN translated title. `shopify_title` is a Shopify-only
        # override and is applied per-platform in _pick() — baking it in here gave
        # Vinted and eBay the Shopify title too.
        try:
            title_en, desc_en = await asyncio.gather(
                _translate_to_english(item.get("title", ""), brand),
                _translate_to_english(item.get("description", ""), brand),
            )
        except VertalingOnbeschikbaar:
            return _zonder_vertaling(item, "en")
        return {**item, "title": title_en, "description": desc_en, TAAL_VELD: "en"}

    async def _build_dutch():
        if _al_in_doeltaal(item, "nl"):
            return {**item, TAAL_VELD: "nl"}
        try:
            title_nl, desc_nl = await asyncio.gather(
                _translate_to_dutch(item.get("title", ""), brand),
                _translate_to_dutch(item.get("description", ""), brand),
            )
        except VertalingOnbeschikbaar:
            return _zonder_vertaling(item, "nl")
        return {**item, "title": title_nl, "description": desc_nl, TAAL_VELD: "nl"}

    translations = await asyncio.gather(
        _build_english() if need_en else asyncio.sleep(0),
        _build_dutch() if need_nl else asyncio.sleep(0),
    )
    if need_en:
        english_item = translations[0]
    if need_nl:
        dutch_item = translations[1]

    _PLATFORM_PRICE_FIELD = {
        "marktplaats": "price_marktplaats",
        "2dehands": "price_2dehands",
        "vinted": "price_vinted",
        "ebay": "price_ebay",
        "shopify": "price_shopify",
    }

    # De vaste tekst van deze verkoper, onder élke advertentie op élk kanaal.
    # Zie instellingen.SLOTTEKST_MAX voor het waarom.
    _slot = slottekst_van(user_id)

    def _pick(platform: str) -> dict:
        if platform in _ENGLISH_PLATFORMS and english_item:
            base = english_item
        elif platform in _DUTCH_PLATFORMS and dutch_item:
            base = dutch_item
        else:
            base = item
        manual_title = (item.get("shopify_title") or "").strip()
        if platform == "shopify" and manual_title:
            base = {**base, "title": manual_title}
        price_field = _PLATFORM_PRICE_FIELD.get(platform)
        if price_field and base.get(price_field):
            base = {**base, "price": base[price_field]}
        # Laatste zeef vlak voor publicatie: nooit een <text>-omhulling in de
        # advertentie. De vertaling haalt hem er al af, maar deze regel geldt voor
        # élk pad hierheen (ook een item dat de tags al opgeslagen had staan).
        titel = _strip_text_tags(base.get("title") or "")
        beschrijving = _met_slot(_strip_text_tags(base.get("description") or ""), _slot)
        # Marktplaats en 2dehands rekenen voor een advertentie met een webadres
        # erin. Zie _zonder_links: dat kostte Egbert Brouwer drie weken en een
        # winkelmandje van EUR 153,00 aan advertenties die nooit online kwamen.
        if platform in ("marktplaats", "2dehands"):
            titel = _zonder_links(titel)
            beschrijving = _zonder_links(beschrijving)
        return {**base, "title": titel, "description": beschrijving}

    # Eerst de extensieplatforms in de wachtrij, dán de API-platforms.
    #
    # Andersom kostte het een keer een halve publicatie: Shopify was traag (het
    # aanmaken van een product wordt gevolgd door foto's, voorraad, collectie en
    # kanalen), de gateway hakte het verzoek af, en daardoor kwamen Marktplaats,
    # 2dehands en Vinted NOOIT in de wachtrij. Het item bleef eindeloos op
    # "Publishing…" staan terwijl er op die kanalen niets was gebeurd.
    #
    # De wachtrij vullen is alleen een paar databaseregels wegschrijven, dus dat
    # is altijd binnen een oogwenk klaar. Wat daarna misgaat kan de extensie niet
    # meer treffen.
    for platform in ext_platforms:
        # Elk kanaal apart afgeschermd. Ging er onderweg iets mis — een
        # weggevallen databaseverbinding bijvoorbeeld — dan brak dat de héle
        # publicatie af met "HTTP 500": Marktplaats en 2dehands stonden er al
        # op, Vinted kwam niet eens in de wachtrij, en de gebruiker zag alleen
        # een serverfout zonder te weten wat er wél gelukt was. Nu meldt het
        # ene kanaal zijn eigen fout en gaan de andere gewoon door.
        try:
            payload = dict(_pick(platform))
            # Marktplaats en 2dehands vragen om de verantwoordelijke partij; de
            # extensie vult die drie velden in als ze in de opdracht staan.
            if platform in ("marktplaats", "2dehands"):
                payload.update(fab)
                # Levering en pakketgrootte horen bij de verkoper, niet bij het
                # artikel. Zonder deze regel kreeg iemand die uitsluitend
                # verzendt bij elke advertentie "Ophalen of Verzenden" — een
                # belofte die hij niet kan waarmaken.
                from backend.services.instellingen import verzendkeuzes, locatie
                payload.update(verzendkeuzes(user_id, payload.get("price")))
                # Waar de verkoper staat. Zonder dit blok neemt het formulier
                # het contactblok uit zijn account op die site, en dat kan een
                # Nederlander op 2dehands.be niet goed zetten: daar past alleen
                # een Belgische postcode in. Zie LOCATIE_VELDEN.
                payload.update(locatie(user_id))
            # Create pending listing record first so failed jobs are visible in dashboard
            existing_listing = await _exec(
                db.table("listings").select("id,status,platform_listing_id,platform_listing_url")
                .eq("item_id", item_id).eq("platform", platform)
            )
            # Staat het er al op? Dan geen tweede advertentie aanmaken. De API-kant
            # had deze bescherming al (_publish_one); de extensieplatforms niet, dus
            # een tweede keer publiceren zette hetzelfde item nog eens op Vinted.
            # Niet de eerste rij, maar de LEVENDE rij. Sinds een tweede
            # advertentie op hetzelfde kanaal een eigen regel krijgt, kan de
            # actieve advertentie ook de tweede regel zijn — en dan zei deze
            # controle "niets gevonden" en publiceerde er nog een derde bij.
            rijen = existing_listing.data or []
            row = next((r for r in rijen
                        if r.get("status") == "active" and r.get("platform_listing_id")),
                       rijen[0] if rijen else None)
            if row and row.get("status") == "active" and row.get("platform_listing_id"):
                # EIGEN STATUS, GEEN "active" (05-09-2026, gemeten bij Papa's
                # Plectrums). "active" betekent op de API-kant juist WEL zojuist
                # gepubliceerd (_publish_one geeft dezelfde waarde terug), dus
                # het scherm kon deze twee niet uit elkaar houden en meldde
                # "Queued" terwijl er geen opdracht werd aangemaakt. Zijn 5533
                # artikelen staan allemaal al op Marktplaats, dus elke publicatie
                # daarheen verdween geruisloos in dit tak.
                results.append({
                    "platform": platform,
                    "status": "already_live",
                    "listing_id": row["id"],
                    "platform_listing_id": row.get("platform_listing_id"),
                    "platform_listing_url": row.get("platform_listing_url"),
                    "message": ALREADY_LIVE_MESSAGE,
                })
                continue
            if not existing_listing.data:
                await _exec(db.table("listings").insert({
                    "item_id": item_id,
                    "platform": platform,
                    "status": "pending",
                }))
            else:
                await _exec(db.table("listings").update({"status": "pending", "error_message": None}).eq("item_id", item_id).eq("platform", platform))
            # Is er al een openstaande publicatieopdracht voor dit item op dit
            # platform? Dan die bijwerken in plaats van een tweede aanmaken. Zonder
            # deze stap leverde één keer opnieuw proberen na een time-out (het
            # verzoek kwam wél aan, alleen het antwoord ging verloren) twee
            # opdrachten op — en dus twee advertenties.
            open_job = (await _exec(
                db.table("jobs").select("id,status,claimed_at")
                .eq("user_id", user_id).eq("item_id", item_id)
                .eq("platform", platform).eq("action", "create")
                .in_("status", ["pending", "claimed"])
                .limit(1)
            )).data
            if open_job:
                job_id = open_job[0]["id"]
                update = _republish_job_update(open_job[0], payload)
                await _exec(db.table("jobs").update(update).eq("id", job_id))
                hergebruikt = True
            else:
                # Het id zelf bepalen: dan is een herhaalde poging na een
                # weggevallen verbinding herkenbaar als "stond er al" in plaats van
                # een tweede opdracht — en dus een tweede advertentie.
                job_id = str(uuid.uuid4())
                await _exec(db.table("jobs").insert({
                    "id": job_id,
                    "user_id": user_id,
                    "item_id": item_id,
                    "platform": platform,
                    "action": "create",
                    "status": "pending",
                    "payload": payload,
                }), dubbel_is_ok=True)
                hergebruikt = False
            results.append({
                "platform": platform,
                "status": "queued",
                "job_id": job_id,
                "message": ("Already queued — the extension is still working on it"
                            if hergebruikt else
                            "Job queued — Chrome extension will process this"),
            })
        except Exception as e:
            logger.exception(f"Publiceren naar {platform} mislukte")
            results.append({
                "platform": platform,
                "status": "error",
                "error": f"Could not queue this listing ({type(e).__name__}). Nothing was published here — try again.",
            })


    # API platforms: run concurrently server-side
    if api_platforms:
        creds_resp = await _exec(
            db.table("platform_credentials")
            .select("*")
            .eq("user_id", user_id)
            .in_("platform", api_platforms)
        )
        creds_by_platform = {c["platform"]: c for c in creds_resp.data}
        tasks = [
            _publish_one(_pick(p), p, creds_by_platform.get(p, {}), user_id)
            for p in api_platforms
        ]
        # Elk kanaal apart, net als bij de extensieplatforms hierboven. Met
        # return_exceptions=False sleepte één struikelende taak de hele
        # publicatie mee: de gebruiker kreeg een kale "HTTP 500 Internal Server
        # Error" en wist niet dat Marktplaats en Vinted wél in de wachtrij
        # stonden. Een fout op eBay hoort een fout op eBay te blijven.
        for platform, uitkomst in zip(api_platforms,
                                      await asyncio.gather(*tasks, return_exceptions=True)):
            if isinstance(uitkomst, BaseException):
                logger.error("Publiceren naar %s mislukte onverwacht", platform,
                             exc_info=uitkomst)
                results.append({
                    "platform": platform, "status": "error",
                    "error": f"Could not publish here ({type(uitkomst).__name__}). "
                             f"Nothing was published on this channel — try again.",
                })
            else:
                results.append(uitkomst)

    return results


async def _publish_one(item: dict, platform_name: str, credentials: dict, user_id: str) -> dict:
    db = get_db()
    # Alles tot en met het klaarzetten van de advertentieregel zit óók in een
    # vangnet. Zonder dit vloog een weggevallen databaseverbinding — of een
    # insert die niets teruggaf, waarna `insert.data[0]` een IndexError werd —
    # ongevangen omhoog tot buiten het verzoek, en zag de gebruiker "HTTP 500:
    # Internal Server Error" zonder één woord over wat er misging.
    try:
        existing = await _exec(db.table("listings").select("id,status,platform_listing_id,platform_listing_url")
                               .eq("item_id", item["id"]).eq("platform", platform_name))
        if existing.data:
            listing_id = existing.data[0]["id"]
            # Staat het er al op? Dan niet nóg een keer aanmaken. create_listing maakt
            # elke keer een nieuw product aan, dus een herhaalde poging (na een
            # time-out bijvoorbeeld) liet er twee achter waarvan het dashboard er
            # maar één kende — de eerste bleef onzichtbaar te koop staan.
            if existing.data[0].get("status") == "active" and existing.data[0].get("platform_listing_id"):
                return {
                    "listing_id": listing_id,
                    "platform": platform_name,
                    "status": "already_live",
                    "platform_listing_id": existing.data[0].get("platform_listing_id"),
                    "platform_listing_url": existing.data[0].get("platform_listing_url"),
                    "message": ALREADY_LIVE_MESSAGE,
                }
            await _exec(db.table("listings").update({"status": "pending", "error_message": None}).eq("id", listing_id))
        else:
            insert = await _exec(db.table("listings").insert({
                "item_id": item["id"],
                "platform": platform_name,
                "status": "pending",
            }))
            if not insert.data:
                raise RuntimeError("de advertentieregel werd niet aangemaakt")
            listing_id = insert.data[0]["id"]
    except Exception as e:  # noqa: BLE001
        logger.exception("Kon de advertentieregel voor %s niet klaarzetten", platform_name)
        return {
            "platform": platform_name,
            "status": "error",
            "error": f"Could not start publishing here ({type(e).__name__}). "
                     f"Nothing was published on this channel — try again.",
        }

    try:
        platform = get_platform(platform_name)

        # Leg vast dát de advertentie bestaat op het moment dat het platform hem
        # bevestigt, niet pas als álle nabewerking klaar is. Shopify doet daarna
        # nog foto's, voorraad, collectie en verkoopkanalen; wordt het verzoek in
        # die seconden afgekapt, dan stond het product wél online terwijl het
        # dashboard eindeloos "Publishing…" bleef tonen.
        async def _leg_vast(vroeg: dict):
            await _exec(db.table("listings").update({
                "platform_listing_id": vroeg.get("platform_listing_id"),
                "platform_listing_url": vroeg.get("platform_listing_url"),
                "status": "active",
                "listed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", listing_id))
            logger.info(f"{platform_name}: listing {listing_id} meteen vastgelegd als actief")

        # Bewust NIET meesmokkelen in de inloggegevens: die worden bij sommige
        # platforms met een ververst token teruggeschreven naar de database, en
        # dan zou er een functie in dat veld belanden.
        if platform_name == "shopify":
            result = await platform.create_listing(item, credentials, on_created=_leg_vast)
        else:
            result = await platform.create_listing(item, credentials)

        listing_update = {
            "platform_listing_id": result["platform_listing_id"],
            "platform_listing_url": result["platform_listing_url"],
            "status": "active",
            "listed_at": datetime.now(timezone.utc).isoformat(),
        }
        if "platform_offer_id" in result:
            listing_update["platform_offer_id"] = result["platform_offer_id"]
        await _exec(db.table("listings").update(listing_update).eq("id", listing_id))

        await asyncio.to_thread(_log_event, listing_id, "listed", result)
        return {"listing_id": listing_id, "platform": platform_name, "status": "active", **result}

    except Exception as e:
        msg = str(e) or f"{type(e).__name__}: {e!r}"
        logger.error(f"Failed to list on {platform_name}: {msg}")
        await _exec(db.table("listings").update({
            "status": "error",
            "error_message": msg,
        }).eq("id", listing_id))
        await asyncio.to_thread(_log_event, listing_id, "error", {"error": msg})
        return {"listing_id": listing_id, "platform": platform_name, "status": "error", "error": msg}


def _last_listed_title(db, item_id: str, platform: str, fallback: str) -> str:
    """
    Marktplaats/2dehands listings are published under a Dutch-translated title
    (see _pick() in publish_to_platforms), but that translation is never
    persisted anywhere — the `items` row keeps the original title. The delete
    automation searches the platform's overview page by title text, so passing
    the untranslated title makes it silently fail to find the listing (and
    the DOM-verification added in background.js means it now surfaces as a
    real error instead of a false "delisted"). Recover the title actually used
    by reading the most recent completed "create" job's payload for this
    item+platform — that's the exact text that was typed into the platform.
    """
    jobs = (
        db.table("jobs")
        .select("payload,created_at")
        .eq("item_id", item_id)
        .eq("platform", platform)
        .eq("action", "create")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if jobs and jobs[0].get("payload", {}).get("title"):
        return jobs[0]["payload"]["title"]
    return fallback


async def delist_all_platforms(item_id: str, user_id: str,
                               alleen_platforms: set[str] | None = None) -> list[dict]:
    """Delist an item from every platform it is currently active on.

    `alleen_platforms` beperkt de ronde tot die kanalen. Alleen het vangnet in
    verkoop_reconciliatie.py geeft dat mee: dat draait elke 20 minuten opnieuw,
    en een kanaal waar de afmelding blijft mislukken moet het kunnen overslaan
    zonder de andere kanalen van hetzelfde artikel mee te slepen. None betekent
    "alle kanalen", precies zoals het altijd werkte.
    """
    db = get_db()
    listings_resp = (
        (await naast_de_lus(lambda: db.table("listings").select("*").eq("item_id", item_id).execute()))
    )
    # Which rows count as "might still be live on the platform".
    #
    # 'delisted' is deliberately included. A delete that only LOOKED like it
    # worked still flipped this row to 'delisted' while the product stayed live
    # in the shop — exactly what the Marktplaats confirm-dialog bug and the
    # Shopify id/SKU bugs did. Once that happened the row was excluded from this
    # query forever, so every later delist silently skipped that platform: no
    # error, no mention in the summary, and the listing never removed. Delist
    # means "make sure this is gone", so re-attempt anything not already sold.
    # Re-deleting something genuinely gone is harmless: the extension verifies
    # presence first and treats an absent listing as success, and the API
    # platforms treat a 404 the same way.
    #
    # 'pending' covers a create that never finished — the product can exist on
    # the platform even though we never recorded its id.
    #
    # 'hidden' counts too: a listing hidden on Vinted still exists on the
    # platform, so "delist" must actually remove it rather than skip it.
    _LEVEND = ("active", "error", "pending", "relisting", "hidden")
    # A platform where this item already SOLD is off limits, whatever other rows
    # exist for it. Deleting a sold ad is pointless (the buyer's transaction lives
    # on it), it fails half the time, and it made the app open a Vinted tab for
    # something the seller had already sold there. One sold row therefore blocks
    # the whole platform, not just its own row.
    sold_platforms = {l["platform"] for l in listings_resp.data if l["status"] == "sold"}

    # Eén verwijdering per ADVERTENTIE, niet per platform. Bij een dubbele import
    # of meerdere herplaatsingen staan er twee VERSCHILLENDE advertenties op
    # hetzelfde platform (verschillend platform_listing_id); de oude "één per
    # platform" liet de tweede staan, dus bleef een verkocht artikel te koop.
    seen_ads: dict[tuple, dict] = {}
    platforms_met_levende_rij = set()
    # De verkochte kanalen zijn hierboven uit ALLE rijen bepaald, ook als de
    # aanroeper zich tot een paar kanalen beperkt: één verkochte rij sluit dat
    # kanaal af, wat de aanroeper ook vraagt.
    rijen = [l for l in listings_resp.data
             if alleen_platforms is None or l.get("platform") in alleen_platforms]
    for l in rijen:
        if l["status"] not in _LEVEND or l["platform"] in sold_platforms:
            continue
        platforms_met_levende_rij.add(l["platform"])
        pid = l.get("platform_listing_id")
        sleutel = (l["platform"], pid or "")
        # Nummerloze rij op een platform waar we al een advertentie mét nummer
        # zagen: vrijwel altijd dezelfde advertentie halverwege het publiceren.
        if not pid and any(k[0] == l["platform"] and k[1] for k in seen_ads):
            continue
        seen_ads.setdefault(sleutel, l)

    # 'delisted' telt alleen mee als VANGNET: op een platform waar géén levende
    # rij meer staat maar wél een 'delisted'-rij, kan een eerdere verwijdering
    # alleen in de database geslaagd zijn terwijl de advertentie live bleef (de
    # oude Marktplaats-bevestigdialoog, de Shopify id/SKU-bugs). Dan één poging
    # per platform. Niet per archiefrij: dat opent tabblad na tabblad voor
    # advertenties die allang weg zijn.
    for l in rijen:
        p = l["platform"]
        if (l["status"] == "delisted" and p not in sold_platforms
                and p not in platforms_met_levende_rij
                and not any(k[0] == p for k in seen_ads)):
            seen_ads[(p, l.get("platform_listing_id") or "")] = l

    active_listings = list(seen_ads.values())

    skipped_sold = [
        {"platform": p, "status": "already_sold",
         "message": "Sold on this platform — left alone on purpose."}
        for p in sorted(sold_platforms)
    ]

    if not active_listings:
        return skipped_sold or [{"status": "nothing_to_delist", "message": "No active listings found"}]

    item = eerste_rij(await naast_de_lus(lambda: db.table("items").select("*").eq("id", item_id).limit(1).execute()))

    results = []

    api_active = [l for l in active_listings if l["platform"] in API_PLATFORMS]
    ext_active = [l for l in active_listings if l["platform"] in EXTENSION_PLATFORMS]

    # Queue the extension-driven delete jobs FIRST. These are the platforms the
    # user watches happen in their own Chrome (MP/2dehands/Vinted/FB). They must
    # be dispatched immediately and can never be blocked by a slow or hanging
    # API-platform delete below — a previous ordering awaited eBay/Shopify first,
    # so a slow eBay call hung the whole request: the dashboard spinner never
    # cleared AND these jobs were never created, so Vinted/MP never opened.
    # Verwijderopdrachten die al klaarstaan voor dit item, per advertentienummer.
    # Zonder deze rem stapelt de reconciliatieronde (elke 20 min) een nieuwe
    # opdracht op dezelfde advertentie, en een dubbele klik op Delist deed dat ook.
    # Wél per ADVERTENTIE: bij twee advertenties op één platform (dubbele import,
    # meerdere herplaatsingen) moet de tweede alsnog een eigen opdracht krijgen.
    open_deletes = (await naast_de_lus(lambda: db.table("jobs")
                    .select("id,platform,payload")
                    .eq("user_id", user_id).eq("item_id", item_id).eq("action", "delete")
                    .in_("status", ["pending", "claimed"]).limit(50).execute())).data or []

    def _al_in_wachtrij(platform: str, ad_id):
        for j in open_deletes:
            if j.get("platform") != platform:
                continue
            j_pid = (j.get("payload") or {}).get("platform_listing_id")
            if (j_pid or "") == (ad_id or "") or (not ad_id and not j_pid):
                return j["id"]
        return None

    for listing in ext_active:
        bestaand_id = _al_in_wachtrij(listing["platform"], listing.get("platform_listing_id"))
        if bestaand_id:
            results.append({
                "platform": listing["platform"],
                "status": "queued",
                "job_id": bestaand_id,
                "message": "Delete job already queued — Chrome extension will process this",
            })
            continue
        payload = {
            **item,
            "title": _last_listed_title(db, item_id, listing["platform"], item.get("title", "")),
            "platform_listing_id": listing["platform_listing_id"],
            "platform_listing_url": listing["platform_listing_url"],
        }
        job = (await naast_de_lus(lambda l=listing, p=payload: db.table("jobs").insert({
            "user_id": user_id,
            "item_id": item_id,
            "platform": l["platform"],
            "action": "delete",
            "status": "pending",
            "payload": p,
        }).execute())).data[0]
        results.append({
            "platform": listing["platform"],
            "status": "queued",
            "job_id": job["id"],
            "message": "Delete job queued — Chrome extension will process this",
        })

    # Listings we genuinely couldn't locate to delist from the backend (no id and
    # no fallback) — surfaced as needs_link so the user can paste the listing URL.
    needs_link: list[dict] = []

    if api_active:
        # For eBay listings without an offer/listing id, resolve by SKU. eBay's
        # Inventory API keys offers on SKU, so getOffers(?sku=) recovers the offerId
        # we can withdraw. On success persist it and delist normally; on failure we
        # can't delete via API (no id) — report needs_link instead of faking success.
        still_delistable = []
        for listing in api_active:
            if (listing["platform"] == "ebay"
                    and not listing.get("platform_offer_id")
                    and not listing.get("platform_listing_id")):
                resolved = None
                sku = item.get("sku", "")
                try:
                    creds = (
                        (await naast_de_lus(lambda: db.table("platform_credentials").select("*")
                        .eq("user_id", user_id).eq("platform", "ebay").execute())).data
                    )
                    if creds and sku:
                        ebay = get_platform("ebay")
                        resolved = await ebay.resolve_offer_by_sku(sku, creds[0])
                except Exception as e:
                    logger.warning(f"eBay SKU→offer resolution failed for {sku}: {e}")
                    resolved = None
                if resolved and resolved.get("platform_offer_id"):
                    listing["platform_offer_id"] = resolved["platform_offer_id"]
                    if resolved.get("platform_listing_id"):
                        listing["platform_listing_id"] = resolved["platform_listing_id"]
                    try:
                        upd = {"platform_offer_id": resolved["platform_offer_id"]}
                        if resolved.get("platform_listing_id"):
                            upd["platform_listing_id"] = resolved["platform_listing_id"]
                        (await naast_de_lus(lambda: db.table("listings").update(upd).eq("id", listing["id"]).execute()))
                    except Exception as e:
                        logger.warning(f"Persisting resolved eBay ids failed: {e}")
                    logger.info(f"Resolved eBay offer by SKU {sku} → {resolved['platform_offer_id']}")
                    still_delistable.append(listing)
                else:
                    needs_link.append({
                        "platform": "ebay",
                        "status": "needs_link",
                        "message": "Couldn't locate this ebay listing to delist — paste its URL to link it.",
                    })
            else:
                still_delistable.append(listing)
        api_active = still_delistable

        # For Shopify listings without a platform_listing_id, look up by SKU first
        for listing in api_active:
            if listing["platform"] == "shopify" and not listing.get("platform_listing_id"):
                sku = item.get("sku", "")
                if not sku:
                    logger.warning("Shopify listing %s has no product id and the item has no SKU — can't locate it", listing["id"])
                    continue
                try:
                    pid = await _find_shopify_product_id_by_sku(sku)
                    if pid:
                        listing["platform_listing_id"] = pid
                        (await naast_de_lus(lambda: db.table("listings").update({"platform_listing_id": pid}).eq("id", listing["id"]).execute()))
                        logger.info(f"Resolved Shopify product by SKU {sku} → {pid}")
                    else:
                        logger.warning("Shopify SKU %s not found in the store — nothing to delete", sku)
                except Exception as e:
                    logger.warning(f"Shopify SKU lookup failed: {e}")

        tasks = [_delist_one(listing) for listing in api_active]
        # Bound the API deletes so a slow/hanging eBay or Shopify call can never
        # keep the dashboard spinner spinning forever. On timeout the listing is
        # reported as an error (retryable) instead of blocking the whole request.
        try:
            api_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=45
            )
        except asyncio.TimeoutError:
            api_results = [asyncio.TimeoutError("delete timed out after 45s")] * len(api_active)
        for listing, res in zip(api_active, api_results):
            if isinstance(res, Exception):
                results.append({"platform": listing["platform"], "status": "error", "error": str(res)})
            else:
                results.append({"platform": listing["platform"], "status": "delisted"})

    results.extend(needs_link)
    results.extend(skipped_sold)
    return results


# Platforms that are driven by the browser extension. Their cross-platform
# delist on a sale MUST go through the extension's delete-job flow (which runs in
# the user's own logged-in Chrome, verifies the listing is still present, deletes
# it, then verifies it's gone). Deleting these server-side with stored cookies is
# exactly the fragile path this project moved away from — a stale server session
# has silently mass-delisted live listings before (see services/polling.py). API
# platforms (eBay/Etsy/Shopify) delete cleanly via their own APIs, server-side.
_EXTENSION_DELIST_PLATFORMS = {"marktplaats", "2dehands", "vinted", "facebook"}


async def handle_item_sold(item_id: str, sold_on_platform: str, sold_price: float | None = None,
                           sold_at: datetime | str | None = None):
    """
    Called when an item is confirmed sold on one platform. Marks that listing
    sold and delists every OTHER active listing for the item — extension
    platforms via a queued delete job, API platforms via their API — so the item
    can't be double-sold.

    sold_price: the amount actually received, when the source knows it (Shopify
    order total, eBay sale price). Left NULL for sources that don't — mainly the
    Vinted wardrobe scan, which only sees that a listing vanished, not for how
    much. Analytics falls back to the asking price and asks the user to confirm.

    sold_at: de ECHTE verkoopdatum, als de bron die kent (de datum op Vinteds
    bestellingenpagina, de besteldatum bij Shopify). Zonder die datum vallen we
    terug op nu — dat klopt zolang we de verkoop meteen opmerken, maar niet als
    er een ronde is overgeslagen. Daarom de harde regel hieronder: een datum mag
    alleen naar VOREN in de tijd worden bijgesteld, nooit naar achteren. Wij
    kunnen een verkoop immers nooit eerder ontdekken dan hij plaatsvond, dus een
    lagere datum is per definitie de betere. Zo repareert een latere ronde met
    de echte datum vanzelf de te late stempel van een eerdere ronde.
    """
    db = get_db()

    from backend.services.verkoopdatum import als_datum, lees_verkoopdatum
    echte_datum = lees_verkoopdatum(sold_at) if sold_at is not None else None

    # Mark sold listing. Only write sold_price when we actually have it, so a
    # later confirmed amount is never overwritten with NULL by a re-detection.
    update = {
        "status": "sold",
        "sold_at": (echte_datum or datetime.now(timezone.utc)).isoformat(),
    }
    if sold_price is not None:
        update["sold_price"] = round(float(sold_price), 2)

    # Welke advertentierij de verkoop draagt, als er meerdere zijn.
    #
    # WAAROM DIT ER IS (01-09-2026). Elke herplaatsing zet er een advertentierij
    # bij: één artikel van Daniel had er zes op Marktplaats. Deze functie zette
    # ze ALLEMAAL op 'verkocht', en Analytics telt per rij — dus één verkoop
    # verscheen zes keer in de omzet. Zichtbaar werd dat pas toen verkopen uit de
    # berichtenlijst geboekt gingen worden; daarvoor werd op Marktplaats vrijwel
    # nooit iets geboekt en bleef het onzichtbaar.
    #
    # De verkoop hoort bij de advertentie die op dat moment leefde; de andere
    # rijen zijn archief van eerdere herplaatsingen en gaan naar 'delisted'.
    LEVEND = ("active", "relisting", "hidden", "sold_unconfirmed", "pending")

    def _kies_rij(rijen: list[dict]) -> dict:
        al_verkocht = [r for r in rijen if r.get("status") == "sold"]
        if al_verkocht:
            return al_verkocht[0]      # herdetectie: dezelfde rij blijft de rij
        levend = [r for r in rijen if r.get("status") in LEVEND]
        kandidaten = levend or rijen
        return max(kandidaten, key=lambda r: str(r.get("listed_at") or r.get("created_at") or ""))

    def _write_sold():
        existing = (
            db.table("listings").select("id,status,sold_at,listed_at,created_at")
            .eq("item_id", item_id).eq("platform", sold_on_platform).execute()
        )
        if existing.data:
            velden = dict(update)
            staand = _kies_rij(existing.data)
            if staand.get("status") == "sold" and staand.get("sold_at"):
                # Al geboekt. De datum alleen aanpassen als de nieuwe aantoonbaar
                # eerder is; anders zou elke herdetectie de verkoop opnieuw naar
                # vandaag schuiven — precies hoe twaalf verkopen van weken op
                # 30-08-2026 op één dag terechtkwamen.
                if not (echte_datum and echte_datum < als_datum(staand["sold_at"])):
                    velden.pop("sold_at", None)
            db.table("listings").update(velden).eq("id", staand["id"]).execute()
            # De overige rijen van dit kanaal zijn archief, geen tweede verkoop.
            for r in existing.data:
                if r["id"] == staand["id"] or r.get("status") in ("sold", "delisted"):
                    continue
                db.table("listings").update({"status": "delisted"}).eq("id", r["id"]).execute()
        else:
            # No listing record on the sold platform (e.g. the user sold something
            # Omnivaleur wasn't tracking there, or a manual/unlinked sale). Still
            # record the sale so it counts in revenue/Analytics rather than silently
            # doing nothing — the manual "Sold" button must never be a no-op.
            db.table("listings").insert({
                "item_id": item_id,
                "platform": sold_on_platform,
                **update,
            }).execute()

    try:
        _write_sold()
    except Exception as e:
        # sold_price column not migrated yet — never let that block the sold flow.
        if "sold_price" in update and "sold_price" in str(e):
            update.pop("sold_price", None)
            _write_sold()
        else:
            raise

    # Verkocht betekent: nergens meer plaatsen. Stond er nog een publicatie in de
    # wachtrij (bijvoorbeeld omdat de browser toen dicht stond), dan zette de
    # extensie het item ná de verkoop alsnog online — en die verse advertentie
    # kreeg geen verwijderopdracht, want die was al langs geweest.
    try:
        (await naast_de_lus(lambda: db.table("jobs").update({
            "status": "cancelled",
            "result": {"cancelled": "item sold elsewhere"},
        }).eq("item_id", item_id).eq("action", "create") \
          .in_("status", ["pending", "claimed"]).execute()))
    except Exception as e:  # noqa: BLE001 - een verkoop mag hier nooit op stuklopen
        logger.warning("[sold] could not cancel queued publish jobs for %s: %s", item_id, e)

    # Hetzelfde voor een verwijderopdracht die nog klaarstond vóór hét platform
    # waar hij nu blijkt te zijn verkocht: die advertentie hoort te blijven staan.
    try:
        (await naast_de_lus(lambda: db.table("jobs").update({
            "status": "cancelled",
            "result": {"cancelled": "sold on this platform"},
        }).eq("item_id", item_id).eq("platform", sold_on_platform).eq("action", "delete") \
          .in_("status", ["pending", "claimed"]).execute()))
    except Exception as e:  # noqa: BLE001
        logger.warning("[sold] could not cancel queued delete jobs for %s: %s", item_id, e)

    # Find other listings to delist. We include 'delisted' and 'error' — NOT just
    # 'active' — on purpose: a broken earlier delete could have flipped the DB to
    # 'delisted' while the listing is in fact still LIVE on the platform (the
    # exact state that made "Sold" silently open nothing). "Sold" means "make sure
    # this is gone everywhere", so we re-attempt removal on any listing that isn't
    # already the sold one. The extension verifies presence first and treats an
    # absent listing as success, so re-checking a genuinely-gone one is harmless.
    # Ook de advertenties van de TWEELING. Dezelfde trui staat vaak twee keer in
    # de voorraad (één rij per importbron, zelfde nummer voor de titel). Verkocht
    # op de ene rij liet de advertenties van de andere gewoon staan — en die werd
    # daarna ook nog opnieuw geplaatst. Zie backend/services/tweelingen.py.
    item_vooraf = ((await naast_de_lus(lambda: db.table("items")
                   .select("id,user_id,title,sku,brand").eq("id", item_id)
                   .limit(1).execute())).data or [None])[0]
    from backend.services.tweelingen import familie_ids
    familie = await naast_de_lus(lambda: familie_ids(db, item_vooraf)) if item_vooraf else [item_id]

    all_rows = (
        (await naast_de_lus(lambda: db.table("listings")
        .select("*")
        .in_("item_id", familie)
        .execute()))
    )
    # Never touch a platform this item already sold on — not the one we just
    # booked, and not one that sold earlier. A second sale record on another
    # channel (a manual "Sold" after an auto-detected one) used to send a delete
    # job to the platform where the buyer's order lives.
    # HET PLATFORM VAN DE VERKOOP BLIJFT MET RUST.
    #
    # Daar zit de koper, en een tweede advertentie op datzelfde platform kan
    # net zo goed een tweede exemplaar zijn dat de verkoper er bewust bij heeft
    # gezet. Dat verschil kunnen wij niet zien, en een advertentie te veel
    # weghalen is niet terug te draaien. Op de ándere kanalen is er geen twijfel:
    # het artikel is verkocht, dus daar hoort het weg — ook de advertenties die
    # bij de tweelingrij horen.
    verkochte_rijen = [l for l in (all_rows.data or []) if l["status"] == "sold"]
    sold_platforms = {l["platform"] for l in verkochte_rijen} | {sold_on_platform}
    other_rows = [
        l for l in (all_rows.data or [])
        if l["platform"] not in sold_platforms
        and l["status"] in ("active", "relisting", "error", "delisted", "hidden", "pending")
    ]

    logger.info(
        "[sold] item_id=%s sold_on=%s → %d other listing(s) to delist: %s (sold platforms left alone: %s)",
        item_id, sold_on_platform, len(other_rows),
        [(l["platform"], l["status"]) for l in other_rows],
        sorted(sold_platforms),
    )

    if not other_rows:
        logger.info("[sold] item_id=%s: NOTHING to delist (no other listing rows found)", item_id)
        return

    item_row = eerste_rij(await naast_de_lus(lambda: db.table("items").select("*").eq("id", item_id).limit(1).execute()))
    user_id = (item_row or {}).get("user_id")

    # Dedup to one delete per platform (a platform can have both an 'error' and a
    # 'delisted' row from earlier attempts — we only need one delete job).
    # Eén verwijderopdracht per ADVERTENTIE, niet per platform: bij een tweeling
    # staan er twee verschillende advertenties op hetzelfde platform en die moeten
    # allebei weg. Rijen zonder advertentienummer worden per platform samengevat,
    # want daar valt niets aan te wijzen.
    seen_plat = set()
    api_listings = []
    for listing in other_rows:
        sleutel = (listing["platform"], str(listing.get("platform_listing_id") or ""))
        if sleutel in seen_plat:
            continue
        seen_plat.add(sleutel)
        plat = listing["platform"]
        if plat in _EXTENSION_DELIST_PLATFORMS and user_id:
            # item_id van de listing zelf: bij een tweeling hoort de advertentie
            # bij de ándere rij, en een verwijderopdracht op het verkeerde item
            # vindt de advertentie niet terug.
            _enqueue_extension_delete(db, user_id, listing["item_id"], listing, item_row)
            logger.info("[sold] queued extension delete for %s (was %s)", plat, listing["status"])
        else:
            api_listings.append(listing)

    if api_listings:
        results = await asyncio.gather(
            *[_delist_one(l) for l in api_listings], return_exceptions=True
        )
        for listing, result in zip(api_listings, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to delist {listing['platform']} listing {listing['id']}: {result}")


def _enqueue_extension_delete(db, user_id: str, item_id: str, listing: dict, item_row: dict | None) -> None:
    """
    Queue a delete job for the extension to remove `listing` in the user's Chrome.
    Skips if a delete is already pending/claimed for this exact ADVERT, so a
    repeated sale detection can't spawn duplicate delete tabs — but a second
    advert on the same platform (double import, extra relist) still gets its own.
    """
    platform = listing["platform"]
    ad_id = listing.get("platform_listing_id") or ""
    open_deletes = (
        db.table("jobs").select("id,payload")
        .eq("user_id", user_id).eq("item_id", item_id).eq("platform", platform)
        .eq("action", "delete").in_("status", ["pending", "claimed"])
        .limit(50).execute().data or []
    )
    for j in open_deletes:
        j_pid = (j.get("payload") or {}).get("platform_listing_id") or ""
        if j_pid == ad_id or (not ad_id and not j_pid):
            return
    payload = {
        **(item_row or {}),
        # MP/2dh delete searches the overview by the exact (Dutch-translated)
        # title that was published — recover it, not the stored English title.
        "title": _last_listed_title(db, item_id, platform, (item_row or {}).get("title", "")),
        "platform_listing_id": listing.get("platform_listing_id"),
        "platform_listing_url": listing.get("platform_listing_url"),
    }
    db.table("jobs").insert({
        "user_id": user_id,
        "item_id": item_id,
        "platform": platform,
        "action": "delete",
        "status": "pending",
        "payload": payload,
    }).execute()
    logger.info(f"Queued extension delete for item {item_id} on {platform} (sold elsewhere)")


# Marktplaats free listings expire silently after 28 days.
# We relist 1 day early to avoid gaps in visibility.
_MARKTPLAATS_EXPIRY_DAYS = 27
# Zie relist_expiring_marktplaats: nooit een hele voorraad op een dag, maar wel
# genoeg om een grote voorraad bij te houden.
_AUTO_RELIST_DOELCYCLUS = 20
_AUTO_RELIST_MIN_PER_DAY = 25
# Bovengrens. Bij calm mode zit er 3 tot 8 minuten tussen elke actie, dus 100
# stuks is al gauw een dag waarop de computer aan moet blijven. Wie boven de
# 2.000 advertenties komt haalt de cyclus daarmee niet meer helemaal; dat is een
# echte grens van deze aanpak en geen stille afronding.
_AUTO_RELIST_MAX_PER_DAY = 100
# Hoeveel dagen ná zijn eigen termijn een advertentie nog automatisch wordt
# opgepakt. Daarbuiten is het geen verversing meer maar een inhaalslag.
_INHAAL_MARGE_DAGEN = 14


def _dagelijkse_relist_grens(db, user_id: str) -> int:
    """Hoeveel advertenties deze verkoper vandaag hoogstens opnieuw geplaatst krijgt.

    Een vaste grens is altijd fout. Te laag en de advertenties van een grote
    verkoper verlopen voordat we erbij zijn — Marktplaats gooit ze na 30 dagen
    weg en wij herplaatsen op 27, dus er is weinig speling. Te hoog en een kleine
    verkoper krijgt alsnog zijn hele voorraad op een dag.

    Uitgangspunt: verdeel de voorraad gelijkmatig over de cyclus. Wie 1.200
    advertenties heeft komt dan op ongeveer 45 per dag — precies het tempo dat
    deze verkopers nu met de hand aanhouden (Jaap noemde 20 tot 30 per dag). Dat
    is geen bulkgedrag maar het gewone onderhoud van een grote winkel.
    """
    import math

    try:
        ids = []
        stap = 1000
        for offset in range(0, 20000, stap):
            # Zonder .order() mag de database elke pagina anders sorteren, dus
            # missen we item-ids en krijgen we andere dubbel — zie de uitleg bij
            # dezelfde fout in backend/api/imports.py. Een gemist item-id hier
            # betekent dat een verkochte advertentie niet elders wordt
            # weggehaald.
            rij = (db.table("items").select("id").eq("user_id", user_id).order("id")
                   .range(offset, offset + stap - 1).execute().data or [])
            ids += [r["id"] for r in rij]
            if len(rij) < stap:
                break
        actief = 0
        for i in range(0, len(ids), 100):
            actief += (db.table("listings").select("id", count="exact")
                       .eq("platform", "marktplaats").eq("status", "active")
                       .in_("item_id", ids[i:i + 100]).execute().count or 0)
    except Exception as e:  # noqa: BLE001 — bij twijfel het veilige minimum
        logger.warning("relist cap: kon voorraad niet tellen voor %s: %s", user_id, e)
        return _AUTO_RELIST_MIN_PER_DAY

    # Delen door 20 en niet door 27. Marktplaats gooit een advertentie na 30
    # dagen weg; herplaatsen we op 27, dan is er maar drie dagen speling. Rekenen
    # we de voorraad uit over 20 dagen, dan is de hele voorraad rond ruim voordat
    # de eerste zou verlopen, ook als er een dag uitvalt doordat de computer uit
    # stond.
    per_dag = math.ceil(actief / _AUTO_RELIST_DOELCYCLUS) if actief else 0
    return max(_AUTO_RELIST_MIN_PER_DAY, min(per_dag, _AUTO_RELIST_MAX_PER_DAY))


async def _echte_datums_ophalen(db) -> None:
    """Geïmporteerde advertenties op hun echte Marktplaats-datum zetten.

    Bij het importeren zetten we listed_at op vandaag, want de datum stond er niet
    bij. Voor het herplaatsen is dat de verkeerde klok: Marktplaats rekent vanaf de
    dag dat de advertentie er echt op kwam en gooit hem na dertig dagen weg. Wie
    zijn voorraad importeert ziet er bij ons dus splinternieuw uit terwijl de helft
    bijna verloopt — en die advertenties zijn weg voordat wij ze oppakken.

    Draait elke ronde opnieuw en overschrijft steeds met dezelfde waarde: het is
    een correctie, geen eenmalige migratie, dus er valt niets stuk als hij een keer
    niet lukt. Marktplaats weet het beter dan wij, altijd.
    """
    try:
        from backend.services.mp_datums import corrigeer_listed_at
    except Exception as e:  # noqa: BLE001 — nooit de hele ronde laten vallen
        logger.warning("echte datums overgeslagen: %s", e)
        return
    try:
        # fetch_all, niet .limit(4000): PostgREST negeert een limiet boven zijn
        # eigen max-rows en geeft er stilzwijgend 1.000 terug. Gemeten
        # 27-08-2026: er staan er 4.751 actief, dus driekwart kreeg nooit zijn
        # echte plaatsingsdatum.
        rijen = (await naast_de_lus(lambda: fetch_all(lambda: db.table("listings")
                 .select("id,item_id,platform_listing_id")
                 .eq("platform", "marktplaats").eq("status", "active")))) or []
    except Exception as e:  # noqa: BLE001
        logger.warning("echte datums: advertenties niet gelezen: %s", e)
        return
    if not rijen:
        return
    per_verkoper: dict[str, list[dict]] = {}
    for r in rijen:
        try:
            item = (eerste_rij(await naast_de_lus(lambda: db.table("items").select("user_id,title")
                    .eq("id", r["item_id"]).limit(1).execute())) or {})
        except Exception:  # noqa: BLE001
            continue
        if item.get("user_id"):
            per_verkoper.setdefault(item["user_id"], []).append(
                {**r, "titel": item.get("title") or ""})
    for user_id, lijst in per_verkoper.items():
        titels = [x["titel"] for x in lijst if x["titel"]][:8]
        nummers = {str(x.get("platform_listing_id") or "").strip()
                   for x in lijst if x.get("platform_listing_id")}
        try:
            await corrigeer_listed_at(db, user_id, titels, nummers)
        except Exception as e:  # noqa: BLE001
            logger.warning("echte datums voor %s mislukt: %s", user_id, e)


async def relist_expiring_marktplaats():
    """
    Queue a new 'create' job for every Marktplaats listing that has been
    active for >= MARKTPLAATS_EXPIRY_DAYS days and hasn't been re-queued yet.
    Marks the old listing 'relisting' so this function won't double-trigger.
    """
    from datetime import datetime, timezone, timedelta
    db = get_db()

    # Elke verkoper stelt zelf in na hoeveel dagen een advertentie opnieuw
    # geplaatst wordt. Hier wordt met de RUIMSTE instelling opgehaald — anders
    # zou wie op 7 dagen staat pas na 27 dagen aan de beurt komen — en verderop
    # per advertentie tegen de eigen instelling van de eigenaar gelegd.
    from backend.services.instellingen import (RELIST_DAGEN_MIN,
                                               RELIST_DAGEN_STANDAARD,
                                               alle_relist_dagen)
    dagen_per_verkoper = alle_relist_dagen()
    await _echte_datums_ophalen(db)
    from backend.services.instellingen import lees as _lees_instellingen
    _auto_aan: dict[str, bool] = {}

    def auto_relist_aan(uid: str) -> bool:
        if uid not in _auto_aan:
            _auto_aan[uid] = bool(_lees_instellingen(uid).get("auto_relist", True))
        return _auto_aan[uid]

    ruimste = min([RELIST_DAGEN_STANDAARD, *dagen_per_verkoper.values()] or
                  [RELIST_DAGEN_STANDAARD])
    ruimste = max(RELIST_DAGEN_MIN, ruimste)
    nu = datetime.now(timezone.utc)
    cutoff = (nu - timedelta(days=ruimste)).isoformat()
    listings_resp = (
        (await naast_de_lus(lambda: db.table("listings")
        .select("*")
        .eq("platform", "marktplaats")
        .eq("status", "active")
        .lt("listed_at", cutoff)
        # Oudste eerst. Wie het langst wacht is het dichtst bij de 30 dagen
        # waarop Marktplaats de advertentie zelf weggooit, dus die heeft voorrang.
        .order("listed_at")
        .execute()))
    )

    if not listings_resp.data:
        return

    # NOOIT ALLES OP EEN DAG.
    #
    # Dit zette een baan klaar voor elke advertentie die ouder was dan 27 dagen,
    # zonder limiet en zonder spreiding. Gemeten geval 18-08-2026: een verkoper
    # importeerde 619 advertenties op twee dagen, dus op 13 en 14 september zouden
    # er 125 en 494 tegelijk verwijderd en opnieuw geplaatst worden. Op een
    # account waar hij drie jaar aan gebouwd heeft.
    #
    # Dat is precies het patroon waar Marktplaats op let, en het is ook nog eens
    # in tegenspraak met de handmatige verversknop, die bewust op 3 per dag staat.
    # Hier hoort dezelfde terughoudendheid.
    #
    # De grens ligt hoger dan bij handmatig verversen, en met opzet: dit is geen
    # extra oppepper maar het redden van een advertentie die anders vanzelf
    # verdwijnt. Zie _dagelijkse_relist_grens voor hoe hij meeschaalt.
    vandaag = datetime.now(timezone.utc).date().isoformat()
    per_verkoper: dict[str, int] = {}
    for row in ((await naast_de_lus(lambda: db.table("jobs")
                .select("user_id")
                .eq("platform", "marktplaats")
                .eq("action", "create")
                .gte("created_at", vandaag)
                .execute())).data or []):
        per_verkoper[row["user_id"]] = per_verkoper.get(row["user_id"], 0) + 1
    grens_per_verkoper: dict[str, int] = {}

    logger.info("Auto-relist: %s expiring Marktplaats listings, spread per seller",
                len(listings_resp.data))

    for listing in listings_resp.data:
        try:
            item = eerste_rij(await naast_de_lus(lambda: db.table("items").select("*").eq("id", listing["item_id"]).limit(1).execute()))
            if not item:
                continue

            eigenaar = item["user_id"]

            # Verkocht op een ander kanaal? Dan niet verversen. De uitdeelstap in
            # backend/api/jobs.py houdt zo'n publicatie ook tegen, maar dan is de
            # oude advertentie al weggehaald — verversen is immers weghalen en
            # opnieuw plaatsen. Hier stoppen betekent dat de advertentie gewoon
            # blijft staan tot de verkoopafhandeling hem netjes weghaalt.
            verkocht = ((await naast_de_lus(lambda: db.table("listings")
                        .select("platform").eq("item_id", listing["item_id"])
                        .eq("status", "sold").limit(1).execute())).data or [])
            if verkocht:
                logger.info("Auto-relist overgeslagen voor listing %s: item al verkocht op %s",
                            listing["id"], verkocht[0]["platform"])
                continue

            # Advertenties uit Admarkt (zakelijk Marktplaats) hebben geen eigen
            # advertentie-adres: het enige adres dat Admarkt teruggeeft is de
            # webwinkel van de verkoper. Zonder dat adres kunnen we de oude niet
            # weghalen — en een Admarkt-campagne verloopt ook niet vanzelf na 30
            # dagen. Een "herplaatsing" zou daar dus geen verversing zijn maar een
            # tweede, gelijke advertentie naast de eerste. Precies waar
            # Marktplaats accounts voor blokkeert. Overslaan dus.
            if not (listing.get("platform_listing_url") or "").strip():
                logger.info("Auto-relist overgeslagen voor listing %s: geen advertentie-adres "
                            "(Admarkt-import verloopt niet en kan niet worden vervangen)",
                            listing["id"])
                continue

            # Uitgezet door de verkoper zelf: dan gebeurt er niets, ook niet
            # stilletjes. De advertentie blijft gewoon op 'active' staan.
            if not auto_relist_aan(eigenaar):
                continue

            # Is deze advertentie voor DEZE verkoper al oud genoeg? De query
            # hierboven haalde ruim op; dit is de eigen instelling.
            eigen_dagen = dagen_per_verkoper.get(eigenaar, _MARKTPLAATS_EXPIRY_DAYS)
            geplaatst = listing.get("listed_at")
            if geplaatst:
                try:
                    toen = datetime.fromisoformat(str(geplaatst).replace("Z", "+00:00"))
                    if toen.tzinfo is None:
                        toen = toen.replace(tzinfo=timezone.utc)
                    if (nu - toen).days < eigen_dagen:
                        continue
                except ValueError:
                    pass          # onleesbare datum: laat de ruime query beslissen

            # NIET ALSNOG EEN HALF JAAR INHALEN.
            #
            # Zodra de echte Marktplaats-datum bekend is, blijkt een geïmporteerde
            # voorraad vaak in één klap "te oud". Gemeten 20-08-2026 bij Jaap:
            # 959 van zijn 1.222 advertenties zijn 25 dagen of ouder, waarvan er
            # 236 al 45 tot 60 dagen online staan — en die staan er dus gewoon
            # nog, ze verlopen kennelijk niet op het schema dat wij aannemen.
            # Zonder deze rem zou Omnivaleur er vanaf morgen 62 per dag gaan
            # verwijderen en opnieuw plaatsen, vijftien dagen lang, met alle
            # reacties en vragen die eraan hangen. Dat is geen redding meer maar
            # een ingreep waar de verkoper zelf over hoort te beslissen.
            #
            # Automatisch herplaatsen pakt de oudste eerst, en niet meer dan de
            # dagelijkse grens per verkoper. Zo wordt een geïmporteerde voorraad
            # in de loop van weken bijgewerkt in plaats van in één dag — zonder
            # dat de oudste, die het eerst verdwijnt, wordt overgeslagen.
            if geplaatst:
                try:
                    toen = datetime.fromisoformat(str(geplaatst).replace("Z", "+00:00"))
                    if toen.tzinfo is None:
                        toen = toen.replace(tzinfo=timezone.utc)
                    # HIER STOND EEN REM DIE PRECIES DE VERKEERDE OVERSLOEG.
                    #
                    # Alles ouder dan de eigen termijn plus veertien dagen werd
                    # overgeslagen, om te voorkomen dat een pas geïmporteerde
                    # voorraad in één klap "te oud" zou zijn. Het gevolg was het
                    # tegenovergestelde van de bedoeling: juist de advertenties
                    # die het dichtst bij verwijdering staan bleven liggen.
                    # Gemeten bij Jaap (21-08-2026): de ronde verversde
                    # advertenties van 17 juli, terwijl die van 14 mei — de
                    # oudste, en dus de eerste die Marktplaats weggooit — er nooit
                    # doorheen kwamen.
                    #
                    # De rem is niet nodig: de dagelijkse grens per verkoper
                    # (_dagelijkse_relist_grens) spreidt het al, en de rij staat
                    # op oudste eerst. Zonder deze uitzondering komt de oudste dus
                    # gewoon als eerste aan de beurt — precies wat een verkoper
                    # verwacht en wat zijn advertenties redt.
                    pass
                except ValueError:
                    pass

            if eigenaar not in grens_per_verkoper:
                grens_per_verkoper[eigenaar] = _dagelijkse_relist_grens(db, eigenaar)
            if per_verkoper.get(eigenaar, 0) >= grens_per_verkoper[eigenaar]:
                # Morgen weer. De advertentie blijft op 'active' staan, dus hij
                # komt de volgende ronde vanzelf opnieuw langs — en omdat we op
                # listed_at sorteren staat hij dan vooraan.
                continue
            per_verkoper[eigenaar] = per_verkoper.get(eigenaar, 0) + 1

            # EERST WEG, DAN OPNIEUW. Hier stond alleen de "create" — op de
            # aanname dat Marktplaats de oude advertentie na 30 dagen zelf al
            # had weggegooid. Die aanname is aantoonbaar onjuist: bij Jaap
            # stonden advertenties van 45 tot 60 dagen oud gewoon nog online.
            # Gevolg: elke automatische herplaatsing zette er een tweede naast.
            # Gemeten op 21-08-2026: 61 nieuwe advertenties, nul verwijderingen,
            # en zijn account groeide van 1.220 naar ongeveer 1.300 — precies het
            # dubbel-plaatsen waar Marktplaats accounts voor blokkeert.
            #
            # refresh_listing doet het wél goed: het zet een verwijderopdracht
            # klaar en plant de nieuwe plaatsing erachteraan, en /jobs/pending
            # laat die tweede stap alleen door als de eerste écht gelukt is.
            from backend.services.relist import refresh_listing, RefreshError
            try:
                await refresh_listing(listing["item_id"], "marktplaats",
                                      item["user_id"], "relist",
                                      eigen_quotum=True)
            except RefreshError as e:
                # Dagquotum vol of nog in afkoeling: morgen weer. De advertentie
                # blijft op 'active' staan en komt vanzelf opnieuw langs.
                logger.info("Auto-relist overgeslagen voor listing %s: %s",
                            listing["id"], e)
                per_verkoper[eigenaar] = max(0, per_verkoper.get(eigenaar, 1) - 1)
                continue

            logger.info(f"Queued relist job for item {listing['item_id']} (listing {listing['id']})")
        except Exception as e:
            logger.error(f"Failed to queue relist for listing {listing['id']}: {e}")


# ── 2DEHANDS: VERLENGEN, NIET HERPLAATSEN ────────────────────────────────────
#
# Een 2dehands-zoekertje is 4 weken zichtbaar en kan daarna GRATIS worden
# verlengd (gemeten op het ingelogde plaatsformulier, 10-09-2026). Anders dan bij
# Marktplaats halen we hier NIETS weg: verlengen is één klik op het eigen
# overzicht. Opnieuw plaatsen zou in een betalende rubriek geld kosten of het
# gratis tegoed opeten (zie docs/team-notes.md, Egberts 24 mislukte
# gitaarzoekertjes) terwijl verlengen altijd gratis is. Daarom een eigen
# opdrachtsoort 'extend' die de advertentierij volledig met rust laat — alleen
# listed_at schuift mee zodra de extensie kan aantonen dat de vervaldatum echt
# vier weken verder ligt.
_EXTEND_MIN_LEEFTIJD_DAGEN = 22   # 2dehands toont "Verlengen" ~7 dagen voor de 28e dag
_EXTEND_MAX_LEEFTIJD_DAGEN = 45   # ouder: waarschijnlijk al verlopen; de extensie kijkt zelf
_EXTEND_MAX_PER_VERKOPER_PER_DAG = 40
_EXTEND_HERKANS_NA_DAGEN = 3      # niet elke 6-uursronde opnieuw inplannen vóór het venster


async def extend_expiring_2dehands():
    """Zet een 'extend'-opdracht klaar voor elk 2dehands-zoekertje dat bijna
    afloopt. Verlengen, niet herplaatsen: er wordt niets weggehaald, de
    advertentierij houdt zijn platform_listing_id en zijn status 'active'.
    """
    import random
    db = get_db()
    from backend.services.instellingen import lees as _lees_instellingen

    nu = datetime.now(timezone.utc)
    ondergrens = (nu - timedelta(days=_EXTEND_MAX_LEEFTIJD_DAGEN)).isoformat()
    bovengrens = (nu - timedelta(days=_EXTEND_MIN_LEEFTIJD_DAGEN)).isoformat()

    rijen = ((await naast_de_lus(lambda: db.table("listings")
             .select("id,item_id,platform_listing_id,platform_listing_url,listed_at")
             .eq("platform", "2dehands")
             .eq("status", "active")
             .gte("listed_at", ondergrens)
             .lte("listed_at", bovengrens)
             # Oudste eerst: die staat het dichtst bij de dag waarop 2dehands hem
             # zelf laat vervallen.
             .order("listed_at")
             .execute())).data or [])
    if not rijen:
        return

    _auto_aan: dict[str, bool] = {}

    def auto_aan(uid: str) -> bool:
        if uid not in _auto_aan:
            _auto_aan[uid] = bool(_lees_instellingen(uid).get("auto_relist", True))
        return _auto_aan[uid]

    vandaag = nu.date().isoformat()
    per_verkoper: dict[str, int] = {}
    for row in ((await naast_de_lus(lambda: db.table("jobs")
                .select("user_id")
                .eq("platform", "2dehands").eq("action", "extend")
                .gte("created_at", vandaag).execute())).data or []):
        per_verkoper[row["user_id"]] = per_verkoper.get(row["user_id"], 0) + 1

    herkans_grens = (nu - timedelta(days=_EXTEND_HERKANS_NA_DAGEN)).isoformat()
    ingepland = 0
    for listing in rijen:
        try:
            item = eerste_rij(await naast_de_lus(lambda: db.table("items").select("id,user_id")
                    .eq("id", listing["item_id"]).limit(1).execute()))
            if not item:
                continue
            eigenaar = item["user_id"]
            if not auto_aan(eigenaar):
                continue

            # Verkocht op welk kanaal dan ook? Dan nooit verlengen. Een verkoop
            # is een eindpunt (zie "herplaatslus-op-verkochte-artikelen").
            verkocht = ((await naast_de_lus(lambda: db.table("listings")
                        .select("platform").eq("item_id", listing["item_id"])
                        .in_("status", ["sold", "sold_unconfirmed"]).limit(1).execute())).data or [])
            if verkocht:
                continue

            # Al een extend-opdracht voor deze advertentie? Loopt er nog een, of
            # is er net een geprobeerd, dan niets nieuws — anders zet elke
            # 6-uursronde er een bij zolang de advertentie nog niet in het
            # verlengvenster van 2dehands zit.
            bestaat = ((await naast_de_lus(lambda: db.table("jobs")
                       .select("id,status,created_at")
                       .eq("item_id", listing["item_id"]).eq("platform", "2dehands")
                       .eq("action", "extend")
                       .order("created_at", desc=True).limit(1).execute())).data or [])
            if bestaat:
                b = bestaat[0]
                if b.get("status") in ("pending", "claimed", "running"):
                    continue
                if str(b.get("created_at") or "") > herkans_grens:
                    continue

            if per_verkoper.get(eigenaar, 0) >= _EXTEND_MAX_PER_VERKOPER_PER_DAG:
                continue
            n = per_verkoper.get(eigenaar, 0)
            per_verkoper[eigenaar] = n + 1

            # Spreiden. Het ritme verraadt automatisering (zie "calm-mode"): geen
            # veertig verlengingen achter elkaar. Elke volgende opdracht van
            # dezelfde verkoper staat vijf tot negen minuten later klaar; de
            # extensie voert er sowieso maar één tegelijk uit.
            scheduled_for = (nu + timedelta(minutes=n * random.randint(5, 9))).isoformat()

            payload = {
                "platform_listing_id": listing.get("platform_listing_id"),
                "platform_listing_url": listing.get("platform_listing_url"),
                "_listing_row_id": listing["id"],
            }
            (await naast_de_lus(lambda p=payload, s=scheduled_for, u=eigenaar, it=listing["item_id"]:
                db.table("jobs").insert({
                    "user_id": u,
                    "item_id": it,
                    "platform": "2dehands",
                    "action": "extend",
                    "status": "pending",
                    "scheduled_for": s,
                    "payload": p,
                }).execute()))
            ingepland += 1
            logger.info("Queued 2dehands extend for item %s (listing %s)",
                        listing["item_id"], listing["id"])
        except Exception as e:  # noqa: BLE001
            logger.error("Kon 2dehands-verlenging niet inplannen voor listing %s: %s",
                         listing["id"], e)
    if ingepland:
        logger.info("Auto-extend 2dehands: %s opdrachten ingepland", ingepland)


async def _find_shopify_product_id_by_sku(sku: str, shop_token: tuple | None = None) -> str | None:
    """
    Locate a Shopify product by variant SKU, walking every page of the catalog.

    The previous version read products.json with limit=50 and gave up — on any
    store with more than 50 products a listing whose product id we'd lost was
    simply never found, so the delist reported "couldn't delete" (or nothing at
    all) while the product stayed live in the shop. Shopify caps a page at 250
    and hands out the next page via a cursor in the Link header.

    `shop_token` = (shop_domain, access_token) for the seller's OWN store. Pass it
    whenever you have per-seller credentials: without it this falls back to the
    single store in the server settings, which is wrong once there are customers
    with their own linked stores.
    """
    if not sku:
        return None
    import httpx
    import re as _re

    if shop_token and shop_token[0] and shop_token[1]:
        shop, token = shop_token
    else:
        from backend.config import settings
        from backend.platforms.shopify_importer import _get_token
        shop, token = settings.shopify_store, await _get_token()
    if not shop or not token or token == "session":
        return None

    url = f"https://{shop}/admin/api/2024-10/products.json"
    params: dict = {"limit": 250, "fields": "id,variants"}
    headers = {"X-Shopify-Access-Token": token}

    async with httpx.AsyncClient(timeout=20) as c:
        for _ in range(40):  # 40 x 250 = 10k products — far beyond any real shop
            r = await c.get(url, params=params, headers=headers)
            r.raise_for_status()
            for p in r.json().get("products", []):
                if any(v.get("sku") == sku for v in p.get("variants", [])):
                    return str(p["id"])
            # Cursor pagination: Link: <https://…page_info=xyz>; rel="next"
            link = r.headers.get("link") or r.headers.get("Link") or ""
            nxt = _re.search(r'<([^>]+)>;\s*rel="next"', link)
            if not nxt:
                return None
            url, params = nxt.group(1), {}
    return None


async def _delist_one(listing: dict):
    db = get_db()
    item_van_de_advertentie = eerste_rij(await naast_de_lus(lambda: db.table("items").select("user_id").eq("id", listing["item_id"]).limit(1).execute()))
    item_user_id = (item_van_de_advertentie or {}).get("user_id")
    creds_resp = (
        (await naast_de_lus(lambda: db.table("platform_credentials")
        .select("*")
        .eq("user_id", item_user_id)
        .eq("platform", listing["platform"])
        .execute()))
    )
    credentials = creds_resp.data[0] if creds_resp.data else {}

    try:
        platform = get_platform(listing["platform"])
        # platform_offer_id is an eBay-only concept (Inventory API offers). Using it
        # as a fallback for every platform meant a stray value on a Shopify row would
        # be sent to Shopify as a product id, which 404s and reads as "delete failed".
        delete_id = (
            listing.get("platform_offer_id") if listing["platform"] == "ebay" else None
        ) or listing.get("platform_listing_id")

        # Shopify-rij zonder product-id: eerst opzoeken in de winkel van DEZE
        # verkoper via de SKU. Zonder deze stap gooide delete_product meteen
        # "No Shopify product id" en bleef het artikel na een verkoop elders
        # gewoon in de webshop staan — precies wat Daniel meldde.
        if listing["platform"] == "shopify" and not delete_id:
            sku = None
            try:
                it = eerste_rij(await naast_de_lus(lambda: db.table("items").select("sku")
                      .eq("id", listing["item_id"]).limit(1).execute()))
                sku = (it or {}).get("sku")
            except Exception:  # noqa: BLE001
                sku = None
            if sku:
                from backend.platforms.shopify import _shop_creds
                try:
                    shop_token = await _shop_creds(credentials)
                except Exception:  # noqa: BLE001
                    shop_token = None
                pid = await _find_shopify_product_id_by_sku(sku, shop_token)
                if pid:
                    delete_id = pid
                    try:
                        (await naast_de_lus(lambda: db.table("listings")
                         .update({"platform_listing_id": pid}).eq("id", listing["id"]).execute()))
                    except Exception:  # noqa: BLE001
                        pass
                    logger.info("Shopify product opgezocht via SKU %s → %s (item %s)",
                                sku, pid, listing["item_id"])

        deleted = await platform.delete_listing(delete_id, credentials)
        if deleted is False:
            raise RuntimeError(f"delete_listing returned False for {listing['platform']} listing {listing['platform_listing_id']}")
        (await naast_de_lus(lambda: db.table("listings").update({
            "status": "delisted",
        }).eq("id", listing["id"]).execute()))
        _log_event(listing["id"], "delisted", {})
    except Exception as e:
        logger.error(f"Delist failed for {listing['id']}: {e}")
        _log_event(listing["id"], "error", {"error": str(e)})
        raise


# ── Price propagation ──────────────────────────────────────────────────────
# Changing a price used to write nothing but the items row, so every "Apply"
# in Stale stock and every bulk reprice was invisible to buyers: the dashboard
# said €19.99 while all six channels kept showing the old price. Anything that
# writes a price now goes through here.

# Platforms whose price we can actually change today.
#   ebay/shopify — direct API call.
#   vinted       — queued as an extension edit job.
# Marktplaats, 2dehands and Facebook have no edit automation at all yet, so
# they are reported as "unsupported" rather than silently skipped.
_PRICE_SYNC_API = {"ebay", "shopify"}
_PRICE_SYNC_EXTENSION = {"vinted"}


async def sync_price_to_platforms(item_id: str, user_id: str) -> list[dict]:
    """Push the item's current price to every platform it is live on.

    Returns one result per live listing: status is 'updated', 'queued',
    'unsupported' or 'error'. Never raises — a failing channel must not undo
    the price change or block the others.
    """
    db = get_db()
    item = eerste_rij(await naast_de_lus(lambda: db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).limit(1).execute()))
    if not item:
        return []

    listings = (
        (await naast_de_lus(lambda: db.table("listings").select("*")
        .eq("item_id", item_id)
        .in_("status", ["active", "hidden"])
        .execute())).data or []
    )
    if not listings:
        return []

    def _price_for(platform: str) -> float | None:
        # Mirror _pick() in publish_to_platforms: a per-platform price override
        # wins over the base price, so syncing never overwrites a price the user
        # deliberately set for one channel.
        field = _PLATFORM_PRICE_FIELD_GLOBAL.get(platform)
        raw = item.get(field) if field else None
        if raw in (None, ""):
            raw = item.get("price")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    results: list[dict] = []
    api_listings = [l for l in listings if l["platform"] in _PRICE_SYNC_API]
    creds_by_platform: dict[str, dict] = {}
    if api_listings:
        creds_resp = (
            (await naast_de_lus(lambda: db.table("platform_credentials").select("*")
            .eq("user_id", user_id)
            .in_("platform", sorted({l["platform"] for l in api_listings}))
            .execute()))
        )
        creds_by_platform = {c["platform"]: c for c in (creds_resp.data or [])}

    for listing in listings:
        platform = listing["platform"]
        price = _price_for(platform)
        if price is None:
            results.append({"platform": platform, "status": "error", "error": "No usable price on this item"})
            continue

        if platform in _PRICE_SYNC_EXTENSION:
            # The extension owns Vinted's edit page. _price_update tells the
            # content script this refresh is specifically about the price —
            # a plain content_refresh deliberately leaves the price alone.
            (await naast_de_lus(lambda: db.table("jobs").insert({
                "user_id": user_id,
                "item_id": item_id,
                "platform": platform,
                "action": "content_refresh",
                "status": "pending",
                "payload": {
                    **item,
                    "price": price,
                    "platform_listing_id": listing.get("platform_listing_id"),
                    "platform_listing_url": listing.get("platform_listing_url"),
                    "_price_update": True,
                },
            }).execute()))
            results.append({"platform": platform, "status": "queued",
                            "message": "Price edit queued — Chrome extension will apply it"})
            continue

        if platform not in _PRICE_SYNC_API:
            results.append({
                "platform": platform, "status": "unsupported",
                "message": f"{platform} has no price-edit automation yet — change it there by hand",
            })
            continue

        try:
            plat = get_platform(platform)
            if platform == "ebay":
                await plat.update_listing_price(
                    listing.get("platform_offer_id") or "", price,
                    creds_by_platform.get(platform, {}), sku=item.get("sku") or item["id"],
                )
            else:
                await plat.update_listing_price(
                    listing.get("platform_listing_id") or "", price,
                    creds_by_platform.get(platform, {}),
                )
            _log_event(listing["id"], "price_updated", {"price": price})
            results.append({"platform": platform, "status": "updated", "price": price})
        except Exception as e:
            msg = str(e) or f"{type(e).__name__}: {e!r}"
            logger.error("Price sync failed on %s for item %s: %s", platform, item_id, msg)
            _log_event(listing["id"], "error", {"error": f"price sync: {msg}"})
            results.append({"platform": platform, "status": "error", "error": msg})

    return results


# Same mapping publish_to_platforms uses; module-level so the price sync can't
# drift away from what publishing actually sends.
_PLATFORM_PRICE_FIELD_GLOBAL = {
    "marktplaats": "price_marktplaats",
    "2dehands": "price_2dehands",
    "vinted": "price_vinted",
    "ebay": "price_ebay",
    "shopify": "price_shopify",
}


def _log_event(listing_id: str, event_type: str, payload: dict):
    db = get_db()
    db.table("sync_events").insert({
        "listing_id": listing_id,
        "event_type": event_type,
        "payload": payload,
    }).execute()
