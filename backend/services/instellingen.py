"""
Persoonlijke instellingen per verkoper.

WAAROM HIER EN NIET IN EEN EIGEN TABEL
Een nieuwe tabel betekent dat Daniel eerst met de hand SQL moet draaien in
Supabase, en tot dat moment werkt de functie voor niemand. Dat is hier al vaker
gebeurd en dan blijft een afgebouwde knop weken dood liggen. `platform_credentials`
bestaat al, staat per gebruiker en heeft een vrij JSON-veld. Er wordt daarom één
rij per verkoper gebruikt met platform `_settings`; geen enkele platformcode kijkt
naar die naam, dus hij komt nergens anders bovendrijven.

Alles wat hier binnenkomt wordt begrensd. Een instelling die de verkoper zelf zet
mag nooit tot een waarde leiden die zijn account in gevaar brengt.
"""
from __future__ import annotations

import logging

from backend.database import get_db, fetch_all

logger = logging.getLogger(__name__)

RIJ = "_settings"

# Hoe vaak een advertentie opnieuw geplaatst mag worden.
#
# Ondergrens 7: vaker dan een keer per week is op Marktplaats geen onderhoud meer
# maar een patroon. Bovengrens 85: Marktplaats gooit een advertentie na 90 dagen
# zelf weg, dus daarboven zou de instelling stilzwijgend niets meer doen.
RELIST_DAGEN_STANDAARD = 27
RELIST_DAGEN_MIN = 7
RELIST_DAGEN_MAX = 85

# Welke categoriegroepen deze verkoper op Vinted wil hebben. Leeg = alles wat
# Vinted zelf toestaat. Dit is een VOORKEUR, geen platformregel: Jaap
# Zilverwebsite wil er alleen sieraden op, maar zijn buurman mag daar prima
# elektronica verkopen. Die twee dingen moeten uit elkaar blijven, anders staat
# de voorkeur van de een als verbod in de weg bij de ander.
# LET OP: deze lijst moet gelijk blijven aan GROEPEN in platformregels.py en aan
# VINTED_GROEPEN in frontend/app.html. Loopt hij achter, dan ontstaat het ergste
# soort fout: het dashboard zegt dat een artikel op Vinted mag en de server
# blokkeert het alsnog, met een reden die naar een instelling wijst die de
# verkoper nooit heeft kunnen aanvinken. Precies dat gebeurde met "wonen" (sinds
# augustus 2026) en zou met "audio" ook zijn gebeurd; beide op 27-08-2026
# toegevoegd. test_vinted_voorkeur bewaakt het nu.
VINTED_GROEPEN_GELDIG = ("dames", "heren", "kinderen", "unisex", "sieraden",
                         "antiek", "kunst", "muziek", "games", "electronics",
                         "wonen", "audio", "boeken", "speelgoed", "fietsen",
                         "sportartikelen", "witgoed", "klussen", "computers")

# De EU verplicht sinds de GPSR bij vrijwel elke advertentie een
# "verantwoordelijke partij": naam, postadres en e-mailadres van de fabrikant of
# van de EU-gemachtigde. Marktplaats markeert die drie velden inmiddels als
# verplicht, en zonder ingevulde waarde weigert het formulier te plaatsen.
#
# Dit hoort NIET geraden te worden. Hier stond ooit Revaleur als vaste waarde,
# waardoor elke klant publiceerde met andermans bedrijfsnaam als aansprakelijke
# partij — juridisch onjuist en niet iets waar een verkoper om heeft gevraagd.
# De verkoper vult het één keer zelf in en het gaat daarna overal mee.
FABRIKANT_VELDEN = ("fabrikant_naam", "fabrikant_adres", "fabrikant_email")

# ... MAAR HET IS EEN KEUZE, GEEN VERPLICHTING (30-08-2026, Amanda).
#
# Zo stond het hier niet. Wie zijn drie velden niet invulde kón niet publiceren
# naar Marktplaats en 2dehands, dus vulde iedereen ze in — en daarna staan je
# bedrijfsnaam, postadres en e-mailadres onder ELKE advertentie, in het blok dat
# op Marktplaats "Fabrikant" heet. Amanda: "hij zet bij fabrikant, adres en
# mailadres de bedrijfsgegevens van mijn bedrijf neer… Dat is niet de bedoeling."
#
# Ze heeft gelijk dat dat een keuze hoort te zijn. Wie tweedehands en brocante
# verkoopt is niet de fabrikant van wat hij verkoopt, en Marktplaats vraagt dit
# blok lang niet in elke categorie. Daarom: aan blijft aan (er verandert niets
# voor wie het al ingevuld heeft), maar het kan uit — en dan wordt er niets meer
# ingevuld en niets meer geblokkeerd.
FABRIKANT_MEESTUREN = "fabrikant_meesturen"

