"""Eén concept per persoon, en altijd op het laatste bericht.

AANLEIDING, 29-08-2026. In de conceptenmap lagen drie voorstellen naast elkaar
voor frenky@autodokumentatie.nl — 08:49, 09:09 en 09:28, alle drie een antwoord
op hetzelfde bericht, alle drie met een andere tekst. Daarnaast bleven er
concepten liggen voor mensen die Daniel zelf al had beantwoord.

De oorzaak zat niet in één van de vier wegen naar een concept, maar in waar de
vraag "mag dit nog?" werd gesteld: in de administratie. Die wordt pas aan het
eind van een stap weggeschreven, en de ronde wordt op de server afgekapt als hij
te lang duurt. Het concept lag er dan al, de administratie wist het niet, en de
volgende ronde deed het nog eens.

Het slot staat daarom nu vlak vóór het neerleggen en vraagt het aan de postbus.
Dit bestand legt vast dat het daar blijft staan.
"""
import email
import sys
import time
from email.utils import formatdate
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import leadgen_mail as L  # noqa: E402


# --------------------------------------------------------------- nep-postbus
def _kop(**velden) -> bytes:
    m = email.message.EmailMessage()
    for k, v in velden.items():
        m[k.replace("_", "-")] = v
    return m.as_bytes()


class NepImap:
    """Zo weinig IMAP als nodig is om het slot te laten draaien."""

    def __init__(self, mappen: dict[str, list[bytes]]):
        self.mappen = mappen
        self.huidig = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, *a):
        return ("OK", [])

    def list(self):
        return ("OK", [f'(\\HasNoChildren) "/" "{m}"'.encode() for m in self.mappen])

    def select(self, naam, readonly=False):
        naam = naam.strip('"')
        self.huidig = naam if naam in self.mappen else None
        return ("OK" if self.huidig else "NO", [b"1"])

    def search(self, _charset, _criteria):
        n = len(self.mappen.get(self.huidig, []))
        return ("OK", [b" ".join(str(i + 1).encode() for i in range(n))])

    def fetch(self, reeks, _wat):
        """Net als imaplib: een reeks nummers in één aanroep, antwoord per
        bericht voorafgegaan door het volgnummer."""
        uit = []
        for deel in str(reeks).replace(" ", "").split(","):
            if not deel.isdigit():
                continue
            i = int(deel)
            berichten = self.mappen.get(self.huidig) or []
            if not 1 <= i <= len(berichten):
                continue
            uit.append((f"{i} (BODY[HEADER] {{0}}".encode(), berichten[i - 1]))
            uit.append(b")")
        return ("OK", uit)


@pytest.fixture
def postbus(monkeypatch):
    monkeypatch.setenv("IMAP_HOST", "imap.test")
    monkeypatch.setenv("MAIL_USER", "daniel@omnivaleur.nl")
    monkeypatch.setenv("MAIL_PASS", "geheim")

    def bouw(**mappen):
        vol = {"INBOX": [], "Beantwoord": [], "Verzonden": [], "Concept": []}
        vol.update(mappen)
        monkeypatch.setattr(L.imaplib, "IMAP4_SSL", lambda *a, **k: NepImap(vol))
        return vol
    return bouw


def _tijd(minuten_geleden: float) -> str:
    return formatdate(time.time() - minuten_geleden * 60, localtime=True)


HUN = {"Message-ID": "<hun-bericht@klant.nl>", "From": "frank@klant.nl",
       "Date": _tijd(120)}


# --------------------------------------------------------------- 1. dubbel
def test_tweede_concept_voor_dezelfde_persoon_wordt_geweigerd(postbus):
    """Precies het geval frenky: er ligt er al een, er komt er geen tweede bij."""
    postbus(Concept=[_kop(To="frank@klant.nl", Subject="Re: vraagje",
                          In_Reply_To="<hun-bericht@klant.nl>", Date=_tijd(30))])
    reden = L._waarom_geen_concept("frank@klant.nl", HUN)
    assert reden and "al een concept" in reden


def test_ander_adres_van_hetzelfde_bedrijf_telt_ook_mee(postbus):
    """Mensen antwoorden vanaf info@bedrijf.nl terwijl wij naar
    info@bedrijf-online.nl schreven. Twee adressen, één gesprek."""
    postbus(Concept=[_kop(To="info@afstandsbediening.nl",
                          In_Reply_To="<een-ander-bericht@klant.nl>", Date=_tijd(30))])
    reden = L._waarom_geen_concept("info@afstandsbediening-online.nl", HUN)
    assert reden and "al een concept" in reden


