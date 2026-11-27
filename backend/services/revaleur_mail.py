"""Mails van de Revaleur-webshop, in Daniels stijl (docs/schrijfstijl-daniel.md).

Nooit "sorry", "ligt aan ons" of "onze fout" (CLAUDE.md, 28-10-2026): begin met het goede
nieuws, zeg neutraal wat er speelde en wat de klant nu kan.
"""
from backend.services.email import send_email_checked

AFZENDER_ANTWOORD = "info@revaleur.com"

_TEKST = {
    "nl": {
        "onderwerp": "Je Revaleur-bestelling is binnen (#{nr})",
        "tekst": ("Hoi{naam},\n\nTop, je bestelling is binnen en betaald. Ik ga er direct mee aan de slag.\n\n"
                  "{regels}\n\nTotaal: {totaal} (verzending {verzend})\n\n"
                  "Je pakket gaat maandag t/m zaterdag meestal binnen 1 werkdag de deur uit. Zodra het onderweg is, "
                  "krijg je een mail met een trackinglink.\n\nVragen? Mail gerust naar info@revaleur.com.\n\nGroet,\nDaniel\nRevaleur"),
    },
    "en": {
        "onderwerp": "Your Revaleur order is in (#{nr})",
        "tekst": ("Hi{naam},\n\nGreat news, your order is in and paid. I'm getting it ready right away.\n\n"
                  "{regels}\n\nTotal: {totaal} (shipping {verzend})\n\n"
                  "Orders ship Monday to Saturday, usually within 1 business day. As soon as your parcel is on its way, "
                  "you'll get an email with a tracking link.\n\nQuestions? Just email info@revaleur.com.\n\nBest,\nDaniel\nRevaleur"),
    },
}


def _euro(x: float, taal: str) -> str:
    s = f"{x:.2f}"
    return "€" + (s.replace(".", ",") if taal == "nl" else s)


def bericht(bestelling: dict) -> tuple[str, str]:
    taal = "nl" if bestelling.get("taal") == "nl" else "en"
    t = _TEKST[taal]
    regels = "\n".join(f"- {a.get('titel')} ({_euro(a.get('prijs') or 0, taal)})" for a in bestelling.get("artikelen") or [])
    voornaam = (bestelling.get("naam") or "").split(" ")[0]
    verzend = _euro(float(bestelling.get("verzendkosten") or 0), taal) if float(bestelling.get("verzendkosten") or 0) else (
        "gratis" if taal == "nl" else "free")
    return (t["onderwerp"].format(nr=bestelling.get("nummer", "")),
            t["tekst"].format(naam=f" {voornaam}" if voornaam else "", regels=regels,
                              totaal=_euro(float(bestelling.get("totaal") or 0), taal), verzend=verzend))


def stuur_bevestiging(bestelling: dict) -> None:
    if not bestelling.get("email"):
        raise RuntimeError("bestelling zonder e-mailadres")
    onderwerp, tekst = bericht(bestelling)
    send_email_checked(onderwerp, tekst, to=bestelling["email"], reply_to=AFZENDER_ANTWOORD)
