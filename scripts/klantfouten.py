#!/usr/bin/env python3
"""De ogen van de automatische starter: waar lopen klanten nú tegenaan.

WAAROM DIT BESTAAT (23-09-2026)
Daniel wil niet elke keer zelf de routine "waar liepen klanten tegenaan" starten.
Een fout bij een klant moet binnen het kwartier opgepakt worden, zonder hem. De
starter (dev_starter.py) kon al zelf een Claude-sessie op zijn abonnement starten,
maar zijn enige bron was de mail-buglijst, en die vult sinds 06-09-2026 niemand
meer. Dit bestand is de nieuwe bron: het leest de echte fouten uit de jobs-tabel.

ZONDER AI, EN LICHT OP DE DATABASE
Dit draait elke tien minuten en kost dus geen tokens: het telt alleen. Claude
start pas als hier iets openstaat. De productiedatabase is twee keer omgevallen
op een meting die `jobs.result` over meerdere klanten las (kennisbank,
meten-op-de-productiedatabase). Daarom: eerst alleen de kleine kolommen over het
tijdvenster, en `result` pas per klant, op id.

WANNEER IETS OPENSTAAT
Een foutsoort (kanaal + handeling + fouttekst zonder getallen) staat open zodra
hij voorkomt en nog niet is afgehandeld. De sessie meldt per soort terug:
    gerepareerd  pas weer open bij een nieuwe fout na drie uur (extensie-updates
                 hebben tijd nodig om bij de klant te komen)
    klant        klant-eigen oorzaak (Chrome uit, uitgelogd): zeven dagen stil
    onbekend     niet te bewijzen: een dag stil
Meldt een sessie een soort niet terug, dan geldt hij als onbekend. Anders begint
hij elke tien minuten opnieuw aan hetzelfde werk.

GEBRUIK
    python3 scripts/klantfouten.py                     # wat staat er open
    python3 scripts/klantfouten.py oordeel <soort> gerepareerd|klant|onbekend "zin"
"""
from __future__ import annotations

import hashlib
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import mail_analyse as A  # noqa: E402

OORDEEL_SLEUTEL = "klantfouten_oordelen"
# Een dag terug: staat de Mac 's nachts uit, dan moeten de fouten van gisteravond
# er 's ochtends nog zijn. Met zes uur vielen ze weg (24-09-2026). Dit leest geen
# result, dus een dag is licht.
VENSTER_UUR = 24
# Het oudste wachtende werk van een klant van wie Chrome aanstaat, terwijl er
# het afgelopen half uur niets van hem klaar kwam. Zo zag de vastloper van
# 23-09-2026 eruit: 28 plaatsingen, 1,3 uur, voor geen enkel kanaal iets uit.
VAST_NA_MIN = 60
STIL_SINDS_MIN = 30
HARTSLAG_VERS_MIN = 15
STILTE = {"gerepareerd": timedelta(hours=3), "klant": timedelta(days=7),
          "onbekend": timedelta(days=1)}


def _nu() -> datetime:
    return datetime.now(timezone.utc)


def _tijd(s) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def soort(platform, action, fout) -> str:
    """Dezelfde fout bij verschillende advertenties of klanten is één soort."""
    tekst = re.sub(r"\d+", "#", str(fout or "(geen fouttekst)").lower())
    tekst = re.sub(r"\s+", " ", tekst).strip()[:90]
    h = hashlib.sha1(f"{platform}|{action}|{tekst}".encode()).hexdigest()[:8]
    return f"fout-{platform}-{action}-{h}"


# ---------------------------------------------------------------- meten
def _db():
    sys.path.insert(0, str(REPO))
    from backend.database import get_db
    return get_db()


