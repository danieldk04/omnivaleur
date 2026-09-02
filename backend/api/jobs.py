from fastapi import APIRouter, HTTPException, Depends, Request
from backend.database import get_db, fetch_all, fetch_all_in, update_in, naast_de_lus, execute_with_retry
from backend.api.deps import get_current_user, require_active_subscription
from backend.api.imports import _backfill_item_from_candidate
from backend.services.crosslist import handle_item_sold
from datetime import datetime, timezone, timedelta
import logging
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
# Hoe vaak een scan die door een te oude kopie is opgepakt terug in de wachtrij
# mag. Twee: genoeg om de bijgewerkte kopie een kans te geven, te weinig om te
# blijven rondzingen bij iemand die alleen die oude kopie heeft.
MAX_HERKANSING_OUDE_EXTENSIE = 2

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


def _record_extension_heartbeat(db, user_id: str, user_agent: str | None = None) -> None:
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
        retry_safe = j["action"] in ("delete", "scan", "content_refresh")

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


@router.get("/pending")
def get_pending_jobs(request: Request, platform: str = None, user_id: str = Depends(require_active_subscription)):
    db = get_db()
    now_dt = datetime.now(timezone.utc)
    # A poll WITH a platform is a real extension dispatch poll (the dashboard
    # polls without one, just to count) — treat it as the extension's heartbeat
    # so the "computer online" indicator works without any extension change.
    if platform is not None:
        _record_extension_heartbeat(db, user_id, request.headers.get("user-agent"))
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
        if gemeld is not None and gemeld < MINIMALE_SCANVERSIE:
            logger.warning(
                "Geen werk uitgedeeld: extensie %s bij gebruiker %s ligt onder %s",
                ".".join(map(str, gemeld)), user_id,
                ".".join(map(str, MINIMALE_SCANVERSIE)),
            )
            return []
    # First, rescue anything stuck 'claimed' from an interrupted run.
    _recover_stale_claims(db, user_id, platform, now_dt)

    q = db.table("jobs").select("*").eq("user_id", user_id).eq("status", "pending")
    if platform:
        q = q.eq("platform", platform)
    result = q.order("created_at").limit(20).execute()
    now = now_dt.isoformat()

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
    SCHRIJVEND = ("create", "delete", "content_refresh")
    is_extension_dispatch = platform is not None
    if is_extension_dispatch:
        for c in (
            db.table("jobs").select("claimed_at,action")
            .eq("user_id", user_id).eq("status", "claimed").execute().data
        ):
            if c.get("action") not in SCHRIJVEND:
                continue  # een lopende scan houdt niemand tegen
            ct = _parse_ts(c.get("claimed_at"))
            if ct and ct >= now_dt - timedelta(minutes=STALE_CLAIM_MINUTES):
                return []  # er wordt nu echt gepubliceerd — nooit een 2e tabblad

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
        ready.append(j)

    # A relist's "create" job can sit queued for 45min-4h (the jittered
    # recreate delay) before it's actually dispatched. Its payload price was
    # snapshotted when the job was queued, so if the user edits the item's
    # price in the frontend in the meantime, the stale snapshot would win and
    # the relist would silently keep republishing the old price. Re-read the
    # item's current price right before handing the job to the extension so
    # the recreate always reflects what the user set, not what was true when
    # the delay started.
    for j in ready:
        if j["action"] == "create" and j.get("scheduled_for") and isinstance(j.get("payload"), dict):
            current = db.table("items").select("price").eq("id", j["item_id"]).execute().data
            if current and current[0].get("price") not in (None, ""):
                j["payload"]["price"] = current[0]["price"]

    # Wie het eerst geholpen wordt: de gebruiker. Een scan die toevallig eerder in
    # de wachtrij kwam (bijvoorbeeld de uurlijkse controle) ging vóór een publicatie
    # waar iemand net op geklikt heeft — en dan lijkt de knop kapot. Publiceren en
    # verwijderen gaan nu altijd voor; scans vullen de rustige momenten op.
    if is_extension_dispatch:
        ready.sort(key=lambda j: 0 if j.get("action") in SCHRIJVEND else 1)

    # Extension: exactly one job at a time. Dashboard: the whole queue, to count.
    return ready[:1] if is_extension_dispatch else ready


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
    # De waarschuwing over een verouderde kopie hoort óók zichtbaar te zijn als
    # de hartslagtabel nog niet bestaat — dat is precies een account waar dit
    # soort dingen ongemerkt misgaat.
    oud = _verouderde_extensie(db, user_id)
    try:
        row = (
            db.table("extension_heartbeat")
            .select("last_seen")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )
    except Exception:
        return {"online": None, **oud}  # table not migrated yet — hide the indicator

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