def test_losse_reparatiemelding_blokkeert_een_echt_antwoord_niet(postbus):
    """Egbert, 30-08-2026. Er lag een concept voor hem, maar dat was de losse
    reparatiemelding over de trage import — geen antwoord op zijn bericht waarin
    hij vroeg of we konden bellen. Het slot keek alleen óf er iets lag, en
    daarmee kon zijn laatste bericht nooit meer een antwoord krijgen.

    Een concept zonder In-Reply-To beantwoordt niemand en mag dus niets
    blokkeren."""
    postbus(Concept=[_kop(To="frank@klant.nl", Subject="Over je melding",
                          Date=_tijd(30))])
    assert L._waarom_geen_concept("frank@klant.nl", HUN) is None


def test_een_concept_voor_iemand_anders_blokkeert_niets(postbus):
    postbus(Concept=[_kop(To="iemand@anders.nl", Date=_tijd(30))])
    assert L._waarom_geen_concept("frank@klant.nl", HUN) is None


# --------------------------------------------------------------- 2. zelfde bericht
def test_geen_tweede_antwoord_op_hetzelfde_bericht(postbus):
    """Ander afzenderadres, maar het antwoord slaat op hetzelfde bericht."""
    postbus(Concept=[_kop(To="frank-prive@elders.nl",
                          In_Reply_To="<hun-bericht@klant.nl>", Date=_tijd(30))])
    reden = L._waarom_geen_concept("frank@klant.nl", HUN)
    assert reden and "dit bericht" in reden


# --------------------------------------------------------------- 3. al beantwoord
def test_niets_meer_als_daniel_zelf_al_geantwoord_heeft(postbus):
    """Hij antwoordt vaak vanaf zijn telefoon, buiten de machine om."""
    postbus(Verzonden=[_kop(To="frank@klant.nl", Date=_tijd(10))])
    reden = L._waarom_geen_concept("frank@klant.nl", HUN)
    assert reden and "zelf al geantwoord" in reden


def test_een_ouder_antwoord_van_daniel_blokkeert_niets(postbus):
    """Ons bericht van vóór het hunne is juist de aanleiding, geen reden om te stoppen."""
    postbus(Verzonden=[_kop(To="frank@klant.nl", Date=_tijd(300))])
    assert L._waarom_geen_concept("frank@klant.nl", HUN) is None


# --------------------------------------------------------------- 4. achterhaald
def test_geen_antwoord_op_een_achterhaald_bericht(postbus):
    """Schreef hij daarna nog iets, dan hoort het antwoord daarop te gaan."""
    postbus(INBOX=[_kop(From="frank@klant.nl", Message_ID="<nieuwer@klant.nl>",
                        Date=_tijd(5))])
    reden = L._waarom_geen_concept("frank@klant.nl", HUN)
    assert reden and "achterhaald" in reden


def test_ook_in_de_map_beantwoord_wordt_gekeken(postbus):
    """De ronde verhuist verwerkte post naar Beantwoord; daar staat het nieuwste
    bericht dus vaak al."""
    postbus(Beantwoord=[_kop(From="frank@klant.nl", Date=_tijd(5))])
    reden = L._waarom_geen_concept("frank@klant.nl", HUN)
    assert reden and "achterhaald" in reden


def test_zijn_eigen_bericht_blokkeert_zichzelf_niet(postbus):
    """Het bericht waarop we antwoorden staat zelf ook in de postbus."""
    postbus(INBOX=[_kop(From="frank@klant.nl", Message_ID="<hun-bericht@klant.nl>",
                        Date=HUN["Date"])])
    assert L._waarom_geen_concept("frank@klant.nl", HUN) is None


# --------------------------------------------------------------- bij twijfel: niet
def test_zonder_mailtoegang_komt_er_geen_concept(monkeypatch):
    """Een gemist concept ziet Daniel; een dubbele mail ziet de klant."""
    monkeypatch.delenv("IMAP_HOST", raising=False)
    monkeypatch.setenv("MAIL_USER", "daniel@omnivaleur.nl")
    monkeypatch.setenv("MAIL_PASS", "geheim")
    assert L._waarom_geen_concept("frank@klant.nl", HUN) is not None