# WAAR DE VERKOPER STAAT, ZOALS HET OP HET ZOEKERTJE KOMT (11-09-2026).
#
# Marktplaats en 2dehands vullen het contactblok uit het account van de
# verkoper, maar dat account kent maar één adresgegeven: een postcode in het
# formaat van dat land. Nagemeten op een ingelogd 2dehands-account (10-09-2026):
# Profiel > Contactgegevens heeft Naam, Postcode ("1234") en Telefoonnummer,
# verder niets. Wie in Nederland woont en op 2dehands.be plaatst kan daar dus
# niets invullen dat klopt.
#
# Op het zoekertje zelf zit die keuze wél: "Je locatie" met België (of, op
# Marktplaats, Nederland) tegenover Buitenland, en bij Buitenland een land uit
# een lijst plus een woonplaats. 2dehands onthoudt die keuze niet — De Juiste
# Toon heeft 402 zoekertjes op "Etten-Leur, Nederland" in acht verschillende
# spellingen, omdat hij het elke keer opnieuw intikt.
#
# Daarom staat het hier: de verkoper vult land en woonplaats één keer in, en de
# extensie zet ze op elk formulier. De postcode is voor het andere geval: woont
# hij in hetzelfde land als het kanaal, dan hoort er een postcode in plaats van
# een land en woonplaats, en die vult het formulier normaal zelf uit het
# account. Is dat veld leeg, dan gebruiken we deze.
#
# Leeg laten mag: dan verandert er niets en blijft het formulier doen wat het
# altijd deed.
LOCATIE_VELDEN = ("locatie_land", "locatie_plaats", "locatie_postcode")

# Hoe deze verkoper levert. Stond alleen in de extensie-instellingen, waar
# vrijwel niemand komt: Jaap verzendt uitsluitend, en kreeg bij elke advertentie
# "Ophalen of Verzenden" — een belofte die hij niet kan waarmaken. Hoort bij het
# account, dus hier, en gaat mee in elke opdracht.
LEVERING_GELDIG = ("beide", "verzenden", "ophalen")

# Pakketgrootte op prijs. Marktplaats kent XS (brievenbuspakje), S, M en L
# (groot pakket). Onder de grens het kleine, daarboven het grote; 0 = laat
# Marktplaats het zelf bepalen. Bewust een grens in euro's en geen slimmigheid
# met afmetingen: de verkoper weet zelf welke waarde hij niet in een
# brievenbuspakje wil hebben, wij kunnen dat niet zien aan een foto.
PAKKET_GRENS_MAX = 5000

# VASTE TEKST ONDER ELKE ADVERTENTIE.
#
# WAAROM (29-08-2026, Jaap van zilverwebsite.nl). Hij meldde dat er onderaan
# elke advertentie "een hele lap tekst" ontbrak: zijn artikelnummer, de uitleg
# over de winkel, de verzendkosten en zijn zoekwoorden. En hij zag scherp dat
# het altijd op DEZELFDE plek stopte — vlak onder gewicht en afmetingen,
# ongeacht hoeveel tekst eraan voorafging.
#
# Nagemeten: de omschrijving in onze database is teken voor teken gelijk aan de
# omschrijving van hetzelfde product in zijn eigen webshop, en die eindigt daar
# ook. Dat blok stond dus nooit in de producttekst; hij tikte het per advertentie
# op Marktplaats zelf erbij. Er viel hier niets af te knippen en niets terug te
# halen — het moest gemaakt worden.
#
# 4.000 tekens is ruim: het langste blok dat we bij hem zagen is er nog geen 800.
SLOTTEKST_MAX = 4000

