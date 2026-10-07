"""
Eenmalige inhaalronde: opvolging na Daniels video voor mensen die buiten de
leadlijst vielen (Daniel, 05-10-2026).

De gewone video-opvolging (leadgen_mail.py, _video_opvolging) kijkt alleen naar
adressen uit de leadlijst. Zeventien mensen die om de video vroegen en daarna stil
bleven stonden daar niet in en kregen dus nooit een opvolging.

De doelen staan NIET in deze repo (die is publiek) maar in Supabase, tabel
leadgen_opslag, naam "video_inhaal": {"doelen": {adres: {"v1": tijd, "v2": tijd,
"klaar": reden}}}. Elke beurt van de leadmachine draait dit script; het is
idempotent en doet meestal niets.

Per doel: opvolging V1 (tekst uit de spreadsheet), na minstens 4 dagen V2, daarna
klaar. Overal dezelfde poorten als de gewone video-opvolging: alleen overdag,
hooguit 5 per beurt, nooit na een reactie van hen of een eigen mail van Daniel
erna, nooit naar een klant of iemand met "Niet meer mailen".

Gebruik: python scripts/video_inhaal.py [--echt]   (zonder --echt alleen kijken)
"""
from __future__ import annotations

import imaplib
import os
import re
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scripts.leadgen_mail as lm  # noqa: E402

NAAM = "video_inhaal"
PER_BEURT = 5
V2_NA_DAGEN = 4


def draai(echt: bool) -> int:
    rec = lm._db_lees(NAAM, {}) or {}
    doelen = rec.get("doelen") or {}
    open_ = [a for a, d in doelen.items() if not d.get("klaar")]
    if not open_:
        return 0
    nu = datetime.now()
    if echt and not (lm.VIDEO_VENSTER[0] <= nu.strftime("%H:%M") <= lm.VIDEO_VENSTER[1]):
        return 0
    gebruiker, host = lm._need("MAIL_USER"), os.environ.get("MAIL_HOST", "")
    m = lm._sheets_module()
    try:
        teksten = lm._teksten()
        gestopt = lm.Leadboek().gestopt()
    except (m.TekstenFout, m.SheetsFout) as e:
        print(f"  (video-inhaal overgeslagen, spreadsheet niet bruikbaar: {e})")
        return 0
    state = lm._state()
    gedaan = 0
    with imaplib.IMAP4_SSL(os.environ["IMAP_HOST"], 993) as imap:
        imap.login(gebruiker, os.environ["MAIL_PASS"])
        ons = lm._laatste_per_adres(imap, ["Verzonden"], "To")
        hun = lm._laatste_per_adres(imap, ["INBOX", lm.MAP_BEANTWOORD, "Afval"], "From")
        for adres in open_:
            if gedaan >= PER_BEURT:
                break
            d = doelen[adres]
            st = state.get(adres, {})
            if hun.get(adres, 0) > ons.get(adres, 0):
                d["klaar"] = "heeft gereageerd"
                continue
            if adres in gestopt or any(st.get(k) for k in ("afgemeld", "afgewezen", "concurrent", "bounce")):
                d["klaar"] = "niet meer mailen"
                continue
            if lm.is_klant(adres):
                d["klaar"] = "heeft een account"
                continue
            if "v1" in d:
                if ons.get(adres, 0) > datetime.fromisoformat(d["v1"]).timestamp() + 600:
                    d["klaar"] = "Daniel schreef zelf daarna"
                    continue
                if (nu - datetime.fromisoformat(d["v1"])).total_seconds() / 86400 < V2_NA_DAGEN:
                    continue
                stap, sleutel = 2, "V2"
            else:
                stap, sleutel = 1, "V1"
            draad = lm._laatste_verzonden_bericht(imap, adres)
            if not draad:
                continue
            if stap == 1 and not lm.VIDEO_LINK.search(draad.get("tekst") or ""):
                d["klaar"] = "laatste mail had geen videolink"
                continue
            if stap == 1 and lm._is_afsluiting(draad["tekst"]):
                d["klaar"] = "afsluitende mail"
                continue
            waarom = lm._waarom_geen_concept(adres, draad)
            if waarom:
                print(f"  video-inhaal niet naar {adres}: {waarom}")
                continue
            rij = teksten[sleutel]
            jullie = "jullie" in (draad.get("Subject") or "").lower() and rij.get("tekst_jullie")
            kern = m.vul_in(rij["tekst_jullie"] if jullie else rij["tekst_je"], {})
            if "[" in kern:
                print(f"  video-inhaal gestopt: onvervulde invulvelden in {sleutel}")
                return gedaan
            tekst = lm._netjes(kern + "\n\n\x00" + teksten["HANDTEKENING"]["tekst_je"])
            plat = lambda v: re.sub(r"\s+", " ", str(v or "")).strip()
            onderwerp = plat(draad.get("Subject"))
            if not onderwerp.lower().startswith("re:"):
                onderwerp = "Re: " + onderwerp
            msg = EmailMessage()
            msg["From"] = f"{lm.AFZENDER_NAAM} <{gebruiker}>"
            msg["To"] = adres
            msg["Subject"] = onderwerp
            msg["List-Unsubscribe"] = f"<mailto:{gebruiker}?subject=stop>"
            mid = plat(draad.get("Message-ID"))
            if mid:
                msg["In-Reply-To"] = mid
                msg["References"] = (plat(draad.get("References")) + " " + mid).strip()
            msg.set_content(tekst)
            msg.add_alternative(lm._open_pixel_html(adres, tekst, "opvolg"), subtype="html")
            if not echt:
                print(f"\n  ZOU VERSTUREN: {sleutel} aan {adres}\n  Onderwerp: {onderwerp}\n\n{tekst}")
                gedaan += 1
                continue
            with lm._postbode(gebruiker, host) as stuur:
                stuur(msg)
            # Het moment van VERSTUREN, niet van het begin van de beurt: de mails gaan
            # een paar minuten na elkaar, en met het beginmoment las de volgende beurt
            # onze eigen mail aan als "Daniel schreef zelf daarna" (06-10-2026).
            d["v1" if stap == 1 else "v2"] = datetime.now().isoformat(timespec="seconds")
            if stap == 2:
                d["klaar"] = "alle opvolgingen verstuurd"
            lm._db_schrijf(NAAM, rec)       # meteen: een afgebroken beurt mag niets dubbel doen
            gedaan += 1
            print(f"  → video-inhaal {sleutel} aan {adres}", flush=True)
    if echt:
        lm._db_schrijf(NAAM, rec)
    return gedaan


if __name__ == "__main__":
    n = draai("--echt" in sys.argv)
    print(f"{n} video-inhaalmail(s) {'verstuurd' if '--echt' in sys.argv else 'zouden nu uitgaan'}.")
