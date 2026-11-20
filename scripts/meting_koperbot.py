"""Meting van een koperbericht-bot op een GESCHREVEN testset (20-11-2026).

LET OP: er zijn geen echte koperberichten opgeslagen (de extensie telt alleen ongelezen
berichten), dus dit zijn 80 realistische Marktplaats-berichten die Claude schreef, met het
verwachte gedrag erbij. Dat is optimistischer dan echte berichten. Echte meting vraagt
berichten van Daniel of een week meelezen met toestemming.

Ontwerp: het model sorteert alleen (intent, bedrag, letterlijk citaat uit de advertentie).
Gewone code beslist:
  beschikbaar              -> auto: "Ja, nog beschikbaar"
  prijs/bod                -> bedrag >= 75% van de prijs: ESCALEER (serieuze koper); anders auto (vaste prijszin)
  vraag, antwoord in ad    -> auto, alleen als het citaat LETTERLIJK in de advertentie staat
  vraag, niet in ad        -> escaleer
  oplichting/buiten platform -> negeer en markeer (nooit antwoorden)
  de rest                  -> escaleer
Onveilig = auto of negeer waar de testset escaleer verwacht (een koper gemist of fout geantwoord).
"""
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

AD = ("Blauwe trui Zara, maat M. 100% wol, lengte 62 cm, borstbreedte 54 cm. Goede staat, een keer gedragen. "
      "Prijs 25 euro. Ophalen in Utrecht Overvecht, of verzenden voor 4,25 euro via PostNL.")
PRIJS = 25.0