# VRAGEN OF IETS VERKOCHT IS, OF NIET (19-09-2026, Egbert van papas-plectrums.nl).
#
# Verdwijnt een advertentie van een kanaal, dan vragen we de verkoper of het
# artikel verkocht is. Dat moet, want afmelden bij de andere kanalen is
# onherstelbaar. Maar het slaat nergens op bij wie NIEUWE voorraad verkoopt:
# daar staan tien dezelfde plectrums op de plank en haalt de verkoper zijn
# advertentie zelf weg zodra de voorraad op is. Egbert: "Voor mij is dit totaal
# niet van toepassing omdat ik altijd nieuwe voorraad koop, zodra dit niet meer
# het geval is verwijder ik het product van de platformen." Hij kreeg de vraag
# en daarna een herinneringsmail over een advertentie die hij zelf had
# weggehaald.
#
# Staat dit uit, dan gaat een verdwenen advertentie meteen naar het archief:
# precies wat er gebeurt als de verkoper zelf "nee" antwoordt. Er gaat niets van
# een ander kanaal af, er komt geen vraag op het dashboard en geen mail.
VERKOOPVRAAG = "verkoopvraag"

# WELKE ARTIKELEN OP 2DEHANDS ZIJN EIGEN MARKTPLAATS-VERZENDBEDRAG KRIJGEN
# (26-09-2026, Egbert van papas-plectrums.nl).
#
# Standaard krijgt een zoekertje op 2dehands Bpost 0-2 kg (EUR 7,10). Het bedrag
# dat de verkoper op Marktplaats bij "Zelf verzenden" zet is een NEDERLANDSE
# prijs, en een koper op 2dehands woont meestal in België. Voor een brief scheelt
# dat een euro; voor een pakje is het verschil groot. Egbert: "4,95 voor een
# pakket naar Belgie is te weinig, de daadwerkelijke kosten zijn €9.50. Met €7.10
# kom ik nog wel weg. Met patches is het verschil tussen NL en BE maar €1,00."
# Aan het bedrag zelf is dat niet te zien: bij hem kosten een rugpatch (brief) en
# een miniatuur (pakje) op Marktplaats allebei EUR 4,95.
#
# Daarom alleen voor artikelen waarvan de titel een van deze woorden bevat. Leeg
# (de standaard) = overal Bpost, zoals het altijd was.
VERZENDING_2DH_WOORDEN = "verzending_2dh_woorden"
VERZENDING_2DH_WOORDEN_MAX = 20
# En voor elk artikel waarvan het Marktplaats-bedrag ONDER dit bedrag (centen)
# ligt, welke titel het ook heeft. 0 (de standaard) = uit.
#
# WAAROM (27-09-2026, Egbert): hij zette magneten, plectrums en sleutelhangers op
# 2dehands; op Marktplaats verstuurt hij die zelf voor EUR 2,25 of 2,95, op
# 2dehands kregen ze Bpost EUR 7,10. "Ik ging er vanuit dat er vanaf nu gekeken
# zou worden naar de verzendkosten zoals ze staan op Marktplaats." Onder de 4,95
# is het bij hem altijd een brief (gemeten: magneet 2,25, plectrum en sleutelhanger
# 2,95, textielposter 3,95); vanaf 4,95 kan het een pakje zijn (miniatuur 4,95,
# slipmat 6,95, mok 6,95), en daar is zijn eigen bedrag te laag voor België.
VERZENDING_2DH_BRIEF_ONDER = "verzending_2dh_brief_onder"
VERZENDING_2DH_BRIEF_ONDER_MAX = 710   # nooit boven Bpost 0-2 kg zelf
# Welke van de drie keuzes de verkoper maakte (27-09-2026, Daniel: "zodat ik niet
# constant iedereen individueel zit te berichten"):
#   "standaard"  altijd Bpost EUR 7,10
#   "regel"      het Marktplaats-bedrag voor brieven: onder de briefgrens en/of
#                titels met een woord (de twee velden hierboven, Egbert: 495 en
#                "patch")
#   "alles"      het Marktplaats-bedrag voor elk artikel, ook boven EUR 7,10.
#                Voor wie vanuit België verstuurt of alleen brieven heeft; de
#                briefgrens kon dat niet, die stopt bij Bpost zelf.
# Ontbreekt de sleutel (iedereen van vóór 27-09), dan volgt hij uit de velden: wie
# een grens of woord had, had "regel". Zo verandert er voor Egbert niets.
VERZENDING_2DH_MODUS = "verzending_2dh_modus"
VERZENDING_2DH_MODI = ("standaard", "regel", "alles")