def meet(db=None, nu: datetime | None = None) -> dict:
    """Alle foutsoorten en vastlopers van de laatste uren, per soort.

    Gooit bij een storing: een lege uitkomst door een kapotte meting mag nooit
    lijken op "geen fouten" (kennisbank: storing-mag-nooit-als-antwoord-tellen).
    """
    db = db or _db()
    nu = nu or _nu()
    grens = (nu - timedelta(hours=VENSTER_UUR)).isoformat()
    soorten: dict = {}

    fouten = (db.table("jobs").select("id,user_id,platform,action,done_at")
              .eq("status", "error").gte("done_at", grens)
              .order("done_at").limit(400).execute().data or [])
    per_klant: dict = {}
    for j in fouten:
        per_klant.setdefault(j["user_id"], []).append(j)
    for uid, rijen in per_klant.items():
        ids = [r["id"] for r in rijen][-60:]
        teksten = {r["id"]: r.get("fout") for r in
                   (db.table("jobs").select("id,fout:result->>error")
                    .eq("user_id", uid).in_("id", ids).execute().data or [])}
        for r in rijen:
            if r["id"] not in teksten:
                continue
            fout = teksten[r["id"]]
            s = soorten.setdefault(soort(r["platform"], r["action"], fout), {
                "wat": f"{r['platform']} {r['action']} mislukt: {str(fout or '(geen fouttekst)')[:200]}",
                "klanten": set(), "aantal": 0, "momenten": []})
            s["klanten"].add(uid)
            s["aantal"] += 1
            s["momenten"].append(r["done_at"])

    oud = (nu - timedelta(minutes=VAST_NA_MIN)).isoformat()
    wachtend = (db.table("jobs").select("user_id,platform,created_at")
                .eq("status", "pending").lte("created_at", oud)
                .order("created_at").limit(400).execute().data or [])
    wachters = {}
    for w in wachtend:
        wachters.setdefault(w["user_id"], []).append(w)
    if wachters:
        vers = (nu - timedelta(minutes=HARTSLAG_VERS_MIN)).isoformat()
        aan = {h["user_id"] for h in
               (db.table("extension_heartbeat").select("user_id")
                .in_("user_id", list(wachters)).gte("last_seen", vers).execute().data or [])}
        stil = (nu - timedelta(minutes=STIL_SINDS_MIN)).isoformat()
        for uid in aan:
            klaar = (db.table("jobs").select("id").eq("user_id", uid)
                     .gte("done_at", stil).limit(1).execute().data or [])
            if klaar:
                continue
            rij = wachters[uid]
            kanalen = sorted({w["platform"] for w in rij})
            s = soorten.setdefault(f"vast-{uid[:8]}", {
                "wat": (f"werk zit vast: {len(rij)} opdrachten wachten langer dan "
                        f"{VAST_NA_MIN} min ({', '.join(kanalen)}), Chrome staat aan, "
                        f"en er kwam {STIL_SINDS_MIN} min niets klaar"),
                "klanten": {uid}, "aantal": len(rij), "momenten": []})
            s["momenten"].append(nu.isoformat())
    for s in soorten.values():
        s["klanten"] = sorted(s["klanten"])
    return soorten


# ---------------------------------------------------------------- open of niet
def oordelen() -> dict:
    return A._lees(OORDEEL_SLEUTEL, {}) or {}


def _stil_tot(sleutel: str, oordeel: dict, staat: dict) -> datetime | None:
    """Tot wanneer deze soort geen nieuwe sessie waard is."""
    kandidaten = []
    o = oordeel.get(sleutel) or {}
    gemeld = _tijd(o.get("wanneer"))
    if gemeld:
        kandidaten.append(gemeld + STILTE.get(o.get("oordeel"), STILTE["onbekend"]))
    # Een sessie die hem meekreeg en klaar is zonder terug te melden: onbekend.
    # Een sessie die nog loopt houdt hem ook stil (die zit er al op).
    for sessie in staat.values():
        if sleutel not in (sessie.get("sleutels") or []) or sessie.get("mislukt"):
            continue
        begon = _tijd(sessie.get("gestart"))
        if sessie.get("status") == "gestart":
            kandidaten.append(_nu() + timedelta(days=1))
        elif begon and not (gemeld and gemeld >= begon):
            klaar = _tijd(sessie.get("afgerond_op")) or begon
            kandidaten.append(klaar + STILTE["onbekend"])
    return max(kandidaten) if kandidaten else None


def open_soorten(gemeten: dict, oordeel: dict, staat: dict) -> dict:
    uit = {}
    for sleutel, s in gemeten.items():
        tot = _stil_tot(sleutel, oordeel, staat)
        nieuw = [m for m in s["momenten"] if tot is None or (_tijd(m) and _tijd(m) > tot)]
        if nieuw:
            uit[sleutel] = dict(s, momenten=sorted(nieuw))
    return uit


def signalen(staat: dict, db=None, nu: datetime | None = None) -> dict:
    """In de vorm die dev_starter kent: hooguit één klantfoutenronde.

    De dagelijkse ronde blijft de geplande taak in de app (08:00); die vangt
    wat hier niet te zien is, zoals betaalsloten en verlopen proeven.

    Alles wat openstaat gaat in één sessie. Vaak zijn drie foutteksten één
    oorzaak, en elke sessie die opstart kost abonnement.
    """
    nu = nu or _nu()
    uit = {}
    try:
        open_ = open_soorten(meet(db, nu), oordelen(), staat)
    except Exception as e:  # noqa: BLE001
        print(f"  !! klantfouten niet gemeten ({type(e).__name__}: {e}); niets gestart")
        open_ = {}
    if open_:
        sleutels = sorted(open_)
        klanten = sorted({k for s in open_.values() for k in s["klanten"]})
        momenten = sorted(m for s in open_.values() for m in s["momenten"])
        # Het eerste moment hoort in de naam: komt dezelfde soort na een
        # reparatie terug, dan is dat een nieuwe ronde en geen afgesloten oude.
        naam = "klantfouten-" + hashlib.sha1(
            ("|".join(sleutels) + momenten[0][:16]).encode()).hexdigest()[:8]
        uit[naam] = {"status": "open", "moet_zeker": True, "soort": "klantfouten",
                     "melders": klanten, "sleutels": sleutels, "soorten": open_,
                     "omschrijving": f"{len(sleutels)} foutsoort(en) bij {len(klanten)} klant(en)",
                     "eerst": momenten[0], "laatst": momenten[-1]}
    return uit


