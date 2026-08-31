"""De mailagent doet zijn eigen werk af, en houdt alleen over wat van Daniel is.

WAAROM DIT ER IS (31-08-2026)
Daniel, met tien concepten in zijn map: "nu staan er veel mails klaar in
concepten die daar niet horen", "nooit meer dubbele mails of dubbele meldingen
dat een concept klaar staat", "automatische follow up automatisch verstuurd
worden".

Van die tien waren er zeven beleefdheidsberichten zonder één belofte — "ik laat
het hierbij", "was het filmpje duidelijk?" — waarvan de oudste twee dagen lag.
De drie die er wél hoorden te liggen hadden alle drie een toezegging die alleen
Daniel kan waarmaken (een belafspraak), of gingen over een storing die nog
openstaat.

Deze proef legt de drie grenzen vast die daaruit volgen. Elke regel die hier
staat is er één die, als hij wegvalt, ofwel een klant een mail bezorgt die
niemand heeft nagekeken, ofwel de map weer laat vollopen.
"""
import importlib.util
import pathlib
import sys
import types

import pytest

WORTEL = pathlib.Path(__file__).resolve().parents[1]


def _laad(naam):
    sys.path.insert(0, str(WORTEL / "scripts"))
    spec = importlib.util.spec_from_file_location(naam, WORTEL / "scripts" / f"{naam}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[naam] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def L(monkeypatch):
    mod = _laad("leadgen_mail")
    monkeypatch.setenv("MAIL_HOST", "smtp.test")
    monkeypatch.setenv("IMAP_HOST", "imap.test")
    monkeypatch.setenv("MAIL_USER", "daniel@omnivaleur.nl")
    monkeypatch.setenv("MAIL_PASS", "geheim")
    return mod


# ── 1. de rem: wat mag vanzelf weg en wat niet ───────────────────────────────

@pytest.mark.parametrize("kern", [
    "Hi Frank,\n\nIk laat het hierbij, ik ga je er niet langer mee lastigvallen.",
    "Hi,\n\nEven een kort berichtje: heb je nog naar de video kunnen kijken?",
    "Hi,\n\nBedankt voor je reactie, dan laat ik het hierbij. Succes!",
])
def test_er_gaat_niets_uit_zichzelf_de_deur_uit(L, kern):
    """DE HOOFDREGEL, en die staat boven alle andere in dit bestand.

    Ik had dit vanochtend aangezet omdat een beleefdheidsmail zonder toezegging
    geen beslissing bevat. Dat was fout. Wat een mail schadelijk maakt zit niet
    alleen in wat hij belooft, maar in of hij nog KLOPT — de aanhef, de naam, of
    het gesprek al gesloten was. Patricia van Boutique MoDo kreeg zo op 31-08
    nog een keer wat Daniel haar op 27-08 zelf al had geschreven.
    """
    assert L.ZELF_VERSTUREN_UIT is True
    assert L._waarom_niet_zelf_versturen(kern, klant=False, bron="klantenservice")


def test_ook_de_terugkoppeling_van_de_developer_gaat_niet_vanzelf(L):
    """Juist deze leek veilig — hij is aan de code getoetst. Maar de mail aan
    Zilverwebsite begon met "Hi Ronald", en die naam bestaat daar niet."""
    kern = "Hi,\n\nJe advertenties komen nu terug in dezelfde categorie."
    assert L._waarom_niet_zelf_versturen(kern, klant=True,
                                         bron="klantenservice + developer")


def test_de_mailflow_staat_stil(L):
    """Op Daniels verzoek van 31-08. `tick` moet stoppen vóór hij iets leest of
    controleert — een pauze die pas werkt als de rest het doet is geen pauze."""
    assert L.MAILFLOW_GEPAUZEERD is True
    bron = (WORTEL / "scripts" / "leadgen_mail.py").read_text(encoding="utf-8")
    body = bron.split("def tick(args) -> None:", 1)[1].split("\ndef ", 1)[0]
    kop = body.split("\n")[:12]
    assert any("MAILFLOW_GEPAUZEERD" in r for r in kop), \
        "de pauze staat niet bovenaan tick"
    # en wel vóór het lezen van de administratie
    assert body.index("MAILFLOW_GEPAUZEERD") < body.index("_state()")


@pytest.mark.parametrize("kern, waarover", [
    ("Ik stuur je zelf een moment met een Meet-link, dan hoef jij alleen te "
     "zeggen of het je uitkomt.", "een belafspraak"),
    ("Bellen doen we, dat lijkt me hier ook het snelste.", "bellen"),
    ("Waarom die lijst bij jou leeg blijft heb ik nog niet scherp. Ik kijk daar "
     "zelf naar en kom er bij je op terug.", "een openstaande toezegging"),
    ("Ik zorg dat je die maand terugbetaald krijgt.", "geld"),
    ("Je krijgt van mij een gratis maand als compensatie.", "geld"),
])
def test_een_toezegging_blijft_altijd_liggen(L, kern, waarover):
    """DE BELANGRIJKSTE REGEL. Alleen Daniel kan een afspraak nakomen of geld
    teruggeven. Gaat zo'n bericht vanzelf de deur uit, dan staat er een belofte
    op zijn naam waar hij niets van weet."""
    reden = L._waarom_niet_zelf_versturen(kern, klant=False, bron="klantenservice")
    assert reden, f"{waarover} werd niet tegengehouden"


def test_een_betalende_klant_krijgt_niets_zonder_developer(L):
    """Bij een klant is een verkeerd woord het duurst. Alleen de terugkoppeling
    van de developer gaat daar vanzelf heen: die is aan de code getoetst voordat
    hij geschreven werd."""
    kern = "Hi, je advertenties komen nu terug in dezelfde categorie.\n\nGroetjes,\nDaniel"
    assert L._waarom_niet_zelf_versturen(kern, klant=True, bron="klantenservice")
    assert L._waarom_niet_zelf_versturen(
        kern, klant=True, bron="klantenservice + developer") == ""


def test_de_rem_kan_alleen_tegenhouden_nooit_doorlaten(L):
    """`zelf_versturen` is een verzoek, geen bevel. Zonder dat verzoek gebeurt
    er niets vanzelf, ook niet bij een volstrekt onschuldige tekst."""
    bron = (WORTEL / "scripts" / "leadgen_mail.py").read_text(encoding="utf-8")
    assert 'rem = _waarom_niet_zelf_versturen(kern, klant, bron) if zelf_versturen else ""' in bron
    assert "if zelf_versturen and not rem:" in bron


# ── 2. wie wat vanzelf mag versturen ─────────────────────────────────────────

def test_de_opvolging_op_stilte_verstuurt_zichzelf(L):
    bron = (WORTEL / "scripts" / "leadgen_mail.py").read_text(encoding="utf-8")
    blok = bron.split("def _warme_opvolging(", 1)[1].split("\ndef ", 1)[0]
    assert "zelf_versturen=True" in blok


def test_een_antwoord_op_nee_gaat_vanzelf_en_op_interesse_niet(L):
    """Een antwoord op "nee bedankt" beslist niets. Een gesprek met iemand die
    misschien klant wordt is van Daniel."""
    bron = (WORTEL / "scripts" / "leadgen_mail.py").read_text(encoding="utf-8")
    assert 'zelf_versturen=soort in ("concurrent", "afwijzing")' in bron


def test_de_terugkoppeling_van_de_developer_gaat_vanzelf(L):
    bron = (WORTEL / "scripts" / "mail_analyse.py").read_text(encoding="utf-8")
    blok = bron.split("def bericht_over_reparaties(", 1)[1].split("\ndef ", 1)[0]
    assert "zelf_versturen=True" in blok


# ── 3. verstuurd betekent: er ligt een spoor in Verzonden ────────────────────

def test_via_resend_komt_er_altijd_een_kopie_in_verzonden(L, monkeypatch):
    """HET SLOT. `_waarom_geen_concept` beantwoordt "hebben wij hierna al iets
    gestuurd?" door in Verzonden te kijken. Op de server loopt alles via Resend,
    en Resend kent Zoho niet — zonder deze kopie ziet de volgende beurt dus geen
    enkel spoor en gaat hetzelfde bericht nog een keer weg."""
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    verstuurd, gearchiveerd = [], []

    class Postbode:
        def __enter__(self):
            return verstuurd.append

        def __exit__(self, *a):
            return False

    class NepImap:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, *a):
            return ("OK", [])

        def append(self, map_, vlaggen, tijd, ruw):
            gearchiveerd.append(map_)
            return ("OK", [])

    monkeypatch.setattr(L, "_postbode", lambda *a, **kw: Postbode())
    monkeypatch.setattr(L.imaplib, "IMAP4_SSL", NepImap)
    monkeypatch.setattr(L, "_onthoud_concept", lambda *a, **kw: None)
    monkeypatch.setattr(L, "_meld_verstuurd", lambda *a, **kw: None)

    from email.message import EmailMessage
    msg = EmailMessage()
    msg["To"] = "info@voorbeeld.nl"
    msg["Subject"] = "Re: vraagje"
    msg.set_content("Hi, ik laat het hierbij.")

    assert L._stuur_zelf({"email": "info@voorbeeld.nl"}, msg, "Hi, ik laat het hierbij.",
                         "klantenservice") is True
    assert len(verstuurd) == 1
    assert '"Verzonden"' in gearchiveerd, \
        "er is verstuurd zonder kopie in Verzonden — het slot tegen dubbele mail is blind"