# NIEUWE SHOPIFY-PRODUCTEN VANZELF IMPORTEREN (08-10-2026, Janneke).
# None = niet zelf gekozen: dan aan zodra de verkoper ooit zelf uit Shopify
# importeerde (zie services/shopify_auto_import.py). De stand schrijft alleen de
# server; het scherm leest er wanneer er gekeken is en wat erbij kwam.
SHOPIFY_AUTO_IMPORT = "shopify_auto_import"
SHOPIFY_AUTO_IMPORT_STAND = "shopify_auto_import_stand"
# Hetzelfde voor WooCommerce (09-10-2026, services/woocommerce_auto_import.py).
WOO_AUTO_IMPORT = "woocommerce_auto_import"
WOO_AUTO_IMPORT_STAND = "woocommerce_auto_import_stand"
_STAND_VELDEN = ("gecontroleerd", "fout", "laatst_nieuw", "te_controleren",
                 "laatst_toegevoegd_om", "totaal_toegevoegd", "achterstand_om")

STANDAARD = {"relist_dagen": RELIST_DAGEN_STANDAARD, "vinted_groepen": [],
             "auto_relist": True, "vinted_herplaatsen": False, VERKOOPVRAAG: True, VERZENDING_2DH_WOORDEN: [],
             VERZENDING_2DH_BRIEF_ONDER: 0, VERZENDING_2DH_MODUS: "standaard",
             "fabrikant_naam": "", "fabrikant_adres": "", "fabrikant_email": "",
             FABRIKANT_MEESTUREN: True,
             "locatie_land": "", "locatie_plaats": "", "locatie_postcode": "",
             "levering": "beide", "pakket_grens": 0, "slottekst": "",
             SHOPIFY_AUTO_IMPORT: None, SHOPIFY_AUTO_IMPORT_STAND: {}, "vinted_taal": "zelf",
             WOO_AUTO_IMPORT: None, WOO_AUTO_IMPORT_STAND: {}}


