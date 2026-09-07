"""Een leeg adresveld op 2dehands krijgt een melding waar de verkoper iets mee kan.

AANLEIDING (07-09-2026, De Juiste Toon): "Ook tweedehands be lukt niet moet ook
ingesteld worden adres niet in Essen maar in Nederland."

Gemeten: 2dehands.be vraagt een Belgische postcode van vier cijfers en biedt
daarnaast "Buitenland" met land plus woonplaats. Die waarden komen uit zijn
account op die site, niet uit Omnivaleur; wij vullen er bewust niets in, want een
verzonnen postcode zet de advertentie in een willekeurige Belgische gemeente. Zijn
2dehands-advertenties die het wél haalden staan gemeten op "Etten-Leur, Nederland"
met abroad=true, dus de instelling kán goed staan.

Wat er misging is niet het weigeren maar de tekst: "open your account settings on
this marketplace" zegt een Nederlandse verkoper niet dat hij "Buitenland" moet
kiezen. Dat is de enige plek waar het misgaat, en dat is precies wat hij twee keer
heeft gevraagd.
"""
from backend.api.jobs import _rechtgezette_foutmelding

LEEG_NL = ("Your postcode is still empty on the listing form, so nothing was "
           "published. Open your account settings on this marketplace...")
LEEG_FORMULIER = ('Error: Not published — complete the fields marked in red and click '
                  'publish yourself. Geen postcode ingevuld. | Fields marked invalid: '
                  'contactInformation.postCode=LEEG')


def _zeg(fout, platform="2dehands"):
    job = {"platform": platform, "action": "create"}
    return _rechtgezette_foutmelding(job, {"error": fout}, versie=None)["error"]


def test_hij_leest_wat_hij_zelf_moet_doen_en_waar():
    for fout in (LEEG_NL, LEEG_FORMULIER):
        uit = _zeg(fout)
        assert "Buitenland" in uit
        assert "account" in uit
        # En niet de suggestie dat wij het wel even invullen.
        assert "verzonnen postcode" in uit


def test_de_oorspronkelijke_melding_blijft_bewaard():
    uit = _rechtgezette_foutmelding({"platform": "2dehands", "action": "create"},
                                    {"error": LEEG_FORMULIER}, versie=None)
    assert uit["error_oorspronkelijk"] == LEEG_FORMULIER


def test_marktplaats_krijgt_hem_ook():
    assert "Buitenland" in _zeg(LEEG_NL, platform="marktplaats")


def test_een_andere_fout_wordt_niet_aangeraakt():
    fout = "Error: These fields were left empty on the form: size."
    assert _zeg(fout) == fout


def test_vinted_valt_hier_niet_onder():
    # Vinted heeft dit veld niet; een toevallige "postcode" in een Vinted-fout
    # mag geen 2dehands-uitleg opleveren.
    assert _zeg("iets met postcode erin", platform="vinted") == "iets met postcode erin"
