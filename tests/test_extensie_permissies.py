"""Bewaakt dat een extensie-update de extensie niet stilzwijgend uitschakelt.

AANLEIDING, 30-08-2026 (Egbert Brouwer, Papa's Plectrums). Zijn extensie had
zich twee dagen niet meer gemeld: geen scan, geen publicatie, geen
verkoopcontrole. Hij was nergens uitgelogd en had niets aangeraakt.

Wat er gebeurd was: versie 1.0.256 zette vier nieuwe VASTE host-toestemmingen in
het manifest, waaronder de brede `https://*.marktplaats.nl/*` naast de al
verleende `https://www.marktplaats.nl/*`. Chrome behandelt zo'n uitbreiding als
"de extensie wil meer dan waar je ja op zei" en zet haar bij ELKE bestaande
gebruiker uit tot hij de nieuwe toestemming goedkeurt. Dat gebeurt zonder
foutmelding en zonder mail — de extensie is er nog, ze staat alleen uit. In het
dashboard is dat niet te zien behalve als "er gebeurt niets".

De ironie: het manifest waarschuwde zelf al voor deze valkuil, in het commentaar
bij `optional_host_permissions` in background.js ("Een update die een nieuwe
VASTE host-toestemming toevoegt, zet Chrome bij iedere bestaande gebruiker de
extensie stil tot hij hem accepteert"). Een commentaar in een ander bestand houdt
niemand tegen. Deze test wel.

DE REGEL. `host_permissions` mag krimpen, nooit groeien. Een nieuw domein hoort
in `optional_host_permissions`: dat vraagt de extensie zelf op het moment dat ze
het nodig heeft, en een gebruiker die nee zegt houdt een werkende extensie.

Moet er tóch een vaste toestemming bij, dan is dat een bewuste keuze met
gevolgen: iedereen ligt stil tot hij klikt. Zet hem er dan hieronder bij ÉN
waarschuw de bestaande klanten voordat de versie naar de Web Store gaat.
"""
import json
from pathlib import Path

REPO = Path(__file__).parent.parent
MANIFEST = json.loads((REPO / "extension" / "manifest.json").read_text(encoding="utf-8"))

# De toestemmingen die klanten al hebben goedgekeurd (stand 1.0.262, de versie
# die op 30-08-2026 in de Chrome Web Store stond). Alles wat hier niet in staat
# is nieuw, en dus een stille uitschakeling voor iedereen die al klant is.
GOEDGEKEURDE_HOSTS = {
    "https://www.marktplaats.nl/*",
    "https://www.2dehands.be/*",
    "https://link.marktplaats.nl/*",
    "https://www.vinted.com/*",
    "https://www.vinted.nl/*",
    "https://www.vinted.be/*",
    "https://www.vinted.de/*",
    "https://www.vinted.fr/*",
    "https://www.facebook.com/*",
    "https://*.vinted.net/*",
    "https://*.supabase.co/*",
    "https://omnivaleur.com/*",
    "https://www.google-analytics.com/*",
    "https://images.marktplaats.com/*",
    "https://images.2dehands.com/*",
    "https://*.marktplaats.nl/*",
    "https://*.2dehands.be/*",
}

# Dezelfde redenering geldt voor de gewone permissies: "downloads", "cookies" of
# "webRequest" erbij zetten levert precies dezelfde stille uitschakeling op.
GOEDGEKEURDE_PERMISSIES = {
    "storage", "tabs", "alarms", "clipboardWrite", "clipboardRead",
    "scripting", "idle", "debugger",
    # "background" is er op 03-09-2026 bij gekomen (1.0.288) en is de enige
    # uitzondering die niet op goed vertrouwen is toegevoegd. Chrome zelf is
    # ernaar gevraagd via chrome.management.getPermissionWarningsByManifest: het
    # huidige manifest en het manifest mét "background" leveren exact dezelfde
    # waarschuwingenlijst op. Geen nieuwe waarschuwing betekent geen nieuwe
    # goedkeuringsvraag, en dus geen stille uitschakeling.
    #
    # Waarom hij erin moet: zonder deze permissie ruimt Chrome het hele profiel
    # op zodra het laatste venster dicht gaat, en dan stopt de extensie meteen.
    # Gemeten met twee identieke testextensies naast elkaar: alle vensters dicht,
    # 155 seconden, zonder de permissie 0 tikken en met de permissie 5. Zie
    # docs/team-notes.md, 03-09-2026.
    "background",
}

HULP = (
    "\n\nEen NIEUWE vaste toestemming zet Chrome de extensie bij ELKE bestaande "
    "klant uit tot hij hem goedkeurt — stil, zonder foutmelding. Zet het domein "
    "in 'optional_host_permissions' en vraag het op het moment dat je het nodig "
    "hebt. Moet het echt vast, breid dan de lijst in deze test uit én waarschuw "
    "de klanten vóór de versie naar de Web Store gaat."
)


def test_geen_nieuwe_vaste_host_toestemming():
    nieuw = set(MANIFEST.get("host_permissions", [])) - GOEDGEKEURDE_HOSTS
    assert not nieuw, f"nieuwe vaste host-toestemming(en): {sorted(nieuw)}{HULP}"


def test_geen_nieuwe_permissie():
    nieuw = set(MANIFEST.get("permissions", [])) - GOEDGEKEURDE_PERMISSIES
    assert not nieuw, f"nieuwe permissie(s): {sorted(nieuw)}{HULP}"


def test_admarkt_blijft_optioneel():
    """Admarkt is de enige optionele, en dat hoort zo te blijven.

    Alleen zakelijke verkopers hebben hem nodig; hem vast maken zou iedereen
    laten klikken voor iets wat de meesten nooit gebruiken.
    """
    assert "https://admarkt.marktplaats.nl/*" in MANIFEST.get("optional_host_permissions", [])