# ---------------------------------------------------------------- opdracht
WERKWIJZE = """Volg CLAUDE.md van deze repo en van ~/. Er is niemand aan de andere kant van
deze sessie: overleg niet, beslis zelf de meest logische oplossing.

1. Begin zoals CLAUDE.md voorschrijft: git log van de laatste 30 uur en de
   onderkant van docs/team-notes.md (het laatste kopje "Dagelijkse klantfouten").
2. Meet met echte data, nooit schatten. Python:
   /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 met
   sys.path.insert(0, repo) en `from backend.database import get_db`. Lees
   jobs.result ALLEEN per user_id, nooit over meerdere klanten (de database is
   daar twee keer op omgevallen; kennisbank meten-op-de-productiedatabase).
3. Onderscheid (a) fout in ONZE code of een kanaal dat zijn pagina veranderde,
   en (b) klant-eigen oorzaak (computer uit, uitgelogd, advertentie al weg,
   betaalmuur). Alleen (a) repareer je.
4. Repareren: bewijs het mechanisme, repareer met de echte code, draai de
   tests, doe de voor-en-na-proef (oude code laten falen, geen HEAD-vergelijking),
   commit en push naar main (Railway deployt). Extensiewijziging: manifest bumpen
   en build-extension.sh volgens de kennisbank. Twijfel je of het de oorzaak is:
   niet repareren, als open punt noteren. Nooit klantdata verwijderen, nooit een
   wachtrij wissen, nooit iets naar klanten mailen. Nooit .env of geheimen committen.
5. Vastleggen: onderaan docs/team-notes.md een kort kopje
   "## DD-MM-JJJJ (HH:MM, automatisch): Klantfouten" met wat je vond, wat
   gerepareerd is (commit) en wat openstaat. Committen en pushen. Nieuwe les:
   memorybestand plus `python3 scripts/export_kennisbank.py`, committen.
6. Meld ELKE foutsoort hieronder terug, ook als je er niets aan deed:
   python3 scripts/klantfouten.py oordeel <soort> gerepareerd|klant|onbekend "zin"
   Zonder terugmelding begint de volgende ronde er morgen opnieuw aan.
7. Sluit af met de vier blokjes. Kort. Geen subagents, batch je opdrachten."""


def opdracht(sleutel: str, signaal: dict) -> str:
    regels = []
    for s_sleutel, s in signaal.get("soorten", {}).items():
        klanten = ", ".join(k[:8] for k in s["klanten"])
        regels.append(f"- {s_sleutel}: {s['wat']}\n  {len(s['momenten'])} keer, "
                      f"klant(en) {klanten}, laatst {s['momenten'][-1][:16]} UTC")
    return f"""Je bent de developer van Omnivaleur (map {REPO}). De wachter zag zojuist
klanten tegen deze fouten aanlopen. Zoek uit wat erachter zit en repareer het
nu, zodat ze direct verder kunnen.

{chr(10).join(regels)}

(De klant-id's zijn de eerste 8 tekens van user_id.)

{WERKWIJZE}"""


# ---------------------------------------------------------------- terugmelden
def oordeel_vastleggen(sleutel: str, uitkomst: str, zin: str) -> bool:
    if uitkomst not in STILTE:
        print(f"Onbekend oordeel '{uitkomst}'; kies uit {', '.join(STILTE)}.")
        return False
    alles = oordelen()
    alles[sleutel] = {"oordeel": uitkomst, "zin": zin, "wanneer": _nu().isoformat()}
    # Oude oordelen opruimen, anders groeit dit eindeloos.
    grens = _nu() - timedelta(days=30)
    alles = {k: v for k, v in alles.items() if (_tijd(v.get("wanneer")) or _nu()) > grens}
    if A._schrijf(OORDEEL_SLEUTEL, alles):
        print(f"Vastgelegd: {sleutel} = {uitkomst}")
        return True
    return False


def main() -> None:
    A._omgeving_uit_env_bestand()
    if len(sys.argv) >= 4 and sys.argv[1] == "oordeel":
        ok = oordeel_vastleggen(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]))
        sys.exit(0 if ok else 1)
    import dev_starter
    gemeten = meet()
    open_ = open_soorten(gemeten, oordelen(), dev_starter._staat())
    print(f"Laatste {VENSTER_UUR} uur: {len(gemeten)} foutsoort(en), {len(open_)} open.")
    for sleutel, s in sorted(gemeten.items(), key=lambda kv: -kv[1]["aantal"]):
        stand = "OPEN" if sleutel in open_ else "afgehandeld"
        print(f"  [{stand}] {sleutel}: {s['wat'][:150]} ({s['aantal']}x, "
              f"{len(s['klanten'])} klant(en))")


if __name__ == "__main__":
    main()
