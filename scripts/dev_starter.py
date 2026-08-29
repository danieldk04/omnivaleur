#!/usr/bin/env python3
"""Zet de developer aan het werk zodra de klantenservice een storing als
"MOET ZEKER" aanmerkt.

WAAROM DIT BESTAAT (29-08-2026)
De rolverdeling ligt vast (docs/team-notes.md): de mailagent is de
klantenservicemedewerker, Claude Code is de developer. De lijn van de een naar
de ander werkt al — `mail_analyse.py bugs` is het postvak — maar hij werd alleen
gelezen wanneer Daniel toevallig een sessie opende. Een klant die woensdag boos
meldt dat het niet werkt, moest dus wachten tot de CEO er zin in had. Dat is
precies de rol die hij niet meer wil hebben.

Deze starter dicht dat gat: hij kijkt elke tien minuten in het postvak en start
zelf een Claude Code-sessie voor één storing, met de opdracht die te repareren
en daarna zelf terug te melden via `mail_analyse.py opgelost`.

DE REMMEN, EN WAAROM ZE ER ZITTEN
- Eén sessie tegelijk. Twee sessies in dezelfde map werken elkaars wijzigingen
  weg; dat is geen theorie maar de reden dat CLAUDE.md begint met "kijk eerst
  wat er veranderd is".
- Nooit twee sessies voor dezelfde sleutel, en een sleutel die eenmaal gestart
  is komt niet terug tot hij is opgelost of afgewezen. Anders begint hij elke
  tien minuten opnieuw aan hetzelfde werk.
- Hooguit MAX_PER_DAG starts per dag. Daniels gebruikslimiet is eindig, en drie
  MOET ZEKER-storingen tegelijk zouden hem in een uur opmaken.
- Alleen bij een schone werkmap. Staat er werk van Daniel zelf klaar, dan blijft
  de starter eraf — een autonome sessie die commit zou dat meenemen.

GEBRUIK
    python3 scripts/dev_starter.py             # één ronde (dit doet de LaunchAgent)
    python3 scripts/dev_starter.py --status    # wat loopt er, wat staat er klaar
    python3 scripts/dev_starter.py --droog     # laat zien wat hij zou starten
    python3 scripts/dev_starter.py --opnieuw <sleutel>   # sleutel weer vrijgeven
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import mail_analyse as A  # noqa: E402

STAAT_SLEUTEL = "dev_sessies"

# Waar de logboeken heen gaan. Bewust buiten ~/Documents: macOS geeft een
# achtergrondtaak daar geen schrijfrecht, en iCloud haalt er bestanden weg die
# even niet gebruikt zijn. Dezelfde reden als bij de koude-mailmachine.
THUIS = Path.home() / "Library" / "Application Support" / "omnivaleur"
LOGMAP = THUIS / "dev-sessies"

MAX_PER_DAG = 3

# Wat de sessie mee mag maken voor hij zichzelf afkapt. Ruim, want repareren,
# testen en pushen kost tijd; niet oneindig, want een vastgelopen sessie mag de
# volgende niet blokkeren.
MAX_MINUTEN = 90


# ---------------------------------------------------------------- staat
def _staat() -> dict:
    return A._lees(STAAT_SLEUTEL, {}) or {}


def _bewaar(staat: dict) -> bool:
    return A._schrijf(STAAT_SLEUTEL, staat)


def _leeft(pid) -> bool:
    """Draait dit procesnummer nog?"""
    try:
        os.kill(int(pid), 0)
    except (OSError, TypeError, ValueError):
        return False
    return True


def _loopt_er_een(staat: dict) -> str | None:
    """De sleutel waarvan de sessie nog draait, of None."""
    for sleutel, s in staat.items():
        if s.get("status") == "gestart" and _leeft(s.get("pid")):
            return sleutel
    return None


def _vandaag_gestart(staat: dict) -> int:
    vandaag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return sum(1 for s in staat.values() if str(s.get("gestart", ""))[:10] == vandaag)


# ---------------------------------------------------------------- keuze
def _te_doen(signalen: dict, staat: dict) -> list[tuple[str, dict]]:
    """De storingen die met zekerheid gerepareerd moeten worden en nog wachten.

    Volgorde: eerst wat de meeste mensen raakt, daarna wat het meest recent is.
    """
    open_ = [(k, v) for k, v in signalen.items()
             if v.get("status") == "open" and v.get("moet_zeker")
             and k not in staat]
    op_datum = sorted(open_, key=lambda kv: kv[1].get("laatst", ""), reverse=True)
    return sorted(op_datum, key=lambda kv: -len(kv[1].get("melders") or []))


def _opruimen(signalen: dict, staat: dict) -> bool:
    """Een sleutel die is opgelost of afgewezen hoeft niet meer op slot.

    Dit is precies de afspraak: een sleutel wordt niet opnieuw gestart zolang hij
    niet is opgelost of afgewezen — en dus wél weer beschikbaar zodra dat gebeurt
    (voor als dezelfde storing later terugkomt).
    """
    veranderd = False
    for sleutel in list(staat):
        stand = (signalen.get(sleutel) or {}).get("status")
        if stand in ("opgelost", "afgewezen"):
            staat.pop(sleutel)
            veranderd = True
        elif staat[sleutel].get("status") == "gestart" and not _leeft(staat[sleutel].get("pid")):
            staat[sleutel]["status"] = "afgerond"
            staat[sleutel]["afgerond_op"] = datetime.now(timezone.utc).isoformat()
            veranderd = True
        elif (staat[sleutel].get("status") == "gestart"
                and _minuten_bezig(staat[sleutel]) > MAX_MINUTEN):
            # Een sessie die vastloopt houdt alle andere storingen tegen, want er
            # mag er maar één tegelijk draaien. Na anderhalf uur is hij niet meer
            # aan het werk maar aan het wachten.
            try:
                os.kill(int(staat[sleutel]["pid"]), 15)
            except Exception:  # noqa: BLE001
                pass
            staat[sleutel]["status"] = "afgebroken"
            staat[sleutel]["afgerond_op"] = datetime.now(timezone.utc).isoformat()
            print(f"  !! sessie voor {sleutel} liep langer dan {MAX_MINUTEN} minuten "
                  f"en is gestopt — zie {staat[sleutel].get('log','het logboek')}")
            veranderd = True
    return veranderd


def _minuten_bezig(s: dict) -> float:
    try:
        gestart = datetime.fromisoformat(str(s.get("gestart")))
    except (TypeError, ValueError):
        return 0.0
    if gestart.tzinfo is None:
        gestart = gestart.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - gestart).total_seconds() / 60


def _werkmap_schoon() -> tuple[bool, str]:
    """Staat er niets van iemand anders klaar?

    .claude-flow schrijft bij elke sessie zijn eigen boekhouding weg; dat is geen
    werk van Daniel en telt hier dus niet mee.
    """
    try:
        uit = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                             capture_output=True, text=True, timeout=60)
    except Exception as e:  # noqa: BLE001
        return False, f"git antwoordde niet ({e})"
    regels = [r for r in uit.stdout.splitlines()
              if r.strip() and ".claude-flow/" not in r]
    if regels:
        return False, f"{len(regels)} bestand(en) met wijzigingen: " + \
                      ", ".join(r[3:] for r in regels[:4])
    return True, ""


# ---------------------------------------------------------------- opdracht
def opdracht(sleutel: str, signaal: dict) -> str:
    melders = ", ".join(signaal.get("melders") or []) or "onbekend"
    waarom = "; ".join(signaal.get("waarom_zeker") or []) or "gemarkeerd als MOET ZEKER"
    return f"""Je bent de developer van Omnivaleur. De klantenservice heeft één storing
