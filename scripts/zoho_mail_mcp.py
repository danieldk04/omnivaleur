# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2"]
# ///
"""Zoho Mail als koppeling voor Claude: lezen, zoeken, ordenen, concepten en versturen.

Draait als MCP-server over stdio (`uv run scripts/zoho_mail_mcp.py`) en praat met Zoho via
IMAP en SMTP. Zonder argument start hij de server, met `--test` controleert hij alleen de
verbinding en toont hij de mappen (nooit het wachtwoord).

Inloggegevens, eerste die er is wint:
  1. omgeving: IMAP_HOST, MAIL_USER, MAIL_PASS (optioneel MAIL_HOST voor SMTP, MAIL_FROM)
  2. ~/.omnivaleur/zoho-mail.json met dezelfde sleutels in kleine letters
  3. .env in de repo (dezelfde namen als mail_analyse.py gebruikt)

Veiligheid: er is geen tool die iets definitief wist (verwijderen = naar de prullenbak) en
`mail_verstuur` weigert zonder `bevestigd=True`.
"""
from __future__ import annotations

import base64
import contextlib
import email
import email.policy
import email.utils
import imaplib
import json
import os
import re
import smtplib
import sys
import time
from email.message import EmailMessage
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAANDEN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MAX_TEKST = 20000


# ---------------------------------------------------------------- instellingen
def _lees_env_bestand(pad: Path) -> dict[str, str]:
    uit: dict[str, str] = {}
    try:
        for regel in pad.read_text(encoding="utf-8").splitlines():
            regel = regel.strip()
            if not regel or regel.startswith("#") or "=" not in regel:
                continue
            naam, waarde = regel.split("=", 1)
            uit[naam.strip()] = waarde.strip().strip('"').strip("'")
    except OSError:
        pass
    return uit


def instellingen() -> dict[str, str]:
    bronnen: list[dict[str, str]] = [dict(os.environ)]
    try:
        js = json.loads((Path.home() / ".omnivaleur" / "zoho-mail.json").read_text())
        bronnen.append({k.upper(): str(v) for k, v in js.items()})
    except (OSError, ValueError):
        pass
    bronnen.append(_lees_env_bestand(REPO / ".env"))

    def pak(naam: str) -> str:
        for b in bronnen:
            if b.get(naam):
                return b[naam]
        return ""

    imap_host = pak("IMAP_HOST") or "imap.zoho.eu"
    gebruiker, wachtwoord = pak("MAIL_USER"), pak("MAIL_PASS")
    if not gebruiker or not wachtwoord:
        raise RuntimeError(
            "MAIL_USER of MAIL_PASS ontbreekt. Zet ze in ~/.omnivaleur/zoho-mail.json "
            '(sleutels "imap_host", "mail_user", "mail_pass") of in de .env.')
    return {
        "imap_host": imap_host,
        "smtp_host": pak("SMTP_HOST") or imap_host.replace("imap", "smtp", 1),
        "gebruiker": gebruiker,
        "wachtwoord": wachtwoord,
        "van": pak("MAIL_FROM") or gebruiker,
    }


# ---------------------------------------------------------------- IMAP-hulpjes
def utf7_decode(s: str) -> str:
    def stuk(m: re.Match) -> str:
        if m.group(1) == "":
            return "&"
        b = m.group(1).replace(",", "/")
        b += "=" * (-len(b) % 4)
        return base64.b64decode(b).decode("utf-16-be")
    return re.sub(r"&([^-]*)-", stuk, s)


def utf7_encode(s: str) -> str:
    uit, rest = [], ""

    def leeg():
        nonlocal rest
        if rest:
            b = base64.b64encode(rest.encode("utf-16-be")).decode().rstrip("=")
            uit.append("&" + b.replace("/", ",") + "-")
            rest = ""
    for ch in s:
        if 0x20 <= ord(ch) <= 0x7E:
            leeg()
            uit.append("&-" if ch == "&" else ch)
        else:
            rest += ch
    leeg()
    return "".join(uit)