def _schoon(rauw: dict | None) -> dict:
    uit = dict(STANDAARD)
    if not isinstance(rauw, dict):
        return uit
    try:
        dagen = int(rauw.get("relist_dagen", RELIST_DAGEN_STANDAARD))
    except (TypeError, ValueError):
        dagen = RELIST_DAGEN_STANDAARD
    uit["relist_dagen"] = max(RELIST_DAGEN_MIN, min(dagen, RELIST_DAGEN_MAX))
    # Alleen groepen die echt bestaan. Een typefout of een verzonnen naam zou
    # anders stilzwijgend álles blokkeren — de instelling zou dan precies het
    # tegenovergestelde doen van wat er staat.
    # Automatisch herplaatsen kan uit. Niet iedereen wil dat zijn advertenties
    # buiten hem om verdwijnen en terugkomen: "hij begint ineens random dingen te
    # listen op marktplaats" is een terechte klacht als je die knop niet hebt.
    if "auto_relist" in rauw:
        uit["auto_relist"] = bool(rauw.get("auto_relist"))
    # Vinted verbiedt sinds 05-10-2026 (voorwaarden par. 6) externe software en
    # het herhaaldelijk verwijderen en opnieuw plaatsen van hetzelfde artikel.
    # Daarom staat herplaatsen op Vinted standaard UIT en kost het een bewuste klik.
    if "vinted_herplaatsen" in rauw:
        uit["vinted_herplaatsen"] = bool(rauw.get("vinted_herplaatsen"))
    # Vinted: standaard exact de tekst van de verkoper ("zelf"). Alleen wie zelf
    # kiest voor "en" krijgt een vertaling naar het Engels (Daniel, 09-10-2026).
    if str(rauw.get("vinted_taal") or "").strip().lower() == "en":
        uit["vinted_taal"] = "en"
    if VERKOOPVRAAG in rauw:
        uit[VERKOOPVRAAG] = bool(rauw.get(VERKOOPVRAAG))
    if SHOPIFY_AUTO_IMPORT in rauw:
        keuze = rauw.get(SHOPIFY_AUTO_IMPORT)
        uit[SHOPIFY_AUTO_IMPORT] = None if keuze is None else bool(keuze)
    stand = rauw.get(SHOPIFY_AUTO_IMPORT_STAND)
    if isinstance(stand, dict):
        uit[SHOPIFY_AUTO_IMPORT_STAND] = {k: stand[k] for k in _STAND_VELDEN if k in stand}
    if WOO_AUTO_IMPORT in rauw:
        keuze = rauw.get(WOO_AUTO_IMPORT)
        uit[WOO_AUTO_IMPORT] = None if keuze is None else bool(keuze)
    stand = rauw.get(WOO_AUTO_IMPORT_STAND)
    if isinstance(stand, dict):
        uit[WOO_AUTO_IMPORT_STAND] = {k: stand[k] for k in _STAND_VELDEN if k in stand}
    # Marktplaats kapt deze velden zelf af op 255 tekens; langer opslaan zou
    # betekenen dat het scherm iets anders toont dan wat er geplaatst wordt.
    for veld in FABRIKANT_VELDEN:
        if veld in rauw:
            uit[veld] = str(rauw.get(veld) or "").strip()[:255]
    if FABRIKANT_MEESTUREN in rauw:
        uit[FABRIKANT_MEESTUREN] = bool(rauw.get(FABRIKANT_MEESTUREN))
    # Land, woonplaats en postcode: korte velden, en wat erin staat moet één op
    # één op het formulier passen. Het land wordt op de site op naam gezocht
    # ("Nederland"), dus spaties eraf en verder niets veranderen — een
    # hoofdletterkuur zou "Verenigd Koninkrijk" onvindbaar maken.
    for veld in LOCATIE_VELDEN:
        if veld in rauw:
            uit[veld] = str(rauw.get(veld) or "").strip()[:100]
    if "slottekst" in rauw:
        uit["slottekst"] = str(rauw.get("slottekst") or "").strip()[:SLOTTEKST_MAX]
    lev = str(rauw.get("levering") or "").strip().lower()
    if lev in LEVERING_GELDIG:
        uit["levering"] = lev
    if "pakket_grens" in rauw:
        try:
            uit["pakket_grens"] = max(0, min(int(float(rauw.get("pakket_grens") or 0)),
                                             PAKKET_GRENS_MAX))
        except (TypeError, ValueError):
            uit["pakket_grens"] = 0
    woorden = rauw.get(VERZENDING_2DH_WOORDEN)
    if isinstance(woorden, list):
        # Kortere woorden dan drie letters zouden in bijna elke titel staan.
        uit[VERZENDING_2DH_WOORDEN] = [w for w in dict.fromkeys(
            str(x).strip().lower() for x in woorden) if 3 <= len(w) <= 40
        ][:VERZENDING_2DH_WOORDEN_MAX]
    if VERZENDING_2DH_BRIEF_ONDER in rauw:
        try:
            uit[VERZENDING_2DH_BRIEF_ONDER] = max(0, min(int(rauw.get(VERZENDING_2DH_BRIEF_ONDER) or 0),
                                                         VERZENDING_2DH_BRIEF_ONDER_MAX))
        except (TypeError, ValueError):
            uit[VERZENDING_2DH_BRIEF_ONDER] = 0
    modus = str(rauw.get(VERZENDING_2DH_MODUS) or "").strip().lower()
    uit[VERZENDING_2DH_MODUS] = (modus if modus in VERZENDING_2DH_MODI
                                 else afgeleide_modus(uit))
    groepen = rauw.get("vinted_groepen")
    if isinstance(groepen, list):
        uit["vinted_groepen"] = [g for g in
                                 dict.fromkeys(str(x).strip().lower() for x in groepen)
                                 if g in VINTED_GROEPEN_GELDIG]
    return uit


def lees(user_id: str) -> dict:
    """De instellingen van één verkoper, altijd compleet en altijd binnen bereik."""
    try:
        rij = (get_db().table("platform_credentials").select("extra_data")
               .eq("user_id", user_id).eq("platform", RIJ).limit(1).execute().data or [])
    except Exception as e:  # noqa: BLE001 — een instelling mag nooit een pagina slopen
        logger.warning("instellingen niet gelezen voor %s: %s", user_id, e)
        return dict(STANDAARD)
    return _schoon(rij[0].get("extra_data") if rij else None)


def schrijf(user_id: str, wijziging: dict) -> dict:
    """Instellingen bijwerken. Geeft terug wat er daadwerkelijk is opgeslagen,
    zodat het scherm de begrensde waarde toont en niet wat er is ingetikt."""
    nieuw = _schoon({**lees(user_id), **(wijziging or {})})
    db = get_db()
    db.table("platform_credentials").upsert(
        {"user_id": user_id, "platform": RIJ, "extra_data": nieuw},
        on_conflict="user_id,platform",
    ).execute()
    return nieuw