met voorrang aan je doorgegeven. Werk die af, van begin tot eind, zonder tussentijds
te overleggen — er is niemand aan de andere kant van deze sessie.

STORING: {sleutel}
Wat klanten melden: {signaal.get('omschrijving', '(geen omschrijving)')}
Gemeld door: {melders}
Met voorrang omdat: {waarom}
Voor het eerst: {str(signaal.get('eerst', ''))[:10]} — laatst: {str(signaal.get('laatst', ''))[:10]}

Doe dit, in deze volgorde:
1. Volg de vaste startstappen uit CLAUDE.md: recente commits en diffs lezen, de
   laatste toevoegingen in docs/team-notes.md, en `python3 scripts/mail_analyse.py bugs`.
2. Zoek de oorzaak uit voordat je iets wijzigt. Er is in dit project meer dan eens
   iets "gerepareerd" wat al gerepareerd was, of wat een andere oorzaak had dan de
   melding suggereert. Kijk ook in het opdrachtenlogboek (tabel jobs in Supabase)
   naar wat er bij deze melders echt misging.
3. Blijkt het al gerepareerd of blijkt het geen storing, wijzig dan NIETS aan de
   code. Meld het terug met `opgelost` (bij gerepareerd) of met
   `python3 scripts/mail_analyse.py afgewezen {sleutel} "reden in één zin"`.