def q(mapnaam: str) -> str:
    """Mapnaam als IMAP-argument: utf-7 en tussen aanhalingstekens."""
    n = utf7_encode(mapnaam).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{n}"'


def imap_datum(iso: str) -> str:
    j, m, d = (int(x) for x in iso.split("-"))
    if not (1 <= m <= 12 and 1 <= d <= 31):
        raise ValueError(f"datum niet geldig: {iso}")
    return f"{d:02d}-{MAANDEN[m - 1]}-{j}"


def zoekcriteria(zoek: str = "", van: str = "", aan: str = "", onderwerp: str = "",
                 sinds: str = "", tot: str = "", alleen_ongelezen: bool = False) -> str:
    def tekst(w: str) -> str:
        return '"' + w.replace("\\", "\\\\").replace('"', '\\"') + '"'
    delen: list[str] = []
    if alleen_ongelezen:
        delen.append("UNSEEN")
    if zoek:
        delen += ["TEXT", tekst(zoek)]
    if van:
        delen += ["FROM", tekst(van)]
    if aan:
        delen += ["TO", tekst(aan)]
    if onderwerp:
        delen += ["SUBJECT", tekst(onderwerp)]
    if sinds:
        delen += ["SINCE", imap_datum(sinds)]
    if tot:
        delen += ["BEFORE", imap_datum(tot)]
    return " ".join(delen) or "ALL"


@contextlib.contextmanager
def imap_sessie():
    c = instellingen()
    imap = imaplib.IMAP4_SSL(c["imap_host"], 993, timeout=30)
    imap._encoding = "utf-8"  # zoeken op niet-ASCII tekst
    try:
        imap.login(c["gebruiker"], c["wachtwoord"])
        yield imap
    finally:
        with contextlib.suppress(Exception):
            imap.logout()


