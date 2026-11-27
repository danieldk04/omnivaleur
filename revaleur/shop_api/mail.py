"""Mails van de Revaleur-webshop via het eigen Resend-account, in Daniels stijl (docs/schrijfstijl-daniel.md in de hoofdrepo).

Nooit "sorry", "ligt aan ons" of "onze fout": begin met het goede nieuws, zeg neutraal wat er speelde en wat de klant nu kan.
"""
import httpx

from .config import settings

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
    kosten = float(bestelling.get("verzendkosten") or 0)
    verzend = _euro(kosten, taal) if kosten else ("gratis" if taal == "nl" else "free")
    return (t["onderwerp"].format(nr=bestelling.get("nummer", "")),
            t["tekst"].format(naam=f" {voornaam}" if voornaam else "", regels=regels,
                              totaal=_euro(float(bestelling.get("totaal") or 0), taal), verzend=verzend))


def stuur_bevestiging(bestelling: dict) -> None:
    if not bestelling.get("email"):
        raise RuntimeError("bestelling zonder e-mailadres")
    if not settings.resend_api_key:
        raise RuntimeError("REVALEUR_RESEND_API_KEY ontbreekt")
    onderwerp, tekst = bericht(bestelling)
    r = httpx.post("https://api.resend.com/emails", timeout=20,
                   headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                   json={"from": settings.mail_van, "to": [bestelling["email"]], "subject": onderwerp, "text": tekst,
                         "reply_to": settings.mail_antwoord})
    if r.status_code >= 300:
        raise RuntimeError(f"Resend weigerde de mail ({r.status_code}): {r.text[:200]}")