VINTED_HERPLAATSEN_UIT = (
    "Refreshing and relisting on Vinted is switched off. Vinted's terms (since "
    "5 October 2026) forbid external tools and deleting and re-adding the same "
    "item, and breaking them can get your account blocked. You can switch it on "
    "in Preferences, at your own risk.")


def vinted_herplaatsen_toegestaan(user_id: str) -> bool:
    """Heeft deze verkoper verversen en herplaatsen op Vinted bewust aangezet?

    Bij twijfel NEE: lukt het lezen van de instelling niet, dan blijft het uit.
    Dit is het enige antwoord waar elk herplaatspad op Vinted langs moet."""
    try:
        return lees(user_id).get("vinted_herplaatsen", False) is True
    except Exception as e:  # noqa: BLE001
        logger.warning("vinted_herplaatsen niet gelezen voor %s: %s", user_id, e)
        return False


def verkoopvraag_aan(user_id: str) -> bool:
    """Wil deze verkoper de vraag "is dit verkocht?" krijgen?

    Bij twijfel ja. Een hik in de instellingen mag nooit stilzwijgend een
    verkoopsignaal weggooien: dan verdwijnt een echte verkoop uit de omzet en
    blijft het artikel op de andere kanalen staan. Zie VERKOOPVRAAG."""
    try:
        return bool(lees(user_id).get(VERKOOPVRAAG, True))
    except Exception as e:  # noqa: BLE001
        logger.warning("verkoopvraag-instelling niet gelezen voor %s: %s", user_id, e)
        return True