def test_via_zoho_wordt_er_niet_dubbel_gearchiveerd(L, monkeypatch):
    """Zoho zet post die via zijn eigen SMTP gaat zelf al in Verzonden. Doen wij
    het er nog eens overheen, dan staat alles dubbel — gemeten op 31-08-2026 met
    negen met de hand verstuurde mails. Dat breekt het slot niet, maar het
    vervuilt wél de map waar `_toonprofiel` Daniels toon uit afleidt."""
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    gearchiveerd = []

    class Postbode:
        def __enter__(self):
            return lambda m: None

        def __exit__(self, *a):
            return False

    class NepImap:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, *a):
            return ("OK", [])

        def append(self, map_, *a):
            gearchiveerd.append(map_)
            return ("OK", [])

    monkeypatch.setattr(L, "_postbode", lambda *a, **kw: Postbode())
    monkeypatch.setattr(L.imaplib, "IMAP4_SSL", NepImap)
    monkeypatch.setattr(L, "_onthoud_concept", lambda *a, **kw: None)
    monkeypatch.setattr(L, "_meld_verstuurd", lambda *a, **kw: None)

    from email.message import EmailMessage
    msg = EmailMessage()
    msg["To"] = "info@voorbeeld.nl"
    msg.set_content("Hi.")
    L._stuur_zelf({"email": "info@voorbeeld.nl"}, msg, "Hi.", "klantenservice")

    assert gearchiveerd == [], "Zoho archiveert zelf al; dit levert een dubbele regel op"


