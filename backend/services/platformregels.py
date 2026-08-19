"""
Wat mag er op welk platform.

TWEE VERSCHILLENDE VRAGEN, EN DIE MOETEN GESCHEIDEN BLIJVEN
1. Wat verbiedt het platform? Dat is niet onderhandelbaar en wordt geweigerd.
2. Wat wil deze verkoper daar zelf niet plaatsen? Dat is een voorkeur, staat in
   zijn eigen instellingen, en hij kan hem elk moment omzetten.

Die twee door elkaar halen is precies de fout die hier eerst in zat. Vinted werd
behandeld als een puur modeplatform en daarmee werden elektronica, muziek en
games geweigerd. Dat is onjuist: Vinted verkoopt sinds de uitbreiding ook Home,
Elektronica, Boeken & multimedia, Hobby's & verzamelen en Sport — nagelezen op
hun eigen categoriepagina (vinted.nl/help/1573). Een verzonnen verbod is net zo
schadelijk als een gemist verbod: het houdt iemand tegen bij iets dat gewoon mag,
en daar kan hij zelf niets tegen beginnen.

WAT VINTED WEL LETTERLIJK VERBIEDT
Van vinted.nl/help/5 ("Artikelen die niet zijn toegestaan"), woordelijk:
"Alle voorwerpen die worden beschouwd als archeologische voorwerpen,
cultuurgoederen of cultureel erfgoed, inclusief postzegels, munten, bankbiljetten
en aandeelbewijzen."
Dat is de harde lijst hieronder. Alles wat daar niet in staat wordt hooguit een
waarschuwing, nooit een weigering.
"""
from __future__ import annotations

import re

OK = "ok"
TWIJFEL = "twijfel"
BLOKKADE = "blokkade"

# Letterlijk door Vinted verboden. Munten, bankbiljetten, postzegels,
# aandeelbewijzen en archeologische vondsten.
#
# "munt" staat er met woordgrenzen en zonder losse samenstellingen: een
# muntstuk is verboden, maar een muntgroene jurk niet, en "gemunt" al helemaal
# niet. Dezelfde soort fout als "aangeboden" die eerder biedingen verzon.
_VERBODEN_RE = re.compile(
    r"\b(munt|munten|muntstuk|muntenverzameling|zilverm[ui]nt\w*|goudm[ui]nt\w*|"
    r"bankbiljet\w*|biljetten|postzegel\w*|aandeelbewijs|aandeelbewijzen|effecten|"
    r"archeologisch\w*|opgraving\w*|romeinse?\s+(munt|vondst)|"
    r"gouden\s*tientje|zilveren\s*dukaat|dukaat|rijksdaalder|gulden\s*munt)\b",
    re.I,
)
_VERBODEN_REDEN = (
    "Vinted verbiedt munten, bankbiljetten, postzegels, aandeelbewijzen en "
    "archeologische voorwerpen. Dit artikel lijkt daaronder te vallen."
)

# Niet letterlijk in de lijst die wij konden nalezen, maar wel het gebied waar
# het misgaat. Waarschuwen, niet weigeren — wij hebben hierover niet het laatste
# woord en de verkoper kent zijn eigen voorraad beter.
_TWIJFEL_PATRONEN = [
    (re.compile(r"\b((zilver|goud|platina)ba(a|e)r\w*|baar|baren|bullion|troy\s*ounce|beleggings(goud|zilver)|"
                r"edelsteen|edelstenen|losse\s*diamant)\b", re.I),
     "Dit lijkt edelmetaal of een losse steen als belegging in plaats van een "
     "sieraad of gebruiksvoorwerp. Controleer of Vinted dit toestaat."),
    (re.compile(r"\b(ivoor|ivoren|bont(jas|kraag)?|nertsbont|vossenbont|"
                r"reptielenhuid|krokodillenleer|schildpad)\b", re.I),
     "Dit lijkt een dierlijk product (ivoor, bont, reptielenhuid). Vinted staat "
     "die niet toe en er gelden vaak ook wettelijke regels."),
]

# De categoriegroepen uit onze eigen boom, zoals ze in het scherm heten.
GROEPEN = ("dames", "heren", "kinderen", "unisex", "sieraden",
           "antiek", "kunst", "muziek", "games", "electronics")


def _groep(item: dict) -> str:
    cat = str(item.get("category") or "").strip().lower()
    for g in GROEPEN:
        if cat.startswith(g + " "):
            return g
    return ""


def _tekst(item: dict) -> str:
    return f"{item.get('title') or ''} {item.get('description') or ''}"


def beoordeel(item: dict, platform: str, voorkeur: list[str] | None = None) -> tuple[str, str]:
    """(oordeel, reden) voor dit artikel op dit platform.

    `voorkeur` is de eigen keuze van de verkoper: de categoriegroepen die hij op
    Vinted wil hebben. Leeg of None betekent "alles wat mag". Een artikel dat
    buiten zijn voorkeur valt wordt geweigerd met een reden die duidelijk zegt
    dat het zíjn instelling is en niet die van Vinted — anders gaat hij zoeken
    naar een fout die er niet is.
    """
    if platform != "vinted":
        return OK, ""

    tekst = _tekst(item)

    if _VERBODEN_RE.search(tekst):
        return BLOKKADE, _VERBODEN_REDEN

    if voorkeur:
        groep = _groep(item)
        # Geen categorie ingevuld? Dan niets beweren. Blokkeren op onwetendheid
        # is het slechtste van twee werelden.
        if groep and groep not in voorkeur:
            return BLOKKADE, (
                f"Je eigen instelling laat op Vinted alleen "
                f"{', '.join(voorkeur)} toe. Dit artikel valt onder {groep}. "
                f"Aan te passen bij Platforms."
            )

    for patroon, reden in _TWIJFEL_PATRONEN:
        if patroon.search(tekst):
            return TWIJFEL, reden

    return OK, ""


def geblokkeerde_platforms(item: dict, platforms: list[str],
                           voorkeur: list[str] | None = None) -> dict[str, str]:
    uit = {}
    for p in platforms:
        oordeel, reden = beoordeel(item, p, voorkeur)
        if oordeel == BLOKKADE:
            uit[p] = reden
    return uit