# (bericht, verwacht): beschikbaar | auto_prijs | auto_info | escaleer | negeer
TESTS = [
    ("Is deze nog beschikbaar?", "beschikbaar"), ("Hoi, nog te koop?", "beschikbaar"),
    ("Is die trui er nog?", "beschikbaar"), ("goedemiddag nog beschikbaar", "beschikbaar"),
    ("Hallo is dit item nog te koop??", "beschikbaar"), ("Nog beschikbaar? Groetjes Mieke", "beschikbaar"),
    ("Wat is je laagste prijs?", "auto_prijs"), ("Laatste prijs?", "auto_prijs"),
    ("Kan er wat vanaf?", "auto_prijs"), ("Wil je 10 euro hiervoor?", "auto_prijs"),
    ("Geef je 8 euro, kan je morgen niet ophalen", "auto_prijs"), ("5 euro en ik haal hem nu op", "auto_prijs"),
    ("Doe 12 euro dan kom ik vandaag", "auto_prijs"), ("Mag het voor 15?", "auto_prijs"),
    ("bod: 3 euro", "auto_prijs"), ("Ik wil er niet meer dan 10 euro voor betalen", "auto_prijs"),
    ("Doe me je laagste prijs, ik koop er meerdere", "escaleer"),
    ("Ik geef 22 euro, kan ik vanavond ophalen?", "escaleer"), ("Doe 20 euro dan neem ik hem direct mee", "escaleer"),
    ("Ik bied 24 euro", "escaleer"), ("Voor 21 euro heb je een deal, ik kan morgen", "escaleer"),
    ("Ik neem hem voor 25 euro, hoe kan ik betalen?", "escaleer"), ("Kan ik hem komen halen vandaag voor de vraagprijs?", "escaleer"),
    ("Wat is de maat?", "auto_info"), ("Van welk materiaal is dit?", "auto_info"),
    ("Hoe lang is de trui?", "auto_info"), ("Wat zijn de verzendkosten?", "auto_info"),
    ("Waar kan ik hem ophalen?", "auto_info"), ("Is het wol?", "auto_info"),
    ("Hoe breed is hij bij de borst?", "auto_info"), ("kan je ook verzenden?", "auto_info"),
    ("Welk merk is het?", "auto_info"), ("In welke staat is hij?", "auto_info"),
    ("Zit er een vlek op?", "escaleer"), ("Heb je ook een foto van de achterkant?", "escaleer"),
    ("Hoe oud is de trui ongeveer?", "escaleer"), ("Is hij gewassen op 40 graden?", "escaleer"),
    ("Kan je hem ook op zaterdag laten bezorgen in Rotterdam?", "escaleer"),
    ("Past dit bij iemand van 1.85?", "escaleer"), ("Is er een etiket in met wasvoorschrift?", "escaleer"),
    ("Heb je nog meer truien van Zara?", "escaleer"), ("Wil je ruilen voor een jas?", "escaleer"),
    ("Kan ik 3 truien samen kopen met korting?", "escaleer"), ("Ik kom vrijdag, past dat?", "escaleer"),
    ("Wat is de nieuwprijs?", "escaleer"), ("Zit er ook een doos bij?", "escaleer"),
    ("Is dit echt een Zara?", "escaleer"),
    ("Ik wil hem graag kopen, kunnen we app'en? Mijn nummer is 0612345678", "negeer"),
    ("Stuur je mailadres dan stuur ik een betaalverzoek", "negeer"),
    ("Ik betaal via een betaallink die ik je stuur, ok?", "negeer"),
    ("Mijn koerier haalt hem op, ik betaal 40 euro, stuur je IBAN", "negeer"),
    ("Ik betaal direct via Marktplaats Betalen, klik op deze link: bit.ly/x8k2", "negeer"),
    ("Ik ben in het buitenland, ik laat mijn neef hem ophalen, stuur je bankgegevens", "negeer"),
    ("Doe 30 euro dan betaal ik meer als je de code van de beveiligde betaling doorgeeft", "negeer"),
    ("Kunnen we dit buiten Marktplaats afhandelen via WhatsApp?", "negeer"),
    ("Ik stuur je een Tikkie, geef je rekeningnummer", "negeer"),
    ("Hallo mooie trui. Bekijk mijn profiel voor goedkope sneakers www.sneakerdeals.biz", "negeer"),
    ("Verkoop jij ook via Vinted? Ik heb een betere dienst voor je", "negeer"),
    ("Geweldige aanbieding! Klik hier om te verdienen", "negeer"),
    ("Ik neem hem, wil je hem verzenden? Ik betaal via PayPal vrienden en familie", "negeer"),
    ("Ik ga hem ophalen, mag ik je telefoonnummer?", "escaleer"),
    ("Nog beschikbaar? Ik wil hem vandaag ophalen, 22 euro", "escaleer"),
    ("Hoi, mag er 5 euro af als ik hem kom halen?", "auto_prijs"),
    ("Is hij nog te koop en wat is je laagste?", "auto_prijs"),
    ("Hallo, ik ben geïnteresseerd. Kan ik morgen langskomen?", "escaleer"),
    ("Ik wil hem graag kopen", "escaleer"), ("Ik koop hem, wanneer kan ik komen?", "escaleer"),
    ("Hij is toch te groot? Ik kijk even verder", "escaleer"),
    ("klopt het dat hij 62 cm lang is?", "auto_info"), ("Is hij 100% wol?", "auto_info"),
    ("Ophalen in Utrecht? Welke wijk precies?", "auto_info"),
    ("Verzenden naar Duitsland mogelijk?", "escaleer"),
    ("Kun je de prijs verlagen naar 10? Dan neem ik er twee", "escaleer"),
    ("wat het laagste wat je wilt hebben, ik wil snel", "auto_prijs"),
    ("Doe 17,50 dan is hij van mij", "auto_prijs"),
    ("Bedankt, ik heb hem inmiddels elders gekocht", "escaleer"),
    ("Mag ik hem eerst passen? Ik woon in Zeist", "escaleer"),
    ("Waarom verkoop je hem?", "escaleer"),
    ("Zit er een gaatje in?", "escaleer"),
    ("Ik zoek een trui als deze maar in L, heb je die?", "escaleer"),
    ("Hallo!", "escaleer"),
    ("😊", "escaleer"),
]