def _verouderde_extensie(db, user_id: str) -> dict:
    """Draait er ergens nog een oude kopie van de extensie mee?

    Een tweede, met de hand geladen kopie beweegt niet mee met de Chrome Web
    Store en blijft dus voor altijd op de versie van de dag dat hij is
    neergezet. Hij haalt wél opdrachten uit dezelfde wachtrij, en bij een grote
    winkel kan hij die niet aan. Dat is van buitenaf niet te zien — het lijkt op
    "de app doet het soms wel en soms niet" (Egbert Brouwer, twee weken lang).

    De extensie stempelt haar versie in elke foutmelding, dus we kunnen dit
    aflezen uit werk dat al gedaan is. Geen extra tabel, geen migratie.
    """
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
    return {"outdated_extension": ".".join(map(str, oudste))}


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
    return {"working": working, "queued": queued}


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
        .select("id")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .eq("platform", platform)
        .in_("action", ["delete", "create"])
        .in_("status", ["pending", "claimed", "error"])
        .execute()))
        .data
        or []
    )
    for j in stale:
        (await naast_de_lus(lambda: db.table("jobs").update({
            "status": "cancelled",
            "done_at": datetime.now(timezone.utc).isoformat(),
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
    try:
        result = await refresh_listing(item_id, platform, user_id, "relist")
    except RefreshError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        .select("id")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .eq("platform", platform)
        .in_("action", ["delete", "create"])
        .in_("status", ["pending", "claimed", "error"])
        .execute()
        .data
        or []
    )
    for j in outstanding:
        db.table("jobs").update({
            "status": "cancelled",
            "done_at": datetime.now(timezone.utc).isoformat(),
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

    logger.info("[sold] item %s op %s: advertentie was al weg en te jong om te verlopen "
                "— %d rij(en) op 'mogelijk verkocht', %d herplaatsing(en) geannuleerd",
                job["item_id"], job["platform"], len(jong), len(wachtend))
    return True


@router.post("/{job_id}/complete")
async def complete_job(job_id: str, body: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    _record_extension_heartbeat(db, user_id)  # only the extension completes jobs
    job = (await naast_de_lus(lambda: db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute())).data
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
                huidig = ((await naast_de_lus(lambda: db.table("items")
                          .select("photo_urls,brand,size,color,condition")
                          .eq("id", job["item_id"]).single().execute())).data or {})
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
    newly_sold, set_aside, matched_without_id = 0, 0, 0
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
            try:
                (await naast_de_lus(lambda: db.table("listings").update({"status": "delisted"}) \
                    .eq("item_id", l["item_id"]).eq("platform", "vinted").execute()))
                set_aside += 1
            except Exception as e:
                logger.warning(f"Vinted reconcile: could not archive vanished listing {l['item_id']}: {e}")
    logger.info(
        "[sold] Vinted reconcile for user %s: %d marked sold (is_closed, of which %d matched by SKU/title), "
        "%d vanished → archived for review",
        job["user_id"], newly_sold, matched_without_id, set_aside,
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
            "status": prior_status.get(str(platform_listing_id), "pending"),
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


def _rechtgezette_foutmelding(job: dict | None, body: dict, versie) -> dict:
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
    if versie and versie < MINIMALE_SCANVERSIE:
        return {**(body or {}), "error_oorspronkelijk": fout, "error": (
            f"Deze opdracht is opgepakt door een verouderde kopie van de "
            f"Omnivaleur-extensie (versie {'.'.join(map(str, versie))}; nodig is "
            f"minstens {'.'.join(map(str, MINIMALE_SCANVERSIE))}). Die kopie kan dit "
            f"werk niet afmaken, en wat ze meldt over inloggen klopt niet. Open "
            f"chrome://extensions, zet \"Ontwikkelaarsmodus\" aan en verwijder elke "
            f"met de hand geladen kopie van Omnivaleur; laat alleen de versie uit "
            f"de Chrome Web Store staan en herstart Chrome.")}
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
    job = db.table("jobs").select("item_id,platform,action,payload").eq("id", job_id).eq("user_id", user_id).single().execute().data

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

    body = _rechtgezette_foutmelding(job, body, versie)

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
    job = db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute().data
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Already finished — nothing to cancel; report where it landed.
    if job["status"] in ("done", "error", "cancelled"):
        return {"ok": True, "status": job["status"]}

    now = datetime.now(timezone.utc).isoformat()
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
        _queue_scan(db, user_id, job["platform"])
    return {"ok": True, "status": "cancelled"}


@router.get("/status/{job_id}")
def get_job_status(job_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return result.data
