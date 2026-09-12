from fastapi import APIRouter, HTTPException, Depends, Request
from backend.database import (get_db, fetch_all, fetch_all_in, update_in, naast_de_lus,
                              execute_with_retry, eerste_rij)
from backend.api.deps import get_current_user, require_active_subscription
from backend.api.imports import _backfill_item_from_candidate
from backend.services.crosslist import handle_item_sold
from backend.services.kleur import normaliseer_kleur
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import logging
import time
import re
import unicodedata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# A claim older than this with no progress means the run was interrupted (the
# MV3 service worker gets killed the moment Chrome closes or after ~30s idle, so
# a job can be claimed but never reach /complete or /error). Nothing ever
# re-surfaced those, so they hung "claimed" forever — blocking paired relists and
# tripping the "extension is working" banner. We recover them below.
STALE_CLAIM_MINUTES = 5
MAX_RECLAIMS = 2

# De oudste extensieversie die we nog vertrouwen voor een scan.
#
# WAAROM DIT BESTAAT (27-08-2026, Egbert Brouwer). Hij bleek de extensie TWEE
# keer te draaien: een bijgewerkte kopie én een losse, met de hand geladen kopie
# van 16 augustus (1.0.207) die nooit meebeweegt met de Chrome Web Store. Beide
# halen opdrachten uit dezelfde wachtrij. Welke van de twee de scan het eerst
# pakt bepaalt de uitslag — en de oude kopie kán het niet: die haalt hooguit 250
# advertenties op en kent de "sla over wat we al hebben"-lijst niet. Uitslag over
# twee weken: 13 geslaagde scans, 18 mislukte, en die 18 meldden allemaal
# "je bent niet ingelogd bij Marktplaats" terwijl hij gewoon ingelogd was.
#
# 1.0.244 is de eerste versie die de bekende-id's-lijst gebruikt; alles daaronder
# kan een grote winkel niet uitlezen.
MINIMALE_SCANVERSIE = (1, 0, 244)
# 'extend' (2dehands verlengen) bestaat pas vanaf 1.0.318. Een oudere kopie kent
# die opdrachtsoort niet en zou hem als een gewone publicatie behandelen — dus
# het plaatsformulier openen en er een TWEEDE advertentie naast zetten. Zolang
# de Chrome Web Store 1.0.318 nog niet heeft goedgekeurd, krijgt zo'n kopie geen
# extend-werk; de opdracht blijft gewoon 'pending' tot een bijgewerkte kopie
# hem oppakt.
MINIMALE_EXTEND_VERSIE = (1, 0, 318)
# Hoe vaak een scan die door een te oude kopie is opgepakt terug in de wachtrij
# mag. Twee: genoeg om de bijgewerkte kopie een kans te geven, te weinig om te
# blijven rondzingen bij iemand die alleen die oude kopie heeft.
MAX_HERKANSING_OUDE_EXTENSIE = 2

# HOEVEEL VERSIES EEN KOPIE MAG ACHTERLOPEN VOORDAT ZE AANTOONBAAR NIET MEEBEWEEGT.
#
# GEMETEN (07-09-2026, De Juiste Toon). Zijn Chromebook draaide 1.0.260 van
# 28 augustus terwijl er 1.0.311 in de Chrome Web Store stond: 51 versies en
# tien dagen achterstand. Alle andere computers die die week werk deden stonden
# op 1.0.308 t/m 1.0.311, dus Chrome werkt de extensie bij zoals het hoort — een
# kopie die dat niet doet is met de hand geladen en zal NOOIT bijwerken.
#
# Waarom niet gewoon de harde ondergrens verhogen: die moet met de hand mee
# omhoog en staat daardoor altijd te laag. Deze grens meet zichzelf tegen wat er
# vandaag in de Web Store staat.
#
# Waarom 20 en niet minder: er gaan ongeveer vijf versies per dag uit, dus twintig
# is ruim vier dagen. Chrome controleert elke paar uur op updates. Wie meer dan
# vier dagen achterloopt, loopt niet achter maar staat stil. De drie andere
# actieve computers stonden op 1, 2 en 3 versies achterstand.
ACHTERSTAND_GRENS = 20


def _achterstand(gemeld, gepubliceerd) -> int | None:
    """Hoeveel versies deze kopie achterloopt, of None als dat niet te zeggen is.

    Alleen binnen dezelfde hoofd- en tussenversie (1.0.x) is het verschil een
    getal met betekenis. Springt de nummering naar 1.1.0, dan telt elke stap
    daar als "ver achter", want dan is er iets fundamenteels veranderd.
    """
    if not gemeld or not gepubliceerd:
        return None
    if gemeld >= gepubliceerd:
        return 0
    if gemeld[:2] != gepubliceerd[:2]:
        return ACHTERSTAND_GRENS   # andere reeks: altijd te ver weg
    return gepubliceerd[2] - gemeld[2]


def _kopie_staat_stil(gemeld) -> tuple[int, str] | None:
    """(achterstand, gepubliceerde versie) als deze kopie zichzelf niet bijwerkt.

    None bij twijfel: komt de Web Store-versie niet binnen, dan houden we niets
    tegen. Een kopie ten onrechte stilzetten is erger dan er een keer eentje
    doorlaten — precies dezelfde afweging als bij _kopstuk_versie.
    """
    if not gemeld:
        return None
    tekst = _gepubliceerde_extensieversie()
    gepubliceerd = _kopstuk_versie(tekst)
    achter = _achterstand(gemeld, gepubliceerd)
    if achter is None or achter < ACHTERSTAND_GRENS:
        return None
    return achter, tekst

_EXT_VERSIE = re.compile(r"\[extensie\s+(\d+)\.(\d+)\.(\d+)\]")


def _extensie_versie(tekst) -> tuple[int, int, int] | None:
    """De versie die de extensie zelf in haar foutmelding stempelt, of None.

    Handig omdat een oude extensie niets anders over zichzelf prijsgeeft: dit
    stempel zit er al sinds 1.0.19x in, dus we kunnen een verouderde kopie
    herkennen zonder dat die kopie daaraan hoeft mee te werken.
    """
    m = _EXT_VERSIE.search(str(tekst or ""))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _kopstuk_versie(waarde) -> tuple[int, int, int] | None:
    """De versie uit het X-Omnivaleur-Ext-kopstuk, of None als die er niet is.

    Anders dan _extensie_versie hoeft er hier niets mis te zijn gegaan: elke
    ronde langs de wachtrij vertelt de extensie wie ze is. Onleesbaar of
    afwezig geeft None — dan houden we niets tegen, want een kopie ten onrechte
    stilzetten is erger dan er een keer eentje doorlaten.
    """
    m = re.fullmatch(r"\s*(\d{1,3})\.(\d{1,3})\.(\d{1,4})\s*", str(waarde or ""))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None

# The optional import_candidates snapshot columns, dropped together if the
# migration hasn't run (see _store_scan_results).
RICH_KEYS = ("photo_urls", "description", "brand", "size", "condition",
             "category", "gender", "color", "material", "is_hidden")

# How recently the extension must have checked in for us to call a computer
# "online". The extension's poll alarm is nominally 15s, but Chrome MV3 throttles
# background alarms to ~30-60s in practice, so a tight window flipped to a false
# "offline" right before each poll even though Chrome was open. 120s tolerates a
# throttled alarm plus a couple of missed check-ins; the trade-off is that
# closing Chrome now shows as offline within ~2 min instead of within one.
EXTENSION_ONLINE_WINDOW_SECONDS = 120


# Of de kolom ext_version bestaat. Niet één keer per proces vaststellen: dan
# blijft een server die toevallig opstartte VOORDAT de kolom werd toegevoegd
# eeuwig zonder versies schrijven, en dat is precies wat er op 05-09-2026
# gebeurde — de kolom stond er, de hartslagen kwamen binnen, en het veld bleef
# leeg tot de volgende deploy. Een mislukking geldt daarom maar een uur.
_HEARTBEAT_VERSIEKOLOM_UIT_TOT = [0.0]
_HEARTBEAT_VERSIEKOLOM_PAUZE = 3600.0


def _record_extension_heartbeat(db, user_id: str, user_agent: str | None = None,
                                versie: str | None = None) -> None:
    """
    Stamp that the extension just checked in, so a user on their phone can see
    whether a computer is online to run their queued jobs. Called from every
    extension-only endpoint (the platform poll AND claim/progress/complete/error),
    so any extension activity — not just the dispatch poll — keeps the computer
    marked online.

    Best-effort: it must never slow down or break dispatch — if the heartbeat
    table hasn't been created yet, or the write fails, we silently move on.
    The user_agent is only written when provided, so a check-in without it (e.g.
    from /complete) refreshes last_seen without wiping the UA the poll captured.
    """
    try:
        row = {
            "user_id": user_id,
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }
        ua = (user_agent or "")[:300]
        if ua:
            row["user_agent"] = ua
        # De versie erbij, zodat we kunnen TELLEN wie er achterloopt in plaats
        # van het af te leiden uit foutmeldingen (waarmee je alleen de mensen
        # ziet die iets kapot hadden). De kolom moet met de hand worden
        # toegevoegd; tot die tijd valt hij hieronder weg zonder dat de
        # aanwezigheidsstempel eronder lijdt.
        if versie and time.monotonic() >= _HEARTBEAT_VERSIEKOLOM_UIT_TOT[0]:
            row["ext_version"] = versie[:20]
        try:
            db.table("extension_heartbeat").upsert(row).execute()
        except Exception:
            if "ext_version" not in row:
                raise
            _HEARTBEAT_VERSIEKOLOM_UIT_TOT[0] = time.monotonic() + _HEARTBEAT_VERSIEKOLOM_PAUZE
            logger.info(
                "Kolom ext_version ontbreekt nog in extension_heartbeat; de "
                "versie wordt niet vastgelegd; over een uur proberen we het "
                "opnieuw. Zet hem erbij met: ALTER TABLE "
                "extension_heartbeat ADD COLUMN ext_version text;")
            row.pop("ext_version")
            db.table("extension_heartbeat").upsert(row).execute()
    except Exception:
        pass


def _scan_sku(t: str) -> str:
    """Het voorloopnummer uit een titel: "(1327) Navy Suit…" → "1327"."""
    m = re.match(r"^\s*\(([^)]{1,24})\)", t or "")
    return m.group(1).strip().lower() if m else ""


def _scan_norm_title(t: str) -> str:
    """Titel zonder accenten, leestekens, SKU-prefix en dubbele spaties."""
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"^\s*\([^)]{1,24}\)\s*", "", t)
    # Apostrofs verdwijnen in plaats van spatie te worden: "B'TWIN" en "BTWIN"
    # zijn hetzelfde merk, en platforms schrijven dat door elkaar.
    t = t.replace("'", "").replace("’", "")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _unique_index(pairs, tweelingen: dict | None = None) -> dict:
    """key → id, maar alleen als die sleutel bij precies één id hoort.

    Uitzondering: TWEELINGEN. Dezelfde trui staat vaak twee keer in de voorraad
    (één rij per importbron), met hetzelfde nummer én dezelfde titel. Dan zijn er
    twee kandidaten en viel de sleutel weg — met als gevolg dat een advertentie
    die gewoon live stond aan geen van beide rijen gekoppeld werd, en het
    dashboard "staat niet op Vinted" toonde terwijl hij er wél stond. Zijn alle
    kandidaten aantoonbaar hetzelfde product, dan kiezen we er één, altijd
    dezelfde (de laagste id, zodat elke ronde tot dezelfde uitkomst komt).
    Verschillende producten met hetzelfde nummer blijven zonder koppeling.
    """
    out: dict = {}
    botsingen: dict = {}
    for key, value in pairs:
        if not key:
            continue
        if key not in out:
            out[key] = value
        elif out[key] != value:
            botsingen.setdefault(key, {out[key]}).add(value)
            out[key] = None
    for key, ids in botsingen.items():
        # Tweelingen zijn vaak VERTALINGEN van elkaar ("Suitable Half Zip" en
        # "Geschikte Halve Rits"), dus titels vergelijken werkt hier niet. Het
        # merk wel: dat staat in een eigen veld en vertaalt niet mee.
        kenmerk = {(tweelingen or {}).get(i) for i in ids}
        if len(kenmerk) == 1 and None not in kenmerk and "" not in kenmerk:
            out[key] = sorted(ids)[0]
    return {k: v for k, v in out.items() if v}