def mappen_lijst(imap) -> list[tuple[str, str]]:
    """[(naam, attributen)] van alle mappen."""
    _, data = imap.list()
    uit = []
    for rij in data or []:
        if not rij:
            continue
        tekst = rij.decode("utf-8", "replace") if isinstance(rij, bytes) else str(rij)
        m = re.match(r'\((?P<attr>[^)]*)\) (?P<sep>"[^"]*"|NIL) (?P<naam>.*)$', tekst)
        if m:
            naam = m.group("naam").strip()
            if naam.startswith('"') and naam.endswith('"'):
                naam = naam[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            uit.append((utf7_decode(naam), m.group("attr")))
    return uit


def speciale_map(imap, vlag: str, terugval: str) -> str:
    for naam, attr in mappen_lijst(imap):
        if vlag.lower() in attr.lower():
            return naam
    return terugval


def kies(imap, mapnaam: str, alleen_lezen: bool = True) -> None:
    typ, dat = imap.select(q(mapnaam), readonly=alleen_lezen)
    if typ != "OK":
        namen = ", ".join(n for n, _ in mappen_lijst(imap))
        raise RuntimeError(f"Map '{mapnaam}' bestaat niet. Beschikbaar: {namen}")


def uid_lijst(waarde) -> list[str]:
    uids = [u.strip() for u in re.split(r"[,\s]+", str(waarde)) if u.strip()]
    if not uids or not all(u.isdigit() for u in uids):
        raise ValueError("uid moet een getal zijn, of een lijst getallen met komma's")
    return uids


def kop_tekst(msg, naam: str) -> str:
    waarde = msg.get(naam)
    return str(waarde).strip() if waarde is not None else ""


def mail_tekst(msg) -> str:
    deel = msg.get_body(preferencelist=("plain", "html"))
    if deel is None:
        return ""
    try:
        inhoud = deel.get_content()
    except (LookupError, UnicodeError):
        inhoud = deel.get_payload(decode=True).decode("utf-8", "replace")
    if deel.get_content_type() == "text/html":
        inhoud = re.sub(r"(?is)<(script|style).*?</\1>", "", inhoud)
        inhoud = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", inhoud)
        inhoud = re.sub(r"<[^>]+>", "", inhoud)
        inhoud = re.sub(r"&nbsp;", " ", inhoud)
        inhoud = re.sub(r"\n\s*\n\s*\n+", "\n\n", inhoud)
    return inhoud.strip()[:MAX_TEKST]


def haal_kopjes(imap, uids: list[str]) -> list[dict]:
    if not uids:
        return []
    typ, data = imap.uid(
        "FETCH", ",".join(uids),
        "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])")
    uit = []
    for deel in data or []:
        if not isinstance(deel, tuple):
            continue
        kop = deel[0].decode("utf-8", "replace")
        uid = re.search(r"UID (\d+)", kop)
        vlaggen = re.search(r"FLAGS \(([^)]*)\)", kop)
        msg = email.message_from_bytes(deel[1], policy=email.policy.default)
        uit.append({
            "uid": uid.group(1) if uid else "",
            "datum": kop_tekst(msg, "Date"),
            "van": kop_tekst(msg, "From"),
            "aan": kop_tekst(msg, "To"),
            "onderwerp": kop_tekst(msg, "Subject"),
            "gelezen": "\\Seen" in (vlaggen.group(1) if vlaggen else ""),
        })
    return sorted(uit, key=lambda r: int(r["uid"] or 0), reverse=True)


def haal_bericht(imap, uid: str):
    typ, data = imap.uid("FETCH", uid, "(BODY.PEEK[])")
    for deel in data or []:
        if isinstance(deel, tuple):
            return email.message_from_bytes(deel[1], policy=email.policy.default)
    raise RuntimeError(f"Geen bericht met uid {uid} in die map")


def bouw_bericht(van: str, aan: str, onderwerp: str, tekst: str, cc: str = "",
                 bcc: str = "", antwoord_op=None) -> EmailMessage:
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = van, aan, onderwerp
    if cc:
        m["Cc"] = cc
    if bcc:
        m["Bcc"] = bcc
    m["Date"] = email.utils.formatdate(localtime=True)
    m["Message-ID"] = email.utils.make_msgid(domain=van.split("@")[-1])
    if antwoord_op is not None:
        mid = kop_tekst(antwoord_op, "Message-ID")
        if mid:
            m["In-Reply-To"] = mid
            m["References"] = (kop_tekst(antwoord_op, "References") + " " + mid).strip()
    m.set_content(tekst)  # platte tekst: geen opmaaktekens in klantmail
    return m


def antwoord_onderwerp(origineel: str, nieuw: str) -> str:
    if nieuw:
        return nieuw
    return origineel if re.match(r"(?i)\s*(re|aw)\s*:", origineel) else f"Re: {origineel}"


# ---------------------------------------------------------------- de server
def _server():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("zoho-mail")

    @mcp.tool()
    def mail_mappen() -> list[dict]:
        """Alle mappen van de Zoho-mailbox, met aantal berichten en aantal ongelezen."""
        with imap_sessie() as imap:
            uit = []
            for naam, attr in mappen_lijst(imap):
                if "\\noselect" in attr.lower():
                    continue
                typ, d = imap.status(q(naam), "(MESSAGES UNSEEN)")
                tekst = d[0].decode() if typ == "OK" and d and d[0] else ""
                tot = re.search(r"MESSAGES (\d+)", tekst)
                ong = re.search(r"UNSEEN (\d+)", tekst)
                uit.append({"map": naam, "berichten": int(tot.group(1)) if tot else None,
                            "ongelezen": int(ong.group(1)) if ong else None})
            return uit

    @mcp.tool()
    def mail_zoek(map: str = "INBOX", zoek: str = "", van: str = "", aan: str = "",
                  onderwerp: str = "", sinds: str = "", tot: str = "",
                  alleen_ongelezen: bool = False, aantal: int = 20) -> list[dict]:
        """Zoek berichten in één map en geef kopjes terug, nieuwste eerst. Alle filters zijn
        optioneel en worden gecombineerd. `zoek` zoekt in tekst en kopjes. Datums als
        JJJJ-MM-DD (sinds is inclusief, tot niet). Lezen zet een bericht niet op gelezen."""
        with imap_sessie() as imap:
            kies(imap, map)
            crit = zoekcriteria(zoek, van, aan, onderwerp, sinds, tot, alleen_ongelezen)
            typ, d = imap.uid("SEARCH", "CHARSET", "UTF-8", crit)
            if typ != "OK":
                raise RuntimeError(f"Zoeken mislukte: {d}")
            uids = (d[0].decode().split() if d and d[0] else [])
            return haal_kopjes(imap, uids[-max(1, min(aantal, 100)):])

    @mcp.tool()
    def mail_lees(uid: str, map: str = "INBOX", markeer_gelezen: bool = False) -> dict:
        """Lees één bericht volledig: kopjes, tekst (platte tekst, html wordt omgezet) en de
        namen van bijlagen. Het bericht blijft ongelezen tenzij markeer_gelezen=True."""
        with imap_sessie() as imap:
            kies(imap, map, alleen_lezen=not markeer_gelezen)
            msg = haal_bericht(imap, uid_lijst(uid)[0])
            if markeer_gelezen:
                imap.uid("STORE", uid, "+FLAGS", "(\\Seen)")
            return {
                "uid": uid, "van": kop_tekst(msg, "From"), "aan": kop_tekst(msg, "To"),
                "cc": kop_tekst(msg, "Cc"), "datum": kop_tekst(msg, "Date"),
                "onderwerp": kop_tekst(msg, "Subject"),
                "tekst": mail_tekst(msg),
                "bijlagen": [b.get_filename() or "(naamloos)" for b in msg.iter_attachments()],
            }

    @mcp.tool()
    def mail_markeer(uid: str, map: str = "INBOX", gelezen: bool | None = None,
                     ster: bool | None = None) -> str:
        """Zet berichten op gelezen of ongelezen en/of geef ze een ster. `uid` mag een lijst
        zijn met komma's. Wat je niet opgeeft blijft zoals het was."""
        uids = ",".join(uid_lijst(uid))
        with imap_sessie() as imap:
            kies(imap, map, alleen_lezen=False)
            if gelezen is not None:
                imap.uid("STORE", uids, "+FLAGS" if gelezen else "-FLAGS", "(\\Seen)")
            if ster is not None:
                imap.uid("STORE", uids, "+FLAGS" if ster else "-FLAGS", "(\\Flagged)")
        return f"Bijgewerkt: {uids}"

    @mcp.tool()
    def mail_verplaats(uid: str, naar_map: str, map: str = "INBOX") -> str:
        """Verplaats berichten naar een andere map. `uid` mag een lijst zijn met komma's.
        Verwijderen doe je met naar_map='Trash': er is bewust geen definitief wissen."""
        uids = ",".join(uid_lijst(uid))
        with imap_sessie() as imap:
            kies(imap, map, alleen_lezen=False)
            doel = speciale_map(imap, "\\Trash", naar_map) if naar_map.lower() in (
                "trash", "prullenbak") else naar_map
            if "MOVE" in imap.capabilities:
                typ, d = imap.uid("MOVE", uids, q(doel))
            else:
                typ, d = imap.uid("COPY", uids, q(doel))
                if typ == "OK":
                    imap.uid("STORE", uids, "+FLAGS", "(\\Deleted)")
                    imap.expunge()
            if typ != "OK":
                raise RuntimeError(f"Verplaatsen mislukte: {d}")
        return f"{uids} verplaatst naar {doel}"

    @mcp.tool()
    def mail_concept(aan: str, onderwerp: str = "", tekst: str = "", cc: str = "",
                     antwoord_op_uid: str = "", antwoord_map: str = "INBOX") -> str:
        """Zet een concept klaar in de map Drafts van Zoho, zodat Daniel het kan nakijken en
        zelf versturen. Met antwoord_op_uid wordt het een antwoord (aan en onderwerp worden
        daaruit ingevuld als je ze leeg laat). Platte tekst, geen opmaaktekens."""
        c = instellingen()
        with imap_sessie() as imap:
            orig = None
            if antwoord_op_uid:
                kies(imap, antwoord_map)
                orig = haal_bericht(imap, uid_lijst(antwoord_op_uid)[0])
                aan = aan or kop_tekst(orig, "Reply-To") or kop_tekst(orig, "From")
                onderwerp = antwoord_onderwerp(kop_tekst(orig, "Subject"), onderwerp)
            if not aan:
                raise ValueError("aan ontbreekt")
            msg = bouw_bericht(c["van"], aan, onderwerp, tekst, cc, antwoord_op=orig)
            drafts = speciale_map(imap, "\\Drafts", "Drafts")
            typ, d = imap.append(q(drafts), "\\Draft",
                                 imaplib.Time2Internaldate(time.time()), msg.as_bytes())
            if typ != "OK":
                raise RuntimeError(f"Concept opslaan mislukte: {d}")
        return f"Concept staat klaar in {drafts}, aan {aan}, onderwerp '{onderwerp}'."

    @mcp.tool()
    def mail_verstuur(aan: str, onderwerp: str, tekst: str, bevestigd: bool = False,
                      cc: str = "", bcc: str = "", antwoord_op_uid: str = "",
                      antwoord_map: str = "INBOX") -> str:
        """Verstuur echt een mail vanuit Zoho. Alleen aanroepen nadat Daniel in de chat
        uitdrukkelijk ja heeft gezegd op deze tekst en deze ontvanger; zonder bevestigd=True
        weigert de tool. Platte tekst. Een kopie komt in Sent. Met antwoord_op_uid blijft
        de mail in dezelfde draad."""
        if not bevestigd:
            raise PermissionError(
                "Niet verstuurd: laat Daniel eerst ja zeggen en zet dan bevestigd=True. "
                "Gebruik anders mail_concept.")
        c = instellingen()
        with imap_sessie() as imap:
            orig = None
            if antwoord_op_uid:
                kies(imap, antwoord_map)
                orig = haal_bericht(imap, uid_lijst(antwoord_op_uid)[0])
            msg = bouw_bericht(c["van"], aan, onderwerp, tekst, cc, bcc, antwoord_op=orig)
            with smtplib.SMTP_SSL(c["smtp_host"], 465, timeout=30) as smtp:
                smtp.login(c["gebruiker"], c["wachtwoord"])
                smtp.send_message(msg)
            verstuurd = speciale_map(imap, "\\Sent", "Sent")
            with contextlib.suppress(Exception):
                imap.append(q(verstuurd), "\\Seen",
                            imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        return f"Verstuurd aan {aan}, onderwerp '{onderwerp}'."

    return mcp


def test() -> int:
    try:
        c = instellingen()
        with imap_sessie() as imap:
            print(f"Inloggen gelukt als {c['gebruiker']} op {c['imap_host']}.")
            for naam, attr in mappen_lijst(imap):
                print(f"  {naam}  {attr}")
        with smtplib.SMTP_SSL(c["smtp_host"], 465, timeout=30) as smtp:
            smtp.login(c["gebruiker"], c["wachtwoord"])
            print(f"Versturen (SMTP {c['smtp_host']}) inloggen gelukt.")
        return 0
    except Exception as e:  # nooit het wachtwoord tonen, alleen de soort fout
        print(f"MISLUKT: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(test())
    _server().run()