def test_een_mislukte_kopie_in_verzonden_slaat_alarm(L, monkeypatch):
    """Stil falen is hier het gevaarlijkst: er is verstuurd, en niemand weet dat
    het slot van de volgende ronde er niets van terugziet."""
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    alarmen = []

    class Postbode:
        def __enter__(self):
            return lambda m: None

        def __exit__(self, *a):
            return False

    class StukkeImap:
        def __init__(self, *a, **kw):
            raise OSError("verbinding geweigerd")

    monkeypatch.setattr(L, "_postbode", lambda *a, **kw: Postbode())
    monkeypatch.setattr(L.imaplib, "IMAP4_SSL", StukkeImap)
    monkeypatch.setattr(L, "_onthoud_concept", lambda *a, **kw: None)
    monkeypatch.setattr(L, "_meld_verstuurd", lambda *a, **kw: None)
    monkeypatch.setattr(L, "_storingsalarm", lambda reden: alarmen.append(reden))

    from email.message import EmailMessage
    msg = EmailMessage()
    msg["To"] = "info@voorbeeld.nl"
    msg.set_content("Hi.")
    L._stuur_zelf({"email": "info@voorbeeld.nl"}, msg, "Hi.", "klantenservice")

    assert alarmen, "een mislukte kopie in Verzonden bleef stil"
    assert "dubbele mail" in alarmen[0]