def _parse_ts(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _recover_stale_claims(db, user_id: str, platform: str, now_dt: datetime) -> None:
    """
    Find jobs stuck in 'claimed' with no recent activity and get them unstuck.

    Retry-safe jobs are reset to 'pending' so the extension runs them again:
      - delete: the extension verifies the listing is still in the wardrobe and
        no-ops if it's already gone, so a re-run can't double-delete.
      - scan: read-only.
      - content_refresh: re-edits the same listing (idempotent).

    NOT retry-safe → marked 'error' instead of retried:
      - ANY create job (initial crosslist OR relist recreate): if the first
        attempt did publish but the completion just wasn't recorded (e.g. the
        MV3 service worker was killed right after the tab confirmed the
        listing), re-running would post a DUPLICATE listing. A relist's create
        is no more idempotent than an initial create — its paired delete only
        guarantees the OLD listing is gone, not that THIS run didn't already
        publish the new one. Safer to surface an error and let the user retry
        manually.
      - anything that already hit the reclaim cap (persistently failing).
    """
    stale_before = (now_dt - timedelta(minutes=STALE_CLAIM_MINUTES)).isoformat()
    q = (
        db.table("jobs")
        .select("id,action,item_id,platform,scheduled_for,claimed_at,result")
        .eq("user_id", user_id)
        .eq("status", "claimed")
    )
    if platform:
        q = q.eq("platform", platform)
    for j in q.execute().data:
        claimed = _parse_ts(j.get("claimed_at"))
        if claimed and claimed.isoformat() > stale_before:
            continue  # claimed recently — genuinely in progress
        res = j.get("result") or {}
        prog_at = _parse_ts((res.get("_progress") or {}).get("at")) if isinstance(res, dict) else None
        if prog_at and prog_at.isoformat() > stale_before:
            continue  # long job (e.g. scan) still posting progress

        reclaims = (res.get("_reclaims", 0) if isinstance(res, dict) else 0)
        is_relist_create = j["action"] == "create" and j.get("scheduled_for")
        # 'extend' opnieuw draaien kan geen kwaad: is het zoekertje al verlengd,
        # dan is de verlengknop weg en meldt de extensie "niets te doen" terug.
        retry_safe = j["action"] in ("delete", "scan", "content_refresh", "extend")

        if retry_safe and reclaims < MAX_RECLAIMS:
            db.table("jobs").update({
                "status": "pending",
                "claimed_at": None,
                "result": {"_reclaims": reclaims + 1, "_last_reclaim": now_dt.isoformat()},
            }).eq("id", j["id"]).eq("status", "claimed").execute()
        else:
            msg = (
                "Publishing was interrupted (Chrome likely closed mid-run) and couldn't be "
                "verified either way — check whether it actually listed before publishing again "
                "to avoid a duplicate."
                if j["action"] == "create" else
                f"This {j['action']} job was interrupted and couldn't finish after retries. Try it again."
            )
            db.table("jobs").update({
                "status": "error",
                "result": {"error": msg},
                "done_at": now_dt.isoformat(),
            }).eq("id", j["id"]).eq("status", "claimed").execute()
            if is_relist_create:
                db.table("listings").update({
                    "status": "error",
                    "error_message": "Relist recreate was interrupted before it finished — the old listing was removed but the new one wasn't confirmed. Refresh again to retry.",
                }).eq("item_id", j["item_id"]).eq("platform", j["platform"]).execute()




def _zet_kleur_goed(jobs: list) -> int:
    """Zet de kleur in elke uitgaande opdracht om naar de naam die Marktplaats
    aanbiedt. Geeft terug hoeveel er zijn aangepast.

    Alleen als we de kleur herkennen. Een woord dat we niet kennen blijft staan
    zoals de verkoper het schreef — nooit een verzonnen kleur. Vinted heeft een
    eigen kleurenlijst en blijft hier buiten.
    """
    aangepast = 0
    for j in jobs or []:
        pl = j.get("payload")
        if j.get("platform") not in ("marktplaats", "2dehands"):
            continue
        if not isinstance(pl, dict) or not pl.get("color"):
            continue
        net = normaliseer_kleur(pl["color"])
        if net and net != str(pl["color"]).strip():
            logger.info("job %s: kleur %r -> %r", j.get("id"), pl["color"], net)
            pl["color"] = net
            aangepast += 1
    return aangepast


def _haal_links_eruit(db, jobs: list) -> int:
    """Geen web- of e-mailadres in een advertentie voor Marktplaats of 2dehands,
    vlak voordat de opdracht de deur uitgaat. Geeft terug hoeveel er zijn
    aangepast.

    WAAROM DIT ER IS (09-09-2026, Egbert Brouwer). Een zoekertje met een link in
    de omschrijving publiceren die sites niet: ze zetten hem klaar als bestelregel
    "Websitevermelding" van EUR 9,00. Zijn winkelmandje bij 2dehands liep zo op
    tot EUR 153,00 aan advertenties die nooit online kwamen, terwijl wij hem
    357 keer vertelden dat hij niet ingelogd zou zijn.

    De filter zelf (`_zonder_links` in crosslist.py) zat op het publicatiepad, in
    `_pick`. Dat is niet het enige pad dat een 'create' klaarzet: de reddingsronde
    in relist.py bouwde haar eigen payload, en `captured_listing` hierboven vult
    een lege omschrijving aan met de tekst die letterlijk van de advertentiepagina
    komt — bij hem dus mét link. Precies dezelfde soort lek als waar
    `_zet_taal_goed` hieronder voor bestaat, en daarom staat het op dezelfde plek:
    hier gaat er precies één opdracht naar de extensie, en pas hier is zeker dat
    hij ook echt gebruikt wordt. Wat voor pad die opdracht ook heeft afgelegd.

    We schrijven het terug in de opdracht, zodat in het dashboard en in de
    geschiedenis staat wat er werkelijk naar de site is gegaan.
    """
    try:
        from backend.services.crosslist import _zonder_links
    except Exception as e:  # noqa: BLE001 — het uitdelen gaat hoe dan ook door
        logger.warning("linkzeef niet beschikbaar: %s", e)
        return 0

    aangepast = 0
    for j in jobs or []:
        if j.get("platform") not in ("marktplaats", "2dehands"):
            continue
        pl = j.get("payload")
        if not isinstance(pl, dict):
            continue
        nieuw = dict(pl)
        for veld in ("title", "description"):
            waarde = pl.get(veld)
            if isinstance(waarde, str) and waarde:
                nieuw[veld] = _zonder_links(waarde)
        if nieuw == pl:
            continue
        logger.info("job %s (%s): web-/e-mailadres uit de advertentie gehaald "
                    "— dat kost EUR 9,00 per plaatsing", j.get("id"), j.get("platform"))
        j["payload"] = nieuw
        aangepast += 1
        try:
            db.table("jobs").update({"payload": nieuw}).eq("id", j["id"]).execute()
        except Exception as e:  # noqa: BLE001 — de opdracht die uitgaat is al schoon
            logger.warning("job %s: schone tekst niet kunnen opslaan: %s", j.get("id"), e)
    return aangepast


def _leest_als_engels(payload: dict, lijkt_al_in_taal) -> bool:
    """Leest deze advertentie overtuigend als Engels? Titel en omschrijving samen.

    Samen wegen en niet los: een titel als "Vintage pijpenstandaard" is te kort
    om een taal aan af te lezen, terwijl de omschrijving eronder glashelder is.
    Bij twijfel False — dit mag alleen ingrijpen als het duidelijk mis is.
    """
    samen = f"{(payload or {}).get('title') or ''}\n{(payload or {}).get('description') or ''}"
    return lijkt_al_in_taal(samen, "en")


def _zet_taal_goed(db, jobs: list) -> int:
    """De advertentie in de taal van het platform, vlak voordat hij de deur uitgaat.

    WAAROM DIT ER IS (04-09-2026, Daniel). Marktplaats en 2dehands zijn
    Nederlandstalig; de verkoper tikt zijn advertentie in het Engels in en de
    publicatiestroom vertaalt hem. Die vertaling zat op drie plekken los
    ingebouwd (publiceren, verversen, herplaatsen) en op een vierde plek niet:
    de reddingsronde zette een 'create' klaar met de kale databaserij erin. Wat
    daar doorheen glipte kwam gewoon in het Engels op Marktplaats te staan —
    "(1357) Lilac Profuomo Shirt - Men 45 - New With Tags" — zonder foutmelding,
    want er ging technisch niets mis.

    De reddingsronde is gerepareerd, maar dat lost alleen het pad op dat we
    kennen. Dit is de laatste zeef, op de enige plek waar élke opdracht
    langskomt: hier gaat er precies één opdracht naar de extensie, en pas hier is
    zeker dat hij ook echt gebruikt wordt. Zie ook _zet_kleur_goed hierboven,
    dat op dezelfde plek en om dezelfde reden staat.

    Herkennen doen we aan TAAL_VELD, dat elke localisatie in de payload zet.
    Ontbreekt het (of staat er een andere taal in), dan vertalen we alsnog en
    schrijven we het resultaat terug in de opdracht — anders zou dezelfde
    opdracht bij elke poll opnieuw vertaald worden.

    Alleen de Nederlandstalige kanalen. Op Vinted en Shopify gaat de tekst uit
    zoals de verkoper hem zelf schreef, en die hoort hier niet alsnog door een
    vertaling heen te gaan.
    """
    try:
        from backend.services.crosslist import (TAAL_VELD, VertalingOnbeschikbaar,
                                                lijkt_al_in_taal, localiseer_sync,
                                                taal_van_platform)
    except Exception as e:  # noqa: BLE001 — het uitdelen gaat hoe dan ook door
        logger.warning("taalzeef niet beschikbaar: %s", e)
        return list(jobs or [])

    door = []
    for j in jobs or []:
        if j.get("action") != "create" or not isinstance(j.get("payload"), dict):
            door.append(j)
            continue
        try:
            platform = j.get("platform")
            if taal_van_platform(platform) != "nl":
                door.append(j)
                continue
            payload = j["payload"]
            # HET STEMPEL IS GEEN BEWIJS — WIJ KIJKEN NAAR DE TEKST ZELF.
            #
            # GEMETEN (12-09-2026, Toon van De Juiste Toon). Een Nederlandse
            # tekst die opnieuw door "vertaal naar het Nederlands" ging kwam er
            # in 3 van de 6 pogingen in het ENGELS uit: het model draait de
            # richting om als er niets te vertalen valt. Die tekst kreeg gewoon
            # TAAL_VELD "nl" mee, en deze zeef liet hem daarop door. Zo gingen
            # 93 advertenties bij 7 verkopers in het Engels de deur uit zonder
            # dat er ergens iets rood werd.
            #
            # Vanaf nu telt alleen wat er in de tekst staat. Ziet de tekst er
            # overtuigend Engels uit, dan gaat hij hoe dan ook nog een keer door
            # de localisatie, wat er ook op het stempel staat.
            if payload.get(TAAL_VELD) == "nl" and not _leest_als_engels(payload, lijkt_al_in_taal):
                door.append(j)
                continue
            nieuw = localiseer_sync(payload, platform)
            # EN DAARNA KIJKEN WE NOG EEN KEER.
            #
            # Komt het er alsnog Engels uit, dan is de vertaling niet te
            # vertrouwen en gaat deze advertentie NIET de deur uit. Hij blijft
            # gewoon 'pending' en loopt vanzelf door zodra het wel lukt —
            # dezelfde keuze als bij een vertaalstoring, om dezelfde reden.
            if _leest_als_engels(nieuw, lijkt_al_in_taal):
                raise VertalingOnbeschikbaar(
                    "De tekst blijft na vertaling Engels, dus er is niets geplaatst.")
            if nieuw.get("title") != payload.get("title"):
                logger.info("job %s: titel alsnog vertaald voor %s (%r -> %r)",
                            j.get("id"), platform,
                            str(payload.get("title"))[:60], str(nieuw.get("title"))[:60])
            j["payload"] = nieuw
            db.table("jobs").update({"payload": nieuw}).eq("id", j["id"]).execute()
            door.append(j)
        except VertalingOnbeschikbaar as e:
            # DE VERTAALDIENST LIGT PLAT — DEZE OPDRACHT BLIJFT STAAN.
            #
            # Hij gaat NIET de deur uit met de onvertaalde tekst en wordt ook
            # niet op fout gezet: hij blijft gewoon 'pending' en gaat vanzelf
            # alsnog lopen zodra de vertaling het weer doet. Zo komt er nooit
            # een Engelse advertentie op een Nederlandse site te staan, en raakt
            # de verkoper zijn werk ook niet kwijt. Zie VertalingOnbeschikbaar
            # in backend/services/crosslist.py voor de meting die hierachter zit.
            logger.error("job %s (%s) blijft wachten: %s", j.get("id"), j.get("platform"), e)
            _meld_vertaalstoring(str(e))
        except Exception as e:  # noqa: BLE001 — een andere hapering mag de uitgifte niet stoppen
            logger.warning("job %s: taal niet kunnen goedzetten: %s", j.get("id"), e)
            door.append(j)
    return door


# Eén waarschuwing per uur, niet één per opdracht. Een lege API-rekening raakt
# elke wachtende advertentie tegelijk; zonder deze rem stond de mailbox vol.
_vertaalstoring_gemeld_op: float = 0.0


def _meld_vertaalstoring(reden: str) -> None:
    """De eigenaar moet dit binnen het uur weten: alles wat vertaald moet worden staat stil."""
    global _vertaalstoring_gemeld_op
    import time
    if time.time() - _vertaalstoring_gemeld_op < 3600:
        return
    _vertaalstoring_gemeld_op = time.time()
    try:
        from backend.services.email import send_email
        from backend.config import settings
        ontvangers = [a.strip() for a in (settings.owner_email or "").split(",") if a.strip()]
        for adres in ontvangers:
            send_email(
                "Omnivaleur: vertaling ligt stil, advertenties wachten",
                "De vertaling naar het Nederlands werkt op dit moment niet.\n\n"
                "Advertenties die vertaald moeten worden gaan NIET de deur uit; ze "
                "blijven in de wachtrij staan en lopen vanzelf door zodra dit is "
                "opgelost. Er komt dus geen Engelse tekst op Marktplaats of "
                "2dehands te staan.\n\n"
                "Meestal is dit het Anthropic-tegoed. Vul het aan, dan lost de "
                "wachtrij zichzelf op.\n\n"
                f"Melding van de server: {reden}",
                to=adres,
            )
    except Exception as e:  # noqa: BLE001 — een mislukte waarschuwing mag niets blokkeren
        logger.warning("kon vertaalstoring niet melden: %s", e)


# ── Wie is er als eerste aan de beurt? ────────────────────────────────────────
#
# WAAROM DIT ER IS (03-09-2026, Toon / De Juiste Toon). Om 02:33 zette de
# nachtelijke verversing 50 opdrachten klaar. Toen hij 's middags zelf op
# publiceren drukte, kwam die klik achteraan die rij te staan: de uitgifte
# pakte simpelweg de oudste twintig. Met Calm mode aan (3 tot 8 minuten tussen
# twee acties) is dat uren wachten op iets waar je net op geklikt hebt, en dat
# voelt als "de knop doet niets".
#
# De volgorde is daarom niet meer "wie het eerst kwam" maar "wie het hardst
# nodig heeft":
#   0. een herplaatsing waarvan de OUDE advertentie al weg is. Die staat nu
#      nergens online; alles wat dat verkort gaat voor.
#   1. wat de verkoper zelf zojuist aanklikte. Iets wat nergens online staat
#      gaat voor het opfrissen van iets wat al te koop staat.
#   2. de nachtronde die al langer dan NACHTRONDE_GEDULD wacht.
#   3. de nachtronde die nog moet beginnen met weghalen. Daar staat de
#      advertentie gewoon nog online, dus die kan wachten.
#   4. scans; die lezen alleen.
# Binnen elke groep blijft het gewoon op volgorde van binnenkomst.
#
# De nachtronde verhongert niet: zodra het eigen werk op is komt groep 2/3 aan
# de beurt, en een verwijdering die lang genoeg heeft gewacht schuift boven de
# verse nachtronde en boven de scans uit.
# 'extend' (2dehands verlengen) klikt een echte knop op de site: het telt als
# schrijvend, dus één tegelijk en meegeteld in het ritme (calm mode).
SCHRIJVEND = ("create", "delete", "content_refresh", "extend")
NACHTRONDE_GEDULD = timedelta(hours=6)
# Hoeveel opdrachten we volledig inlezen nadat de volgorde bepaald is. De
# volgorde wordt over de HELE wachtrij bepaald (alleen de lichte velden), de
# zware payloads halen we daarna alleen op voor deze kop. Zo kost het kiezen
# niets extra's aan dataverkeer.
WACHTRIJ_KOP = 25
WACHTRIJ_MAX = 500


def _wachtrij_volgorde(licht: list[dict], now_dt: datetime) -> list[dict]:
    """De hele wachtrij op urgentie zetten (alleen met de lichte velden)."""
    # Welke verwijderingen staan er nog te wachten? Staat de verwijdering die bij
    # een herplaatsing hoort er niet meer bij, dan is ze al gelopen en is de oude
    # advertentie hoogstwaarschijnlijk offline.
    open_verwijderingen = {(j.get("item_id"), j.get("platform"))
                           for j in licht if j.get("action") == "delete"}
    herplaats_paren = {(j.get("item_id"), j.get("platform"))
                       for j in licht
                       if j.get("action") == "create" and j.get("scheduled_for")}

    def groep(j: dict) -> int:
        actie = j.get("action")
        if actie not in SCHRIJVEND:
            return 4
        sleutel = (j.get("item_id"), j.get("platform"))
        if actie == "create" and j.get("scheduled_for"):
            return 3 if sleutel in open_verwijderingen else 0
        if actie == "delete" and sleutel in herplaats_paren:
            gemaakt = _parse_ts(j.get("created_at"))
            if gemaakt and now_dt - gemaakt >= NACHTRONDE_GEDULD:
                return 2          # lang genoeg gewacht, anders komt hij nooit
            return 3
        return 1

    return sorted(licht, key=lambda j: (groep(j), j.get("created_at") or ""))


def _ruim_dubbele_scans_op(db, licht: list[dict], now: str) -> list[dict]:
    """Meer dan één wachtende scan op hetzelfde kanaal is altijd per ongeluk.

    WAAROM (03-09-2026, Toon). Er stonden vier identieke Marktplaats-scans van
    dezelfde seconde klaar, en op 02-09 zelfs dertien. Dat gebeurt als er niets
    lijkt te gebeuren en iemand nog een keer drukt. Elke scan leest dan opnieuw
    de hele voorraad; de tweede tot en met de dertiende leveren niets op en
    houden alleen de rij bezet.

    We houden de NIEUWSTE over, niet de oudste. In de payload van een scan zit
    een momentopname van wat we al binnen hebben (`bekende_ids`, `tekst_bekend`,
    zie imports.py). Die lijst is bij de jongste opdracht het meest bij, en juist
    daarop bespaart de extensie haar verzoeken — bij Toon 52 pagina's in plaats
    van 1.017.
    """
    gezien: set = set()
    weg: list[str] = []
    houden = []
    for j in sorted(licht, key=lambda r: r.get("created_at") or "", reverse=True):
        if j.get("action") != "scan":
            houden.append(j)
            continue
        sleutel = j.get("platform")
        if sleutel in gezien:
            weg.append(j["id"])
            continue
        gezien.add(sleutel)
        houden.append(j)
    houden.sort(key=lambda r: r.get("created_at") or "")
    for job_id in weg:
        try:
            db.table("jobs").update({
                "status": "cancelled",
                "result": {"cancelled": "Duplicate scan — an identical scan for this "
                                        "marketplace was already queued."},
                "done_at": now,
            }).eq("id", job_id).execute()
        except Exception as e:  # noqa: BLE001 — nooit de uitgifte omgooien
            logger.warning("dubbele scan %s niet opgeruimd: %s", job_id, e)
    if weg:
        logger.info("%d dubbele scan(s) opgeruimd", len(weg))
    return houden


# ── Hoe snel loopt deze wachtrij ECHT? ───────────────────────────────────────
#
# WAAROM DIT ER IS (03-09-2026, Toon). Het dashboard belooft op zes plekken
# "within ~15 seconds". Met Calm mode aan zit er 3 tot 8 minuten tussen twee
# publicaties, en die schakelaar zit in de extensie: de server weet er niets
# van en het dashboard dus ook niet. Toon keek naar een balk die zei dat het zo
# ging beginnen, zag acht minuten lang niets, en meldde "er gebeurt eigenlijk
# niets". Zijn opdrachten liepen gewoon.
#
# We kunnen het niet vragen — een nieuwe extensie is pas over weken bij hem —
# maar we kunnen het METEN: het staat in de tijdstippen van werk dat al gedaan
# is. Werkt vandaag, op de kopie die hij nu draait.
TEMPO_KALM_DREMPEL = 150       # 2,5 min; zonder Calm mode is de tussentijd < 30s
TEMPO_ONDERBREKING = 20 * 60   # groter gat = de computer stond uit, niet meetellen
TEMPO_MONSTERS = 12
# Het dashboard vraagt /active elke vier seconden op. Een extra databasevraag in
# dat ritme is vijftien per minuut per open scherm, en de Supabase-client blokkeert
# de lus terwijl hij wacht. Het tempo verandert langzaam, dus een minuut onthouden
# kost niets en scheelt 95% van die vragen.
TEMPO_GELDIG_SECONDEN = 60
_tempo_cache: dict[str, tuple[float, dict]] = {}


def _gemeten_tempo(db, user_id: str) -> dict:
    """De echte tussentijd tussen twee schrijvende opdrachten, in seconden."""
    leeg = {"seconds_between": None, "seconds_per_job": None,
            "calm": False, "samples": 0}
    nu = time.monotonic()
    bewaard = _tempo_cache.get(user_id)
    if bewaard and nu - bewaard[0] < TEMPO_GELDIG_SECONDEN:
        return bewaard[1]
    try:
        grens = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        rijen = (db.table("jobs").select("action,claimed_at,done_at")
                 .eq("user_id", user_id).in_("action", list(SCHRIJVEND))
                 .gte("claimed_at", grens).not_.is_("done_at", "null")
                 .order("claimed_at", desc=True).limit(TEMPO_MONSTERS).execute().data or [])
    except Exception as e:  # noqa: BLE001 — een schatting mag nooit een scherm slopen
        logger.warning("tempo niet te meten voor %s: %s", user_id, e)
        return leeg
    rijen = [r for r in rijen if r.get("claimed_at") and r.get("done_at")]
    rijen.sort(key=lambda r: r["claimed_at"])
    gaten = []
    # HOE LANG DUURT ÉÉN OPDRACHT ÉCHT?
    #
    # Het gat tussen twee opdrachten (klaar → volgende opgepakt) zegt hoe snel
    # de extensie eráán begint. Het zegt niet hoe lang een wachtrij duurt: het
    # werk zelf zit er niet in. Gemeten bij Toon (dejuistetoon) op 05-09-2026,
    # 39 monsters uit twaalf uur: gat 16 s, werk 29 s, van start tot start 46 s.
    # Wie met het gat rekent belooft dus bijna drie keer te snel — precies de
    # soort belofte waar hij op 03-09 op afknapte.
    cycli = []
    for vorige, volgende in zip(rijen, rijen[1:]):
        klaar = _parse_ts(vorige["done_at"])
        begin = _parse_ts(vorige["claimed_at"])
        start = _parse_ts(volgende["claimed_at"])
        if not klaar or not start:
            continue
        gat = (start - klaar).total_seconds()
        if 0 <= gat <= TEMPO_ONDERBREKING:
            gaten.append(gat)
            if begin:
                cyclus = (start - begin).total_seconds()
                if cyclus > 0:
                    cycli.append(cyclus)
    if len(gaten) < 3:
        _tempo_cache[user_id] = (nu, leeg)
        return leeg               # te weinig om iets over te beweren
    gaten.sort()
    cycli.sort()
    midden = gaten[len(gaten) // 2]
    uitkomst = {"seconds_between": int(midden),
                "seconds_per_job": int(cycli[len(cycli) // 2]) if len(cycli) >= 3 else None,
                "calm": midden >= TEMPO_KALM_DREMPEL,
                "samples": len(gaten)}
    uitkomst.update(_stille_uren(db, user_id))
    _tempo_cache[user_id] = (nu, uitkomst)
    return uitkomst


def _stille_uren(db, user_id: str) -> dict:
    """Hoe lang stond er werk te wachten terwijl er niets liep?

    WAAROM (12-09-2026, De Juiste Toon). "Deze pc staat de hele dag aan en toch
    zie ik nog steeds 50 stuks staan." Gemeten op zijn eigen rij: tussen 07:51
    en 11:12 UTC werd er geen enkele opdracht opgepakt terwijl er honderd
    klaarstonden, en daarna nog eens 54 minuten niet. In diezelfde uren liepen
    er bij twee andere verkopers 46 en 24 opdrachten per uur door, dus de server
    deelde gewoon uit. Zijn Chromebook sliep: de opdracht van 07:51 meldde zich
    om 11:12 alsnog klaar, precies negen seconden na de eerstvolgende poll, en
    ook het dashboard zelf had al die tijd niet gepolld (anders had de
    opruimronde die vastzittende claim allang afgesloten).

    Het tempo hierboven gooit zulke gaten er bewust uit — anders zou één nacht
    de gemeten snelheid verzieken. Maar daarmee belooft de balk "deze 50 duren
    een uur" terwijl het bij hem een hele dag werd. Die belofte is precies
    waarom hij al vier keer meldde dat er "niets gebeurt". Dus meten we de stille
    uren er apart bij: hoeveel tijd ging er verloren terwijl er werk lag.

    Alleen een gat telt waarvan we ZEKER weten dat er werk stond te wachten: de
    opdracht die ná het gat werd opgepakt moet al vóór het gat hebben
    klaargestaan. Een rustige nacht met een lege rij telt dus niet mee.
    """
    leeg = {"idle_seconds": 0, "idle_gaps": 0, "idle_since": None,
            "done_last_hour": 0}
    nu_dt = datetime.now(timezone.utc)
    grens = nu_dt - timedelta(hours=STIL_VENSTER_UREN)
    try:
        rijen = (db.table("jobs").select("created_at,claimed_at,done_at,status")
                 .eq("user_id", user_id).in_("action", list(SCHRIJVEND))
                 .gte("created_at", grens.isoformat())
                 .order("created_at").limit(STIL_MONSTERS).execute().data or [])
    except Exception as e:  # noqa: BLE001 — een schatting mag nooit een scherm slopen
        logger.warning("stille uren niet te meten voor %s: %s", user_id, e)
        return leeg

    opgepakt = sorted(
        [(_parse_ts(r["claimed_at"]), _parse_ts(r["created_at"])) for r in rijen
         if r.get("claimed_at") and r.get("created_at")],
        key=lambda t: t[0],
    )
    stil, gaten, sinds = 0.0, 0, None
    for (vorige, _), (start, gemaakt) in zip(opgepakt, opgepakt[1:]):
        gat = (start - vorige).total_seconds()
        if gat > TEMPO_ONDERBREKING and gemaakt <= vorige:
            stil += gat
            gaten += 1
    # De staart: staat er nú werk te wachten dat al klaarstond toen de laatste
    # opdracht werd opgepakt, dan loopt het stille gat op dit moment nog door.
    if opgepakt:
        laatste = opgepakt[-1][0]
        loopt = (nu_dt - laatste).total_seconds()
        wacht_al = any(
            r["status"] == "pending" and _parse_ts(r["created_at"]) <= laatste
            for r in rijen
        )
        if loopt > TEMPO_ONDERBREKING and wacht_al:
            stil += loopt
            gaten += 1
            sinds = laatste.isoformat()

    uur_terug = nu_dt - timedelta(hours=1)
    klaar = sum(1 for r in rijen
                if r.get("done_at") and (_parse_ts(r["done_at"]) or grens) >= uur_terug)
    return {"idle_seconds": int(stil), "idle_gaps": gaten,
            "idle_since": sinds, "done_last_hour": klaar}


def _geeft_teken_van_leven(job: dict, now_dt: datetime) -> bool:
    """Loopt deze geclaimde opdracht NU echt, of hangt hij alleen nog?

    Een scan meldt elke paar seconden zijn vordering. Blijft dat teken uit, dan
    is de opdracht blijven hangen en mag hij niets meer tegenhouden — anders zou
    één vastgelopen scan het verversen dagenlang stil kunnen leggen.
    """
    res = job.get("result")
    stempels = [_parse_ts(job.get("claimed_at"))]
    if isinstance(res, dict):
        stempels.append(_parse_ts((res.get("_progress") or {}).get("at")))
    laatste = max([t for t in stempels if t], default=None)
    return bool(laatste and laatste >= now_dt - timedelta(minutes=STALE_CLAIM_MINUTES))


def _is_verversing(job: dict) -> bool:
    """Hoort deze opdracht bij het verversen/herplaatsen en niet bij een klik?

    Verversen is onderhoud dat best een half uur kan wachten. Een publicatie
    waar de verkoper zelf op drukte hoort nooit te wachten (zie
    docs/kennisbank.md, "eigen klik gaat voor de nachtronde").
    """
    if job.get("action") in ("content_refresh", "extend"):
        return True
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    if job.get("action") == "delete" and "_refresh_rollback" in payload:
        return True
    # De herplaatsing zelf: de enige create met een tijdstip in de toekomst.
    if job.get("action") == "create" and job.get("scheduled_for"):
        return True
    return False


@router.get("/pending")
def get_pending_jobs(request: Request, platform: str = None, user_id: str = Depends(require_active_subscription)):
    db = get_db()
    now_dt = datetime.now(timezone.utc)
    versie_van_de_kopie = None   # wat de pollende extensie zelf zegt te zijn
    # A poll WITH a platform is a real extension dispatch poll (the dashboard
    # polls without one, just to count) — treat it as the extension's heartbeat
    # so the "computer online" indicator works without any extension change.
    if platform is not None:
        _record_extension_heartbeat(db, user_id, request.headers.get("user-agent"),
                                    versie=request.headers.get("x-omnivaleur-ext"))
        # Een te oude kopie krijgt niets meer te doen.
        #
        # WAAROM (27-08-2026, Jaap): drie weken lang draaide bij hem 1.0.218
        # terwijl de Web Store al op 1.0.249 stond. Die kopie NAM het werk wel
        # aan — ze bleef staan op het "verkocht via Marktplaats?"-venster en
        # maakte daarna advertenties zonder foto's en zonder tekst. Werk dat
        # niet wordt opgepakt is zichtbaar; werk dat half wordt afgemaakt niet.
        #
        # De versie komt uit een kopstuk dat de extensie zelf meestuurt. Kopieen
        # van voor 1.0.250 sturen dat kopstuk niet; die worden hier dus niet
        # tegengehouden (we weten hun versie eenvoudigweg niet) — daarvoor staat
        # de blokkerende melding in het dashboard. Vanaf 1.0.250 sluit deze
        # controle het gat definitief.
        gemeld = _kopstuk_versie(request.headers.get("x-omnivaleur-ext"))
        versie_van_de_kopie = gemeld
        if gemeld is not None and gemeld < MINIMALE_SCANVERSIE:
            logger.warning(
                "Geen werk uitgedeeld: extensie %s bij gebruiker %s ligt onder %s",
                ".".join(map(str, gemeld)), user_id,
                ".".join(map(str, MINIMALE_SCANVERSIE)),
            )
            return []
        # EN EEN KOPIE DIE ZICHZELF NIET MEER BIJWERKT KRIJGT OOK NIETS.
        #
        # De harde ondergrens hierboven vangt alleen wat we ooit met de hand te
        # laag hebben gezet. Toon (07-09-2026) zat er ruim bóven — 1.0.260 — en
        # kreeg dus gewoon werk, terwijl elke reparatie van de tien dagen daarna
        # bij hem niet bestond: de drie rubrieken waar hij op vastliep waren
        # precies de drie die na 1.0.260 zijn toegevoegd. Zo'n kopie neemt werk
        # aan en levert het half af, en de verkoper ziet alleen dat het "weer"
        # niet werkt. Zie ACHTERSTAND_GRENS.
        stil = _kopie_staat_stil(gemeld)
        if stil:
            achter, gepubliceerd = stil
            logger.warning(
                "Geen werk uitgedeeld: extensie %s bij gebruiker %s loopt %s "
                "versies achter op %s en werkt zichzelf niet bij",
                ".".join(map(str, gemeld)), user_id, achter, gepubliceerd,
            )
            return []
    # First, rescue anything stuck 'claimed' from an interrupted run.
    _recover_stale_claims(db, user_id, platform, now_dt)

    now = now_dt.isoformat()
    if platform:
        # ALLEEN de lichte velden over de HELE wachtrij: daarmee bepalen we de
        # volgorde zonder ook maar één payload op te halen. Daarna lezen we
        # alleen de kop volledig in — evenveel dataverkeer als de oude
        # limit(20), maar dan wel de twintig die er echt toe doen.
        licht = (db.table("jobs")
                 .select("id,action,platform,item_id,created_at,scheduled_for")
                 .eq("user_id", user_id).eq("status", "pending").eq("platform", platform)
                 .order("created_at").limit(WACHTRIJ_MAX).execute().data or [])
        licht = _ruim_dubbele_scans_op(db, licht, now)
        kop = [j["id"] for j in _wachtrij_volgorde(licht, now_dt)[:WACHTRIJ_KOP]]
        rijen = []
        if kop:
            # Dezelfde afbakening als hierboven, plus de gekozen kop. Nooit een
            # rij inladen die niet van deze gebruiker, dit kanaal en deze
            # wachtrij is.
            rijen = (db.table("jobs").select("*")
                     .eq("user_id", user_id).eq("status", "pending").eq("platform", platform)
                     .in_("id", kop).execute().data or [])
            op_plek = {job_id: i for i, job_id in enumerate(kop)}
            rijen.sort(key=lambda j: op_plek.get(j["id"], len(kop)))
        result = SimpleNamespace(data=rijen)
    else:
        result = (db.table("jobs").select("*").eq("user_id", user_id)
                  .eq("status", "pending").order("created_at").limit(20).execute())

    # STRICT GLOBAL SERIALISATION (extension dispatch only).
    # Every job drives a REAL browser tab. The create path doesn't wait for one
    # publish to finish before the next is claimed, and the extension stores the
    # active job under a single per-platform key — so running two at once let a
    # second tab overwrite the first's data, publishing listings with each other's
    # photos, prices, titles and descriptions. To make that impossible we hand the
    # extension exactly ONE job at a time and refuse to dispatch anything while a
    # job is genuinely in flight (a fresh claim). The dashboard (which calls
    # /pending WITHOUT a platform, just to count the queue) is never throttled.
    #
    # NUANCE: alleen SCHRIJVENDE opdrachten blokkeren elkaar. Een scan ("reading
    # your listings") leest alleen en loopt door de hele garderobe — dat duurt
    # minuten. Zolang die als blokkade telde, kon je op publiceren drukken en
    # gebeurde er simpelweg niets: geen tabblad, geen melding, alleen een oranje
    # stip. Precies wat een gebruiker als "hij doet het niet" ervaart. Een scan
    # tegelijk met één publicatie kan geen kwaad: elk tabblad heeft zijn eigen
    # opdracht (jobtab_<tabId>), dus ze kunnen elkaars gegevens niet overschrijven.
    #
    # EEN UITZONDERING OP DIE NUANCE: VINTED + VERVERSEN. Vinted knijpt een
    # sessie af die te veel verzoeken achter elkaar doet ("you are rate
    # limited"). Een scan van een grote garderobe loopt daar minutenlang tegenaan
    # het plafond, en een verversing die daar dwars doorheen begint, krijgt de
    # dichte deur. Gemeten op 06-09-2026: scan van 365 advertenties bezig van
    # 06:50 tot na 07:14, verversing gestart om 07:11:39, tabblad weg, oude
    # advertentie bleef staan. Publiceren waar de verkoper zélf op drukte blijft
    # gewoon doorgaan (zie _is_verversing) — die mag nooit stilvallen omdat er
    # toevallig een leesronde loopt.
    is_extension_dispatch = platform is not None
    vinted_scan_bezig = False
    if is_extension_dispatch:
        for c in (
            db.table("jobs").select("claimed_at,action,platform,result")
            .eq("user_id", user_id).eq("status", "claimed").execute().data
        ):
            if c.get("action") not in SCHRIJVEND:
                # Een lopende scan houdt niemand tegen. Alleen onthouden we van
                # een Vinted-scan DAT hij loopt, voor de verversrem hieronder.
                if (c.get("action") == "scan" and c.get("platform") == "vinted"
                        and _geeft_teken_van_leven(c, now_dt)):
                    vinted_scan_bezig = True
                continue
            ct = _parse_ts(c.get("claimed_at"))
            if ct and ct >= now_dt - timedelta(minutes=STALE_CLAIM_MINUTES):
                return []  # er wordt nu echt gepubliceerd — nooit een 2e tabblad

    # ── OM DE BEURT TUSSEN DE KANALEN ─────────────────────────────────────────
    #
    # Lynn (De Juiste Toon), 05-09-2026: "Marktplaats ging vandaag helemaal
    # super. Naar tweedehands pakt ie nog niet." Gemeten: op 04-09 stond er om
    # 14:08:09 één 2dehands-publicatie klaar die nooit is opgepakt (ze heeft hem
    # om 18:23 zelf geannuleerd), terwijl er in diezelfde vier uur negen
    # Marktplaats-publicaties doorheen gingen. Op haar drukke dagen ging er van
    # de 75 en 98 publicaties telkens precies één naar 2dehands.
    #
    # De extensie vraagt de kanalen in een vaste volgorde, marktplaats altijd
    # eerst, terwijl de rem hierboven voor álle kanalen tegelijk geldt: er mag er
    # maar één tegelijk publiceren. Wie vooraan staat pakt dus elke vrijgekomen
    # plek, en met een volle Marktplaats-rij kwam 2dehands nooit aan bod.
    #
    # De extensie deelt de beurt sinds 1.0.306 zelf eerlijk rond, maar een
    # nieuwe versie is er pas na de Web Store en niet iedereen werkt bij. Daarom
    # ook hier: heeft dit kanaal zojuist nog gepubliceerd en staat er op een
    # ánder kanaal werk te wachten, dan geven we DAT werk terug. De extensie
    # kijkt niet naar het kanaal dat ze vroeg maar naar het kanaal in de opdracht
    # zelf (nagekeken tot en met de versies die nu bij klanten draaien), dus dit
    # werkt ook op een kopie van weken oud.
    #
    # Bewust teruggeven en niet "even niets": een opdracht die om welke reden dan
    # ook nooit kan lopen zou anders de hele wachtrij stil kunnen leggen. Wat we
    # teruggeven wordt geclaimd, en daarmee lost het zichzelf op — het lukt, of
    # het mislukt met een melding, en in beide gevallen is de rij weer vrij.
    if is_extension_dispatch and any(j.get("action") in SCHRIJVEND for j in result.data):
        try:
            laatste = (db.table("jobs").select("platform,claimed_at,action")
                       .eq("user_id", user_id).in_("action", list(SCHRIJVEND))
                       .not_.is_("claimed_at", "null")
                       .gte("claimed_at", (now_dt - timedelta(hours=2)).isoformat())
                       .order("claimed_at", desc=True).limit(1).execute().data or [])
            if laatste and laatste[0].get("platform") == platform:
                anderen = (db.table("jobs").select("*")
                           .eq("user_id", user_id).eq("status", "pending")
                           .in_("action", list(SCHRIJVEND))
                           .neq("platform", platform)
                           .or_(f"scheduled_for.is.null,scheduled_for.lte.{now}")
                           .order("created_at").limit(WACHTRIJ_KOP).execute().data or [])
                if anderen:
                    logger.info("Beurt doorgegeven aan %s: %s had de vorige "
                                "publicatie (gebruiker %s)",
                                anderen[0].get("platform"), platform, user_id)
                    result = SimpleNamespace(data=anderen)
        except Exception as e:  # noqa: BLE001
            # Kunnen we de beurt niet bepalen, dan delen we gewoon uit wat er voor
            # dit kanaal klaarstond. Een oneerlijke volgorde is vervelend; niets
            # uitdelen is erger.
            logger.warning("Beurtverdeling overgeslagen (%s)", e)

    # Jobs with a future scheduled_for (used to jitter relist recreates) aren't due yet.
    due = [j for j in result.data if not j.get("scheduled_for") or j["scheduled_for"] <= now]

    # A relist's "create" job (scheduled_for set) must never fire if the delete
    # job it's paired with actually failed — otherwise the old listing stays
    # live on the platform and this would create a duplicate. Hold/fail those
    # instead of handing them to the extension.
    # VERKOCHT IS VERKOCHT — HIER KOMT NIETS MEER DOORHEEN.
    #
    # Elke publicatie loopt langs dit punt: de gewone knop, de automatische
    # verversing, het herstel van vastgelopen werk en de herkansing. Eerder werd
    # er alleen bij het inplannen gekeken, en een opdracht kan uren in de wachtrij
    # staan — verkoopt het artikel in die tijd op een ander kanaal, dan zette de
    # extensie het daarna alsnog online. Ook een verkoop die pas ná het inplannen
    # werd opgemerkt kwam er zo doorheen. Daarom hier, vlak voor het uitdelen, en
    # niet bij het aanmaken.
    # Ook de TWEELING telt mee. Dezelfde trui staat vaak twee keer in de
    # voorraad (één keer per importbron, herkenbaar aan het nummer voor de
    # titel). Verkocht op Vinted op rij A betekende niets voor rij B, en die werd
    # daarna gewoon opnieuw op Marktplaats gezet. Zie backend/services/tweelingen.py.
    verkocht_op: dict[str, list[str]] = {}
    te_toetsen = [j["item_id"] for j in due
                  if j["action"] == "create" and j.get("item_id")]
    if te_toetsen:
        try:
            from backend.services.tweelingen import familie_ids
            familie_van: dict[str, list[str]] = {}
            alle_ids: list[str] = []
            for iid in dict.fromkeys(te_toetsen):
                rij = (db.table("items").select("id,user_id,title,sku,brand")
                       .eq("id", iid).limit(1).execute().data or [None])[0]
                fam = familie_ids(db, rij) if rij else [iid]
                familie_van[iid] = fam
                alle_ids += fam
            verkocht_per_item: dict[str, list[str]] = {}
            for rij in (db.table("listings").select("item_id,platform")
                        .in_("item_id", list(dict.fromkeys(alle_ids)))
                        .eq("status", "sold").execute().data or []):
                verkocht_per_item.setdefault(rij["item_id"], []).append(rij["platform"])
            for iid, fam in familie_van.items():
                kanalen = [p for f in fam for p in verkocht_per_item.get(f, [])]
                if kanalen:
                    verkocht_op[iid] = kanalen
        except Exception as e:  # noqa: BLE001
            # Kunnen we het niet nakijken, dan delen we geen publicatiewerk uit.
            # Een gemiste publicatie is een vertraging; een dubbelverkocht artikel
            # is een boze koper op twee kanalen.
            logger.warning("Verkoopcontrole voor publicatie mislukt (%s) — "
                           "publicaties deze ronde overgeslagen", e)
            due = [j for j in due if j["action"] != "create"]

    ready = []
    for j in due:
        # Een 'extend'-opdracht gaat alleen naar een kopie die hem kent (1.0.318+).
        # Een oudere kopie zou er een tweede advertentie van maken. De opdracht
        # blijft 'pending' tot een bijgewerkte kopie polt.
        if j.get("action") == "extend" and platform is not None:
            if versie_van_de_kopie is None or versie_van_de_kopie < MINIMALE_EXTEND_VERSIE:
                logger.info("Extend %s niet uitgedeeld: kopie %s kent 'extend' nog niet",
                            j["id"], versie_van_de_kopie)
                continue
        # Niet verversen op Vinted zolang de leesronde daar bezig is: samen zijn
        # het twee stromen verzoeken naar dezelfde Vinted-sessie, en dan knijpt
        # Vinted af. De opdracht blijft gewoon staan en komt bij de volgende
        # poll (15 seconden) opnieuw langs; zodra de scan klaar is, gaat hij door.
        if (vinted_scan_bezig and j.get("platform") == "vinted"
                and _is_verversing(j)):
            logger.info("Verversing %s (%s) wacht: er loopt een Vinted-scan "
                        "voor gebruiker %s", j["id"], j["action"], user_id)
            continue
        if j["action"] == "create" and verkocht_op.get(j.get("item_id")):
            kanalen = ", ".join(sorted(set(verkocht_op[j["item_id"]])))
            db.table("jobs").update({
                "status": "cancelled",
                "result": {"cancelled": f"Item already sold on {kanalen} — not published again."},
                "done_at": now,
            }).eq("id", j["id"]).execute()
            logger.info("Publicatie geannuleerd: item %s is al verkocht op %s",
                        j["item_id"], kanalen)
            continue
        if j["action"] == "create" and j.get("scheduled_for"):
            paired_delete = (
                db.table("jobs")
                .select("status,payload")
                .eq("user_id", user_id)
                .eq("item_id", j["item_id"])
                .eq("platform", j["platform"])
                .eq("action", "delete")
                .lte("created_at", j["created_at"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
                .data
            )
            # "cancelled" telt hier hetzelfde als "error". Een verwijdering die
            # is afgebroken gaat NOOIT meer lopen, dus een herplaatsing die op
            # hem wacht bleef eeuwig "pending" staan: het scherm bleef melden
            # "nieuwe advertentie over ~X min" terwijl er niets meer zou komen.
            # Zo stond bij Pleun Aertssen (30-08-2026) een herplaatsing van
            # 12:35 uur nog steeds te wachten op een verwijdering die al om
            # 12:48 was afgebroken.
            if paired_delete and paired_delete[0]["status"] in ("error", "cancelled"):
                mislukt = paired_delete[0]["status"] == "error"
                db.table("jobs").update({
                    "status": "error",
                    "result": {"error": "Skipped — the paired delist failed, so the old listing is still live; creating a new one would duplicate it."
                                        if mislukt else
                                        "Skipped — the paired delist was cancelled, so the old listing is still live and this recreate would duplicate it."},
                    "done_at": now,
                }).eq("id", j["id"]).execute()
                # De verwijdering ging niet door, dus de OUDE advertentie staat er
                # nog. Laat de regel op "active" staan — hij is nooit van het
                # platform verdwenen en mag dus niet uit het dashboard vallen.
                db.table("listings").update({
                    "status": "active",
                    "error_message": "Relist aborted: the old listing couldn't be removed, so it's still live and no duplicate was created. You can retry the relist.",
                }).eq("item_id", j["item_id"]).eq("platform", j["platform"]).execute()
                # EN de boekhouding terugdraaien. Zonder deze regel bleef de
                # verversing meetellen: teller opgehoogd, veertien dagen
                # afkoeling en een dagquotum opgesnoept — voor een verversing
                # die aantoonbaar nooit heeft plaatsgevonden. Het dashboard zei
                # dan "ververst" over een advertentie waar niets mee gebeurd is.
                rollback = ((paired_delete[0].get("payload") or {}).get("_refresh_rollback"))
                if rollback:
                    try:
                        from backend.services.relist import rollback_refresh
                        rollback_refresh(rollback, user_id)
                    except Exception as e:  # noqa: BLE001 — nooit de uitgifte blokkeren
                        logger.warning("Kon de verversing van item %s niet terugdraaien: %s",
                                       j["item_id"], e)
                continue
            # Delete not confirmed "done" yet (still pending/claimed, e.g. Chrome
            # was closed and just reopened) — hold the create job rather than
            # risk it firing before the old listing is actually gone. It stays
            # "pending" and will be re-checked on the next poll.
            if paired_delete and paired_delete[0]["status"] != "done":
                continue
        # Alleen bij een ECHTE poll van de extensie (die stuurt een platform mee).
        # Het dashboard telt hier alleen opdrachten; dan weten we niet welke kopie
        # er draait, en op dat niet-weten mag geen herplaatsing sneuvelen.
        if j["action"] == "delete" and platform is not None:
            reden = _herplaatsing_kansloos(db, user_id, j, versie_van_de_kopie)
            if reden:
                _neem_herplaatsing_terug(db, j, now, reden)
                continue
        ready.append(j)

    # A relist's "create" job can sit queued for 45min-4h (the jittered
    # recreate delay) before it's actually dispatched. Its payload price was
    # snapshotted when the job was queued, so if the user edits the item's
    # price in the frontend in the meantime, the stale snapshot would win and
    # the relist would silently keep republishing the old price. Re-read the
    # item's current price right before handing the job to the extension so
    # the recreate always reflects what the user set, not what was true when
    # the delay started.
    #
    # EN OM DEZELFDE REDEN DE STAAT VAN DE GOEDEREN, BIJ ÉLKE PUBLICATIE.
    #
    # WAAROM DIT ERBIJ MOEST (10-09-2026, Egbert Brouwer / Papa's Plectrums).
    # Hij zette 561 zoekertjes klaar voor 2dehands. In de wachtrij staat een
    # kopie van het artikel zoals het op het moment van klikken was, en dat is
    # bij een grote bulk urenlang geleden: zijn rij was na twee uur nog 402 lang.
    # Corrigeert hij in die tijd in het dashboard de staat — precies wat hij
    # moest doen, want alles stond op "Zo goed als nieuw" — dan verandert dat aan
    # de wachtende opdrachten niets en gaat elke volgende advertentie tóch met de
    # oude, onjuiste staat online. Voor de verkoper is dat niet te onderscheiden
    # van "hij luistert niet naar wat ik instel".
    #
    # Alleen de velden die de goederen beschrijven en die in het dashboard te
    # wijzigen zijn. Titel, tekst, prijs en categorie blijven met rust: die
    # kennen bewuste afwijkingen per opdracht (een prijs per kanaal, een
    # vertaalde tekst, een categorie die van de advertentiepagina zelf is
    # gelezen). Dezelfde vijf velden die de herplaatsroute al als waarheid van
    # het artikel behandelt.
    _UIT_HET_ARTIKEL = ("condition", "brand", "size", "color", "material")
    verse_items = {}
    te_verversen = sorted({j["item_id"] for j in ready
                           if j["action"] == "create" and j.get("item_id")})
    if te_verversen:
        try:
            for i in range(0, len(te_verversen), 200):
                for rij in (db.table("items")
                            .select("id," + ",".join(_UIT_HET_ARTIKEL))
                            .in_("id", te_verversen[i:i + 200]).execute().data or []):
                    verse_items[rij["id"]] = rij
        except Exception as e:  # noqa: BLE001
            # Lukt het niet, dan gaat de opdracht met zijn eigen kopie de deur
            # uit. Een verouderd kenmerk is vervelend; niets uitdelen is erger.
            logger.warning("Kenmerken niet ververst voor uitgifte (%s)", e)

    for j in ready:
        if j["action"] != "create" or not isinstance(j.get("payload"), dict):
            continue
        if j.get("scheduled_for"):
            current = db.table("items").select("price").eq("id", j["item_id"]).execute().data
            if current and current[0].get("price") not in (None, ""):
                j["payload"]["price"] = current[0]["price"]
        vers = verse_items.get(j.get("item_id")) or {}
        for veld in _UIT_HET_ARTIKEL:
            waarde = vers.get(veld)
            if isinstance(waarde, str):
                waarde = waarde.strip()
            # Een leeg veld in het artikel overschrijft nooit iets wat de
            # opdracht wél heeft: dat zou een advertentie juist armer maken.
            if waarde and str(j["payload"].get(veld) or "") != str(waarde):
                j["payload"][veld] = waarde

    # DE KLEUR GOEDZETTEN VLAK VOOR UITGIFTE.
    #
    # Marktplaats en 2dehands bieden alleen kale kleurnamen aan (Bruin, Rood,
    # Wit); verkopers schrijven "bruine", "rode", "crème". Zo'n woord past op
    # geen enkele optie, het verplichte veld blijft leeg, en dan doet de
    # plaatsknop stil niets. Bij Toon raakte dat 175 van zijn 1.024 artikelen.
    #
    # De extensie kan dit sinds 1.0.282 zelf, maar die bereikt hem pas nadat de
    # Chrome Web Store hem heeft goedgekeurd en Chrome hem heeft opgehaald —
    # dagen tot weken. Hier gezet werkt het bij de eerstvolgende opdracht, ook op
    # de kopie die hij vandaag draait. De extensie kiest daarna nog steeds uit
    # wat er in die categorie echt in de lijst staat; dit maakt alleen de kans
    # dat er iets past zo groot mogelijk.
    #
    # Alleen als we de kleur herkennen. Een woord dat we niet kennen blijft staan
    # zoals de verkoper het schreef — nooit een verzonnen kleur. Vinted heeft een
    # eigen kleurenlijst en blijft hier buiten.
    _zet_kleur_goed(ready)

    # Wie het eerst geholpen wordt: de gebruiker. Een scan die toevallig eerder in
    # de wachtrij kwam (bijvoorbeeld de uurlijkse controle) ging vóór een publicatie
    # waar iemand net op geklikt heeft — en dan lijkt de knop kapot. Publiceren en
    # verwijderen gaan nu altijd voor; scans vullen de rustige momenten op.
    if is_extension_dispatch:
        ready.sort(key=lambda j: 0 if j.get("action") in SCHRIJVEND else 1)

    # Extension: exactly one job at a time. Dashboard: the whole queue, to count.
    if not is_extension_dispatch:
        return ready
    # Pas hier, en niet een regel eerder: vertalen kost een gesprek met een
    # dienst buiten de deur. Het dashboard telt alleen en krijgt niets vertaald,
    # en van de wachtrij gaat er precies één opdracht doorheen — die ene die de
    # extensie nu ook echt gaat uitvoeren.
    #
    # Ligt de vertaling plat, dan blijft die ene opdracht staan en proberen we de
    # volgende. Anders zou één onvertaalbare advertentie vooraan de hele wachtrij
    # blokkeren: alles erachter (ook wat al in het Nederlands staat) zou stilvallen.
    for kandidaat in ready[:5]:
        uit = _zet_taal_goed(db, [kandidaat])
        if uit:
            # NA de vertaling, want die levert een nieuwe tekst op waar het
            # webadres gewoon weer in kan staan. Zie _haal_links_eruit.
            _haal_links_eruit(db, uit)
            return uit
    return []


# ── Welke extensieversie staat er in de Chrome Web Store? ────────────────────
#
# WAAROM DIT ER IS (01-09-2026, Egbert). Hij draaide 1.0.258 terwijl de Web Store
# op 1.0.279 stond, en het dashboard zei al die tijd groen "Extension active".
# De ondergrens hieronder (1.0.244) is een HARDE grens: alles daarboven gold als
# in orde, ook eenentwintig versies achter. Chrome werkt een extensie normaal
# vanzelf bij, maar alleen elke paar uur en alleen terwijl hij draait — en een
# met de hand geladen kopie nooit. Wie dus achterloopt, hoort dat te horen.
#
# De enige eerlijke bron voor "wat kan hij nu installeren" is de Web Store zelf.
# Dit is dezelfde vraag die Chrome stelt om te kijken of er een update is; het
# antwoord is een doorverwijzing waarin de versie in de bestandsnaam staat
# (..._1_0_279_0.crx). We halen de crx niet op — alleen de doorverwijzing.
_WEBSTORE_EXT_ID = "gfaogapbhaacfbpdppdcmnkjndlphleh"
_WEBSTORE_URL = (
    "https://clients2.google.com/service/update2/crx"
    "?response=redirect&acceptformat=crx3&prodversion=126.0"
    f"&x=id%3D{_WEBSTORE_EXT_ID}%26installsource%3Dondemand%26uc"
)
_CRX_VERSIE = re.compile(r"_(\d+)_(\d+)_(\d+)(?:_(\d+))?\.crx", re.I)
# Eén uur onthouden. Een nieuwe versie doorgeven mag best een uur duren; Google
# elke paar seconden bevragen mag niet. Een mislukking onthouden we tien minuten,
# zodat een storing bij Google geen bui van verzoeken oplevert.
_WEBSTORE_CACHE = {"versie": None, "ts": 0.0, "ok": False}
_WEBSTORE_TTL_OK = 3600
_WEBSTORE_TTL_FOUT = 600


def _gepubliceerde_extensieversie() -> str | None:
    """De versie die op dit moment in de Chrome Web Store staat, of None."""
    import time as _t
    nu = _t.monotonic()
    ttl = _WEBSTORE_TTL_OK if _WEBSTORE_CACHE["ok"] else _WEBSTORE_TTL_FOUT
    if _WEBSTORE_CACHE["ts"] and (nu - _WEBSTORE_CACHE["ts"]) < ttl:
        return _WEBSTORE_CACHE["versie"]
    versie = None
    try:
        import httpx
        # follow_redirects=False: we willen juist de doorverwijzing, niet het
        # bestand. Zo halen we nooit een crx binnen — alleen een kopregel.
        r = httpx.get(_WEBSTORE_URL, follow_redirects=False, timeout=8.0)
        m = _CRX_VERSIE.search(r.headers.get("location") or "")
        if m:
            versie = f"{int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}"
    except Exception as e:  # noqa: BLE001
        logger.info("versie uit de Web Store ophalen mislukt: %s", e)
    _WEBSTORE_CACHE.update(
        versie=versie or _WEBSTORE_CACHE["versie"], ts=nu, ok=bool(versie)
    )
    return _WEBSTORE_CACHE["versie"]


@router.get("/extension-version")
def extension_version(user_id: str = Depends(get_current_user)):
    """Welke extensieversie hoort erop te staan.

    `minimum` is de harde grens: daaronder blokkeert het dashboard, want dan
    kán het werk niet slagen. `published` is wat er nu in de Chrome Web Store
    staat; daartussenin krijgt de verkoper een gewone bijwerkmelding die hij weg
    kan klikken. Komt `published` niet binnen, dan is hij leeg en verandert er
    niets aan wat het scherm laat zien.
    """
    return {
        "published": _gepubliceerde_extensieversie(),
        "minimum": ".".join(str(x) for x in MINIMALE_SCANVERSIE),
        # Vanaf hoeveel versies achterstand het dashboard niet meer "er is een
        # update" zegt maar "deze kopie werkt zichzelf niet bij". Meegegeven en
        # niet in het scherm hard gezet, zodat er één grens is die klopt met wat
        # de server doet: daarboven deelt hij geen werk meer uit.
        "blokkeer_achterstand": ACHTERSTAND_GRENS,
    }


@router.get("/extension-status")
def extension_status(user_id: str = Depends(get_current_user)):
    """
    Is a computer with the extension online for this user? Powers the dashboard
    indicator so someone working from their phone knows whether their queued
    publishes/relists will run now or just wait. Reads the heartbeat stamped by
    the extension's own /pending polls.

    Returns online=None ("unknown") when the heartbeat table doesn't exist yet,
    so the frontend can simply hide the indicator instead of showing a wrong
    "offline". online=False means we've never seen it, or not recently.
    """
    db = get_db()
    # Eén vraag voor allebei. Dit scherm klopt elke 20 seconden aan bij iedereen
    # die de app open heeft, en de server draait op één werker met een
    # blokkerende databaseclient: een tweede vraag hier is een tweede wachtrij
    # voor de hele site.
    try:
        row = (
            db.table("extension_heartbeat")
            .select("last_seen,ext_version")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )
    except Exception:
        # De waarschuwing over een verouderde kopie hoort óók zichtbaar te zijn
        # als de hartslagtabel nog niet bestaat — dat is precies een account
        # waar dit soort dingen ongemerkt misgaat.
        return {"online": None, **_verouderde_extensie(db, user_id)}
    oud = _verouderde_extensie(
        db, user_id, hartslag_versie=(row or [{}])[0].get("ext_version"))

    if not row or not row[0].get("last_seen"):
        return {"online": False, "last_seen": None, "seconds_ago": None, **oud}

    last_seen = _parse_ts(row[0]["last_seen"])
    if not last_seen:
        return {"online": False, "last_seen": None, "seconds_ago": None, **oud}

    seconds_ago = int((datetime.now(timezone.utc) - last_seen).total_seconds())
    return {
        "online": seconds_ago <= EXTENSION_ONLINE_WINDOW_SECONDS,
        "last_seen": last_seen.isoformat(),
        "seconds_ago": max(0, seconds_ago),
        **oud,
    }


_ZELF_LEZEN = object()


def _verouderde_extensie(db, user_id: str, hartslag_versie=_ZELF_LEZEN) -> dict:
    """Draait er ergens nog een oude kopie van de extensie mee?

    Een tweede, met de hand geladen kopie beweegt niet mee met de Chrome Web
    Store en blijft dus voor altijd op de versie van de dag dat hij is
    neergezet. Hij haalt wél opdrachten uit dezelfde wachtrij, en bij een grote
    winkel kan hij die niet aan. Dat is van buitenaf niet te zien — het lijkt op
    "de app doet het soms wel en soms niet" (Egbert Brouwer, twee weken lang).

    De extensie stempelt haar versie in elke foutmelding, dus we kunnen dit
    aflezen uit werk dat al gedaan is. Geen extra tabel, geen migratie.

    EN OOK ALS DIE KOPIE ZICH NIET MEER MELDT (09-09-2026, De Juiste Toon).
    Hierboven stond alleen de harde ondergrens (1.0.244). Toons kopie zat daar
    ruim boven — 1.0.260 — dus zei het dashboard hier niets, terwijl de uitgifte
    diezelfde kopie al twee dagen géén werk meer gaf omdat ze 53 versies achter
    de Web Store liep. Zijn wachtrij liep vol en het enige wat hij las was "je
    extensie heeft zich niet gemeld, zet Chrome aan, dan pakt hij het vanzelf
    op". Chrome aanzetten hielp niet en kon niet helpen: een met de hand
    geladen kopie werkt zichzelf nooit bij.

    Daarom kijken we eerst naar de versie uit de aanwezigheidsstempel. Die staat
    er ook nog als de kopie al uren stil is, dus dit werkt juist wél op het
    moment dat de verkoper zit te wachten.
    """
    draait = (_draaiende_extensieversie(db, user_id)
              if hartslag_versie is _ZELF_LEZEN
              else _kopstuk_versie(hartslag_versie))
    stilstaand = _kopie_staat_stil(draait)
    if stilstaand:
        achter, gepubliceerd = stilstaand
        return {
            "outdated_extension": ".".join(map(str, draait)),
            "published_extension": gepubliceerd,
            "outdated_versies_achter": achter,
            # Deze kopie krijgt van de uitgifte niets meer te doen. Het scherm
            # mag dus niet zeggen dat de wachtrij vanzelf op gang komt.
            "outdated_krijgt_geen_werk": True,
        }
    try:
        grens = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        rijen = (db.table("jobs").select("result")
                 .eq("user_id", user_id).eq("status", "error")
                 .gte("created_at", grens)
                 .order("created_at", desc=True).limit(40).execute().data or [])
    except Exception:  # noqa: BLE001 — een waarschuwing mag nooit de indicator slopen
        return {}
    oudste = None
    for r in rijen:
        res = r.get("result")
        v = _extensie_versie((res or {}).get("error") if isinstance(res, dict) else res)
        if v and v < MINIMALE_SCANVERSIE and (oudste is None or v < oudste):
            oudste = v
    if not oudste:
        return {}
    return {
        "outdated_extension": ".".join(map(str, oudste)),
        "published_extension": _gepubliceerde_extensieversie(),
        # Onder de harde ondergrens deelt de uitgifte ook niets meer uit.
        "outdated_krijgt_geen_werk": True,
    }


@router.get("/relist-status")
def relist_status(user_id: str = Depends(get_current_user)):
    """
    In-progress relists for the dashboard's Refresh view: any scheduled recreate
    ("create" job with a future/pending scheduled_for) plus the state of its
    paired delete, so the UI can show "old listing removed, new one in ~X min".
    """
    db = get_db()
    # Include recently-DONE recreates too, not just in-flight ones: when the
    # extension finishes, the create job flips to "done" and would instantly drop
    # out of this list — so the dashboard card vanished mid-"Publishing now" with
    # no "it's live" confirmation, which read as "nothing happened / stuck". We
    # keep a completed recreate around for a short window so the UI can show an
    # explicit "✓ New listing is live" before clearing it.
    JUST_DONE_WINDOW = timedelta(seconds=90)
    now_dt = datetime.now(timezone.utc)
    create_jobs = (
        db.table("jobs")
        .select("item_id,platform,status,scheduled_for,created_at,done_at,result")
        .eq("user_id", user_id)
        .eq("action", "create")
        .in_("status", ["pending", "claimed", "done"])
        # Alleen herplaatsingen dragen een scheduled_for, en hieronder wordt al
        # het andere meteen weggegooid. Toch werd het eerst allemáál opgehaald —
        # elke 15 seconden opnieuw, en die stapel groeit met elke publicatie mee.
        # Filteren doet de database gratis; ophalen kost dataverkeer (01-09-2026).
        .not_.is_("scheduled_for", "null")
        .execute()
        .data
    )
    out = []
    for j in create_jobs:
        if not j.get("scheduled_for"):
            continue  # only relist recreates carry a scheduled_for
        if j["status"] == "done":
            done_at = _parse_ts(j.get("done_at"))
            if not done_at or (now_dt - done_at) > JUST_DONE_WINDOW:
                continue  # long-finished — no longer "in progress"
        paired = (
            db.table("jobs")
            .select("status,result")
            .eq("user_id", user_id)
            .eq("item_id", j["item_id"])
            .eq("platform", j["platform"])
            .eq("action", "delete")
            .lte("created_at", j["created_at"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        entry = {
            "item_id": j["item_id"],
            "platform": j["platform"],
            "recreate_at": j["scheduled_for"],
            "recreate_status": j["status"],
            "delete_status": paired[0]["status"] if paired else None,
            # Surface WHY the delist failed: without this the dashboard could
            # only say "Failed", which hid a real bug for weeks.
            "delete_error": (
                ((paired[0].get("result") or {}).get("error") or None)
                if paired and paired[0]["status"] == "error" else None
            ),
        }
        # Hand the new listing's URL to the UI so the "live" confirmation can link
        # straight to it.
        if j["status"] == "done":
            entry["recreate_url"] = (j.get("result") or {}).get("platform_listing_url")
        out.append(entry)
    return out


@router.get("/active")
def active_jobs(user_id: str = Depends(get_current_user)):
    """
    Everything the extension is either actively running or about to run, so the
    dashboard can warn the user to stay hands-off while it works.

    Two buckets:
      - "working": jobs the extension claimed RECENTLY — a Chrome tab is genuinely
        open and it's deleting/creating/scanning right now. Critically, we only
        count a claim as "working" if it happened within the last few minutes: a
        publish/delete finishes in seconds, so a job still "claimed" long after
        that isn't being worked — it's stuck (Chrome was closed mid-run, the tab
        failed, etc.). Without this window those abandoned claims made the
        "extension is working — don't touch" banner show forever even though
        nothing was happening.
      - "queued": pending jobs that are due now (no future scheduled_for). These
        will be picked up within one poll (~15s). Relist recreates sitting on a
        future timer are deliberately excluded — nothing is happening yet, so
        they shouldn't trip the "busy, don't touch" warning.
    """
    db = get_db()
    rows = (
        db.table("jobs")
        .select("id,action,platform,item_id,status,scheduled_for,claimed_at,result")
        .eq("user_id", user_id)
        .in_("status", ["pending", "claimed"])
        .order("created_at")
        .limit(50)
        .execute()
        .data
    )
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    # A genuinely active claim is very recent. Beyond this the run is stuck/abandoned.
    active_cutoff = now_dt - timedelta(minutes=3)

    def _fresh(ts) -> bool:
        if not ts:
            return False
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= active_cutoff

    def _is_working(j) -> bool:
        # Fresh claim = a publish/delete tab is open right now.
        if _fresh(j.get("claimed_at")):
            return True
        # Long-running jobs (mainly Vinted scans) can legitimately run past the
        # claim window, but they post live progress — treat a recent progress
        # ping as "still working" so the tab stays flagged, while a claim with no
        # recent activity at all is correctly treated as stuck and dropped.
        prog = (j.get("result") or {}).get("_progress")
        if isinstance(prog, dict) and _fresh(prog.get("at")):
            return True
        return False

    # Settle anything stuck 'claimed' with no activity. The stale sweep used to run
    # ONLY from /pending, i.e. only while the extension was still polling — but the
    # cases that strand a job (content script hung on a Vinted colour panel, MV3
    # service worker killed so armJobWatchdog's setTimeout never fires, Chrome
    # closed) are exactly the cases where that poll may never come. The dashboard
    # polls THIS endpoint every 4s, so sweeping here makes a stuck job go terminal
    # on its own, with no user action. Anti-duplicate protection is unchanged: the
    # sweep marks a create 'error' and never re-dispatches it.
    if any(j["status"] == "claimed" and not _is_working(j) for j in rows):
        try:
            _recover_stale_claims(db, user_id, None, now_dt)
        except Exception as e:  # never let the banner endpoint fail on a sweep
            logger.warning(f"active_jobs: stale-claim sweep failed: {e}")

    working, queued = [], []
    for j in rows:
        if j["status"] == "claimed":
            if _is_working(j):
                # Don't leak the raw progress/result blob to the client.
                j.pop("result", None)
                working.append(j)
        elif not j.get("scheduled_for") or j["scheduled_for"] <= now:
            j.pop("result", None)
            queued.append(j)
    # Het gemeten tempo mee terug: het dashboard beloofde "within ~15 seconds"
    # terwijl Calm mode er 3 tot 8 minuten van maakt. Zie _gemeten_tempo.
    return {"working": working, "queued": queued, "pace": _gemeten_tempo(db, user_id)}


@router.post("/reschedule-now")
def reschedule_now(body: dict, user_id: str = Depends(require_active_subscription)):
    """
    Bring a scheduled relist recreate forward so it fires on the next poll —
    clears the jittered delay for a specific item's still-pending "create" job.
    Only touches the caller's own pending job. Body: {item_id, platform}.
    """
    db = get_db()
    item_id = body.get("item_id")
    platform = body.get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform are required")
    rows = (
        db.table("jobs")
        .select("id")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .eq("platform", platform)
        .eq("action", "create")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No pending recreate job found for this item")
    now = datetime.now(timezone.utc).isoformat()
    db.table("jobs").update({"scheduled_for": now}).eq("id", rows[0]["id"]).execute()
    return {"ok": True, "job_id": rows[0]["id"], "scheduled_for": now}


@router.post("/relist-retry")
async def relist_retry(body: dict, user_id: str = Depends(require_active_subscription)):
    """
    Retry a relist that failed at the delist step. The old listing is still live
    on the platform (a failed delist removes nothing), so retrying is safe and is
    exactly what the user wants after "Relist failed".

    Ordering matters for correctness: we FIRST cancel any leftover delete/create
    jobs from the failed attempt (a still-pending recreate would otherwise fire
    later and duplicate the listing), reset the listing to a clean "active"
    state, and only THEN queue a brand-new relist via refresh_listing().
    """
    item_id = body.get("item_id")
    platform = body.get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform are required")

    db = get_db()

    # EERST DE BOEKHOUDING VAN DE MISLUKTE POGING TERUGDRAAIEN.
    #
    # WAAROM (30-08-2026, Pleun Aertssen). Een verversing hoogt de teller op,
    # zet de afkoelperiode van veertien dagen en snoept een dagquotum op zodra
    # hij in de wachtrij staat — vóórdat er iets gebeurd is. Mislukt de
    # verwijdering, dan geeft `fail_job` dat allemaal terug. Maar bij een
    # herkansing gebeurde dat niet, en dan botste de herkansing op de
    # afkoelperiode die zijn eigen mislukte poging net had gezet:
    #
    #     "This listing was refreshed 0d ago. Wait 14d more."
    #
    # De opdrachten waren op dat moment al geannuleerd en de foutmelding was al
    # gewist. Wat overbleef was een advertentie die volgens het dashboard net
    # ververst was — teller op 1, geen foutmelding — terwijl er niets was
    # gebeurd en er ook niets meer stond te gebeuren. Precies het beeld
    # "foutmelding op het scherm, maar gemeld als gelukt".
    laatste_delete = (
        (await naast_de_lus(lambda: db.table("jobs")
        .select("status,payload")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .eq("platform", platform)
        .eq("action", "delete")
        .order("created_at", desc=True)
        .limit(1)
        .execute()))
        .data
        or []
    )
    vorige = laatste_delete[0] if laatste_delete else {}
    # Alleen terugdraaien als die verwijdering NIET is gelukt. Was hij wél
    # gelukt, dan is de advertentie echt van het platform gehaald en is de
    # verversing echt gebeurd — die mag je niet terugdraaien.
    rollback = ((vorige.get("payload") or {}).get("_refresh_rollback")
                if vorige.get("status") != "done" else None)
    if rollback:
        from backend.services.relist import rollback_refresh
        await naast_de_lus(lambda: rollback_refresh(rollback, user_id))

    # Cancel any outstanding jobs from the failed relist so nothing fires twice.
    # Only pending/claimed/error jobs — never a job that already completed ("done").
    stale = (
        (await naast_de_lus(lambda: db.table("jobs")
        .select("id,status,result")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .eq("platform", platform)
        .in_("action", ["delete", "create"])
        .in_("status", ["pending", "claimed", "error"])
        .execute()))
        .data
        or []
    )
    # MET REDEN, EN ZONDER DE OUDE FOUTMELDING TE WISSEN (08-09-2026).
    #
    # Hier stond een kale statuswijziging. Twee gevolgen, allebei gemeten: in het
    # logboek stonden 77 afgebroken opdrachten met een leeg vakje "reden" — de
    # verkoper zag "Cancelled" en niets erbij. En erger: een opdracht die op
    # 'error' stond werd óók meegenomen, dus zodra iemand op "Retry" drukte was
    # de uitleg waaróm het de vorige keer misging voorgoed weg. Precies de
    # informatie die je nodig hebt als het een tweede keer misgaat.
    for j in stale:
        was_fout = j.get("status") == "error"
        oude_reden = (j.get("result") or {}).get("error") if isinstance(j.get("result"), dict) else None
        (await naast_de_lus(lambda j=j, was_fout=was_fout, oude_reden=oude_reden: db.table("jobs").update({
            "status": "cancelled",
            "done_at": datetime.now(timezone.utc).isoformat(),
            "result": {
                "cancelled": "Replaced by a new attempt you started from the dashboard.",
                **({"eerdere_fout": oude_reden} if was_fout and oude_reden else {}),
            },
        }).eq("id", j["id"]).execute()))

    # De advertentie staat nog gewoon live (een mislukte verwijdering haalt niets
    # weg), dus "active" is zijn echte staat. De FOUTMELDING BLIJFT STAAN tot de
    # nieuwe poging echt in de wachtrij staat: hem alvast wissen betekende dat
    # een geweigerde herkansing een schoon scherm achterliet waarop niets meer
    # te zien was van wat er misging.
    (await naast_de_lus(lambda: db.table("listings").update({
        "status": "active",
    }).eq("item_id", item_id).eq("platform", platform).execute()))

    from backend.services.relist import refresh_listing, RefreshError
    from backend.services.crosslist import VertalingOnbeschikbaar
    try:
        result = await refresh_listing(item_id, platform, user_id, "relist")
    except RefreshError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except VertalingOnbeschikbaar as e:
        # 500, geen 503 — Cloudflare vervangt een 503 door zijn eigen
        # storingspagina en dan leest de verkoper "de server was druk" in plaats
        # van de echte reden. Zie crosslist_item in backend/api/items.py.
        from backend.services.crosslist import NIETS_GEPLAATST_VERTALING
        logger.warning("Vertaalstoring hield herplaatsing van %s tegen: %s", item_id, e)
        raise HTTPException(status_code=500, detail=NIETS_GEPLAATST_VERTALING)

    # Pas nu weg met de oude foutmelding: er staat een nieuwe poging klaar.
    (await naast_de_lus(lambda: db.table("listings").update({
        "error_message": None,
    }).eq("item_id", item_id).eq("platform", platform).execute()))
    return {"ok": True, **result}


@router.post("/relist-cancel")
def relist_cancel(body: dict, user_id: str = Depends(get_current_user)):
    """
    Cancel a relist that's still mid-flight and put the listing back where it was.

    A relist is only safely reversible WHILE THE OLD LISTING IS STILL LIVE — i.e.
    the paired "delete" job hasn't completed yet. In that window we cancel both the
    (pending) delete and the (scheduled) recreate, roll back the cooldown/quota the
    refresh optimistically spent, and flip the listing straight back to "active".
    Nothing was ever removed from the platform, so this is a true no-op undo.

    Once the delete HAS completed, the old listing is already gone from the
    platform and there's nothing to restore — cancelling here would strand the
    item off-platform forever (exactly the "my listing vanished" bug). So we
    refuse and tell the UI to offer "Publish now" (reschedule-now) instead, which
    brings the item back live immediately.
    """
    item_id = body.get("item_id")
    platform = body.get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform are required")

    db = get_db()

    # Most recent delete for this relist — its status tells us whether the old
    # listing is still live (safe to undo) or already gone (can't undo).
    del_rows = (
        db.table("jobs")
        .select("id,status,payload")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .eq("platform", platform)
        .eq("action", "delete")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    delete_job = del_rows[0] if del_rows else None

    if delete_job and delete_job["status"] == "done":
        # Old listing already removed — a cancel can't bring it back. Steer the
        # user to publish the new listing now instead of stranding the item.
        raise HTTPException(
            status_code=409,
            detail="The old listing has already been removed, so this relist can't "
                   "be cancelled without leaving your item offline. Use \"Publish now\" "
                   "to bring it back live immediately.",
        )

    # Old listing is still live (delete pending/claimed/errored, or never ran).
    # Cancel every outstanding job from this relist so nothing fires later.
    outstanding = (
        db.table("jobs")
        .select("id,status,result")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .eq("platform", platform)
        .in_("action", ["delete", "create"])
        .in_("status", ["pending", "claimed", "error"])
        .execute()
        .data
        or []
    )
    # Zelfde reden als bij relist_retry hierboven: een afgebroken opdracht zonder
    # uitleg is in het logboek niet te onderscheiden van een storing, en een
    # eerdere foutmelding mag niet verdwijnen omdat iemand op Cancel drukt.
    for j in outstanding:
        was_fout = j.get("status") == "error"
        oude_reden = (j.get("result") or {}).get("error") if isinstance(j.get("result"), dict) else None
        db.table("jobs").update({
            "status": "cancelled",
            "done_at": datetime.now(timezone.utc).isoformat(),
            "result": {
                "cancelled": "Cancelled by you from the dashboard.",
                **({"eerdere_fout": oude_reden} if was_fout and oude_reden else {}),
            },
        }).eq("id", j["id"]).execute()

    # Give back the cooldown + daily-quota slot the refresh spent up front, so a
    # cancelled relist doesn't count against the user (same rollback the failed-job
    # path uses).
    rollback = ((delete_job or {}).get("payload") or {}).get("_refresh_rollback")
    if rollback:
        from backend.services.relist import rollback_refresh
        rollback_refresh(rollback, user_id)

    # The listing was flipped to "relisting" at enqueue time; nothing was ever
    # removed, so "active" is its true state again. Clear any stale error banner.
    db.table("listings").update({
        "status": "active",
        "error_message": None,
    }).eq("item_id", item_id).eq("platform", platform).execute()

    return {"ok": True, "cancelled": len(outstanding), "status": "active"}


@router.post("/{job_id}/claim")
def claim_job(job_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    _record_extension_heartbeat(db, user_id)  # only the extension claims jobs
    result = db.table("jobs").update({
        "status": "claimed",
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).eq("user_id", user_id).eq("status", "pending").execute()
    if not result.data:
        raise HTTPException(status_code=409, detail="Job already claimed or not found")
    return result.data[0]


@router.post("/{job_id}/progress")
def report_job_progress(job_id: str, body: dict, user_id: str = Depends(get_current_user)):
    """
    Lightweight live-progress channel for long-running jobs (mainly scans). The
    extension posts a small {stage, message, current, total} object at each phase;
    the dashboard polls /status/{job_id} and renders it so the user can see exactly
    what's happening and how far along it is. Stored in `result` under `_progress`
    (the final /complete overwrites `result`, so this never lingers).
    """
    db = get_db()
    _record_extension_heartbeat(db, user_id)  # progress pings only come from the extension
    db.table("jobs").update({
        "result": {"_progress": {**body, "at": datetime.now(timezone.utc).isoformat()}},
    }).eq("id", job_id).eq("user_id", user_id).execute()
    return {"ok": True}


async def _rond_publicatie_af(db, job: dict, body: dict) -> None:
    """Schrijf het resultaat van een geslaagde publicatie naar `listings`.

    WELKE RIJ HOORT BIJ DEZE PUBLICATIE (31-08-2026).

    Hier stond `.eq(item_id).eq(platform)` en dan meteen een update. Dat was
    goed zolang één artikel hoogstens één advertentie per kanaal had — wat de
    unieke index `listings_item_platform_unique` afdwong. Sinds dubbele rijen
    samengevoegd kunnen worden (zie scripts/fix_listings_unique.sql) klopt die
    aanname niet meer: één artikel draagt nu de acht Marktplaats-advertenties
    van zijn acht voormalige kopieën.

    De oude regel werkte ze dan ALLEMAAL bij met hetzelfde advertentienummer.
    De database weigert dat sinds de indexwijziging (foutcode A1C211), maar het
    was daarvóór net zo fout en alleen onzichtbaar: acht verschillende
    advertenties kregen stilletjes hetzelfde nummer, en daarmee raakten we het
    spoor van zeven ervan kwijt.

    De juiste rij, in deze volgorde:
      1. staat dit advertentienummer er al? Dan is dit een herhaalde of late
         afronding van dezelfde publicatie — die rij bijwerken.
      2. anders de rij die nog op een nummer wacht: door deze opdracht
         aangemaakt en nog niet afgerond.
      3. anders is dit een echt nieuwe advertentie en komt er een rij bij.
    """
    if body.get("platform_listing_id"):
        rijen = (await naast_de_lus(lambda: db.table("listings")
                                    .select("id,platform_listing_id,status")
                                    .eq("item_id", job["item_id"])
                                    .eq("platform", job["platform"]).execute())).data or []
        doel = next((r for r in rijen
                     if r.get("platform_listing_id") == body["platform_listing_id"]), None)
        if doel is None:
            doel = next((r for r in rijen if not r.get("platform_listing_id")), None)
        if doel is None:
            # DIT IS EEN HERPLAATSING: DE OUDE RIJ IS DE JUISTE (05-09-2026, Amanda).
            #
            # Bij herplaatsen blijft het oude advertentienummer op de rij staan
            # terwijl de status op 'relisting' gaat. Geen van de twee regels
            # hierboven vindt die rij, dus kwam er een tweede rij naast — en de
            # oude bleef op 'relisting' hangen. De reddingsronde leest zo'n rij
            # als "halverwege blijven steken" en zet er elke zes uur opnieuw een
            # plaatsing voor klaar. Gemeten bij Amanda Haas: één hamsterknuffel
            # stond met drie identieke advertenties tegelijk op Marktplaats.
            #
            # refresh_listing schrijft daarom nu in de opdracht welke rij deze
            # plaatsing vervangt.
            #
            # WAAROM 'delisted' HIER OOK MEETELT (05-09-2026, gemeten op Daniels
            # eigen account, artikel (1275)). De rij gaat bij het inplannen op
            # 'relisting', maar zodra de extensie de oude advertentie heeft
            # weggehaald zet _verwijderdoelen diezelfde rij op 'delisted'. Tegen
            # de tijd dat de plaatsing binnenkomt staat er dus nooit meer
            # 'relisting' — precies het geval waarin het mis ging. Alleen als de
            # verwijdering mislukte bleef de rij op 'relisting' staan, en dat is
            # het enige geval dat de vorige versie afving. 'active' blijft
            # buiten schot: die rij hoort bij een advertentie die gewoon online
            # staat, en die mogen we nooit overschrijven.
            VERVANGBAAR = ("relisting", "delisted")
            vervangt = ((job.get("payload") or {}).get("_vervangt_listing_id"))
            if not vervangt:
                # Opdrachten van vóór het merkteken (en alles wat al in de
                # wachtrij stond) hebben het niet. De bijbehorende verwijdering
                # weet het wél: die draagt het rij-id in _refresh_rollback.
                vervangt = await _rij_van_de_gepaarde_verwijdering(db, job)
            if vervangt:
                doel = next((r for r in rijen
                             if r["id"] == vervangt
                             and r.get("status") in VERVANGBAAR), None)
            if doel is None:
                # Oudere opdrachten (nog zonder merkteken) en de reddingsronde:
                # is er precies één rij die op zijn herplaatsing wacht, dan is
                # dat hem. Bij twijfel (meer dan één) geen gok, dan komt er een
                # rij bij zoals voorheen.
                wachtend = [r for r in rijen if r.get("status") == "relisting"]
                if len(wachtend) == 1:
                    doel = wachtend[0]
        if doel is not None:
            (await naast_de_lus(lambda: db.table("listings").update({
                "platform_listing_id": body["platform_listing_id"],
                "platform_listing_url": body.get("platform_listing_url"),
                "status": "active",
                # This completion may arrive AFTER the job was marked failed
                # (the user fixed the form by hand and published themselves —
                # the extension's auto-detect then completes it late). Clear the
                # stale error, otherwise the listing shows as live and broken at
                # the same time.
                "error_message": None,
                "listed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", doel["id"]).execute()))
        else:
            (await naast_de_lus(lambda: db.table("listings").insert({
                "item_id": job["item_id"],
                "platform": job["platform"],
                "platform_listing_id": body["platform_listing_id"],
                "platform_listing_url": body.get("platform_listing_url"),
                "status": "active",
                "listed_at": datetime.now(timezone.utc).isoformat(),
            }).execute()))
        return

    # Zonder advertentienummer: alleen de rij die op deze publicatie wachtte.
    # Alle rijen van dit kanaal op 'error' zetten zou zeven lopende advertenties
    # als kapot markeren omdat de achtste faalde.
    wachtend = (await naast_de_lus(lambda: db.table("listings")
                                   .select("id").eq("item_id", job["item_id"])
                                   .eq("platform", job["platform"])
                                   .is_("platform_listing_id", "null")
                                   .execute())).data or []
    if wachtend:
        (await naast_de_lus(lambda: db.table("listings").update({
            "status": "error",
            "error_message": "Extension completed job but returned no platform_listing_id",
        }).eq("id", wachtend[0]["id"]).execute()))


# Statussen die een verwijderopdracht nooit mag overschrijven. Een bevestigde
# verkoop en een al gestelde verkoopvraag zijn eindpunten, en een allang
# afgemelde advertentie hoort niet terug te komen omdat een ÁNDERE advertentie
# van hetzelfde artikel niet verwijderd kon worden.
EINDSTATUSSEN = ("sold", "sold_unconfirmed", "delisted", "archived")

# Hoe lang een gratis Marktplaats-advertentie blijft staan voor het platform hem
# zelf weggooit. Is een verdwenen advertentie jónger dan dit, dan kan hij niet
# vanzelf verlopen zijn en heeft iemand hem weggehaald — meestal de verkoper,
# omdat het artikel verkocht is.
ZELF_VERLOPEN_NA_DAGEN = 28


async def _rij_van_de_gepaarde_verwijdering(db, job: dict):
    """Welke advertentierij haalde de verwijdering weg die bij deze plaatsing hoort?

    Een herplaatsing is twee opdrachten: eerst weghalen, dan plaatsen. De
    verwijdering draagt het rij-id mee in `_refresh_rollback`; de plaatsing
    kreeg dat pas op 05-09-2026. Alles wat op dat moment al in de wachtrij
    stond mist het merkteken dus, en zonder deze terugval zou daar nog één
    dubbele advertentie uit komen. Een handmatige verwijdering heeft geen
    `_refresh_rollback` en levert hier dus niets op: alleen een herplaatsing
    kan een rij overnemen.
    """
    try:
        rijen = (await naast_de_lus(lambda: db.table("jobs")
                 .select("payload,created_at")
                 .eq("user_id", job["user_id"]).eq("item_id", job["item_id"])
                 .eq("platform", job["platform"]).eq("action", "delete")
                 .lte("created_at", job["created_at"])
                 .order("created_at", desc=True).limit(1).execute())).data or []
    except Exception:  # noqa: BLE001
        return None
    if not rijen:
        return None
    verwijdering = rijen[0]
    # Een verwijdering van weken geleden hoort niet bij deze plaatsing.
    begin, eind = _parse_ts(verwijdering.get("created_at")), _parse_ts(job.get("created_at"))
    if begin and eind and (eind - begin) > timedelta(days=2):
        return None
    return ((verwijdering.get("payload") or {}).get("_refresh_rollback") or {}).get("listing_id")


def _verwijderdoelen(db, job: dict) -> list[dict]:
    """De advertentierij(en) die bij DEZE verwijderopdracht horen.

    WAAROM DIT ER IS (01-09-2026, item 1288 en 1314). Een verwijdering werkte
    élke advertentierij van dat artikel op dat kanaal bij. Eén artikel heeft daar
    inmiddels tot zes rijen van: elke herplaatsing zet er een nieuwe bij. Gevolg:
    een mislukte verwijdering zette OOK de rij van juni weer op 'actief', met de
    datum van juni erbij. Die was daarmee meteen weer een kandidaat voor het
    automatisch herplaatsen — dus werd hetzelfde artikel elke ronde opnieuw
    weggehaald en geplaatst, dag na dag. Gemeten bij (1314): zes herplaatsingen
    in vier dagen, terwijl de instelling op 30 dagen staat.

    De verwijderopdracht weet precies welke rij hij te pakken had: hij draagt het
    rij-id van de herplaatsing mee, en anders het advertentienummer. Alleen als
    geen van beide bekend is vallen we terug op "alle rijen van dit kanaal", en
    dan nog zonder de rijen die al een eindstatus hebben.
    """
    payload = job.get("payload") or {}
    rij_id = (payload.get("_refresh_rollback") or {}).get("listing_id")
    nummer = payload.get("platform_listing_id")
    basis = (lambda: db.table("listings").select("id,status,listed_at,platform_listing_id")
             .eq("item_id", job["item_id"]).eq("platform", job["platform"]))
    if rij_id:
        rijen = execute_with_retry(basis().eq("id", rij_id)).data or []
        if rijen:
            return rijen
    if nummer:
        rijen = execute_with_retry(basis().eq("platform_listing_id", nummer)).data or []
        if rijen:
            return rijen
    alle = execute_with_retry(basis()).data or []
    return [r for r in alle if r.get("status") not in EINDSTATUSSEN]


async def _al_weg_voor_wij_er_waren(db, job: dict) -> bool:
    """Advertentie was al weg toen we hem kwamen weghalen: verkocht, of verlopen?

    WAAROM DIT ER IS (01-09-2026, Daniel over (1288) en (1314)). Bij het
    herplaatsen haalt de extensie eerst de oude advertentie weg. Stond die er al
    niet meer, dan gold dat als "doel bereikt" en plaatste stap twee vrolijk een
    nieuwe. Precies wat er gebeurt bij een VERKOCHT artikel: de verkoper haalt de
    advertentie weg, wij zien hem niet meer, en zetten hem opnieuw te koop. Elke
    ronde opnieuw, want de verkoop wordt zo ook nooit opgemerkt.

    Het onderscheid zit in de leeftijd. Marktplaats gooit een gratis advertentie
    pas na dertig dagen zelf weg. Is de advertentie jonger dan dat en tóch weg,
    dan kán het geen verlopen zijn en heeft iemand hem weggehaald. Dat is geen
    bewijs van verkoop — de verkoper kan hem ook zelf hebben verwijderd — dus we
    boeken niets, we vrágen het: de advertentie krijgt de status 'mogelijk
    verkocht' die in het dashboard al een ja/nee-knop heeft, en de nieuwe
    advertentie wordt niet geplaatst.

    Is de advertentie wél oud genoeg om verlopen te zijn, dan verandert er niets
    aan het oude gedrag: herplaatsen is dan juist de bedoeling.
    """
    if job["platform"] not in ("marktplaats", "2dehands"):
        return False
    doelen = await naast_de_lus(lambda: _verwijderdoelen(db, job))
    jong = []
    for rij in doelen:
        if rij.get("status") in ("sold", "sold_unconfirmed"):
            continue
        geplaatst = rij.get("listed_at")
        if not geplaatst:
            return False        # zonder datum valt er niets te concluderen
        try:
            leeftijd = datetime.now(timezone.utc) - datetime.fromisoformat(geplaatst)
        except (TypeError, ValueError):
            return False
        if leeftijd >= timedelta(days=ZELF_VERLOPEN_NA_DAGEN):
            return False        # oud genoeg om vanzelf verlopen te zijn
        jong.append(rij)
    if not jong:
        return False

    # Staat dit artikel al ELDERS bevestigd op 'verkocht' (Vinted-order,
    # Shopify/eBay-bestelling), dan is de verkoop geen vraag meer. De verdwenen
    # advertentie op dit kanaal gaat dan rechtstreeks naar het archief in plaats
    # van de verkoper opnieuw "is dit verkocht?" te vragen. Dit is precies het
    # geval dat de reconciliatie-ronde oplevert: verkocht op A, nog een oude
    # 'active'-rij op B.
    verkochte_rijen = ((await naast_de_lus(lambda: db.table("listings")
        .select("platform").eq("item_id", job["item_id"]).eq("status", "sold")
        .execute())).data or [])
    al_verkocht_elders = [r for r in verkochte_rijen if r.get("platform") != job["platform"]]
    if al_verkocht_elders:
        for rij in jong:
            (await naast_de_lus(lambda r=rij: db.table("listings").update({
                "status": "delisted",
                "error_message": None,
                "last_checked": datetime.now(timezone.utc).isoformat(),
            }).eq("id", r["id"]).execute()))
        logger.info("[sold] item %s op %s: advertentie was al weg en het artikel is elders al "
                    "verkocht (%s) — %d rij(en) gearchiveerd, geen vraag gesteld",
                    job["item_id"], job["platform"],
                    al_verkocht_elders[0]["platform"], len(jong))
    else:
        from backend.api.listings import VERDENKING_REDENEN
        reden = VERDENKING_REDENEN["verdwenen_te_jong"]
        for rij in jong:
            (await naast_de_lus(lambda r=rij: db.table("listings").update({
                "status": "sold_unconfirmed",
                "error_message": reden,
                "last_checked": datetime.now(timezone.utc).isoformat(),
            }).eq("id", r["id"]).execute()))

    # De nieuwe advertentie mag niet geplaatst worden zolang niet vaststaat dat
    # het artikel nog te koop is. Zonder dit blijft de lus gewoon draaien: de
    # herplaatsing staat immers al klaar in de wachtrij.
    wachtend = ((await naast_de_lus(lambda: db.table("jobs").select("id")
                .eq("item_id", job["item_id"]).eq("platform", job["platform"])
                .eq("action", "create").in_("status", ["pending", "claimed"])
                .gte("created_at", job["created_at"]).execute())).data or [])
    for baan in wachtend:
        (await naast_de_lus(lambda b=baan: db.table("jobs").update({
            "status": "cancelled",
            "done_at": datetime.now(timezone.utc).isoformat(),
            "result": {"cancelled": (
                "De oude advertentie was al van het platform af voordat wij hem "
                "weghaalden, en daarvoor was hij te jong om vanzelf te verlopen. "
                "Bevestig eerst in het dashboard of dit artikel verkocht is.")},
        }).eq("id", b["id"]).execute()))

    if wachtend:
        logger.info("[sold] item %s op %s: %d herplaatsing(en) geannuleerd "
                    "(advertentie was al weg en te jong om te verlopen)",
                    job["item_id"], job["platform"], len(wachtend))
    return True


@router.post("/{job_id}/complete")
async def complete_job(job_id: str, body: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    _record_extension_heartbeat(db, user_id)  # only the extension completes jobs
    job = eerste_rij(await naast_de_lus(lambda: db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).limit(1).execute()))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # The user explicitly cancelled this run — honour that and don't silently
    # revive the listing to "active" if a late completion trickles in afterwards.
    if job["status"] == "cancelled":
        return {"ok": True, "status": "cancelled"}

    # EERST OPSLAAN, DAN PAS "KLAAR" ZEGGEN.
    #
    # Een scan werd hier op 'done' gezet vóórdat de gevonden advertenties waren
    # weggeschreven. Ging dat wegschrijven daarna stuk, dan zag de verkoper een
    # geslaagde scan terwijl er niets bewaard was — en de volgende scan sloeg
    # diezelfde advertenties over, want de opdracht stond immers op klaar.
    # Gemeten bij Egbert Brouwer: drie scans op rij, elk 2.000 nieuwe
    # advertenties, nul opgeslagen, scherm meldde "niets nieuws".
    if job["action"] == "scan":
        import asyncio
        listings = body.get("listings", [])
        try:
            await asyncio.to_thread(_store_scan_results, db, job, listings)
        except Exception as e:  # noqa: BLE001
            logger.exception("Scan store failed for job %s (%d listings)", job_id, len(listings))
            (await naast_de_lus(lambda: db.table("jobs").update({
                "status": "error",
                "result": {"error": f"Saving the scan results failed: {e}",
                           "listings": listings},
                "done_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", job_id).execute()))
            raise HTTPException(
                status_code=500,
                detail="The scan was fetched but saving it failed. Nothing was lost — run the scan again.")

    (await naast_de_lus(lambda: db.table("jobs").update({
        "status": "done",
        "result": body,
        "done_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()))

    if job["action"] == "create":
        await _rond_publicatie_af(db, job, body)

    elif job["action"] == "delete":  # noqa: SIM114
        # De extensie kan tijdens het verwijderen ontdekken dat de advertentie op
        # DIT platform verkocht is (Vinted: is_closed; MP/2dehands: een
        # "Verkocht"-label op de rij). Dan is verwijderen precies het verkeerde:
        # we boeken de verkoop, waardoor het item uit "live" verdwijnt en juist de
        # ándere platforms worden opgeruimd.
        if body.get("sold_on_platform"):
            from backend.services.crosslist import handle_item_sold
            logger.info("[sold] delete job %s reported a sale on %s — booking it instead of deleting",
                        job_id, job["platform"])
            try:
                await handle_item_sold(job["item_id"], job["platform"], body.get("sold_price"))
            except Exception as e:  # noqa: BLE001
                logger.warning("[sold] booking sale from delete job %s failed: %s", job_id, e)
            return {"ok": True, "status": "sold_on_platform"}

        # De advertentie stond er al niet meer toen de extensie hem kwam
        # weghalen. Was hij te jong om vanzelf verlopen te zijn, dan heeft iemand
        # hem weggehaald en is "verkocht?" de juiste vraag — geen herplaatsing.
        if body.get("note") == "already_absent" and await _al_weg_voor_wij_er_waren(db, job):
            return {"ok": True, "status": "possibly_sold"}

        # Alleen de advertentie die deze opdracht te pakken had. Zie
        # _verwijderdoelen: een artikel heeft er inmiddels meerdere.
        for rij in await naast_de_lus(lambda: _verwijderdoelen(db, job)):
            if rij.get("status") in ("sold", "sold_unconfirmed"):
                continue        # een verkoop is een eindpunt, geen tussenstand
            (await naast_de_lus(lambda r=rij: db.table("listings")
                                .update({"status": "delisted"}).eq("id", r["id"]).execute()))

        # If this delete is the first half of a relist, the extension may have
        # snapshotted the full live listing before removing it (imported items
        # otherwise carry almost no data). Merge that snapshot into the paired,
        # still-pending recreate ("create") job so the new listing is a faithful
        # copy instead of just title+price. Only fill fields that are actually
        # present in the snapshot and missing/empty in the current payload.
        captured = body.get("captured_listing") or {}
        if captured:
            paired = (
                (await naast_de_lus(lambda: db.table("jobs")
                .select("id,payload")
                .eq("user_id", user_id)
                .eq("item_id", job["item_id"])
                .eq("platform", job["platform"])
                .eq("action", "create")
                .eq("status", "pending")
                .gte("created_at", job["created_at"])
                .order("created_at")
                .limit(1)
                .execute()))
                .data
            )
            if paired:
                payload = dict(paired[0].get("payload") or {})
                for key in ("description", "brand", "size", "condition", "color", "material", "category", "gender"):
                    val = captured.get(key)
                    if val and not payload.get(key):
                        payload[key] = val
                # DE ECHTE CATEGORIE VAN DE ADVERTENTIE OVERSCHRIJFT WEL.
                #
                # Anders dan de velden hierboven is dit geen aanvulling maar een
                # correctie: de categorie in de opdracht is geraden uit de titel,
                # deze is letterlijk van de advertentiepagina van Marktplaats
                # gelezen vlak voor we hem weghaalden. Amanda, 30-08-2026: na een
                # verversing kwam alles in de verkeerde categorie terug, en op
                # Marktplaats is dat achteraf niet te wijzigen.
                cap_cat = captured.get("mp_category") or {}
                if cap_cat.get("l1") and cap_cat.get("l2"):
                    payload["mp_category"] = cap_cat
                # Photos: prefer the fuller captured set (imports often keep only 1).
                cap_photos = captured.get("photo_urls") or []
                if len(cap_photos) > len(payload.get("photo_urls") or []):
                    payload["photo_urls"] = cap_photos
                # Price: the captured value is the real live Vinted price. The
                # dashboard's jittered price can be wrong for imported items, so
                # trust the captured one when present.
                cap_price = captured.get("price")
                if cap_price is not None:
                    try:
                        payload["price"] = float(cap_price)
                    except (TypeError, ValueError):
                        pass
                (await naast_de_lus(lambda: db.table("jobs").update({"payload": payload}).eq("id", paired[0]["id"]).execute()))

            # HET ITEM ZELF OOK BIJWERKEN.
            #
            # Een geïmporteerde advertentie kwam met één foto binnen: de zoeklijst
            # van Marktplaats geeft alleen het omslagplaatje mee. Bij het
            # verwijderen hebben we de advertentiepagina gezien en dáár staan ze
            # allemaal. Zetten we die alleen in de plaatsingsopdracht, dan is het
            # item volgende keer weer arm — en publiceren naar Vinted of eBay
            # blijft dan ook met één foto gebeuren.
            #
            # Alleen als het item er zelf hooguit één had. Een verkoper die zijn
            # foto's zelf heeft gekozen wordt hier nooit overruled.
            #
            # Hetzelfde geldt voor merk, maat, kleur en staat: die staan wél op de
            # advertentie maar niet in de zoeklijst waaruit geïmporteerd wordt.
            # Zolang ze leeg zijn weigert het dashboard te publiceren naar
            # Marktplaats en 2dehands ("Vul merk en maat aan") — precies de
            # melding die bij elke geïmporteerde advertentie stond.
            cap_photos = captured.get("photo_urls") or []
            try:
                huidig = (eerste_rij(await naast_de_lus(lambda: db.table("items")
                          .select("photo_urls,brand,size,color,condition")
                          .eq("id", job["item_id"]).limit(1).execute())) or {})
                patch = {}
                if len(cap_photos) > 1 and len(huidig.get("photo_urls") or []) <= 1:
                    patch["photo_urls"] = cap_photos
                for veld in ("brand", "size", "color", "condition"):
                    waarde = (captured.get(veld) or "")
                    if isinstance(waarde, str):
                        waarde = waarde.strip()
                    if waarde and not str(huidig.get(veld) or "").strip():
                        patch[veld] = waarde
                if patch:
                    (await naast_de_lus(lambda: db.table("items")
                     .update(patch).eq("id", job["item_id"]).execute()))
                    logger.info("[relist] item %s aangevuld uit de live advertentie: %s",
                                job["item_id"], ", ".join(sorted(patch)))
            except Exception as e:  # noqa: BLE001 — nooit de afronding laten vallen
                logger.warning("[relist] kon gegevens niet terugschrijven naar item %s: %s",
                               job["item_id"], e)

    elif job["action"] == "content_refresh":
        # Listing stays active — this is an in-place edit, not a new listing.
        pass

    elif job["action"] == "extend":
        # 2dehands verlengen. Er is GEEN nieuwe advertentie en er is niets
        # weggehaald, dus de status van de advertentierij blijft met rust.
        #
        # ALLEEN met bewijs schuift listed_at mee. De extensie stuurt de oude en
        # de nieuwe vervaldatum mee; die moet echt ~4 weken verder liggen
        # (`verlengd: true`). Zonder dat bewijs veranderen we niks — een
        # "klaar"-melding zonder opgeschoven datum is geen verlenging (zie
        # docs/kennisbank.md, "succes-nooit-uit-uitsluitingslijst"). listed_at
        # blijft dan staan, zodat de volgende ronde het opnieuw probeert.
        if body.get("verlengd") is True and body.get("new_close"):
            rid = (job.get("payload") or {}).get("_listing_row_id")

            def _schuif():
                q = db.table("listings").update({
                    "listed_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": None,
                })
                if rid:
                    q = q.eq("id", rid)
                else:
                    q = (q.eq("item_id", job["item_id"]).eq("platform", "2dehands")
                          .eq("status", "active"))
                return q.execute()

            (await naast_de_lus(_schuif))
            logger.info("[extend] 2dehands zoekertje %s verlengd tot %s — listed_at bijgezet",
                        job["item_id"], body.get("new_close"))
        else:
            logger.warning("[extend] job %s meldde klaar zonder bewijs dat de "
                           "vervaldatum opschoof (%s) — listed_at ongemoeid",
                           job_id, body.get("note"))

    elif job["action"] == "scan":
        # De kandidaten zijn hierboven al opgeslagen (vóór 'done'). Wat hier
        # overblijft is de Vinted-nabewerking; die mag de scan niet laten
        # mislukken als hij zelf hapert.
        import asyncio
        listings = body.get("listings", [])
        if job["platform"] == "vinted":
            await asyncio.to_thread(_sync_vinted_hidden, db, job, listings)
            await _reconcile_vinted_sales(db, job, listings, body.get("scan_meta") or {})

    return {"ok": True}


def _sync_vinted_hidden(db, job, scraped: list[dict]):
    """
    Mirror Vinted's `is_hidden` onto our listings.

    A hidden listing still exists and is still yours, but nobody can see or buy
    it — so it must not sit in the dashboard next to what's genuinely for sale
    (and it must not be counted as stale stock, which measures how long
    something has been ON SALE without selling).

    Unlike the sale reconcile this is safe on a PARTIAL snapshot: it only ever
    changes listings whose id we actually saw, so a truncated scan simply
    updates fewer rows instead of drawing a wrong conclusion from absence.
    Hidden is fully reversible — unhide on Vinted and the next scan flips it
    straight back to active.
    """
    if not scraped:
        return

    hidden_ids, visible_ids = set(), set()
    for r in scraped:
        pid = r.get("platform_listing_id")
        if pid is None or r.get("is_closed"):
            continue
        (hidden_ids if r.get("is_hidden") else visible_ids).add(str(pid))
    if not hidden_ids and not visible_ids:
        return

    item_ids = [it["id"] for it in fetch_all(
        lambda: db.table("items").select("id").eq("user_id", job["user_id"]))]
    if not item_ids:
        return

    rows = fetch_all_in(lambda: db.table("listings")
                        .select("id,platform_listing_id,status")
                        .eq("platform", "vinted")
                        .in_("status", ["active", "relisting", "hidden"]),
                        "item_id", item_ids)

    to_hide, to_show = [], []
    for l in rows:
        pid = l.get("platform_listing_id")
        if pid is None:
            continue
        pid = str(pid)
        if pid in hidden_ids and l["status"] != "hidden":
            to_hide.append(l["id"])
        # Only un-hide on positive evidence that it's visible again.
        elif pid in visible_ids and l["status"] == "hidden":
            to_show.append(l["id"])

    for ids, new_status in ((to_hide, "hidden"), (to_show, "active")):
        if not ids:
            continue
        try:
            update_in(lambda: db.table("listings"), "id", ids, {"status": new_status})
        except Exception as e:
            logger.warning(f"Vinted hidden sync ({new_status}) failed: {e}")
    if to_hide or to_show:
        logger.info(
            "Vinted hidden sync for user %s: %d hidden, %d back to active",
            job["user_id"], len(to_hide), len(to_show),
        )


# De rem op "weg uit de kast is verkocht". Verdwijnt er in één ronde meer dan dit
# aandeel van de kast, dan gelooft de code de momentopname niet meer en vraagt ze
# het aan de verkoper in plaats van overal af te melden. De ondergrens is er voor
# kleine kasten, waar een tiende al bij twee advertenties bereikt is.
VERDWIJN_AANDEEL = 0.10
VERDWIJN_ONDERGRENS = 10


async def _reconcile_vinted_sales(db, job, scraped: list[dict], scan_meta: dict | None = None):
    """
    Vinted has no webhook and (deliberately, after a past incident with a stale
    session) no server-side polling — so a Vinted sale is otherwise invisible
    until the user notices it themselves. A COMPLETE wardrobe scan lets us spot
    one: a listing Vinted marks `is_closed` has sold or ended, and one that has
    vanished from the wardrobe entirely was deleted.

    Two hard safety rules, both learned the hard way:

    1. Only ever act on a COMPLETE snapshot. The scan used to read just the
       newest 96 listings (Vinted caps per_page at 96, and the pager mistook
       that short page for the last one). Every older listing therefore looked
       "missing" and was marked sold — and handle_item_sold then delisted it
       from every other platform. Absence is only meaningful if we truly saw
       everything, so an incomplete scan reconciles nothing.

    2. Absence is the weaker signal; `is_closed` is the real one. Sold listings
       stay in the wardrobe, so the closed flag is what actually tells us.
       Hidden listings are NOT sold — the seller just took them out of view —
       so they're deliberately left alone.
    """
    if not scraped:
        return

    meta = scan_meta or {}
    # No meta at all means an old extension build, whose snapshot we now know
    # was truncated. Refuse rather than repeat the damage.
    if not meta.get("complete"):
        logger.warning(
            "Vinted reconcile skipped for user %s — snapshot not complete (%s; %s of %s fetched). "
            "Update the extension so sold-detection can run again.",
            job["user_id"],
            meta.get("truncated_reason") or "no scan_meta (old extension build)",
            meta.get("fetched"), meta.get("total_entries"),
        )
        return

    # Everything Vinted still knows about, and which of those are closed.
    seen_ids: set[str] = set()
    closed_ids: set[str] = set()
    # Een advertentie zonder opgeslagen Vinted-nummer was tot nu toe onzichtbaar
    # voor deze controle: geen nummer = geen match = verkoop gemist, en het item
    # bleef bij "live" staan (en werd later alsnog "verwijderd" op Vinted).
    # Daarom twee vervangende sleutels, allebei alleen geldig als ze binnen de
    # garderobe naar precies één advertentie wijzen:
    #   1. de titel, 1-op-1 vergeleken na normalisatie (accenten, leestekens,
    #      hoofdletters en een eventuele "(1337)"-prefix doen niet mee);
    #   2. dat nummer tussen haakjes, als de verkoper dat gebruikt.
    # Dubbele titels of dubbele nummers worden bewust weggegooid: liever geen
    # match dan het verkeerde item als verkocht boeken.
    closed_id_by_sku: dict[str, str | None] = {}
    closed_id_by_title: dict[str, str | None] = {}

    # Dezelfde sleutels als waarmee de scan advertenties aan items koppelt — één
    # definitie, zodat "verkocht herkennen" en "advertentie koppelen" nooit uit
    # elkaar lopen.
    _sku_of = _scan_sku
    _norm_title = _scan_norm_title

    def _register(index: dict, key: str, pid: str) -> None:
        if not key:
            return
        # None = dubbel gezien, dus onbruikbaar als sleutel.
        index[key] = pid if key not in index else (pid if index[key] == pid else None)

    for r in scraped:
        pid = r.get("platform_listing_id")
        if pid is None:
            continue
        pid = str(pid)
        seen_ids.add(pid)
        if r.get("is_closed"):
            closed_ids.add(pid)
            _register(closed_id_by_title, _norm_title(r.get("title")), pid)
            _register(closed_id_by_sku, _sku_of(r.get("title")), pid)

    items_rows = fetch_all(
        lambda: db.table("items").select("id,sku,title").eq("user_id", job["user_id"]))
    item_ids = [it["id"] for it in items_rows]
    items_by_id = {it["id"]: it for it in items_rows}
    own_title_counts: dict[str, int] = {}
    for it in items_rows:
        key = _norm_title(it.get("title"))
        if key:
            own_title_counts[key] = own_title_counts.get(key, 0) + 1
    if not item_ids:
        return

    # Plaatselijke import: listings.py leunt op dit bestand, dus bovenaan zou
    # dit een kringetje worden (zelfde reden als bij 'verdwenen_te_jong').
    from backend.api.listings import VERDENKING_REDENEN

    # Waar staat dit artikel NOG te koop? Een advertentie die van Vinted af is
    # maar elders gewoon online staat, is precies het geval waarin de verkoper
    # iets moet beslissen; staat hij nergens anders meer, dan valt er niets te
    # vragen en gaat hij zonder omhaal het archief in.
    elders_levend: set[str] = set()
    try:
        for r in (await naast_de_lus(lambda: fetch_all_in(
                lambda: db.table("listings").select("item_id")
                .neq("platform", "vinted")
                .in_("status", ["active", "relisting", "hidden", "pending"]),
                "item_id", item_ids))):
            elders_levend.add(r["item_id"])
    except Exception as e:  # noqa: BLE001
        # Niet fataal, maar wel bepalend: zonder deze lijst zouden we iedereen
        # een vraag stellen die niets oplevert. Dan liever doen wat we altijd
        # deden en archiveren.
        logger.warning("Vinted reconcile: kon 'staat elders nog te koop' niet bepalen: %s", e)

    active = await naast_de_lus(lambda: fetch_all_in(
        lambda: db.table("listings")
        .select("id,item_id,platform_listing_id")
        .eq("platform", "vinted")
        # 'hidden' hoort erbij: een verborgen advertentie kan gewoon verkocht zijn
        # (Vinted zet hem dan op closed), en die verkoop werd anders nooit gezien.
        .in_("status", ["active", "relisting", "hidden"]),
        "item_id", item_ids))
    # Two very different signals, handled differently on purpose:
    #   is_closed  → Vinted's own "sold/ended" flag. On Vinted a listing doesn't
    #                expire on its own, so closed ≈ sold → book it as a sale.
    #   vanished   → gone from a COMPLETE wardrobe with no sold flag. Could be sold
    #                then removed, but could equally be manually deleted/expired.
    #                We do NOT fabricate a sale from absence (that would inflate
    #                revenue and cross-delist live listings). Instead we just take
    #                it off "Live" → 'delisted', so it lands in Archived for the
    #                user to confirm and mark sold themselves if it really sold.
    newly_sold, set_aside, matched_without_id, gevraagd, weg_en_verkocht = 0, 0, 0, 0, 0
    verdwenen: list[dict] = []
    for l in active:
        pid = l.get("platform_listing_id")
        if pid is None:
            # Geen Vinted-nummer bekend: match op de SKU-prefix van de titel, en
            # anders op de exacte titel. Alleen een POSITIEF "gesloten" kaartje
            # telt — afwezigheid blijft betekenisloos, precies zoals hieronder.
            item = items_by_id.get(l["item_id"]) or {}
            title = _norm_title(item.get("title"))
            # De titel is de gewone sleutel; het nummer tussen haakjes (of het
            # SKU-veld) is een extra, voor wie dat gebruikt. Een titel die bij
            # meerdere eigen items hoort is geen sleutel — dan liever niets doen.
            hit = None
            if title and own_title_counts.get(title) == 1:
                hit = closed_id_by_title.get(title)
            if not hit:
                keys = [k for k in (str(item.get("sku") or "").strip().lower(),
                                    _sku_of(item.get("title"))) if k]
                hit = next((closed_id_by_sku[k] for k in keys if closed_id_by_sku.get(k)), None)
            if not hit:
                continue
            matched_without_id += 1
            # Meteen het nummer vastleggen, zodat de volgende ronde gewoon op id matcht.
            try:
                (await naast_de_lus(lambda: db.table("listings").update({"platform_listing_id": hit}).eq("id", l["id"]).execute()))
            except Exception as e:  # noqa: BLE001
                logger.warning("Vinted reconcile: could not backfill listing id for %s: %s", l["item_id"], e)
            try:
                await handle_item_sold(l["item_id"], "vinted")
                newly_sold += 1
            except Exception as e:
                logger.warning(f"Vinted sale reconcile failed for item {l['item_id']}: {e}")
            continue
        pid = str(pid)
        if pid in closed_ids:
            try:
                await handle_item_sold(l["item_id"], "vinted")
                newly_sold += 1
            except Exception as e:
                logger.warning(f"Vinted sale reconcile failed for item {l['item_id']}: {e}")
        elif pid not in seen_ids:
            verdwenen.append(l)

    # ── WEG UIT DE KAST IS VERKOCHT ─────────────────────────────────────────
    #
    # GEMETEN 12-09-2026 (De Juiste Toon). Hij verkocht 23 artikelen op Vinted
    # en haalde die advertenties daar zelf weg, zoals vrijwel iedereen doet. Op
    # Marktplaats bleven ze staan. Dat was geen storing maar het ontwerp: een
    # verdwenen advertentie ging stil naar 'delisted' en verder gebeurde er
    # niets, dus het antwoord op "wanneer gaan ze automatisch van Marktplaats
    # af" was: nooit.
    #
    # Op Vinted verloopt niets vanzelf en een verkochte advertentie blijft
    # gewoon in de kast staan. Weg uit de kast betekent dus: de verkoper heeft
    # hem met eigen hand verwijderd, en dat doet vrijwel iedereen meteen na een
    # verkoop. Dat handelen we voortaan zelf af, zonder iets te vragen.
    #
    # DE REM DIE ERBIJ HOORT. Deze conclusie is precies de conclusie die ooit
    # levende advertenties overal weghaalde: de scan las toen alleen de 96
    # nieuwste advertenties, waardoor alles daaronder "weg" leek. Daar liggen nu
    # twee sloten op:
    #   1. Alleen een als VOLLEDIG gemelde momentopname telt (hierboven).
    #   2. En een volledige momentopname kan alsnog liegen, dus: verdwijnt er in
    #      één ronde meer dan een tiende van de kast (met een ondergrens van
    #      tien), dan is dat geen dag verkopen maar een kapotte scan. Dan wordt
    #      er niets afgemeld en krijgt de verkoper de ja/nee-vraag, zoals
    #      hiervoor. Bij Toon: 23 van de bijna duizend, ruim onder de rem.
    grens = max(VERDWIJN_ONDERGRENS, int(len(active) * VERDWIJN_AANDEEL))
    te_veel_ineens = len(verdwenen) > grens
    if te_veel_ineens:
        logger.warning(
            "Vinted reconcile voor %s: %d van de %d advertenties ineens weg (rem staat op %d). "
            "Dat telt niet als verkopen; de verkoper krijgt de vraag.",
            job["user_id"], len(verdwenen), len(active), grens)

    for l in verdwenen:
        if not te_veel_ineens:
            # Gewoon verkocht: handle_item_sold boekt de verkoop en zet de
            # verwijderopdrachten klaar voor Marktplaats, 2dehands en de rest.
            try:
                await handle_item_sold(l["item_id"], "vinted")
                weg_en_verkocht += 1
                continue
            except Exception as e:  # noqa: BLE001
                logger.warning("Vinted reconcile: afmelden van item %s mislukt, wordt een vraag: %s",
                               l["item_id"], e)
        # De rem staat erop (of het afmelden ging mis): vragen in plaats van doen.
        # Staat het artikel nergens anders meer te koop, dan valt er niets te
        # vragen en gaat de rij gewoon het archief in.
        vraag = l["item_id"] in elders_levend
        velden = ({"status": "sold_unconfirmed",
                   "error_message": VERDENKING_REDENEN["vinted_weg"],
                   "last_checked": datetime.now(timezone.utc).isoformat()}
                  if vraag else {"status": "delisted"})
        try:
            (await naast_de_lus(lambda v=velden, i=l["item_id"]: db.table("listings").update(v) \
                .eq("item_id", i).eq("platform", "vinted")
                .in_("status", ["active", "relisting", "hidden"]).execute()))
            if vraag:
                gevraagd += 1
            else:
                set_aside += 1
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Vinted reconcile: could not archive vanished listing {l['item_id']}: {e}")
    logger.info(
        "[sold] Vinted reconcile for user %s: %d marked sold (is_closed, of which %d matched by SKU/title), "
        "%d vanished → booked as sold and delisted elsewhere, %d vanished → asked the seller, "
        "%d vanished → archived",
        job["user_id"], newly_sold, matched_without_id, weg_en_verkocht, gevraagd, set_aside,
    )


def _fix_photo_url(u):
    """
    Repair a scraped image url that lost its protocol.

    Marktplaats' own overview API returns protocol-relative urls ("//images.
    marktplaats.com/…"). The extension turned those into
    "https://www.marktplaats.nl//images.marktplaats.com/…" — a 404, so every
    imported thumbnail was blank and the photo copy silently produced nothing.
    Cheap to repair here, and it fixes the rows already stored as well.
    """
    if not isinstance(u, str):
        return None
    s = u.strip()
    if not s:
        return None
    m = re.search(r"^https?://[^/]+//(.+)$", s)
    if m and "." in m.group(1).split("/")[0]:
        return "https://" + m.group(1)
    if s.startswith("//"):
        return "https:" + s
    return s


def _rijke_velden(row: dict, photo_urls, vorige: dict | None) -> dict:
    """Wat er van deze gescande advertentie in de kandidaat komt te staan.

    EEN SCAN MAG AANVULLEN EN BIJWERKEN, NOOIT LEEGHALEN.

    Toon (dejuistetoon), 02-09-2026. Hier stond simpelweg
    `"description": row.get("description") or None`. Vinted knijpt af tijdens
    een scan — gemeten laat hij er zo'n vijftien per minuut door en geeft daarna
    429 — dus komt een scan geregeld terug met een lege omschrijving voor een
    advertentie waar de vórige scan er wél een vond. Die leegte ging er keihard
    overheen. Nagemeten in zijn gegevens: 271 kandidaten stonden zonder tekst
    terwijl het artikel dat eruit geïmporteerd was er wél een had — die tekst
    kán alleen uit een eerdere scan zijn gekomen, dus die 271 zijn achteraf
    gewist. Wie daarna importeerde kreeg een artikel zonder tekst, en zonder
    tekst weigert het dashboard te publiceren naar Marktplaats, 2dehands en
    Facebook: alles grijs, niets aanklikbaar.

    Zuiver rekenwerk, geen database — zo is deze regel te testen zonder scan.
    """
    nieuw = {
        "photo_urls": photo_urls or None,
        "description": (row.get("description") or None),
        "brand": (row.get("brand") or None),
        "size": (row.get("size") or None),
        "condition": (row.get("condition") or None),
        "category": (row.get("category") or None),
        "gender": (row.get("gender") or None),
        "color": (row.get("color") or None),
        "material": (row.get("material") or None),
    }
    if not vorige:
        return nieuw
    for veld, waarde in list(nieuw.items()):
        if waarde:
            continue  # de scan wéét iets — dat wint altijd
        oud = vorige.get(veld)
        if oud not in (None, "", [], {}):
            nieuw[veld] = oud
    return nieuw


def _store_scan_results(db, job, scraped: list[dict]):
    """
    Persist scraped "my listings" cards as import_candidates for manual review.
    Never touches the items/listings tables directly — a human links or
    imports each candidate explicitly via /api/imports.
    """
    if not scraped:
        return
    from backend.api.imports import BACKFILL_FIELDS, _backfill_patch

    # Read the items ONCE, with every field the backfill needs. This used to be a
    # select per candidate inside the loop below, so a 500-listing wardrobe meant
    # ~1000 round-trips and "Saving to your dashboard…" sat there for minutes.
    items = fetch_all(lambda: db.table("items").select(BACKFILL_FIELDS + ",title,sku").eq("user_id", job["user_id"]))
    items_by_id = {it["id"]: it for it in items}
    # Extra koppelsleutels: het SKU-nummer vooraan de titel en de titel zonder
    # leestekens/accenten. Die overleven een vertaling of een kleine handmatige
    # aanpassing op het platform, waar een exacte titelvergelijking op stukliep.
    # Merk per item: waarmee _unique_index kan zien of twee kandidaten met
    # hetzelfde nummer echt hetzelfde product zijn.
    _merk_van = {it["id"]: str(it.get("brand") or "").strip().lower() for it in items}
    _sku_index = _unique_index(
        [(_scan_sku(it.get("title")), it["id"]) for it in items]
        + [(str(it.get("sku") or "").strip().lower(), it["id"]) for it in items],
        _merk_van,
    )
    _norm_title_index = _unique_index(
        ((_scan_norm_title(it.get("title")), it["id"]) for it in items), _merk_van)
    # (platform, listing id) → item_id, so a re-scan of an already-known listing
    # links back to the exact same item. Scoped by the user's item ids because
    # the listings table has no user_id column.
    item_ids = [it["id"] for it in items]
    listings_by_id = {}
    # (item_id, platform) → de bestaande listing-rij, zodat we hieronder kunnen
    # zien of het dashboard al wéét dat dit item op dit platform staat.
    listing_by_item = {}
    if item_ids:
        # In brokken: met meer dan ~639 item-id's wordt de URL van dit filter te
        # lang en gooit httpx een uitzondering (zie database.IN_BROK). Die knalde
        # hier midden in het opslaan van een scan, waardoor GEEN ENKELE gevonden
        # advertentie werd bewaard terwijl de opdracht al op "klaar" stond.
        lrows = fetch_all_in(lambda: db.table("listings")
                             .select("id,item_id,platform,status,platform_listing_id"),
                             "item_id", item_ids)
        for l in lrows:
            pid = l.get("platform_listing_id")
            if pid is not None and l.get("item_id"):
                listings_by_id[(l.get("platform"), str(pid))] = l["item_id"]
            if l.get("item_id"):
                listing_by_item[(l["item_id"], l.get("platform"))] = l

    # De titel die de extensie daadwerkelijk in het formulier zette (uit de
    # publicatie-opdracht). Die staat op het platform, terwijl de itemtitel in
    # het dashboard anders kan zijn (vertaald of ingekort) — daarom herkende hij
    # zelf afgemaakte advertenties niet.
    job_titles = {}
    try:
        jrows = fetch_all(lambda: db.table("jobs")
                          .select("item_id,payload")
                          .eq("user_id", job["user_id"])
                          .eq("platform", job["platform"])
                          .eq("action", "create"))
        for j in jrows:
            t = ((j.get("payload") or {}).get("title") or "").strip().lower()
            t = " ".join(t.split())
            if t and j.get("item_id"):
                # Bij twijfel (twee items met dezelfde formuliertitel) liever geen
                # koppeling dan de verkeerde.
                job_titles[t] = None if t in job_titles and job_titles[t] != j["item_id"] else j["item_id"]
    except Exception as e:
        logger.warning(f"Scan store: could not read create-job titles: {e}")

    # What we already decided about each candidate. The upsert below refreshes the
    # scraped snapshot, but it must NOT undo a decision: it used to write
    # status='pending' unconditionally, so a re-scan resurrected every listing you
    # had already imported, linked or ignored straight back into the review list.
    prior_status = {}
    # Wat een EERDERE scan al wist. Dit is niet alleen de status: ook de
    # omschrijving, het merk, de foto's.
    #
    # Toon (dejuistetoon), 02-09-2026: een tweede scan van dezelfde kast wiste de
    # omschrijvingen van 271 advertenties. Vinted knijpt af — het detail-endpoint
    # is dood (404) en de openbare pagina geeft na ~14 snelle verzoeken 429 — dus
    # een scan komt regelmatig terug met een lege omschrijving voor advertenties
    # waar de vorige scan er wél een vond. Die lege waarde werd hier keihard
    # overheen geschreven. Wie daarna importeerde kreeg een artikel zonder tekst,
    # en zonder tekst weigert het dashboard te publiceren naar Marktplaats,
    # 2dehands en Facebook: alles grijs, niets aanklikbaar.
    #
    # Regel: een scan mag toevoegen en bijwerken, nooit leeghalen. Staat er een
    # waarde en levert de nieuwe scan niets, dan blijft de oude staan.
    prior_rich = {}
    # fetch_all, niet één select: PostgREST geeft er stilzwijgend hooguit 1.000
    # terug. Bij een verkoper met meer kandidaten kregen alle rijen daarboven
    # opnieuw status 'pending' — advertenties die hij al geïmporteerd had,
    # stonden daarna zó weer op de te-beoordelen lijst.
    def _lees_vorige(kolommen: str):
        return fetch_all(lambda: db.table("import_candidates")
                         .select(kolommen)
                         .eq("user_id", job["user_id"])
                         .eq("platform", job["platform"]))
    try:
        prev = _lees_vorige("platform_listing_id,status," + ",".join(RICH_KEYS))
    except Exception as e:
        # Nog niet gemigreerde database: de rijke kolommen bestaan daar niet.
        # Dan alleen de status lezen — beschermen kan niet wat er niet is.
        logger.warning(f"Scan store: rich prior read failed ({e}); status only.")
        prev = _lees_vorige("platform_listing_id,status")
    for c in prev:
        pid = c.get("platform_listing_id")
        if pid is not None:
            prior_status[str(pid)] = c.get("status") or "pending"
            prior_rich[str(pid)] = {k: c[k] for k in RICH_KEYS if k in c}

    rows = []          # candidate rows, upserted in bulk below
    backfills = {}     # item_id -> merged patch, applied in bulk below
    live_links = {}    # item_id -> listing data we saw live on this platform

    for row in scraped:
        platform_listing_id = row.get("platform_listing_id")
        title = row.get("title") or ""
        if not platform_listing_id:
            continue
        # Sold/ended and draft listings ride along in the scan payload purely so
        # the sale reconcile can see them — nobody wants to import them. Without
        # this a full wardrobe scan would dump every listing ever sold into the
        # import queue for manual review.
        if row.get("is_closed") or row.get("is_draft"):
            continue
        # Strongest signal: the exact same listing id already lives on an item.
        # Otherwise a UNIQUE exact title match. Fuzzy matching wrongly links items
        # differing only by size/colour/number (see imports._best_match), so a
        # wrong suggestion is worse than none.
        best_id = listings_by_id.get((job["platform"], str(platform_listing_id)))
        if not best_id:
            want = " ".join(title.lower().split())
            title_matches = [it["id"] for it in items if " ".join((it.get("title") or "").lower().split()) == want and want]
            best_id = title_matches[0] if len(title_matches) == 1 else None
        if not best_id:
            # Laatste, even harde sleutel: exact de titel die wij zelf in het
            # formulier hebben gezet voor dit platform.
            best_id = job_titles.get(" ".join(title.lower().split())) or None
        if not best_id:
            # Twee even harde, maar veel robuustere sleutels. Zonder deze bleef
            # een advertentie die de gebruiker zélf plaatste (of die op het
            # platform in het Nederlands staat terwijl het dashboard Engels is)
            # ongekoppeld — en dan kan hij bij verkoop nergens automatisch
            # weggehaald worden. Dubbel voorkomende sleutels tellen niet mee, dus
            # liever geen koppeling dan de verkeerde.
            best_id = _sku_index.get(_scan_sku(title)) or _norm_title_index.get(_scan_norm_title(title))

        # Dit item staat aantoonbaar live op dit platform (we hebben zijn kaartje
        # net gezien). Zet dat vast in `listings`, zodat een handmatig geplaatste
        # advertentie in het dashboard ook als "online" telt — voorheen bleef die
        # onbekend en bood de app hem gewoon opnieuw aan om te publiceren.
        if best_id:
            live_links[best_id] = {
                "platform_listing_id": str(platform_listing_id),
                "platform_listing_url": row.get("platform_listing_url"),
                "platform_listed_at": row.get("platform_listed_at"),
            }

        # If this scanned listing already belongs to an item, push the freshly
        # scraped rich data straight into that item's empty fields. This is what
        # makes a re-scan actually enrich already-imported items (description,
        # colour, …) without the user having to re-import anything.
        if best_id:
            try:
                current = items_by_id.get(best_id)
                if current:
                    patch = _backfill_patch(current, row)
                    if patch:
                        # Collect now, write later in one pass — and keep the local
                        # copy in step so a second listing for the same item sees
                        # the fields we're about to fill.
                        backfills[best_id] = {**backfills.get(best_id, {}), **patch}
                        current.update(patch)
            except Exception as e:
                logger.warning(f"Scan store: item backfill failed for {platform_listing_id}: {e}")

        # `photo_urls` (the full ordered list) is the source of truth; keep the
        # single `photo_url` populated too for the old thumbnail/UI path.
        photo_urls = [u for u in (_fix_photo_url(u) for u in (row.get("photo_urls") or [])) if u]
        if not photo_urls and row.get("photo_url"):
            photo_urls = [u for u in [_fix_photo_url(row["photo_url"])] if u]
        photo_url = _fix_photo_url(row.get("photo_url")) or (photo_urls[0] if photo_urls else None)

        base = {
            "user_id": job["user_id"],
            "platform": job["platform"],
            "platform_listing_id": platform_listing_id,
            "platform_listing_url": row.get("platform_listing_url"),
            "title": title,
            "price": row.get("price"),
            "photo_url": photo_url,
            "suggested_item_id": best_id,
            "platform_listed_at": row.get("platform_listed_at"),
            # Keep whatever we already decided; only genuinely new rows start pending.
            #
            # EN "AL GEIMPORTEERD" IS GEEN BESLISSING MEER (05-09-2026, Amanda).
            #
            # Een advertentie die wij zelf zojuist hebben geplaatst of herplaatst
            # heeft een nieuw advertentienummer, dus stond hij hier als "nieuw" en
            # kwam hij op de te-beoordelen lijst. Bij Amanda stonden er zo 117
            # advertenties te wachten, waarvan er 111 allang in haar overzicht
            # stonden. De zes advertenties die ze ECHT zelf op Marktplaats had
            # gezet verdronken daarin, en dat leest als "hij importeert mijn
            # nieuwe advertenties niet".
            #
            # Hangt dit advertentienummer al aan een artikel, dan valt er niets te
            # beslissen: het is gekoppeld. Alleen het nummer telt hier; een
            # gelijkende titel is een vermoeden en geen bewijs.
            "status": prior_status.get(
                str(platform_listing_id),
                "linked" if listings_by_id.get((job["platform"], str(platform_listing_id)))
                else "pending"),
        }
        # Full snapshot columns — only present once the schema migration has run.
        # If they don't exist yet, PostgREST rejects the whole upsert, so retry
        # with just the base fields so scanning never breaks on an un-migrated DB.
        rich = _rijke_velden(row, photo_urls,
                             prior_rich.get(str(platform_listing_id)))
        # is_hidden is the newest optional column, so it gets its own tier: if only
        # THAT one is missing we still want the description/brand/photos to land,
        # instead of dropping every rich field over one absent column.
        hidden = {"is_hidden": bool(row.get("is_hidden"))}
        rows.append({**base, **rich, **hidden})

    # ── Write everything in as few round-trips as possible ────────────────
    # PostgREST upserts a whole list in one request, so a 500-listing wardrobe
    # costs a handful of calls instead of 500. Chunked so no single request grows
    # large enough for the gateway to time out on.
    CHUNK = 100
    bewaard = 0
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        # Optional columns may not exist yet on an un-migrated database. Drop the
        # newest tier first, then the whole rich snapshot — never the base fields.
        for attempt in range(3):
            drop = () if attempt == 0 else (("is_hidden",) if attempt == 1 else RICH_KEYS)
            payload = [{k: v for k, v in r.items() if k not in drop} for r in chunk]
            try:
                db.table("import_candidates").upsert(
                    payload, on_conflict="user_id,platform,platform_listing_id"
                ).execute()
                bewaard += len(chunk)
                break
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"Scan store: is_hidden column missing ({e}); run the import_candidates ALTER migration.")
                elif attempt == 1:
                    logger.warning(f"Scan store: rich upsert failed ({e}); falling back to base fields. Run the import_candidates ALTER migration.")
                else:
                    # NIET stil doorlopen. Dit werd gelogd en verder genegeerd,
                    # dus een mislukte opslag kwam bij de verkoper aan als een
                    # geslaagde scan zonder resultaat — en de volgende scan sloeg
                    # diezelfde advertenties over. Opwerpen, zodat de opdracht op
                    # 'fout' gaat en opnieuw scannen daadwerkelijk helpt.
                    logger.error(f"Scan store: base upsert failed for {len(chunk)} rows: {e}")
                    raise RuntimeError(
                        f"could not save {len(chunk)} of {len(rows)} scanned listings: {e}") from e

    # Item backfills: one update per item that actually gained something, rather
    # than a select+update per scanned listing. On a re-scan most items are
    # already complete, so this is usually a handful of writes.
    for item_id, patch in backfills.items():
        try:
            db.table("items").update(patch).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"Scan store: item backfill failed for {item_id}: {e}")

    # Live-koppelingen: markeer items die we zojuist op het platform zagen als
    # daadwerkelijk online. Een 'sold' rij blijft met rust — die is bewust zo
    # gezet en mag niet terug naar actief.
    platform = job["platform"]
    for item_id, link in live_links.items():
        existing = listing_by_item.get((item_id, platform))
        try:
            if existing:
                if existing.get("status") == "sold":
                    continue
                # EEN LOPENDE HERPLAATSING NIET AANRAKEN (06-09-2026, Daniel).
                #
                # Een herplaatsing zet de rij op 'relisting', haalt de oude
                # advertentie weg en plant de nieuwe 45 min tot 4 uur later. Een
                # scan die vlak daarvoor de garderobe las, ziet het oude
                # advertentienummer nog wél staan — die momentopname is ouder
                # dan de verwijdering. Verwerkte de scan dat hieronder, dan zette
                # hij de rij terug op 'active' met het intussen verwijderde
                # nummer én sloot hij de wachtende herplaatsopdracht af als "al
                # online". Gevolg: het artikel stond nergens meer op Vinted,
                # terwijl het dashboard "nieuwe advertentie staat live" meldde
                # met een link naar een 404. De herplaatsing heeft zijn eigen
                # afhandeling (de recreate-opdracht plus de reddingsronde in
                # relist.py); de scan blijft eraf.
                if existing.get("status") == "relisting":
                    continue
                if (existing.get("status") == "active"
                        and str(existing.get("platform_listing_id") or "") == link["platform_listing_id"]):
                    continue
                # Staat er al een ander advertentienummer op dit item, dan is dit
                # een TWEEDE advertentie van hetzelfde artikel (tien identieke
                # blikjes = tien advertenties). Overschrijven maakte de vorige
                # onvindbaar, en dan kan die bij verkoop nergens weg.
                huidig = str(existing.get("platform_listing_id") or "")
                if huidig and huidig != link["platform_listing_id"]:
                    continue
                db.table("listings").update({
                    "status": "active",
                    "error_message": None,
                    "platform_listing_id": link["platform_listing_id"],
                    "platform_listing_url": link["platform_listing_url"],
                }).eq("id", existing["id"]).execute()
            else:
                db.table("listings").insert({
                    "item_id": item_id,
                    "platform": platform,
                    "status": "active",
                    "platform_listing_id": link["platform_listing_id"],
                    "platform_listing_url": link["platform_listing_url"],
                }).execute()
        except Exception as e:
            logger.warning(f"Scan store: live link failed for {item_id}/{platform}: {e}")

        # We hebben deze advertentie zojuist LIVE gezien. Staat er dan nog een
        # plaatsingsopdracht te wachten (bijvoorbeeld een republicatie die bleef
        # hangen en die de verkoper daarom zelf heeft afgemaakt), dan moet die
        # weg: anders komt er straks alsnog een tweede advertentie bij, en blijft
        # het kaartje "Publishing now…" eeuwig staan.
        try:
            done = (
                db.table("jobs").update({
                    "status": "done",
                    "done_at": datetime.now(timezone.utc).isoformat(),
                    "result": {"note": "already live on the platform (seen by scan)",
                               "platform_listing_id": link["platform_listing_id"],
                               "platform_listing_url": link["platform_listing_url"]},
                })
                .eq("user_id", job["user_id"]).eq("item_id", item_id).eq("platform", platform)
                .eq("action", "create").in_("status", ["pending", "claimed"])
                # Alleen een blijven-hangen directe publicatie afsluiten, nooit
                # een geplande herplaatsing (die draagt een scheduled_for). Die
                # is een bewuste toekomstige actie, geen vastgelopen opdracht —
                # afsluiten liet het artikel van het platform verdwijnen.
                .is_("scheduled_for", "null")
                .execute().data
            )
            if done:
                logger.info("Scan store: closed %d queued publish job(s) for %s/%s — it's already live",
                            len(done), item_id, platform)
        except Exception as e:
            logger.warning(f"Scan store: could not close queued create for {item_id}/{platform}: {e}")

    logger.info(
        "Scan store for user %s: %d/%d candidates upserted, %d items enriched",
        job["user_id"], bewaard, len(rows), len(backfills),
    )


def _queue_scan(db, user_id: str, platform: str):
    """Zet een scan-opdracht klaar (tenzij er al één wacht). Nooit fataal."""
    from backend.api.imports import SCANNABLE_PLATFORMS
    if platform not in SCANNABLE_PLATFORMS:
        return
    try:
        existing = (db.table("jobs").select("id")
                    .eq("user_id", user_id).eq("platform", platform).eq("action", "scan")
                    .in_("status", ["pending", "claimed"]).limit(1).execute().data)
        if existing:
            return
        db.table("jobs").insert({
            "user_id": user_id, "item_id": None, "platform": platform,
            "action": "scan", "status": "pending", "payload": {},
        }).execute()
    except Exception as e:
        logger.warning(f"Could not queue follow-up scan for {platform}: {e}")


# De melding die de bewaker van de extensie achterlaat als het invulscript zich
# nooit heeft gemeld. Dat is geen "de pagina is veranderd": dat is "de pagina die
# openging was het plaatsformulier niet".
_TIJDSOVERSCHRIJDING = re.compile(r"timed out waiting for this .* job to finish", re.I)

# Alle fouten die NIETS over dit ene artikel zeggen: het formulier ging niet open,
# de sessie werd afgewezen, of de wachtrij is al gestopt. Een "vul de foto's in"
# is een uitgelegde fout en hoort hier NIET bij — die zegt wél iets, en drie keer
# dezelfde uitgelegde fout mag geen wachtrij wissen (zie test_kansloze_wachtrij).
#
# GEMETEN (07-09-2026, Egbert Brouwer). Van zijn 671 plaatsopdrachten voor
# 2dehands is er nooit één geslaagd. De laatste tientallen wisselen tussen
# "timed out", "not signed in" en "queue stopped" — drie verschijningsvormen van
# hetzelfde: 2dehands.be laat dit account niet plaatsen via /plaats. De oude rem
# keek alleen naar drie identieke "timed out" op rij en sloeg daardoor over.
_ONDOORGROND = re.compile(
    r"timed out waiting for this .* job to finish"
    r"|not signed in to|je bent niet ingelogd"
    r"|listing form never opened|form never opened|never opened"
    r"|queue stopped|wachtrij .*gestopt|we stopped the .* queue",
    re.I,
)
# Zoveel ondoorgronde mislukkingen zonder ooit één succes: dan is het kanaal
# aantoonbaar kansloos voor dit account, ongeacht de exacte fouttekst.
_KANSLOOS_DREMPEL = 10


# DE BETAALMUUR VAN MARKTPLAATS / 2DEHANDS.
#
# GEMETEN OP 09-09-2026 in de opdrachten van Egbert Brouwer (papas-plectrums).
# Zijn 2dehands liep niet vast op het formulier en niet op zijn inlog. Het
# formulier ging open, werd ingevuld, en na de plaatsklik sprong het tabblad
# naar https://www.2dehands.be/payments/orderOverview/index.html: de advertentie
# werd een bestelregel van EUR 9,00 in plaats van een advertentie. Drie van zijn
# opdrachten dragen dat adres letterlijk in hun foutmelding.
#
# Dit is een andere soort fout dan alle andere hier, en wel om deze reden: elke
# nieuwe poging kost de verkoper geld. De gewone rem zet een kanaal op pauze en
# laat er bewust één proefadvertentie per ronde doorheen, want alleen zo kan een
# pauze zichzelf opheffen. Bij een betaalmuur is die proef juist het probleem:
# hij is niet gratis. Zijn winkelmandje stond op 17 regels, EUR 153,00.
#
# Daarom telt één waarneming, en gaat het kanaal hard dicht in plaats van op
# pauze. Alleen 2dehands of Marktplaats zelf kan dit veranderen, geen nieuwe
# versie van onze extensie.
_BETAALMUUR = re.compile(
    r"(?:marktplaats\.nl|2dehands\.be)/payments/"
    r"|does not let (?:this|your) account place adverts for free",
    re.I,
)


# EEN LEEG ADRESBLOK OP HET FORMULIER, HERKEND AAN DE MELDING ZELF.
#
# Zowel de tekst van de site ("Geen postcode ingevuld",
# "contactInformation.postCode=LEEG") als die van onze eigen weigering
# (wachtOpPostcode in extension/content/shared.js) draagt het woord postcode.
# Meer is er niet nodig, en meer moet het ook niet worden: dit patroon mag niet
# aanslaan op een gewone tekst waarin het woord toevallig voorkomt, daarom
# staat het aan een van deze vaste zinnen vast.
_GEEN_ADRES = re.compile(
    r"postcode is still empty"
    r"|geen postcode ingevuld"
    r"|contactInformation\.postCode"
    r"|geen adres op het formulier",
    re.I,
)


# EEN BETALENDE RUBRIEK IS IETS ANDERS DAN EEN BETAALMUUR OP HET HELE KANAAL.
#
# GEMETEN OP 10-09-2026 in de opdrachten van Egbert Brouwer (papas-plectrums).
# Van zijn bulk naar 2dehands mislukten er 24 met "Je hebt geen zoekertjesvorm
# gekozen". Alle 24 stonden in dezelfde drie gitaarrubrieken (/plaats/728/746,
# /747 en /748), de pagina meldde letterlijk "Dit is een betalende categorie",
# de gratis keuze bestond daar niet ("Free option: knop niet gevonden") en de
# plaatsknop heette "Naar betalen". In diezelfde drie rubrieken lukten de eerste
# twee zoekertjes wél — elektrisch 13:06 en 13:07, akoestisch 13:09 en 13:17,
# bas 13:10 en 13:56 — en pas daarna sloeg het om. Het gratis tegoed van die
# rubriek was op.
#
# HET KANAAL ZELF WERKT DUS GEWOON. Op hetzelfde moment gingen zijn zoekertjes
# in Behuizingen en koffers, Standaards en Toebehoren wél gratis online. Het
# hele kanaal dichtzetten (_BETAALMUUR) zou hier 127 zoekertjes tegenhouden die
# niets kosten. Daarom een eigen rem op alleen die ene rubriek.
#
# Dit herkent ook wat de kopie herkent die NU bij hem draait. Een nieuwe
# extensie is bij een verkoper pas weken later binnen (de Chrome Web Store deed
# er eerder drie weken over), en zijn huidige melding draagt de bewijzen al:
# de zin van de pagina zelf en de naam van de knop.
_BETAALDE_RUBRIEK = re.compile(
    r"betalende (?:categorie|rubriek)"
    r"|cat[ée]gorie payante"
    r"|knop \"(?:Naar betalen|Betalen|Vers le paiement)\""
    r"|charges for an advert in this category",
    re.I,
)


def _kanaal_hard_dicht(db, user_id: str, platform: str) -> bool:
    """Vraagt dit kanaal dit account geld voor een advertentie?

    Eén waarneming is genoeg. Anders dan bij de gewone rem hoeven we hier niets
    af te wegen: een kanaal dat om geld vraagt gaat niet vanzelf weer gratis
    plaatsen, en elke extra poging is een extra bestelregel.
    """
    try:
        rijen = (db.table("jobs").select("result,payload").eq("user_id", user_id)
                 .eq("platform", platform).eq("action", "create")
                 .in_("status", ["error", "cancelled"])
                 .order("created_at", desc=True).limit(120).execute().data or [])
    except Exception:  # noqa: BLE001 — een rem mag nooit op een storing dichtvallen
        return False
    from backend.services.crosslist import _zonder_links  # laat: kringverwijzing
    for j in rijen:
        res = j.get("result") or {}
        tekst = f"{res.get('error') or ''} {res.get('error_oorspronkelijk') or ''}"
        if not _BETAALMUUR.search(tekst):
            continue
        # EEN MISLUKKING MET EEN VERKLAARDE OORZAAK TELT NIET MEE.
        #
        # Elke betaalmuur die we tot nu toe hebben gezien kwam van een
        # advertentie met een webadres in de tekst, en dáár rekende 2dehands
        # voor (zie _zonder_links in crosslist.py). Dat webadres halen we er nu
        # uit vóór we plaatsen, dus die mislukkingen zeggen niets meer over wat
        # we nu zouden versturen. Zouden ze wél meetellen, dan bleef het kanaal
        # dicht om een reden die er niet meer is: precies de muur die we bij de
        # vorige rem al eens hebben moeten slopen.
        #
        # Blijft er een betaalmuur staan bij een advertentie die al schoon was,
        # dan is er iets anders aan de hand (een limiet, een rubriek, een
        # zakelijk account) en gaat het kanaal wél dicht.
        tekstVanAdvertentie = str((j.get("payload") or {}).get("description") or "")
        if tekstVanAdvertentie and _zonder_links(tekstVanAdvertentie) != tekstVanAdvertentie:
            continue
        return True
    return False


def _nooit_gelukt_op(db, user_id: str, platform: str) -> bool:
    """Heeft deze verkoper op dit kanaal ooit iets GEPLAATST gekregen?

    Dit is het verschil tussen "deze ene advertentie liep vast" en "dit kanaal
    heeft bij hem nog nooit gewerkt". Alleen in het tweede geval mogen we de
    hele wachtrij terugnemen.

    ALLEEN create/content_refresh telt (07-09-2026, gemeten bij Egbert Brouwer).
    Hij heeft twee geslaagde 2dehands-SCANS, en op grond daarvan zei deze functie
    "het kanaal heeft ooit gewerkt" — waardoor de rem nooit aansloeg terwijl geen
    van zijn 671 plaatsopdrachten ooit is geslaagd. Een scan is geen plaatsing.
    """
    return not (db.table("jobs").select("id").eq("user_id", user_id)
                .eq("platform", platform).eq("status", "done")
                .in_("action", ["create", "content_refresh"])
                .limit(1).execute().data or [])


def _kansloze_reeks(db, user_id: str, platform: str) -> bool:
    """Drie keer op rij dezelfde stilte, en nog nooit één geslaagde plaatsing.

    GEMETEN (03-09-2026, Egbert Brouwer / papas-plectrums). Hij zette 305
    artikelen klaar voor 2dehands. Op 2dehands was hij niet ingelogd, dus gaf de
    site op het plaatsadres HTTP 401 en ging het formulier nooit open. Elke
    opdracht liep daardoor tegen de bewaker van drie minuten aan: 26 keer
    dezelfde onbegrijpelijke melding, met nog 279 opdrachten erachter. De
    extensie doet met opzet één opdracht tegelijk, dus dat waren zestien uur
    waarin hij verder niets kon publiceren. Zijn woorden: "ik loop compleet vast".

    Drie op rij is de rem: één keer kan pech zijn, drie keer op een kanaal dat
    nog nooit heeft gewerkt is een patroon. Dat kost hem tien minuten in plaats
    van zestien uur.
    """
    laatste = (db.table("jobs").select("status,result").eq("user_id", user_id)
               .eq("platform", platform).eq("action", "create")
               .in_("status", ["done", "error"])
               .order("created_at", desc=True).limit(12).execute().data or [])
    op_rij = 0
    for j in laatste:
        if j.get("status") == "done":
            return False
        if not _TIJDSOVERSCHRIJDING.search(str((j.get("result") or {}).get("error") or "")):
            return False
        op_rij += 1
        if op_rij >= 3:
            break
    return op_rij >= 3 and _nooit_gelukt_op(db, user_id, platform)


def _draaiende_extensieversie(db, user_id: str) -> tuple[int, int, int] | None:
    """Welke kopie van de extensie draait er NU bij deze verkoper.

    Uit de aanwezigheidsstempel, die elke ronde wordt bijgewerkt. None als we
    het niet weten (kolom ontbreekt, nooit gepolst) — en "weet niet" mag nooit
    een reden zijn om iets tegen te houden.
    """
    try:
        rij = (db.table("extension_heartbeat").select("ext_version")
               .eq("user_id", user_id).limit(1).execute().data or [])
    except Exception:  # noqa: BLE001 — een onbekende versie is geen storing
        return None
    return _kopstuk_versie((rij[0] or {}).get("ext_version")) if rij else None


def _verdient_nieuwe_kans(db, user_id: str, platform: str) -> bool:
    """Mag dit kanaal ondanks de rem tóch weer open?

    WAAROM DIT ER IS (08-09-2026, Egbert Brouwer). De rem hieronder was een deur
    die alleen dichtging. Hij slaat aan zolang er nog nooit één plaatsing is
    geslaagd, en hij houdt precies de poging tegen waarmee dat zou kunnen
    veranderen. Gemeten gevolg: na 06-09 21:14 is er voor zijn 2dehands geen
    enkele opdracht meer aangemaakt, ook niet nadat zijn kopie was bijgewerkt van
    1.0.306 naar 1.0.311 — de versie waarin de twee gemeten oorzaken (een
    doorverwijzing naar de inlogpagina die pas ná het injecteren kwam, en pauzes
    die in een verborgen venster stilvielen) juist waren verholpen. Hij klikte
    op publiceren en kreeg de melding van drie dagen eerder terug.

    Een rem die zichzelf nooit meer kan opheffen is geen rem maar een muur.

    De uitweg: elke foutmelding draagt het versiestempel van de extensie die hem
    schreef. Draait er nu een nieuwere kopie dan die alle gestapelde
    mislukkingen maakte, dan zeggen die mislukkingen niets over wat deze kopie
    kan, en krijgt het kanaal een schone start. Weten we de draaiende versie
    niet, of komen de stempels ermee overeen, dan blijft de rem staan.
    """
    draait = _draaiende_extensieversie(db, user_id)
    if not draait:
        return False
    # VRAAG GERICHT OM DE GESTEMPELDE MELDINGEN (08-09-2026, gemeten bij Egbert
    # Brouwer). Een door de rem teruggenomen opdracht draagt de tekst die de
    # SERVER schreef, en daar staat geen versiestempel in. Bij hem waren dat er
    # 622 op rij, dus in elk normaal venster (40, zelfs 200 rijen) was geen
    # enkele versie te zien en greep deze uitweg niet. De stempels zitten op de
    # meldingen die de extensie zelf schreef; die halen we hier expliciet op.
    try:
        rijen = (db.table("jobs").select("result").eq("user_id", user_id)
                 .eq("platform", platform).eq("action", "create")
                 .in_("status", ["error", "cancelled"])
                 .filter("result->>error", "ilike", "%[extensie %")
                 .order("created_at", desc=True).limit(10).execute().data or [])
    except Exception:  # noqa: BLE001 — kan de database het filter niet, dan geen uitweg
        return False
    stempels = [v for v in (
        _extensie_versie((j.get("result") or {}).get("error")) for j in rijen
    ) if v]
    # Geen enkel stempel gevonden: dan weten we niets over de kopie die dit
    # veroorzaakte, en blijft de rem staan (de proefopdracht in crosslist zorgt
    # dat dat nooit een muur wordt).
    return bool(stempels) and draait > max(stempels)


def _kanaal_kansloos(db, user_id: str, platform: str) -> bool:
    """Is dit kanaal aantoonbaar kansloos voor dit account?

    Twee ingangen, allebei vereisen dat er NOOIT één plaatsing is geslaagd:

    1. Drie identieke tijdsoverschrijdingen op rij (`_kansloze_reeks`, ongewijzigd).
    2. Tien of meer ondoorgronde mislukkingen (`_ONDOORGROND`) bij elkaar, ook
       als ze van vorm wisselen. Egbert Brouwer: 671 pogingen voor 2dehands,
       nul geslaagd, met "timed out", "not signed in" en "queue stopped" door
       elkaar. Ingang 1 keek naar drie identieke op rij en zag dit patroon niet.

    Een uitgelegde fout ("vul de foto's in") telt nooit mee: die zegt wél iets
    over dit artikel, en drie ervan mogen geen wachtrij wissen.

    En over alles heen: is de kopie die nu draait niet de kopie die deze
    mislukkingen maakte, dan tellen ze niet meer mee. Zie _verdient_nieuwe_kans.
    """
    # DE BETAALMUUR GAAT VOOR, EN GAAT VOOR ALLES.
    #
    # Bewust vóór _nooit_gelukt_op en vóór _verdient_nieuwe_kans. Een nieuwere
    # kopie van onze extensie is hier geen argument: 2dehands vraagt geld, en
    # daar verandert onze versie niets aan. Zie _kanaal_hard_dicht.
    if _kanaal_hard_dicht(db, user_id, platform):
        return True
    if not _nooit_gelukt_op(db, user_id, platform):
        return False
    recent = (db.table("jobs").select("status,result").eq("user_id", user_id)
              .eq("platform", platform).eq("action", "create")
              .in_("status", ["error", "cancelled"])
              .order("created_at", desc=True).limit(40).execute().data or [])
    ondoorgrond = [
        j for j in recent
        if _ONDOORGROND.search(str((j.get("result") or {}).get("error") or ""))
        # EEN BETALENDE RUBRIEK IS EEN UITGELEGDE FOUT, GEEN RAADSEL.
        # Zonder deze uitzondering zou een verkoper die met tien zoekertjes in
        # één betalende rubriek begint zijn hele kanaal dicht zien gaan, terwijl
        # elke gratis rubriek daarnaast het gewoon doet.
        and not _BETAALDE_RUBRIEK.search(
            f"{(j.get('result') or {}).get('error') or ''} "
            f"{(j.get('result') or {}).get('error_oorspronkelijk') or ''}")
    ]
    if not (len(ondoorgrond) >= _KANSLOOS_DREMPEL
            or _kansloze_reeks(db, user_id, platform)):
        return False
    return not _verdient_nieuwe_kans(db, user_id, platform)


# Het adres waarop de verkoper zelf, in een klik, kan zien of hij is ingelogd.
# GEMETEN op 03-09-2026 met een kale aanvraag zonder cookies: allebei deze
# pagina's antwoorden dan met HTTP 401 en het kale woord "Unauthorized"
# (twaalf bytes). Met een geldige sessie krijg je je advertentieoverzicht. Er
# bestaat dus een test die geen uitleg nodig heeft en niet te misverstaan is,
# en die hoort in de melding zelf te staan in plaats van in een mailwisseling.
_CONTROLEPAGINA = {
    "marktplaats": "https://www.marktplaats.nl/my-account/sell/index.html",
    "2dehands": "https://www.2dehands.be/my-account/sell/index.html",
}


def _melding_geen_adres(platform: str) -> str:
    """Wat de verkoper leest als het adresblok op het formulier leeg bleef.

    EEN LEEG ADRESVELD IS EEN ACCOUNTINSTELLING, GEEN STORING.

    Marktplaats en 2dehands vullen de postcode zelf uit het account van de
    verkoper. Wij typen daar bewust niets in: een verzonnen postcode zet de
    advertentie in een willekeurige gemeente. Blijft het veld leeg, dan weigert
    de extensie te plaatsen (`wachtOpPostcode` in extension/content/shared.js).

    HIER STOND EERST EEN ADVIES DAT NERGENS HEEN LEIDDE (10-09-2026). De vorige
    tekst zei: zet in je account op 2dehands niet een Belgische postcode maar
    "Buitenland", met Nederland en je woonplaats erachter. Die instelling
    bestaat niet. Nagemeten op een ingelogd 2dehands-account (10-09-2026): het
    hele accountmenu heeft zeven onderdelen en geen instellingenscherm voor een
    adres; Profiel > Contactgegevens kent precies drie velden, Naam, Postcode
    (voorbeeld "1234", dus Belgisch) en Telefoonnummer. Marktplaats heeft exact
    hetzelfde scherm, alleen met een Nederlandse postcode erin.

    De keuze tussen binnen- en buitenland zit alleen op het zoekertje zelf. Op
    het plaatsformulier staat "Je locatie: Belgie | Buitenland". Bij Belgie
    staat er een veld contactInformation.postCode dat uit het account wordt
    voorgevuld; klik je Buitenland, dan verdwijnt dat veld en komen er twee
    lege verplichte velden voor terug: select#country en
    contactInformation.foreignCity. Er is bij buitenland geen postcode.

    Dat verklaart ook de vingerafdruk in het aanbod van De Juiste Toon: van zijn
    458 zoekertjes staan er 402 op "Etten-Leur, Nederland", verdeeld over acht
    spellingen van diezelfde woonplaats en een keer Mauritanie. Werd het adres
    onthouden, dan was de spelling elke keer dezelfde geweest. Het wordt per
    zoekertje opnieuw ingetypt, omdat het formulier het elke keer opnieuw vraagt.
    """
    if platform == "2dehands":
        return (
            "Er stond geen adres op het formulier, dus er is niets geplaatst. "
            "2dehands haalt de postcode uit je account op die site, niet uit "
            "Omnivaleur; wij vullen daar bewust niets in, want een verzonnen "
            "postcode zet je advertentie in een willekeurige gemeente.\n\n"
            "Vul die postcode een keer in bij Profiel > Contactgegevens > "
            "Postcode op 2dehands.be. Let op: daar past alleen een Belgische "
            "postcode. Woon je in Nederland, dan is er in je account geen plek "
            "voor je echte adres; de keuze \"Buitenland\" met land en woonplaats "
            "bestaat alleen op het zoekertje zelf, en 2dehands onthoudt die niet. "
            "Zolang wij dat blok niet kunnen invullen, kun je op 2dehands kiezen "
            "tussen een Belgische postcode in je profiel, of dit kanaal uit "
            "laten en daar met de hand plaatsen.\n\n"
            "De rest van je wachtrij voor dit kanaal is gepauzeerd, want elke "
            "volgende advertentie loopt op precies dezelfde lege regel vast. "
            "Zodra er een postcode in je profiel staat, druk je gewoon opnieuw "
            "op publiceren."
        )
    return (
        "Er stond geen adres op het formulier, dus er is niets geplaatst. "
        "Marktplaats haalt de postcode uit je account op die site, niet uit "
        "Omnivaleur; wij vullen daar bewust niets in, want een verzonnen "
        "postcode zet je advertentie in een willekeurige gemeente.\n\n"
        "Vul je postcode een keer in bij Profiel > Contactgegevens > Postcode "
        "op marktplaats.nl, dan vult het formulier zich daarna vanzelf en staat "
        "je woonplaats op al je advertenties hetzelfde.\n\n"
        "De rest van je wachtrij voor dit kanaal is gepauzeerd, want elke "
        "volgende advertentie loopt op precies dezelfde lege regel vast. Zodra "
        "de postcode er staat, druk je gewoon opnieuw op publiceren."
    )


def _melding_formulier_ging_niet_open(platform: str) -> str:
    """Wat de verkoper leest als het plaatsformulier zich nooit meldde.

    HIER STOND EERST EEN CONCLUSIE, EN DIE WAS FOUT (03-09-2026).

    De eerste versie zei het zonder voorbehoud: "That is what it looks like when
    you are not signed in". Het bewijs daarvoor was dat www.2dehands.be op het
    plaatsadres HTTP 401 geeft zolang je niet bent ingelogd. Dat klopt, maar het
    bewijst niets: www.marktplaats.nl doet op precies hetzelfde adres precies
    hetzelfde, en daar publiceert dezelfde verkoper wel. Nagemeten, allebei 401,
    twaalf bytes.

    Egbert Brouwer kreeg die tekst op 275 artikelrijen te zien en mailde terug:
    "Ik ben ingelogd op 2dehands, dus weet niet wat er nu mis gaat?" Hij had
    gelijk. Zijn eigen scan van diezelfde ochtend meldde HTTP 200 op het
    afgeschermde advertentie-overzicht, en dat antwoord krijg je alleen met een
    geldige sessie.

    Wat we wel weten is dit: het tabblad ging open en er kwam nooit een teken
    van leven uit. Dat is de waarneming, en die schrijven we op. Welke van de
    twee oorzaken het is kan hij in een klik zelf zien, en dat staat erbij.
    """
    site = {"marktplaats": "Marktplaats (marktplaats.nl)",
            "2dehands": "2dehands (2dehands.be)"}.get(platform, platform)
    controle = _CONTROLEPAGINA.get(platform, "")
    return (
        f"The {site} listing form never opened: the page never reported back, so nothing was "
        f"filled in and nothing was published. The rest of the queue for {site} has been stopped, "
        f"so it will not keep repeating this for hours.\n\n"
        f"One click tells you which of the two causes it is. Open this page in this browser:\n"
        f"{controle}\n\n"
        f"1. You see your own adverts page. Then you are signed in and the fault is on our side. "
        f"You do not have to wait for us: press publish again. We always send one single test "
        f"listing through, even while this channel is paused, and the extension now records "
        f"every step it takes, so the next message names the exact step it stopped on instead "
        f"of leaving us both guessing.\n"
        f"2. You see the word \"Unauthorized\", or a login screen. Then you are not signed in to "
        f"{site} in this browser. Marktplaats and 2dehands are separate sites with separate "
        f"logins, so being signed in to one does not sign you in to the other. Go there, "
        f"sign in, and publish again."
    )


def _melding_link_uit_advertentie(platform: str) -> str:
    """Wat er op een advertentie staat die op de betaalmuur strandde door een link.

    Dit is een andere boodschap dan _melding_kanaal_vraagt_geld: daar kan de
    verkoper niets aan doen, hier is het opgelost en hoeft hij alleen opnieuw op
    publiceren te klikken. Het verschil hardop zeggen is het hele punt: bij
    Egbert Brouwer stonden er 116 rode regels die naar zijn inlog wezen terwijl
    de oorzaak in zijn advertentietekst zat.
    """
    site = {"marktplaats": "Marktplaats (marktplaats.nl)",
            "2dehands": "2dehands (2dehands.be)"}.get(platform, platform)
    betaalpagina = ("https://www.2dehands.be/payments/orderOverview/index.html"
                    if platform == "2dehands"
                    else "https://www.marktplaats.nl/payments/orderOverview/index.html")
    return (
        f"This one did not go online because the advert text contained your website address. "
        f"{site} charges EUR 9 for an advert with a link in it, so instead of publishing it, it "
        f"put the advert on an order to be paid. Nothing went online and nothing was paid.\n\n"
        f"That is fixed: we now leave the website address and the email address out of adverts "
        f"for {site}. The rest of your text stays exactly as it is, and your other channels are "
        f"not touched. Press publish again and it goes through.\n\n"
        f"One thing left for you: the adverts that ended up on that unpaid order are still there. "
        f"Open this page and remove them with the bin icon, so nothing can be charged:\n"
        f"{betaalpagina}"
    )


def _melding_kanaal_vraagt_geld(platform: str) -> str:
    """Wat de verkoper leest als het kanaal geld vraagt voor elke advertentie.

    Bewust een andere tekst dan de pauze hieronder, want het is een ander
    verhaal: er komt geen proefadvertentie meer, en wachten heeft geen zin.
    """
    site = {"marktplaats": "Marktplaats (marktplaats.nl)",
            "2dehands": "2dehands (2dehands.be)"}.get(platform, platform)
    betaalpagina = ("https://www.2dehands.be/payments/orderOverview/index.html"
                    if platform == "2dehands"
                    else "https://www.marktplaats.nl/payments/orderOverview/index.html")
    return (
        f"{site} does not let your account place adverts for free: it puts every advert on an "
        f"order to be paid instead of publishing it. That is why nothing has ever gone online "
        f"there. This is not a rejection of this item, and nothing has been paid.\n\n"
        f"{site} is switched off for your account, so we do not add anything else to that order. "
        f"Open this page and remove the unpaid lines with the bin icon:\n{betaalpagina}\n\n"
        f"Your other channels keep working and your items stay ready here. As soon as {site} "
        f"lets your account place adverts for free, tell us and we switch the channel back on."
    )


def _rubrieknaam(fouttekst: str, rubriek: str | None) -> str:
    """De rubriek zoals de VERKOPER hem kent, niet zoals wij hem opslaan.

    Onze eigen naam is een sleutel ("muziek snaarinstrumenten gitaren
    elektrisch"); dat leest als een foutcode. Het plaatsformulier zet zijn eigen
    naam boven aan de pagina ("Gekozen categorie Muziek en Instrumenten Gitaren |
    Elektrisch Wijzigen") en die staat al in de melding die de extensie meestuurt.
    Die heeft dus altijd voorrang.
    """
    m = re.search(r"Gekozen categorie\s+(.{2,80}?)\s+Wijzigen", fouttekst or "")
    if m:
        return " ".join(m.group(1).split())
    slug = " ".join(str(rubriek or "").split())
    return slug[:1].upper() + slug[1:] if slug else ""


def _melding_rubriek_vraagt_geld(platform: str, rubriek: str | None) -> str:
    """Wat de verkoper leest als één rubriek geld vraagt en de rest gratis blijft.

    Bewust een andere tekst dan _melding_kanaal_vraagt_geld: daar staat het hele
    kanaal uit, hier gaat alles buiten deze rubriek gewoon door. Dat verschil
    moet erin staan, anders leest hij "2dehands doet het niet" terwijl er op
    hetzelfde moment zoekertjes van hem online gaan.
    """
    site = {"marktplaats": "Marktplaats (marktplaats.nl)",
            "2dehands": "2dehands (2dehands.be)"}.get(platform, platform)
    naam = f'"{rubriek}"' if rubriek else "this category"
    return (
        f"{site} charges for adverts in {naam}: the site says this is a paid category, and it now "
        f"puts every next advert there on an order to be paid instead of publishing it. Nothing "
        f"was published, nothing was ordered, and we never click a payment button for you.\n\n"
        f"We have taken the rest of your queue for {naam} back, so it does not fail one item at a "
        f"time. Everything you have queued for other categories on {site} keeps going as normal.\n\n"
        f"Want these online anyway? Either place them yourself on {site} and pay per advert, or "
        f"move the items to a category that is free there."
    )


def _melding_kanaal_op_pauze(platform: str) -> str:
    """Wat de verkoper leest als de rem dit kanaal op pauze heeft gezet.

    WAAROM DIT EEN EIGEN TEKST IS (08-09-2026). Hier werd de melding van de
    laatste mislukking hergebruikt, dus las Egbert Brouwer bij elke nieuwe klik
    de fout van drie dagen eerder terug, met een controle die hij toen al had
    gedaan. Dat leest als "er is niets veranderd", terwijl er wél iets is
    veranderd: er staat nu een pauze, en er gaat één test doorheen.
    """
    site = {"marktplaats": "Marktplaats (marktplaats.nl)",
            "2dehands": "2dehands (2dehands.be)"}.get(platform, platform)
    return (
        f"{site} is on hold for your account: every publish so far has failed there and not one "
        f"has ever gone through, so we are not queueing hundreds more. This is not a rejection of "
        f"this item.\n\n"
        f"One test listing IS being sent to {site} right now. If it goes through, the hold lifts "
        f"by itself and everything else follows. If it fails, the message on that one item names "
        f"the step it stopped on."
    )


def _rechtgezette_foutmelding(job: dict | None, body: dict, versie, kansloos: bool = False) -> dict:
    """Welke foutmelding de verkoper te zien krijgt bij een mislukte opdracht.

    Los van de database gehouden zodat hij te testen is — deze tekst is precies
    wat een klant dagenlang de verkeerde kant op stuurde.

    Twee rechtzettingen, in deze volgorde, en die volgorde is het hele punt:

    1. WETEN WE DAT DE KOPIE TE OUD IS, DAN IS DAT HET ANTWOORD.
       Dit stond er niet, en dat kostte twee klanten samen ruim dertig
       foutmeldingen die de verkeerde kant op wezen. Nagemeten in het
       opdrachtenlogboek op 29-08-2026:
         Dennis (info@retrogameking.com)   14 mislukte scans vanaf 1.0.217/218
         Egbert (info@papas-plectrums.nl)  11 mislukte scans vanaf 1.0.200/202/207
       Beiden kregen "je bent niet ingelogd", en Egbert daarna "zet Admarkt aan"
       — terwijl de server uit hun eigen versiestempel wist dat het aan de kopie
       lag. Die wetenschap werd weggegooid zodra de twee herkansingen op waren.
       Beiden zijn dagenlang hun inlog blijven controleren.
       Dit geldt voor elk platform en elke soort opdracht; de herkansing in
       fail_job blijft beperkt tot een scan, want een halve publicatie opnieuw
       uitdelen is een ander risico. Een verkeerd antwoord is overal even schadelijk.

    2. Tot 1.0.259 meldde de extensie bij een lege Marktplaats-scan altijd "je
       bent niet ingelogd". Voor een zakelijke verkoper is dat aantoonbaar
       onjuist: zijn persoonlijke overzicht IS leeg, zijn advertenties staan in
       Admarkt, en het enige wat helpt is de Admarkt-schakelaar aanzetten. Een
       nieuwe extensie staat pas dagen later bij hem op de computer, dus zetten
       we die tekst hier recht voor iedereen die nog een oudere kopie draait.
    """
    fout = str((body or {}).get("error") or "")
    # 0. DE BETAALMUUR BLIJFT STAAN ZOALS HIJ IS.
    #
    # Deze melding is de enige hier die op een GEMETEN adres berust: het
    # tabblad kwam aantoonbaar uit op /payments/. Elke rechtzetting hieronder is
    # een gok die het beter denkt te weten, en precies zo'n gok maakte hier drie
    # weken lang "je bent misschien niet ingelogd" van. Niet meer aankomen.
    if _BETAALMUUR.search(fout) or _BETAALDE_RUBRIEK.search(fout):
        return dict(body or {})
    # 3. HET FORMULIER GING NOOIT OPEN — zie _kansloze_reeks.
    #    Bewust vóór de rest: dit is de enige rechtzetting die weet dat het
    #    kanaal bij deze verkoper nog nooit heeft gewerkt, en dat weegt zwaarder
    #    dan elke gok over wat er in het formulier is misgegaan.
    if kansloos and (job or {}).get("action") == "create" and _ONDOORGROND.search(fout):
        return {**(body or {}), "error_oorspronkelijk": fout,
                "error": _melding_formulier_ging_niet_open((job or {}).get("platform") or "")}
    if versie and versie < MINIMALE_SCANVERSIE:
        return {**(body or {}), "error_oorspronkelijk": fout, "error": (
            f"Deze opdracht is opgepakt door een verouderde kopie van de "
            f"Omnivaleur-extensie (versie {'.'.join(map(str, versie))}; nodig is "
            f"minstens {'.'.join(map(str, MINIMALE_SCANVERSIE))}). Die kopie kan dit "
            f"werk niet afmaken, en wat ze meldt over inloggen klopt niet. Open "
            f"chrome://extensions, zet \"Ontwikkelaarsmodus\" aan en verwijder elke "
            f"met de hand geladen kopie van Omnivaleur; laat alleen de versie uit "
            f"de Chrome Web Store staan en herstart Chrome.")}
    _stil = _kopie_staat_stil(versie) if versie else None
    if _stil:
        achter, gepubliceerd = _stil
        return {**(body or {}), "error_oorspronkelijk": fout, "error": (
            f"Deze opdracht is opgepakt door een kopie van de Omnivaleur-extensie "
            f"die zichzelf niet bijwerkt: versie {'.'.join(map(str, versie))}, terwijl "
            f"{gepubliceerd} in de Chrome Web Store staat ({achter} versies "
            f"achterstand). Chrome werkt een kopie uit de Web Store elke paar uur "
            f"bij, dus deze is met de hand geladen. Open chrome://extensions, "
            f"verwijder elke Omnivaleur die er staat, en installeer hem opnieuw uit "
            f"de Chrome Web Store. Alles wat hierna misgaat is met die kopie niet "
            f"te verhelpen.")}
    # EEN LEEG ADRESVELD OP 2DEHANDS IS EEN ACCOUNTINSTELLING, GEEN STORING.
    #
    # 2dehands.be vult alleen de postcode uit het account; wij typen daar bewust
    # niets in, want een verzonnen postcode zet de advertentie in een
    # willekeurige Belgische gemeente. Is het veld leeg, dan weigert de extensie
    # te plaatsen.
    #
    # LET OP, DIT IS NAGEMETEN OP 10-09-2026 EN NIET WAT HIER EERST STOND: het
    # account biedt geen buitenland-adres aan. Profiel > Contactgegevens kent
    # drie velden (Naam, Postcode met voorbeeld "1234", Telefoonnummer) en het
    # accountmenu heeft verder geen instellingenscherm. De keuze
    # "Belgie | Buitenland" bestaat alleen op het zoekertje: bij Belgie het veld
    # contactInformation.postCode uit het account, bij Buitenland verdwijnt dat
    # veld en komen select#country en contactInformation.foreignCity ervoor in de
    # plaats, allebei leeg en verplicht. Wie in Nederland woont kan dus niets in
    # zijn account zetten dat hier helpt; verwijs hem daar niet naar toe.
    #
    # Toon (dejuistetoon, 05-09 en 07-09-2026) vroeg er twee keer naar: "adres
    # niet in Essen maar in Nederland". Zijn 402 zoekertjes op "Etten-Leur,
    # Nederland" staan in acht spellingen: het formulier onthoudt het
    # buitenlandblok niet, hij typt het elke keer opnieuw.
    if _GEEN_ADRES.search(fout) and (job or {}).get("platform") in ("2dehands", "marktplaats"):
        return {**(body or {}), "error_oorspronkelijk": fout,
                "error": _melding_geen_adres((job or {}).get("platform") or "")}
    if ((job or {}).get("action") == "scan"
            and (job or {}).get("platform") == "marktplaats"
            and "appear to be signed in" in fout):
        return {**(body or {}), "error_oorspronkelijk": fout, "error": (
            "Je persoonlijke advertentieoverzicht op Marktplaats is leeg. Bij een "
            "zakelijk account hoort dat zo: die advertenties staan in Admarkt, met "
            "een eigen inlog. Klik op het Omnivaleur-icoon in je browserbalk en zet "
            "\"Business account (Admarkt)\" aan, en start de scan opnieuw. Heb je een "
            "gewoon particulier account, controleer dan of je op Marktplaats zelf "
            "bent ingelogd.")}
    return body or {}


@router.post("/{job_id}/error")
def fail_job(job_id: str, body: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    _record_extension_heartbeat(db, user_id)  # only the extension reports job errors
    job = eerste_rij(db.table("jobs").select("item_id,platform,action,payload").eq("id", job_id).eq("user_id", user_id).limit(1).execute())

    # Een scan die door een verouderde kopie van de extensie is opgepakt telt
    # niet als mislukt: die kopie kán het werk gewoon niet. Terug in de wachtrij,
    # zodat de bijgewerkte kopie hem alsnog oppakt. Zie MINIMALE_SCANVERSIE.
    versie = _extensie_versie(body.get("error"))
    if job and job["action"] == "scan" and versie and versie < MINIMALE_SCANVERSIE:
        payload = dict(job.get("payload") or {})
        pogingen = int(payload.get("_oude_extensie_pogingen") or 0)
        if pogingen < MAX_HERKANSING_OUDE_EXTENSIE:
            payload["_oude_extensie_pogingen"] = pogingen + 1
            payload["_oude_extensie_versie"] = ".".join(map(str, versie))
            execute_with_retry(db.table("jobs").update({
                "status": "pending", "payload": payload, "claimed_at": None,
            }).eq("id", job_id))
            logger.info("Scan %s geweigerd door extensie %s (te oud) — terug in de wachtrij (%d/%d)",
                        job_id, payload["_oude_extensie_versie"], pogingen + 1,
                        MAX_HERKANSING_OUDE_EXTENSIE)
            return {"ok": True, "requeued": True, "reason": "outdated_extension"}

    # Alleen navragen als het er echt toe doet: een ondoorgronde mislukking op een
    # publicatie (tijdsoverschrijding, inlogverwijt, wachtrij gestopt). Anders is
    # dit een extra databasevraag bij elke foutmelding.
    kansloos = False
    if (job and job.get("action") == "create"
            and _ONDOORGROND.search(str((body or {}).get("error") or ""))):
        try:
            kansloos = _kanaal_kansloos(db, user_id, job.get("platform") or "")
        except Exception:
            logger.warning("kansloze reeks niet vast te stellen voor %s", job_id)
    body = _rechtgezette_foutmelding(job, body, versie, kansloos)

    # DE BETAALMUUR STOPT DE RIJ METEEN, EN VANAF DE SERVER.
    #
    # Dit hoort hier en niet alleen in de extensie. Een nieuwe extensie is bij
    # deze verkoper pas over weken binnen (de Chrome Web Store deed er eerder
    # drie weken over), en tot die tijd is dit de enige plek die het kán zien.
    # Het bewijs zit al in de melding die zijn huidige kopie stuurt: die zet het
    # adres van het tabblad erbij, en dat adres was /payments/orderOverview.
    #
    # En het moet meteen gebeuren, niet na een drempel van drie of tien. Elke
    # volgende opdracht in die rij is opnieuw EUR 9,00 in een bestelling waar
    # niemand om heeft gevraagd. Zie _kanaal_hard_dicht.
    if (job and job.get("action") in ("create", "content_refresh")
            and job.get("platform") in ("marktplaats", "2dehands")
            and _BETAALMUUR.search(str((body or {}).get("error") or ""))):
        try:
            reden = _melding_kanaal_vraagt_geld(job.get("platform") or "")
            body = {**body,
                    "error_oorspronkelijk": body.get("error_oorspronkelijk") or body.get("error"),
                    "error": reden}
            aantal = _stop_wachtrij(db, user_id, job["platform"], reden)
            _gelijk_de_kansloze_muur(db, user_id, job["platform"], reden)
            logger.warning("Betaalmuur op %s bij %s: %d wachtende opdrachten teruggenomen",
                           job["platform"], user_id, aantal)
        except Exception:  # noqa: BLE001 — een fout hier mag de foutmelding niet opeten
            logger.warning("Betaalmuur: wachtrij niet teruggenomen voor %s/%s",
                           user_id, job.get("platform"))

    # EEN BETALENDE RUBRIEK STOPT ALLEEN DIE RUBRIEK.
    #
    # Zie _BETAALDE_RUBRIEK voor de meting. Dit moet hier op de server staan en
    # niet alleen in de extensie: de kopie die nu bij deze verkoper draait meldt
    # de bewijzen al ("Dit is een betalende categorie", knop "Naar betalen"),
    # en een nieuwe extensie is bij hem pas weken later binnen.
    #
    # Bewust NA de betaalmuur-controle en met een uitsluiting erop: staat het
    # hele kanaal al op slot, dan is dat het zwaardere en juistere antwoord.
    fouttekst_nu = str((body or {}).get("error") or "")
    if (job and job.get("action") in ("create", "content_refresh")
            and job.get("platform") in ("marktplaats", "2dehands")
            and not _BETAALMUUR.search(fouttekst_nu)
            and _BETAALDE_RUBRIEK.search(fouttekst_nu)):
        try:
            rubriek = str(((job.get("payload") or {}).get("category") or "")).strip()
            reden = _melding_rubriek_vraagt_geld(
                job["platform"], _rubrieknaam(fouttekst_nu, rubriek) or None)
            body = {**body,
                    "error_oorspronkelijk": body.get("error_oorspronkelijk") or body.get("error"),
                    "error": reden}
            # Zonder rubriek valt er niets gericht te stoppen. Dan blijft het bij
            # deze ene uitgelegde melding: de hele rij terugnemen op grond van
            # één zoekertje in een onbekende rubriek zou meer kapotmaken dan het
            # oplost.
            aantal = (_stop_wachtrij(db, user_id, job["platform"], reden, rubriek=rubriek)
                      if rubriek else 0)
            logger.warning("Betalende rubriek op %s (%s) bij %s: %d wachtende opdrachten teruggenomen",
                           job["platform"], rubriek or "onbekend", user_id, aantal)
        except Exception:  # noqa: BLE001 — een rem mag de foutmelding niet opeten
            logger.warning("Betalende rubriek: wachtrij niet teruggenomen voor %s/%s",
                           user_id, job.get("platform"))

    # EEN LEEG ADRESBLOK STOPT DE RIJ VOOR DAT KANAAL.
    #
    # GEMETEN 10-09-2026, De Juiste Toon: "ik ben nu ook op tweedehands aan het
    # plaatsen, die komen niet door zoals die van mp wel doen". Tussen 18:00 en
    # 18:03 mislukten zes plaatsingen op 2dehands achter elkaar met dezelfde
    # reden (het adresblok bleef leeg), en er stonden er nog tien te wachten die
    # allemaal op precies dezelfde regel zouden vastlopen. Elke poging houdt zijn
    # browser twee minuten bezig en schrijvende opdrachten gaan één voor één, dus
    # dat is een half uur waarin er niets anders kan.
    #
    # Het adres komt uit zijn account op die site en verandert niet doordat wij
    # het nog een keer proberen. Eén uitgelegde melding en de rij op pauze is dus
    # het hele juiste antwoord; publiceren zet hem weer aan. Zelfde afweging als
    # bij de betaalmuur hierboven, en om dezelfde reden op de server: een nieuwe
    # extensie is bij een verkoper pas weken later binnen.
    if (job and job.get("action") in ("create", "content_refresh")
            and job.get("platform") in ("marktplaats", "2dehands")
            and not _BETAALMUUR.search(fouttekst_nu)
            and _GEEN_ADRES.search(
                f"{fouttekst_nu} {(body or {}).get('error_oorspronkelijk') or ''}")):
        try:
            reden = _melding_geen_adres(job.get("platform") or "")
            body = {**body,
                    "error_oorspronkelijk": body.get("error_oorspronkelijk") or body.get("error"),
                    "error": reden}
            aantal = _stop_wachtrij(db, user_id, job["platform"], reden)
            logger.warning("Leeg adresblok op %s bij %s: %d wachtende opdrachten teruggenomen",
                           job["platform"], user_id, aantal)
        except Exception:  # noqa: BLE001 — een rem mag de foutmelding niet opeten
            logger.warning("Leeg adres: wachtrij niet teruggenomen voor %s/%s",
                           user_id, job.get("platform"))

    # Deze vier bijwerkingen MOETEN aankomen. Viel de verbinding met de database
    # weg, dan kreeg de extensie een 500 terug en bleef de opdracht op "claimed"
    # staan — waarna de hele wachtrij stilstond en de verkoper zag dat "hij niks
    # doet". Gemeten op 30-08-2026: twee van deze fouten binnen tien minuten.
    # Herhalen mag hier, want het zijn vaste waarden op één opdracht: twee keer
    # hetzelfde wegschrijven verandert niets. Bij een insert zou dat wél een
    # tweede rij opleveren; die blijven daarom met rust.
    execute_with_retry(db.table("jobs").update({
        "status": "error",
        "result": body,
        "done_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id))
    # A content-refresh or relist-delete bumped the listing's cooldown + daily
    # quota at enqueue time; since the job failed, give both back.
    rollback = ((job or {}).get("payload") or {}).get("_refresh_rollback")
    if rollback:
        from backend.services.relist import rollback_refresh
        rollback_refresh(rollback, user_id)
    if job and job["action"] == "create":
        execute_with_retry(db.table("listings").update({
            "status": "error",
            "error_message": body.get("error", "Extension reported failure"),
        }).eq("item_id", job["item_id"]).eq("platform", job["platform"]).eq("status", "pending"))
        # EEN MISLUKTE HERPLAATSING MOET OOK TE ZIEN ZIJN (03-09-2026, Amanda).
        #
        # De regel hierboven raakt alleen een rij die op 'pending' staat — dat is
        # een eerste publicatie. Bij een herplaatsing is de oude advertentie op
        # dit moment al weggehaald en staat die rij op 'delisted'. Er werd dus
        # NERGENS iets vastgelegd: het artikel had geen advertentie meer, geen
        # foutmelding, geen bolletje, niets. Precies haar melding: "dan zie ik
        # vervolgens niks in het overzicht bij mp, terwijl hij wel aangeeft een
        # nieuwe advertentie te hebben geplaatst." Gemeten bij haar: elf
        # artikelen in die stille toestand.
        #
        # De status wordt 'error' en niet 'active', want de advertentie is er
        # echt niet meer; 'active' zou hem ook meteen weer kandidaat maken voor
        # de volgende herplaatsronde. Alleen de rij die bij DEZE herplaatsing
        # hoort, via dezelfde weg als bij een mislukte verwijdering.
        _meld_mislukte_herplaatsing(db, user_id, job,
                                    body.get("error", "Extension reported failure"))
        # DE REST VAN DE RIJ HEEFT GEEN KANS MEER.
        #
        # Dit hoort hier en niet alleen in de extensie: een reparatie in de
        # extensie bereikt een verkoper pas nadat Google hem heeft goedgekeurd
        # en Chrome hem heeft opgehaald — bij Egbert duurde dat drie weken.
        # Hier werkt hij vandaag, ook op de kopie die nu bij hem draait.
        if kansloos:
            reden = _melding_formulier_ging_niet_open(job["platform"])
            _stop_wachtrij(db, user_id, job["platform"], reden)
            # De wachtrij stoppen raakt alleen wat nóg wacht. Wie al tientallen
            # rode balken had (Egbert: tien zichtbaar, honderden eerder) keek
            # daarna tegen een muur van verschillende onbegrijpelijke teksten aan.
            # Zet die allemaal op deze ene, uitgelegde reden.
            _gelijk_de_kansloze_muur(db, user_id, job["platform"], reden)
        # Een mislukte publicatie betekent vaak dat de gebruiker het formulier
        # zelf heeft afgemaakt. Plan meteen een scan in, zodat de app binnen
        # enkele minuten zelf ziet dat de advertentie tóch online staat in
        # plaats van te wachten op de volgende ronde.
        _queue_scan(db, user_id, job["platform"])
    elif job and job["action"] == "delete":
        # A failed delist means NOTHING was removed — the listing is still live on
        # the platform. Setting it to "error" hid it from the dashboard's active
        # views, so it looked deleted while it was actually still up (and, for a
        # relist, left the item in limbo). Keep it "active" (its true state) and
        # attach a visible message so the UI can offer a retry instead of hiding it.
        #
        # ALLEEN DE ADVERTENTIE DIE DEZE OPDRACHT TE PAKKEN HAD (01-09-2026).
        # Dit werkte élke rij van dat artikel op dat kanaal bij, en daar zijn er
        # inmiddels tot zes van — één per eerdere herplaatsing. Eén mislukte
        # verwijdering zette ze dus allemaal terug op 'actief', mét hun oude
        # plaatsingsdatum, waarna het automatisch herplaatsen ze meteen weer
        # oppakte. Dat is de lus waardoor (1288) en (1314) dagelijks opnieuw
        # geplaatst werden. Bovendien wiste het een al gestelde vraag
        # "is dit verkocht?" weer uit. Zie _verwijderdoelen.
        melding = body.get("error", "Delist failed — the listing is still live. You can retry.")
        for rij in _verwijderdoelen(db, job):
            if rij.get("status") in ("sold", "sold_unconfirmed"):
                continue
            execute_with_retry(db.table("listings").update({
                "status": "active",
                "error_message": melding,
            }).eq("id", rij["id"]))
    return {"ok": True}


# Vanaf deze versie kan de extensie een advertentie zonder vraagprijs plaatsen
# (ze zet de advertentievorm dan op "Bieden"). Zie extension/content/shared.js,
# mpPrijsvorm. Dit is GEEN nieuwe ondergrens: alles wat een prijs heeft blijft op
# elke kopie gewoon werken.
KAN_BIEDEN_VANAF = (1, 0, 285)


def _herplaatsing_kansloos(db, user_id: str, verwijderopdracht: dict,
                           versie: tuple | None) -> str | None:
    """Zou de plaatsing die bij DEZE verwijdering hoort zeker mislukken?

    WAAROM DIT ER IS (03-09-2026, Amanda Haas). Van haar 479 artikelen hebben er
    179 geen vraagprijs: op Marktplaats staan die als "Bieden". Een kopie van de
    extensie van vóór 1.0.285 vult dan een leeg prijsveld in bij "Vraagprijs",
    waarop Marktplaats weigert met "Geen prijs ingevuld". Op dat moment is de
    oude advertentie al weg — elf van haar advertenties waren zo verdwenen.

    De reparatie zit in de extensie, maar die bereikt haar pas nadat de Chrome
    Web Store hem heeft goedgekeurd; bij een eerdere klant duurde dat drie weken.
    Deze rem staat daarom hier: draait er nog een oudere kopie, dan gaat de
    verwijdering niet door en blijft de advertentie gewoon staan. Zodra de
    bijgewerkte kopie draait, loopt alles weer zoals bedoeld.

    Een onbekende versie telt als oud: kopieën van vóór 1.0.250 sturen hun
    versie niet mee, en die kunnen dit zeker niet.
    """
    if verwijderopdracht.get("platform") not in ("marktplaats", "2dehands"):
        return None
    if versie is not None and versie >= KAN_BIEDEN_VANAF:
        return None
    try:
        paar = (db.table("jobs").select("id,payload")
                .eq("user_id", user_id).eq("item_id", verwijderopdracht["item_id"])
                .eq("platform", verwijderopdracht["platform"]).eq("action", "create")
                .eq("status", "pending")
                .gte("created_at", verwijderopdracht["created_at"])
                .order("created_at").limit(1).execute().data or [])
    except Exception as e:  # noqa: BLE001 — een rem mag nooit de uitgifte omgooien
        logger.warning("kon de gepaarde plaatsing niet nakijken voor %s: %s",
                       verwijderopdracht.get("id"), e)
        return None
    if not paar:
        return None                      # losse verwijdering, geen herplaatsing
    prijs = (paar[0].get("payload") or {}).get("price")
    try:
        heeft_prijs = float(prijs) > 0
    except (TypeError, ValueError):
        heeft_prijs = False
    if heeft_prijs:
        return None
    return ("Relist skipped: this listing has no asking price (it runs as \"Bieden\" on "
            "Marktplaats), and the extension on this computer cannot publish that yet. "
            "Your listing is untouched and still live. Update the Omnivaleur extension "
            "and it will refresh on the next round.")


def _neem_herplaatsing_terug(db, verwijderopdracht: dict, now: str, reden: str) -> None:
    """Verwijdering én de bijbehorende plaatsing terugnemen, advertentie blijft staan."""
    ids = [verwijderopdracht["id"]]
    try:
        paar = (db.table("jobs").select("id")
                .eq("user_id", verwijderopdracht["user_id"])
                .eq("item_id", verwijderopdracht["item_id"])
                .eq("platform", verwijderopdracht["platform"]).eq("action", "create")
                .eq("status", "pending")
                .gte("created_at", verwijderopdracht["created_at"])
                .order("created_at").limit(1).execute().data or [])
        ids += [r["id"] for r in paar]
    except Exception as e:  # noqa: BLE001
        logger.warning("gepaarde plaatsing niet gevonden bij het terugnemen: %s", e)
    for job_id in ids:
        try:
            db.table("jobs").update({
                "status": "cancelled", "result": {"cancelled": reden}, "done_at": now,
            }).eq("id", job_id).execute()
        except Exception as e:  # noqa: BLE001
            logger.warning("opdracht %s niet teruggenomen: %s", job_id, e)

    # De verversbeurt en het dagquotum teruggeven: er is niets ververst.
    rollback = (verwijderopdracht.get("payload") or {}).get("_refresh_rollback")
    if rollback:
        try:
            from backend.services.relist import rollback_refresh
            rollback_refresh(rollback, verwijderopdracht["user_id"])
        except Exception as e:  # noqa: BLE001
            logger.warning("verversbeurt niet teruggedraaid: %s", e)

    # De advertentie stond op 'relisting' vanaf het inplannen. Er is niets
    # weggehaald, dus 'active' is de waarheid — en de melding erbij, anders is
    # het een stille niet-gebeurtenis.
    for rij in _verwijderdoelen(db, verwijderopdracht):
        if rij.get("status") in ("sold", "sold_unconfirmed"):
            continue
        try:
            db.table("listings").update({
                "status": "active", "error_message": reden,
            }).eq("id", rij["id"]).execute()
        except Exception as e:  # noqa: BLE001
            logger.warning("advertentie %s niet teruggezet: %s", rij.get("id"), e)
    logger.info("Herplaatsing teruggenomen voor item %s op %s: %s",
                verwijderopdracht.get("item_id"), verwijderopdracht.get("platform"), reden)


def _meld_mislukte_herplaatsing(db, user_id: str, job: dict, melding: str) -> int:
    """De weggehaalde advertentie van een mislukte herplaatsing zichtbaar maken.

    Was dit een herplaatsing (er hoort een geslaagde verwijdering bij die vlak
    hiervoor liep), dan is de oude advertentie weg en is er geen nieuwe gekomen.
    Zonder deze regel blijft dat artikel achter zonder advertentie én zonder
    uitleg — een doodlopende straat in het scherm.
    """
    try:
        paar = (db.table("jobs").select("id,item_id,platform,payload,status,created_at")
                .eq("user_id", user_id).eq("item_id", job["item_id"])
                .eq("platform", job["platform"]).eq("action", "delete")
                .lte("created_at", job["created_at"])
                .order("created_at", desc=True).limit(1).execute().data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("mislukte herplaatsing niet te melden voor %s: %s", job.get("id"), e)
        return 0
    if not paar or paar[0].get("status") != "done":
        return 0                      # geen herplaatsing, of er is niets weggehaald

    uitleg = (f"{melding} — the old listing was already removed for this refresh, "
              f"so this item is not live here right now. Publish it again, or mark "
              f"it as listed if you finished the form yourself.")
    geraakt = 0
    for rij in _verwijderdoelen(db, paar[0]):
        if rij.get("status") in ("sold", "sold_unconfirmed", "active"):
            continue                  # verkocht of tóch nog live: afblijven
        execute_with_retry(db.table("listings").update({
            "status": "error",
            "error_message": uitleg,
        }).eq("id", rij["id"]))
        geraakt += 1
    return geraakt


def _stop_wachtrij(db, user_id: str, platform: str, reden: str,
                   rubriek: str | None = None) -> int:
    """Neem alles terug wat nog voor dit kanaal in de wachtrij staat.

    `rubriek` maakt er een gerichte rem van: dan blijft alleen wat in DIE
    rubriek staat achterwege en gaat de rest van het kanaal gewoon door. Zie
    _BETAALDE_RUBRIEK — een rubriek die geld kost zegt niets over de rubrieken
    die gratis zijn, en die van iemand afnemen is schade in plaats van hulp.
    """
    wachtend = db.table("jobs").select("id,item_id,action,payload").eq(
        "user_id", user_id).eq("platform", platform).eq("status", "pending").execute().data or []
    if rubriek is not None:
        doel = str(rubriek or "").strip().lower()
        wachtend = [j for j in wachtend
                    if str(((j.get("payload") or {}).get("category") or "")).strip().lower() == doel]
    if not wachtend:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    ids = [j["id"] for j in wachtend]
    # Per brok bijwerken: boven ongeveer 640 id's breekt PostgREST het verzoek
    # stil af op de lengte van de URL. Zie de kennisbank; dat heeft eerder
    # scans, verkoopcontrole en herplaatsen kapotgemaakt.
    for i in range(0, len(ids), 200):
        execute_with_retry(db.table("jobs").update({
            "status": "cancelled",
            "result": {"cancelled": "queue stopped", "error": reden},
            "done_at": now,
        }).in_("id", ids[i:i + 200]))

    # De advertentierijen die op deze opdrachten stonden te wachten horen niet
    # op "bezig" te blijven staan: er is niets geplaatst. Met de reden erbij,
    # want een leeg foutveld leest als een raadsel.
    item_ids = sorted({j["item_id"] for j in wachtend
                       if j.get("action") == "create" and j.get("item_id")})
    for i in range(0, len(item_ids), 200):
        execute_with_retry(db.table("listings").update({
            "status": "error", "error_message": reden,
        }).in_("item_id", item_ids[i:i + 200]).eq("platform", platform).eq("status", "pending"))

    # Een herplaatsing leende bij het inplannen alvast uit de dagteller en de
    # afkoeltijd. De ronde gaat niet door, dus dat gaat terug.
    from backend.services.relist import rollback_refresh
    for j in wachtend:
        rollback = (j.get("payload") or {}).get("_refresh_rollback")
        if rollback:
            try:
                rollback_refresh(rollback, user_id)
            except Exception:
                logger.warning("stop-wachtrij: teruggeven van de herplaatsteller mislukt voor %s", j["id"])

    logger.warning("stop-wachtrij: %d opdrachten voor %s teruggenomen bij %s (%s)",
                   len(ids), platform, user_id, reden[:120])
    return len(ids)


def _gelijk_de_kansloze_muur(db, user_id: str, platform: str, reden: str) -> int:
    """Zet elke mislukte advertentie op dit kanaal op dezelfde uitgelegde reden.

    WAAROM (07-09-2026, Egbert Brouwer). Zijn 671 mislukte plaatsopdrachten voor
    2dehands lieten evenveel rode balken achter, met wisselende teksten: "timed
    out", "not signed in", "queue stopped". Elke ronde een andere. Dat leest als
    tien verschillende storingen terwijl het er één is: 2dehands laat dit account
    niet plaatsen. `_stop_wachtrij` raakt alleen wat nóg wacht; deze functie zet
    ook de al bestaande foutregels recht.

    Alleen rijen zonder advertentienummer: die hebben nooit een advertentie gehad
    en zijn dus echt kansloos. Een rij mét nummer is een levende advertentie en
    blijft met rust.
    """
    try:
        rijen = fetch_all(lambda: db.table("listings")
                          .select("id,platform_listing_id,items!inner(user_id)")
                          .eq("items.user_id", user_id)
                          .eq("platform", platform).eq("status", "error"),
                          page_size=1000)
    except Exception as e:  # noqa: BLE001 — recht­zetten mag nooit fataal zijn
        logger.warning("kansloze muur niet te lezen voor %s/%s: %s", user_id, platform, e)
        return 0
    ids = [r["id"] for r in rijen if not r.get("platform_listing_id")]
    for i in range(0, len(ids), 200):
        execute_with_retry(db.table("listings").update({
            "error_message": reden,
        }).in_("id", ids[i:i + 200]))
    if ids:
        logger.warning("kansloze muur gelijkgetrokken: %d rijen voor %s bij %s",
                       len(ids), platform, user_id)
    return len(ids)


@router.post("/stop-platform")
def stop_platform(body: dict, request: Request, user_id: str = Depends(get_current_user)):
    """Neem in één keer alles terug wat nog voor één kanaal in de wachtrij staat.

    WAAROM DIT BESTAAT (03-09-2026, gemeten bij Egbert Brouwer). Hij zette 152
    artikelen tegelijk klaar voor Marktplaats én 2dehands. Op 2dehands was hij
    niet ingelogd, dus ging daar het plaatsformulier nooit open. Elke opdracht
    liep daardoor tegen de bewaker van drie minuten aan: 26 keer dezelfde
    onbegrijpelijke melding, met nog 279 opdrachten erachter. De extensie doet
    met opzet één opdracht tegelijk, dus dat was zestien uur waarin hij niets
    anders kon publiceren. Zijn woorden: "ik loop compleet vast".

    Weet de extensie zeker dat het formulier niet opengaat, dan heeft de rest
    van de rij geen enkele kans meer. Die halen we hier in één keer weg, met de
    reden erbij, zodat hij ziet wat er is gebeurd in plaats van het zestien uur
    lang opnieuw te zien mislukken.
    """
    platform = str(body.get("platform") or "").strip()
    if not platform:
        raise HTTPException(status_code=400, detail="platform is required")
    db = get_db()
    reden = str(body.get("reason") or "").strip() or _melding_formulier_ging_niet_open(platform)
    reden = _reden_zonder_vals_verwijt(
        db, user_id, platform, reden, request.headers.get("x-omnivaleur-ext"))
    gestopt = _stop_wachtrij(db, user_id, platform, reden)
    # Is het kanaal aantoonbaar kansloos, trek dan ook de al bestaande rode balken
    # gelijk — anders blijft er een muur van oude, wisselende teksten staan naast
    # de ene uitgelegde reden. Alleen bij bewezen kansloos: een eenmalige stop
    # (tijdelijke storing) mag niet het hele overzicht herschrijven.
    try:
        if _kanaal_kansloos(db, user_id, platform):
            _gelijk_de_kansloze_muur(db, user_id, platform,
                                     _melding_formulier_ging_niet_open(platform))
    except Exception:  # noqa: BLE001
        logger.warning("stop-platform: kansloze-muur gelijktrekken mislukt voor %s/%s", user_id, platform)
    return {"ok": True, "cancelled": gestopt}


# Een "je bent niet ingelogd" dat de extensie meestuurt is een oordeel uit haar
# eigen achtergrond, en dat oordeel is aantoonbaar fout geweest.
_CLAIM_NIET_INGELOGD = re.compile(r"you are not signed in to|je bent niet ingelogd", re.I)
# Vanaf deze versie vraagt de extensie het na in een tabblad op de site zelf.
# Alles daaronder oordeelt uitsluitend op de achtergrondmeting, en die is
# aantoonbaar blind geweest, dus zo'n oordeel geven we nooit door.
_VERSIE_MET_EIGEN_INLOGMETING = (1, 0, 308)


def _laatste_eigen_meting(db, user_id: str, platform: str) -> str | None:
    """Wanneer de browser van deze verkoper zélf bij zijn advertentieoverzicht kon.

    De scan draait in een echt tabblad OP de site en vraagt daar het
    afgeschermde /my-account/sell/api/listings op. HTTP 200 daar krijg je alleen
    met een geldige sessie — dat is precies de aanname waar de inlogcontrole van
    de extensie op gebouwd is. Geeft de tijd van de laatste 200 terug, of None.
    """
    try:
        rijen = execute_with_retry(
            db.table("jobs").select("result,done_at,created_at")
            .eq("user_id", user_id).eq("platform", platform)
            .eq("action", "scan").eq("status", "done")
            .order("created_at", desc=True).limit(10)
        ).data or []
    except Exception as e:  # noqa: BLE001 — geen meting is geen storing
        logger.warning("Kon de eigen inlogmeting niet lezen voor %s/%s: %s", user_id, platform, e)
        return None
    grens = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    for r in rijen:
        meta = ((r.get("result") or {}).get("scan_meta") or {})
        wanneer = r.get("done_at") or r.get("created_at") or ""
        if meta.get("api_status") == 200 and wanneer >= grens:
            return wanneer
    return None


def _reden_zonder_vals_verwijt(db, user_id: str, platform: str, reden: str,
                               kopstuk_versie=None) -> str:
    """Laat de server geen verwijt doorgeven dat hij zelf kan weerleggen.

    WAAROM DIT ER IS (07-09-2026, gemeten bij Egbert Brouwer).

    De extensie kreeg op 06-09 om 21:07:48 vanuit haar service worker HTTP 401
    van 2dehands, en nam daarop zijn hele wachtrij van 346 opdrachten terug met
    de tekst dat hij niet was ingelogd. Dertien seconden eerder, om 21:07:35,
    had zijn eigen browser vanuit een tabblad OP www.2dehands.be op precies
    dezelfde URL HTTP 200 gekregen. Om 21:11 gebeurde hetzelfde nog een keer.
    Hij was ingelogd, en het was de derde keer dat hij dit verwijt kreeg.

    De extensie is gerepareerd (zij vraagt het nu na in een tabblad op de site
    zelf), maar een nieuwe extensie is er pas na de Web Store en niet iedereen
    werkt tegelijk bij. Deze rem staat daarom hier: de server weet uit de scans
    van dezelfde verkoper of zijn browser wél bij zijn account kon, en weigert
    dan het verwijt door te geven. De wachtrij stoppen doen we wél — anders
    loopt hij opnieuw uren tegen dezelfde muur — maar met wat we echt weten.
    """
    if not _CLAIM_NIET_INGELOGD.search(reden or ""):
        return reden
    versie = _kopstuk_versie(kopstuk_versie)
    oude_kopie = versie is not None and versie < _VERSIE_MET_EIGEN_INLOGMETING
    wanneer = _laatste_eigen_meting(db, user_id, platform)
    if not wanneer and not oude_kopie:
        return reden
    site = {"marktplaats": "Marktplaats (marktplaats.nl)",
            "2dehands": "2dehands (2dehands.be)"}.get(platform, platform)
    logger.warning(
        "stop-platform: verwijt 'niet ingelogd' geweigerd voor %s/%s (versie %s, eigen scan 200 op %s)",
        user_id, platform, versie, wanneer)
    if not wanneer:
        # Geen recente eigen meting, maar wel een kopie waarvan we WETEN dat ze
        # dit alleen uit haar achtergrond kan hebben. Dan doen we geen uitspraak
        # en laten we hem het in één klik zelf zien.
        controle = _CONTROLEPAGINA.get(platform, "")
        return (
            f"We stopped the {site} queue. The extension blamed your login, but the version you "
            f"are running cannot tell that apart from a check of ours failing on its own, so we "
            f"are not passing that on as the reason.\n\n"
            f"One click tells you which of the two it is. Open this page in this browser:\n"
            f"{controle}\n\n"
            f"1. You see your own adverts page. Then you are signed in and the fault is ours. "
            f"Please tell us, because we cannot see that from here.\n"
            f"2. You see a login screen. Then sign in there and publish again.\n\n"
            f"Nothing was published and nothing was changed on {site}."
        )
    return (
        f"We stopped the {site} queue, but not for the reason the extension gave. It blamed your "
        f"login. We do not believe that: your own browser reached your {site} account page on "
        f"{wanneer[:16].replace('T', ' ')} (HTTP 200), and that only works with a valid session. "
        f"So this is a fault on our side, not with your account.\n\n"
        f"Nothing was published and nothing was changed on {site}. We have already fixed the check "
        f"that got this wrong, and it reaches your browser with the next extension update. Until "
        f"then the queue may stop again with this message, so please tell us if it does."
    )


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, user_id: str = Depends(get_current_user)):
    """
    User-triggered abort of a still-running/queued job. Used when a publish run got
    stuck — e.g. the extension picked a wrong category and the user touched the tab,
    so the job never reaches complete/error and the "extension is working" banner
    hangs while the item is NOT actually published. Cancelling settles the job so the
    banner clears and the item correctly reads as not-listed.
    """
    db = get_db()
    job = eerste_rij(db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).limit(1).execute())
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Already finished — nothing to cancel; report where it landed.
    if job["status"] in ("done", "error", "cancelled"):
        return {"ok": True, "status": job["status"]}

    now = datetime.now(timezone.utc).isoformat()

    # De verwijdering van een HERPLAATSING annuleren betekent: de oude
    # advertentie blijft gewoon online. Dan hoort de rij terug op 'active' en
    # moet de gepaarde plaatsing mee vervallen. Bleef de rij op 'relisting'
    # staan, dan zette de reddingsronde er zes uur later een kale plaatsing
    # voor klaar, naast de advertentie die nooit weg was (Toon, 03-09-2026:
    # drie kelims, drie dubbele plaatsingen in de wachtrij).
    if job["action"] == "delete" and (job.get("payload") or {}).get("_refresh_rollback"):
        _neem_herplaatsing_terug(
            db, job, now,
            "Cancelled by you: the old listing was never removed and is still live here. "
            "Nothing was reposted.")
        return {"ok": True, "status": "cancelled"}

    db.table("jobs").update({
        "status": "cancelled",
        "result": {"cancelled": "by user"},
        "done_at": now,
    }).eq("id", job_id).execute()

    # A content-refresh or relist-delete bumped the listing's cooldown/quota at enqueue
    # time; hand it back since the run was aborted.
    rollback = ((job.get("payload")) or {}).get("_refresh_rollback")
    if rollback:
        from backend.services.relist import rollback_refresh
        rollback_refresh(rollback, user_id)

    # For a create, drop the not-yet-confirmed "pending" listing so the item shows as
    # not-listed (its true state) — the publish didn't complete. An already-active
    # listing (a retry over a live one) is left untouched.
    if job["action"] == "create":
        db.table("listings").update({
            "status": "error",
            "error_message": "Publishing was cancelled — the item is not listed. Publish again, or mark it listed if it did go live.",
        }).eq("item_id", job["item_id"]).eq("platform", job["platform"]).eq("status", "pending").execute()
        # Vaak maakt de gebruiker de advertentie na een afbreking zelf af. Een
        # scan erachteraan zorgt dat het dashboard dat vanzelf oppikt.
        #
        # ALLEEN als de extensie er ook echt aan begonnen was. Een opdracht die
        # nooit is opgepakt heeft geen tabblad gehad en dus niets half
        # achtergelaten; daar valt niets op te halen. Het scheelde bovendien een
        # stortvloed: toen Toon op 04-09-2026 in één klik 39 wachtende
        # publicaties weggooide, vroegen die 39 annuleringen tegelijk om een
        # scan. De dubbelcontrole in _queue_scan leest en schrijft niet in
        # dezelfde stap, dus vier daarvan glipten er samen doorheen en zijn
        # wachtrij stond meteen weer vol met scans die niemand had gevraagd.
        if job.get("claimed_at"):
            _queue_scan(db, user_id, job["platform"])
    return {"ok": True, "status": "cancelled"}


@router.get("/status/{job_id}")
def get_job_status(job_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    job = eerste_rij(db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).limit(1).execute())
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
