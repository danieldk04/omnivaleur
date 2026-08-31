"""De mailagent verstuurt niets uit zichzelf, en meldt niets twee keer.

WAAROM DIT ER IS (31-08-2026) — en dit is een correctie op mijn eigen werk van
diezelfde ochtend.

Ik had de agent laten versturen wat volgens mij "geen beslissing" bevatte:
beleefdheidsantwoorden, opvolgingen op stilte, terugkoppelingen van de
developer. De toets was: staat er een toezegging in? Zo nee, dan mag hij weg.

Dat was fout, en het ging binnen een uur mis:

  * Zilverwebsite kreeg een mail die begon met "Hi Ronald". Die naam bestaat
    daar niet — het model had hem verzonnen. Er staat al sinds 20-08 vast dat
    een aanhef nooit een geraden naam mag bevatten. Geen enkele toets op
    toezeggingen ziet zoiets.
  * Patricia van Boutique MoDo kreeg een antwoord op een bericht dat Daniel op
    27-08 zelf al had beantwoord.
  * Frank de Veer kreeg een derde bericht terwijl hij al met vakantie was.

De les: wat een mail schadelijk maakt zit niet in wat hij BELOOFT maar in of hij
nog KLOPT — de aanhef, de naam, of het gesprek al gesloten was. Daar is geen
filter tegen te bouwen dat ik veilig kan noemen.

Daniel: "nooit uit jezelf versturen." Deze proeven houden dat vast.
"""
import importlib.util
import pathlib
import sys
import types

import pytest

WORTEL = pathlib.Path(__file__).resolve().parents[1]
BRON = (WORTEL / "scripts" / "leadgen_mail.py").read_text(encoding="utf-8")
ANALYSE = (WORTEL / "scripts" / "mail_analyse.py").read_text(encoding="utf-8")


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


# ── 1. de mailflow staat stil ────────────────────────────────────────────────

def test_de_mailflow_staat_op_pauze(L):
    """Door Daniel uitgezet op 31-08. Weer aanzetten is zijn besluit."""
    assert L.MAILFLOW_GEPAUZEERD is True


def test_de_pauze_werkt_voordat_er_iets_gelezen_of_gecontroleerd_wordt():
    """Een pauze die pas werkt als de rest het doet, is geen pauze. Bij de
    Supabase-storing van 31-08 klapte `tick` al om op zijn eerste regel."""
    body = BRON.split("def tick(args) -> None:", 1)[1].split("\ndef ", 1)[0]
    assert "MAILFLOW_GEPAUZEERD" in body
    assert body.index("MAILFLOW_GEPAUZEERD") < body.index("_controleer_afzender")
    assert body.index("MAILFLOW_GEPAUZEERD") < body.index("_state()")


def test_de_pauze_stopt_de_beurt_echt(L, monkeypatch):
    """Niet alleen een regel in het logboek: er mag geen enkele stap volgen."""
    geraakt = []
    monkeypatch.setattr(L, "_controleer_afzender",
                        lambda *a, **k: geraakt.append("afzender"))
    monkeypatch.setattr(L, "_state", lambda: geraakt.append("state") or {})

    L.tick(types.SimpleNamespace(per_dag=0, max_per_beurt=0))
    assert geraakt == [], f"de beurt liep door tot {geraakt}"


# ── 2. er gaat niets uit zichzelf de deur uit ────────────────────────────────

def test_er_is_geen_weg_meer_die_zelf_verstuurt():
    """Bewust weggehaald in plaats van uitgezet met een schakelaar: een
    schakelaar is iets wat iemand later per ongeluk omzet."""
    for verboden in ("zelf_versturen", "_stuur_zelf", "_waarom_niet_zelf_versturen"):
        assert verboden not in BRON, f"{verboden} staat er nog in leadgen_mail.py"
        assert verboden not in ANALYSE, f"{verboden} staat er nog in mail_analyse.py"


def test_het_klaarzetten_van_een_concept_verstuurt_niets(L, monkeypatch):
    """`_zet_concept_klaar` mag alleen in de conceptenmap schrijven. Zou hier
    ooit een `_postbode` bij komen, dan gaat er weer post uit zonder Daniel."""
    functie = BRON.split("def _zet_concept_klaar(", 1)[1].split("\ndef ", 1)[0]
    assert "_postbode" not in functie
    assert '"Verzonden"' not in functie
    assert '"\\\\Draft"' in functie


def test_de_terugkoppeling_van_de_developer_blijft_ook_een_concept():
    """Deze leek het veiligst — hij is aan de code getoetst. Juist hier stond
    "Hi Ronald" in."""
    blok = ANALYSE.split("def bericht_over_reparaties(", 1)[1].split("\ndef ", 1)[0]
    assert "_zet_concept_klaar" in blok
    assert "zelf_versturen" not in blok


def test_de_opvolging_op_stilte_blijft_ook_een_concept():
    blok = BRON.split("def _warme_opvolging(", 1)[1].split("\ndef ", 1)[0]
    assert "_zet_concept_klaar" in blok
    assert "zelf_versturen" not in blok


# ── 3. nooit twee keer hetzelfde seintje ─────────────────────────────────────

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
