"""Een antwoord van een ander adres telt via de draad, niet via het adres.

AANLEIDING, 06-10-2026. Antiek de Evenaar kreeg mail 1 op info@antiekdeevenaar.nl
en antwoordde op 29-09 "geen interesse" vanaf ed.adema@planet.nl (iPhone, citaat
zonder ontvanger). Domein en citaat vonden niets, dus het antwoord werd niet
gezien en op 06-10 ging mail 2 toch uit. Zijn reactie: dat is volstrekt overbodig.
De headers van dat antwoord wezen wél naar onze mail; daar zoeken we nu op.
"""
import email
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import leadgen_mail as L  # noqa: E402

MID = "<1a0eccde869.73c36e0e-728297332.-7880685764527329929@zoho.eu>"
ANTWOORD = (
    "From: Eddie <ed.adema@planet.nl>\r\nTo: Daniel de Koning <daniel@omnivaleur.nl>\r\n"
    "Subject: Re: Vraagje over jullie winkel-aanbod\r\n"
    f"In-Reply-To: {MID}\r\nReferences: {MID}\r\n\r\n"
    "Fijn dat je aan ons denkt maar we hebben voor jouw aanbod geen interesse.\r\n\r\n"
    "> Op 29 sep 2026 om 14:06 heeft Daniel de Koning <daniel@omnivaleur.nl> het volgende geschreven:\r\n"
)
VERZONDEN = [{"mid": MID, "adres": "info@antiekdeevenaar.nl"},
             {"mid": "<anders@zoho.eu>", "adres": "iemand@anders.nl"}]
STATE = {"info@antiekdeevenaar.nl": {}, "iemand@anders.nl": {}}


def test_oude_wegen_missen_dit_antwoord():
    """Voor-proef: precies de wegen die er vóór de draad waren, falen hier."""
    msg = email.message_from_string(ANTWOORD)
    van = "ed.adema@planet.nl"
    assert L._zelfde_bedrijf(van, STATE) is None
    assert L._adres_uit_citaat(L._platte_tekst(msg), STATE) is None


def test_draad_vindt_het_adres_waar_wij_naartoe_schreven():
    msg = email.message_from_string(ANTWOORD)
    assert L._adres_uit_draad(msg, STATE, VERZONDEN) == "info@antiekdeevenaar.nl"


def test_draad_gokt_niet_zonder_bewijs():
    losse = email.message_from_string(ANTWOORD.replace(MID, "<onbekend@x>"))
    assert L._adres_uit_draad(losse, STATE, VERZONDEN) is None
    assert L._adres_uit_draad(email.message_from_string(ANTWOORD), {}, VERZONDEN) is None