# ── 4. nooit twee keer hetzelfde seintje ─────────────────────────────────────

def test_een_seintje_dat_al_gestuurd_is_gaat_niet_nog_een_keer(L, monkeypatch):
    post = []

    class Postbode:
        def __enter__(self):
            return post.append

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(L, "_postbode", lambda *a, **kw: Postbode())
    monkeypatch.setattr(L, "_archiveer", lambda msg: None)
    monkeypatch.setattr(L, "_al_gemeld", lambda sleutel: True)

    from email.message import EmailMessage
    msg = EmailMessage()
    msg["To"] = "daniel@omnivaleur.nl"
    msg.set_content("x")
    L._seintje(msg, "abc123", "concept klaar")

    assert post == [], "hetzelfde seintje ging twee keer de deur uit"


def test_elk_seintje_laat_een_kenmerk_achter_om_op_te_zoeken(L, monkeypatch):
    """Zonder kenmerk én kopie werkt de controle hierboven niet en zijn we terug
    bij dubbele meldingen."""
    post, kopieen = [], []

    class Postbode:
        def __enter__(self):
            return post.append

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(L, "_postbode", lambda *a, **kw: Postbode())
    monkeypatch.setattr(L, "_archiveer", lambda msg: kopieen.append(msg))
    monkeypatch.setattr(L, "_al_gemeld", lambda sleutel: False)

    from email.message import EmailMessage
    msg = EmailMessage()
    msg["To"] = "daniel@omnivaleur.nl"
    msg.set_content("x")
    L._seintje(msg, "abc123", "concept klaar")

    assert len(post) == 1
    assert post[0][L.MELDKOP] == "abc123"
    assert kopieen, "het seintje is niet gearchiveerd en dus straks onvindbaar"


def test_hetzelfde_bericht_levert_hetzelfde_kenmerk(L):
    a = L._meldsleutel("concept", "Klant@example.nl", "Hi, dit is de tekst.")
    b = L._meldsleutel("concept", "klant@example.nl", "Hi, dit is de tekst.")
    c = L._meldsleutel("concept", "klant@example.nl", "Hi, dit is een ANDERE tekst.")
    assert a == b
    assert a != c


def test_het_seintje_zegt_waarom_iets_blijft_liggen(L, monkeypatch):
    """Zonder die zin lijkt elk wachtend concept willekeurig, en dan is de map
    weer een stapel."""
    post = []

    class Postbode:
        def __enter__(self):
            return post.append

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(L, "_postbode", lambda *a, **kw: Postbode())
    monkeypatch.setattr(L, "_archiveer", lambda msg: None)
    monkeypatch.setattr(L, "_al_gemeld", lambda sleutel: False)
    monkeypatch.setitem(sys.modules, "mail_analyse",
                        types.SimpleNamespace(bugs=lambda: {}))

    L._meld_concept_klaar({"email": "info@voorbeeld.nl"}, "Re: vraag", "Hi.",
                          wachtreden="er staat een toezegging in ('bellen')")
    assert len(post) == 1
    assert "toezegging" in post[0].get_content()