def verzending_2dh_regel(user_id: str, db=None) -> dict | None:
    """Wanneer 2dehands het Marktplaats-bedrag van deze verkoper overneemt:
    {"woorden": [...], "brief_onder": centen}. Zie VERZENDING_2DH_WOORDEN en
    VERZENDING_2DH_BRIEF_ONDER. None = niet te lezen: een storing is geen
    antwoord, dus dan legt de aanroeper niets vast."""
    try:
        rij = ((db or get_db()).table("platform_credentials").select("extra_data")
               .eq("user_id", user_id).eq("platform", RIJ).limit(1).execute().data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("verzendregel niet gelezen voor %s: %s", user_id, e)
        return None
    schoon = _schoon(rij[0].get("extra_data") if rij else None)
    return {"modus": schoon[VERZENDING_2DH_MODUS],
            "woorden": schoon[VERZENDING_2DH_WOORDEN],
            "brief_onder": schoon[VERZENDING_2DH_BRIEF_ONDER]}


def afgeleide_modus(regel: dict) -> str:
    """De keuze bij wie er nog geen maakte: "regel" als er een grens of woord
    staat, anders "standaard". Werkt op de instellingen én op een regel."""
    woorden = regel.get(VERZENDING_2DH_WOORDEN, regel.get("woorden"))
    grens = regel.get(VERZENDING_2DH_BRIEF_ONDER, regel.get("brief_onder"))
    return "regel" if (woorden or grens) else "standaard"


def modus_van(regel: dict) -> str:
    modus = regel.get("modus")
    return modus if modus in VERZENDING_2DH_MODI else afgeleide_modus(regel)


def titel_neemt_over(regel: dict, titel: str) -> bool:
    """Staat er een woord uit de regel in de titel? Dan geldt het eigen bedrag,
    wat het ook is (bij Egbert: een rugpatch van EUR 4,95 is een brief)."""
    if modus_van(regel) != "regel":
        return False
    t = str(titel or "").lower()
    return any(w in t for w in regel.get("woorden") or [])


def heeft_marktplaats_nodig(regel: dict, titel: str) -> bool:
    """Doet het Marktplaats-bedrag voor dit artikel ertoe? Zo niet, dan hoeft
    Marktplaats niet eens gevraagd: het wordt Bpost."""
    modus = modus_van(regel)
    if modus == "alles":
        return True
    return modus == "regel" and (bool(regel.get("brief_onder")) or titel_neemt_over(regel, titel))


def neemt_bedrag_over(regel: dict, titel: str, cents) -> bool:
    """Krijgt dit artikel op 2dehands het eigen Marktplaats-bedrag `cents`?"""
    modus = modus_van(regel)
    if modus == "alles":
        return isinstance(cents, int) and cents > 0
    if modus != "regel":
        return False
    if titel_neemt_over(regel, titel):
        return True
    return isinstance(cents, int) and 0 < cents < int(regel.get("brief_onder") or 0)

def alle_relist_dagen() -> dict[str, int]:
    """Per verkoper het ingestelde aantal dagen, voor de dagelijkse ronde.

    Eén aanroep in plaats van een aanroep per advertentie: die ronde loopt over
    duizenden regels en mag de database niet duizend keer bevragen.
    """
    uit: dict[str, int] = {}
    try:
        # fetch_all: een gewone select stopt stilzwijgend bij 1.000 rijen, en dan
        # draaien de verkopers daarboven op de standaardinstelling in plaats van
        # de hunne.
        for rij in fetch_all(lambda: get_db().table("platform_credentials")
                             .select("user_id,extra_data").eq("platform", RIJ)):
            uit[rij["user_id"]] = _schoon(rij.get("extra_data"))["relist_dagen"]
    except Exception as e:  # noqa: BLE001
        logger.warning("instellingen niet gelezen: %s", e)
    return uit


def fabrikant(user_id: str) -> dict:
    """De verantwoordelijke partij van deze verkoper, of een leeg blok.

    Apart van `lees` omdat de publicatiekant hier maar drie velden van nodig
    heeft en die één op één de namen van het Marktplaats-formulier volgen.

    Staat de schakelaar uit, dan geeft dit een LEEG blok terug — dan wordt er
    niets ingevuld op het formulier en wordt er ook niets geëist voor het
    publiceren. Zie FABRIKANT_MEESTUREN."""
    s = lees(user_id)
    if not s.get(FABRIKANT_MEESTUREN, True):
        return {"manufacturer_name": "", "manufacturer_address": "",
                "manufacturer_email": ""}
    return {
        "manufacturer_name": s.get("fabrikant_naam") or "",
        "manufacturer_address": s.get("fabrikant_adres") or "",
        "manufacturer_email": s.get("fabrikant_email") or "",
    }


def locatie(user_id: str) -> dict:
    """Waar deze verkoper staat, in de namen die de extensie op het formulier zet.

    Leeg blok = niets doen. Dat is bewust: wie hier niets invult houdt precies
    het gedrag dat hij altijd had, namelijk het contactblok zoals het uit zijn
    account komt. Zie LOCATIE_VELDEN."""
    s = lees(user_id)
    return {
        "location_country": s.get("locatie_land") or "",
        "location_city": s.get("locatie_plaats") or "",
        "location_postcode": s.get("locatie_postcode") or "",
    }


def fabrikant_compleet(user_id: str) -> bool:
    return all(fabrikant(user_id).values())


def fabrikant_verplicht(user_id: str) -> bool:
    """Moeten we het publiceren tegenhouden als het blok niet compleet is?

    Alleen als de verkoper het wíl meesturen. Staat de schakelaar uit, dan is
    een leeg blok zijn eigen keuze en geen ontbrekend gegeven."""
    return bool(lees(user_id).get(FABRIKANT_MEESTUREN, True))


# De radiowaarden zoals Marktplaats ze zelf op het formulier zet, live afgelezen
# op 21-08-2026: XS = Brievenbuspakje (0-2kg), S = Klein (0-3kg),
# M = Gemiddeld (0-10kg), L = Groot pakket (10-23kg).
PAKKET_KLEIN = "XS"
PAKKET_GROOT = "L"


def verzendkeuzes(user_id: str, prijs) -> dict:
    """Levering en pakketgrootte voor één advertentie.

    De pakketgrootte hangt van de prijs af: onder de door de verkoper ingestelde
    grens past het in een brievenbuspakje, daarboven wil hij het als groot pakket
    verzekerd versturen. Staat de grens op 0, dan bemoeien we ons er niet mee."""
    s = lees(user_id)
    uit = {"levering": s.get("levering") or "beide"}
    grens = int(s.get("pakket_grens") or 0)
    if grens:
        try:
            uit["pakket"] = PAKKET_KLEIN if float(prijs or 0) < grens else PAKKET_GROOT
        except (TypeError, ValueError):
            pass
    return uit