def test_een_kapotte_postbus_levert_geen_concept_op(postbus, monkeypatch):
    postbus()

    class Stuk(NepImap):
        def login(self, *a):
            raise OSError("verbinding weg")
    monkeypatch.setattr(L.imaplib, "IMAP4_SSL", lambda *a, **k: Stuk({}))
    reden = L._waarom_geen_concept("frank@klant.nl", HUN)
    assert reden and "niet te controleren" in reden


def test_schone_postbus_laat_het_concept_gewoon_door(postbus):
    postbus()
    assert L._waarom_geen_concept("frank@klant.nl", HUN) is None


# --------------------------------------------------- het slot zit in de enige doorgang
def test_elke_weg_naar_een_concept_komt_langs_het_slot(monkeypatch, postbus):
    """Niet bij de vier aanroepers, maar in _zet_concept_klaar zelf — anders is
    het vier keer onthouden en dat is precies hoe het misging."""
    postbus(Concept=[_kop(To="frank@klant.nl", Date=_tijd(30))])
    monkeypatch.setattr(L, "_concept_tekst", lambda *a, **k: "Hoi, dit is een "
                        "voldoende lange tekst om als concept te tellen.")
    gelukt = L._zet_concept_klaar({"email": "frank@klant.nl"}, HUN, "hun tekst")
    assert gelukt is False


def test_de_administratie_wordt_meteen_vastgelegd():
    """Niet aan het eind van de ronde: die kan afgekapt worden, en dan ligt het
    concept er wel maar weet de administratie het niet."""
    bron = (Path(__file__).parent.parent / "scripts" / "leadgen_mail.py").read_text()
    blok = bron.split('st["warm_opvolg"] = beurt + 1')[1].split("klaar += 1")[0]
    assert "_save_state(state)" in blok


def test_opruimen_gaat_vooraf_aan_schrijven():
    """Anders houdt een achterhaald concept een nieuw, wél nodig antwoord tegen —
    en wordt het opruimen helemaal niet meer bereikt als de ronde wordt afgekapt."""
    bron = (Path(__file__).parent.parent / "scripts" / "leadgen_mail.py").read_text()
    ronde = bron.split("def tick(args)")[1]
    assert ronde.index("_ruim_concepten_op()") < ronde.index("_check_inbox(")
    assert ronde.index("_ruim_concepten_op()") < ronde.index("_warme_opvolging(")


def test_de_nep_postbus_levert_echt_koppen_op(postbus):
    """Vangnet voor deze tests zelf: leest het slot de postbus niet, dan zou
    alles er 'schoon' uitzien en zouden de tests hierboven niets bewijzen."""
    import imaplib
    postbus(Concept=[_kop(To="frank@klant.nl", Date=_tijd(30)),
                     _kop(To="iemand@anders.nl", Date=_tijd(30))])
    with imaplib.IMAP4_SSL() as imap:
        imap.select('"Concept"', readonly=True)
        _, d = imap.search(None, "ALL")
        koppen = L._koppen_in_bulk(imap, (d[0] or b"").split())
    assert len(koppen) == 2
    assert {k["To"] for k in koppen.values()} == {"frank@klant.nl", "iemand@anders.nl"}


# ------------------------------------- antwoorden op de code, niet op gevoel
def test_technische_vragen_krijgen_de_broncode_als_bewijs():
    """Zonder dit schrijft het model een zelfverzekerde uitleg die nergens op
    steunt — zoals "platgeslagen vanuit Shopify" aan Jaap, die helemaal geen
    Shopify-koppeling heeft."""
    bewijs = L._grondslag("Mijn advertenties op Vinted worden niet geplaatst")
    assert "extension/content/vinted.js" in bewijs


def test_een_gewoon_bericht_sleept_geen_code_mee():
    assert L._grondslag("Hoi Daniel, bedankt voor je bericht!") == ""


def test_het_bewijs_gaat_ook_echt_mee_in_de_opdracht():
    bron = (Path(__file__).parent.parent / "scripts" / "leadgen_mail.py").read_text()
    schrijver = bron.split("def _slim_concept")[1].split("def ")[0]
    assert "_grondslag(" in schrijver
    assert "GRONDSLAG_REGEL" in schrijver


def test_de_losse_support_mailagent_is_weg():
    """Eén klantenservicemedewerker, niet twee. Een tweede script dat nergens
    draait maar er wel uitziet alsof het meedoet, kost alleen maar tijd bij het
    zoeken naar waar iets misging."""
    scripts = Path(__file__).parent.parent / "scripts"
    assert not (scripts / "support_mail_agent.py").exists()