PROMPT = (
    "You triage a buyer's message about a second-hand listing. Answer with ONLY one JSON object: "
    '{"intent": one of beschikbaar | prijs | vraag | oplichting | anders, '
    '"bedrag": the euro amount the buyer offers as a number or null, '
    '"citaat": for intent vraag: the EXACT words copied from the listing that answer the question, or null if the '
    "listing does not contain the answer}.\n"
    "beschikbaar = only asks if it is still for sale. prijs = asks lowest price or offers an amount. "
    "vraag = asks a question about the item or handover. oplichting = wants to move to WhatsApp/email/phone, "
    "payment links, shipping on the buyer's account, IBAN requests, advertising or spam. anders = everything else "
    "(wants to buy or pick up, trade, bundle, greeting, unclear).\n"
    "LISTING: " + json.dumps(AD) + "\nMESSAGE: ")


def beslis(ant: dict) -> str:
    intent = ant.get("intent")
    if intent == "oplichting":
        return "negeer"
    if intent == "beschikbaar":
        return "beschikbaar"
    if intent == "prijs":
        b = ant.get("bedrag")
        if isinstance(b, (int, float)) and not isinstance(b, bool) and b >= 0.75 * PRIJS:
            return "escaleer"
        if isinstance(b, (int, float)) and not isinstance(b, bool):
            return "auto_prijs"
        return "auto_prijs"
    if intent == "vraag":
        c = ant.get("citaat")
        if isinstance(c, str) and len(c) >= 3 and re.sub(r"\s+", " ", c.strip().lower()) in re.sub(r"\s+", " ", AD.lower()):
            return "auto_info"
        return "escaleer"
    return "escaleer"


def main():
    from backend.services import taalmodel, gemini_vertaling
    import os
    if os.environ.get("MODEL"):
        gemini_vertaling._kandidaten = lambda: [os.environ["MODEL"]]
    uit, fouten = [], []
    for msg, verwacht in TESTS:
        time.sleep(5)
        try:
            t = taalmodel.vraag(PROMPT + json.dumps(msg, ensure_ascii=False), max_tokens=200, wat="koperbot",
                                denken=False, claude_toegestaan=False, alleen_lite=True)
            ant = json.loads(re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip())
            if not isinstance(ant, dict):
                raise ValueError
        except Exception as e:  # noqa: BLE001
            uit.append({"msg": msg, "verwacht": verwacht, "gekozen": "GEEN_ANTWOORD", "fout": str(e)[:60]})
            continue
        gekozen = beslis(ant)
        uit.append({"msg": msg, "verwacht": verwacht, "gekozen": gekozen, "ant": ant})
        print(("ok  " if gekozen == verwacht else "FOUT"), verwacht, "->", gekozen, "|", msg[:70], flush=True)
    n = [x for x in uit if x["gekozen"] != "GEEN_ANTWOORD"]
    goed = sum(x["gekozen"] == x["verwacht"] for x in n)
    # onveilig: koper gemist of fout beantwoord = de bot doet iets automatisch of negeert waar de mens moest kijken
    onveilig = [x for x in n if x["verwacht"] == "escaleer" and x["gekozen"] != "escaleer"]
    gemist_scam = [x for x in n if x["verwacht"] == "negeer" and x["gekozen"] != "negeer"]
    ten_onrechte_negeer = [x for x in n if x["gekozen"] == "negeer" and x["verwacht"] != "negeer"]
    auto_fout = [x for x in n if x["gekozen"] in ("beschikbaar", "auto_prijs", "auto_info") and x["verwacht"] != x["gekozen"]]
    print({"beantwoord": len(n), "van": len(uit), "exact_goed": goed,
           "onveilig_koper_gemist_of_fout_geantwoord": len(onveilig),
           "oplichting_niet_herkend": len(gemist_scam), "ten_onrechte_genegeerd": len(ten_onrechte_negeer),
           "auto_fout": len(auto_fout), "verwacht": dict(Counter(x["verwacht"] for x in n))})
    for x in onveilig + gemist_scam + auto_fout:
        print("  !", x["verwacht"], "->", x["gekozen"], "|", x["msg"], x.get("ant"))
    Path.home().joinpath(".omnivaleur/meting_ai/koperbot.json").write_text(json.dumps(uit, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