4. Repareer het anders zo klein mogelijk, met een test die de storing vastlegt.
5. Draai de tests. Zijn ze niet allemaal groen, push dan NIETS en laat het staan.
6. Zijn ze groen: commit en push naar origin/main.
7. Meld terug, altijd, ook als er niets veranderd is:
   python3 scripts/mail_analyse.py opgelost {sleutel} "wat er nu anders is, in gewone taal"
   Zonder die stap hoort de klant nooit dat zijn melding iets heeft opgeleverd.
8. Zet een gedateerde notitie onder in docs/team-notes.md over wat je hebt gevonden.

Regels: nooit secrets of .env committen, niets in de hoofdmap opslaan, altijd een
bestand lezen voor je het wijzigt."""


# ---------------------------------------------------------------- starten
def _start(sleutel: str, signaal: dict, staat: dict) -> bool:
    exe = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")
    if not Path(exe).exists():
        print("  !! de claude-opdrachtregel is niet gevonden — niets gestart")
        return False
    LOGMAP.mkdir(parents=True, exist_ok=True)
    stempel = datetime.now().strftime("%Y%m%d-%H%M")
    log = LOGMAP / f"{stempel}-{sleutel}.log"

    # De sessie draait op Daniels eigen abonnement, niet op de API-sleutel uit
    # .env: die sleutel wordt per woord afgerekend en dit is werk dat onder zijn
    # abonnement hoort te vallen. Weghalen dus, anders erft het kindproces hem.
    omgeving = dict(os.environ)
    omgeving.pop("ANTHROPIC_API_KEY", None)

    try:
        with log.open("w") as uit:
            uit.write(f"# {datetime.now():%d-%m-%Y %H:%M} — sessie voor {sleutel}\n\n")
            uit.flush()
            proc = subprocess.Popen(
                [exe, "-p", opdracht(sleutel, signaal),
                 "--dangerously-skip-permissions"],
                cwd=str(REPO), env=omgeving, stdin=subprocess.DEVNULL,
                stdout=uit, stderr=subprocess.STDOUT, start_new_session=True)
    except Exception as e:  # noqa: BLE001
        print(f"  !! sessie voor {sleutel} niet gestart: {type(e).__name__}: {e}")
        return False

    staat[sleutel] = {"status": "gestart", "pid": proc.pid, "log": str(log),
                      "gestart": datetime.now(timezone.utc).isoformat()}
    if not _bewaar(staat):
        # Kunnen we niet onthouden dat hij loopt, dan start de volgende ronde
        # hem opnieuw. Liever afbreken dan twee sessies in dezelfde map.
        proc.terminate()
        print(f"  !! staat niet opgeslagen — sessie voor {sleutel} weer gestopt")
        return False
    print(f"  ↳ sessie gestart voor {sleutel} (pid {proc.pid})\n     logboek: {log}")
    return True


# ---------------------------------------------------------------- rondes
HARTSLAG_SLEUTEL = "dev_starter_hartslag"


def _hartslag() -> None:
    """Zeggen dat hij langs is geweest.

    Zonder dit valt de starter stil zonder dat iemand het merkt — macOS geeft een
    achtergrondtaak standaard geen toegang tot ~/Documents en meldt dat nergens.
    Het beheerdashboard leest deze hartslag en waarschuwt als hij uitblijft
    terwijl er werk klaarstaat. Zie _starter_stand in backend/api/beheer.py.
    """
    A._schrijf(HARTSLAG_SLEUTEL, {"wanneer": datetime.now(timezone.utc).isoformat()})


def ronde(droog: bool = False) -> None:
    signalen = A.bugs()
    staat = _staat()
    if not droog:
        _hartslag()
    if _opruimen(signalen, staat):
        _bewaar(staat)

    loopt = _loopt_er_een(staat)
    if loopt:
        print(f"Er loopt al een sessie voor '{loopt}' — niets gestart.")
        return

    wachtrij = _te_doen(signalen, staat)
    if not wachtrij:
        print("Geen storing die met zekerheid gerepareerd moet worden. Niets gestart.")
        return

    if _vandaag_gestart(staat) >= MAX_PER_DAG:
        print(f"Vandaag al {MAX_PER_DAG} sessies gestart — de rest wacht tot morgen. "
              f"In de wachtrij: {', '.join(k for k, _ in wachtrij)}")
        return

    schoon, waarom = _werkmap_schoon()
    if not schoon:
        print(f"Werkmap is niet schoon ({waarom}) — niets gestart.")
        return

    sleutel, signaal = wachtrij[0]
    if droog:
        print(f"Zou een sessie starten voor '{sleutel}'.\n")
        print(opdracht(sleutel, signaal))
        return
    _start(sleutel, signaal, staat)


def status() -> None:
    signalen = A.bugs()
    staat = _staat()
    if staat:
        print("Sessies:")
        for sleutel, s in sorted(staat.items(), key=lambda kv: kv[1].get("gestart", "")):
            leeft = " (draait nog)" if s.get("status") == "gestart" and _leeft(s.get("pid")) else ""
            print(f"  {sleutel}: {s.get('status')}{leeft} sinds "
                  f"{str(s.get('gestart',''))[:16].replace('T',' ')}")
            if s.get("log"):
                print(f"      {s['log']}")
    else:
        print("Nog geen sessies gestart.")
    wachtrij = _te_doen(signalen, staat)
    print(f"\nWacht op een sessie: {', '.join(k for k, _ in wachtrij) or 'niets'}")


def opnieuw(sleutel: str) -> None:
    staat = _staat()
    if sleutel not in staat:
        print(f"'{sleutel}' staat niet op slot.")
        return
    staat.pop(sleutel)
    _bewaar(staat)
    print(f"'{sleutel}' is weer vrijgegeven; de volgende ronde mag hem oppakken.")


def main() -> None:
    A._omgeving_uit_env_bestand()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--status", action="store_true", help="wat loopt er en wat wacht er")
    p.add_argument("--droog", action="store_true", help="laat zien wat hij zou starten")
    p.add_argument("--opnieuw", metavar="SLEUTEL", help="een sleutel weer vrijgeven")
    args = p.parse_args()
    if args.status:
        status()
    elif args.opnieuw:
        opnieuw(args.opnieuw)
    else:
        ronde(droog=args.droog)


if __name__ == "__main__":
    main()
