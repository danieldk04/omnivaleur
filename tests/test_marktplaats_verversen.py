"""Verversen op Marktplaats/2dehands: verwijderen is de eerste helft.

WAAROM DIT BESTAAT (30-08-2026)
Een verversing is: de oude advertentie weghalen en een nieuwe plaatsen. De
server laat die tweede helft alleen los als de verwijderopdracht "done" meldt
(backend/api/jobs.py). Meldt het verwijderen dus ten onrechte succes, dan komt
er een tweede advertentie naast de eerste te staan. Precies de melding van
zilverwebsite.nl: "Na verversen blijven oude advertenties staan, aantal op
Marktplaats is gegroeid."

TWEE GATEN, ALLEBEI IN EEN ECHTE BROWSER AANGETOOND
(tests/vinted-mock/mp-delete.html draait de ECHTE bgDeleteMp2dh tegen een
nagebouwd "Mijn advertenties", met de code van vóór vandaag ernaast):

1. De controle achteraf telde niet hoeveel advertenties de pagina liet zien.
   Bij het ZOEKEN werd dat al wel gedaan — juist om "hij staat er niet" te
   kunnen onderscheiden van "de pagina laadde niet / je bent uitgelogd" — maar
   bij het NAKIJKEN na het verwijderen niet. Een leeg overzicht las de extensie
   daar als "verwijderd", en meldde de opdracht als geslaagd.

2. De verwijderknop werd gekozen op "tekst begint met verwijder". Dat is één
   woord te ruim: elke knop die "Verwijder <iets>" heet en hoger op de pagina
   staat, won. Er werd dan geklikt, er kwam geen venster, en de verversing
   eindigde zonder dat iemand kon zien dat de verkeerde knop was geraakt.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BG = (ROOT / "extension/background.js").read_text(encoding="utf-8")
HARNAS = ROOT / "tests/vinted-mock/mp-delete.html"


def _body_vanaf(bron: str, vanaf: int) -> str:
    """Accolades tellen zonder je te laten foppen door strings, commentaar en
    regex-literals — /[^)]{1,24}/ zou een domme teller meteen laten ontsporen."""
    i = bron.index("{", vanaf)
    start, diepte, vorig = i, 0, ""
    while i < len(bron):
        c, twee = bron[i], bron[i:i + 2]
        if twee == "//":
            i = bron.index("\n", i)
            continue
        if twee == "/*":
            i = bron.index("*/", i) + 2
            continue
        if c in "\"'`":
            q, i = c, i + 1
            while i < len(bron):
                if bron[i] == "\\":
                    i += 2
                    continue
                if bron[i] == q:
                    break
                i += 1
            i, vorig = i + 1, q
            continue
        if c == "/" and (vorig == "" or vorig in "(,=:[!&|?{};+~*%^<>"):
            i += 1
            in_klasse = False
            while i < len(bron):
                if bron[i] == "\\":
                    i += 2
                    continue
                if bron[i] == "[":
                    in_klasse = True
                elif bron[i] == "]":
                    in_klasse = False
                elif bron[i] == "/" and not in_klasse:
                    break
                elif bron[i] == "\n":
                    break
                i += 1
            i, vorig = i + 1, "/"
            continue
        if c == "{":
            diepte += 1
        elif c == "}":
            diepte -= 1
            if diepte == 0:
                return bron[start:i + 1]
        if not c.isspace():
            vorig = c
        i += 1
    raise AssertionError("geen sluitende accolade")


def _verwijderroutine() -> str:
    m = re.search(r"^async function bgDeleteMp2dh\s*\(", BG, re.M)
    assert m, "bgDeleteMp2dh staat niet meer in de extensie"
    return _body_vanaf(BG, m.end())


# ── 1. Een leeg overzicht bewijst geen verwijdering ────────────────────────

def test_de_controle_achteraf_telt_hoeveel_advertenties_er_stonden():
    routine = _verwijderroutine()
    na = routine[routine.index("after confirming delete") - 3000:]
    assert "rendered" in na, (
        "de controle na het verwijderen telt niet meer hoeveel advertenties de pagina liet zien — "
        "een leeg overzicht wordt dan weer als 'verwijderd' gelezen"
    )


def test_een_leeg_overzicht_na_verwijderen_geeft_een_fout_en_geen_succes():
    routine = _verwijderroutine()
    assert "came back empty right after" in routine, (
        "er is geen foutmelding meer voor 'het overzicht kwam leeg terug' — "
        "dan wordt zo'n ronde weer als geslaagd gemeld en volgt er een dubbele advertentie"
    )
    # De melding moet vóór het afronden staan: eerst weigeren, dan pas complete.
    assert routine.index("came back empty right after") < routine.rindex('finaliseJob(serverUrl, job.id, "complete"')


def test_met_een_advertentienummer_wordt_de_advertentie_zelf_nagekeken():
    """Het overzicht rendert vijftig advertenties per keer en wij klikken
    maximaal veertig keer door. Boven de tweeduizend advertenties — Jaap heeft er
    1.284, Egbert 5.540 — staat de onze daar dus gewoon niet tussen, en zegt "ik
    zie hem niet meer" niets. De advertentiepagina antwoordt wel eenduidig."""
    routine = _verwijderroutine()
    na_bevestigen = routine[routine.index("CONFIRM_STEPS"):]
    assert "/seller/view/" in na_bevestigen, (
        "na het bevestigen wordt de advertentie zelf niet meer opgevraagd — "
        "op een groot account is het overzicht geen bewijs"
    )
    assert "is still online on" in na_bevestigen, (
        "een advertentie die na het bevestigen aantoonbaar nog leeft, hoort een fout te geven"
    )


def test_de_advertentie_zelf_blijft_natuurlijk_ook_een_reden_om_te_stoppen():
    routine = _verwijderroutine()
    assert "still visible on" in routine


# ── 2. De verwijderknop, niet zomaar een knop die met "verwijder" begint ───

def test_de_verwijderknop_moet_precies_verwijderen_heten():
    routine = _verwijderroutine()
    # De oude vorm eindigde op \b: dan matcht "Verwijder zoekopdracht" ook.
    assert r"verwijder(en)?\b" not in routine, (
        "de knopkeuze staat weer open voor 'Verwijder <iets>' — een opgeslagen zoekopdracht "
        "of filter hoger op de pagina wint dan van de echte knop boven de lijst"
    )
    assert r"^(🗑\s*)?verwijder(en)?(\s*\(\d+\))?$" in routine, (
        "de knop wordt niet meer op zijn hele tekst herkend"
    )


def test_de_knop_met_de_telling_wint():
    routine = _verwijderroutine()
    assert re.search(r"passend\.find\([^)]*\\\(\\d\+\\\)", routine), (
        "'Verwijder (1)' hoort te winnen van een kale 'Verwijder': alleen de bulk-knop "
        "krijgt een telling zodra er iets is aangevinkt"
    )


def test_bij_een_onvindbare_knop_reizen_de_knopteksten_mee():
    routine = _verwijderroutine()
    assert "Buttons on that page:" in routine, (
        "zonder de knoppen die er wél stonden is elke mislukking dezelfde ene zin"
    )


# ── 3. Wat in de pagina wordt uitgevoerd, moet in de pagina kunnen bestaan ──

def _geinjecteerde_functies():
    """Alles wat via execInTab in de pagina wordt uitgevoerd."""
    uit = []
    definitie = BG.index("function execInTab")
    for m in re.finditer(r"execInTab\(\s*\w+\s*,\s*", BG):
        if BG[:m.start()].count("\n") == BG[:definitie].count("\n"):
            continue
        regel = BG[:m.start()].count("\n") + 1
        naam = re.match(r"([A-Za-z_$][\w$]*)\s*[,)]", BG[m.end():m.end() + 80])
        if naam:
            fm = re.search(r"^(?:async\s+)?function %s\s*\(" % re.escape(naam.group(1)), BG, re.M)
            assert fm, f"{naam.group(1)} wordt geïnjecteerd maar bestaat niet"
            uit.append((f"{naam.group(1)}()", regel, _body_vanaf(BG, fm.end()), naam.group(1)))
        else:
            uit.append((f"inline op regel {regel}", regel, _body_vanaf(BG, m.end()), None))
    return uit


def test_er_worden_functies_in_de_pagina_uitgevoerd():
    assert len(_geinjecteerde_functies()) >= 20


@pytest.mark.parametrize("label,regel,body,eigen", _geinjecteerde_functies(),
                         ids=lambda v: str(v) if isinstance(v, (str, int)) else "")
def test_elke_geinjecteerde_functie_staat_helemaal_op_zichzelf(label, regel, body, eigen):
    """Chrome injecteert ALLEEN de meegegeven functie.

    Alles wat daarbuiten in background.js staat bestaat in de pagina niet. Roept
    een geïnjecteerde functie zoiets toch aan, dan klapt hij daar om vóór hij
    ook maar gekeken heeft — en dat leest de extensie als "niets gevonden".
    Zo werd op 30-08-2026 elke Vinted-verversing "Delete control not found",
    terwijl er in werkelijkheid niet eens gezocht wás. Deze test bewaakt dat
    voor álle geïnjecteerde functies, niet alleen die ene.
    """
    top = set(re.findall(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", BG, re.M))
    top |= set(re.findall(r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)", BG, re.M))
    lokaal = set(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)", body))
    lokaal |= set(re.findall(r"\bfunction\s*\*?\s*([A-Za-z_$][\w$]*)", body))

    buiten = [naam for naam in sorted(top)
              if naam != eigen and naam not in lokaal
              and re.search(r"(?<![.\w$])%s\s*[({\[.,)=;]" % re.escape(naam), body)]
    assert not buiten, (
        f"{label} gebruikt {buiten} — dat bestaat in de pagina niet en geeft daar een fout "
        f"vóór er iets gedaan is"
    )


# ── 4. De proef in een echte browser hoort te blijven bestaan ──────────────

def test_het_namaakoverzicht_bestaat_en_zet_de_oude_code_ernaast():
    assert HARNAS.exists(), "tests/vinted-mock/mp-delete.html is weg"
    tekst = HARNAS.read_text(encoding="utf-8")
    assert "bgDeleteMp2dh" in tekst
    assert "_oudBgDeleteMp2dh" in tekst, (
        "zonder de code van vóór de reparatie ernaast bewijst 'alles groen' niets"
    )
    assert "uitgelogdNaHerladen" in tekst, "het scenario met de weggevallen sessie is verdwenen"
    assert "VALS-GELUKT" in tekst, (
        "de proef controleert niet meer of 'verwijderd' ook echt verwijderd betekent"
    )


def test_de_bouwer_snijdt_de_echte_marktplaats_code_mee():
    bouwer = (ROOT / "tests/vinted-mock/build.js").read_text(encoding="utf-8")
    for naam in ("bgDeleteMp2dh", "expandMp2dhOverview", "verwijderViaAdvertentiepagina"):
        assert naam in bouwer, f"{naam} wordt niet meer in het namaakscherm geladen"


# ─────────────────────────────────────────────────────────────────────────────
# DE ADVERTENTIE KOMT TERUG IN ZIJN EIGEN CATEGORIE (30-08-2026, Amanda)
#
# "Als je een advertentie van marktplaats laat refreshen: dan gaat dat goed, tot
# het punt dat de advertentie is geplaatst: hij zet deze dan in de verkeerde
# categorie. Dit kun je bij MP niet aanpassen, dus moet je de advertentie weer
# in zijn geheel handmatig plaatsen."
#
# Oorzaak: bij het importeren werd de categorie van Marktplaats weggegooid en
# door een taalmodel opnieuw geraden uit onze eigen lijst. Die lijst kent
# kleding, wonen, antiek, muziek en sieraden — Amanda verkoopt daarnaast munten,
# bankbiljetten, postzegels en boeken. Voor die takken bestaat er geen goede
# doos, dus werd het altijd de verkeerde.
#
# Marktplaats zet de echte categorie gewoon op de advertentiepagina. Die wordt nu
# vlak vóór het verwijderen gelezen (en nog eens door de extensie zelf, die daar
# ingelogd staat) en gaat mee in de plaatsingsopdracht.

import json
import shutil
import subprocess
import sys

sys.path.insert(0, str(ROOT))
NODE = shutil.which("node")

# Zoals het er letterlijk op een echte, openbare advertentiepagina staat
# (marktplaats.nl, 30-08-2026, een Libisch bankbiljet).
ECHTE_PAGINA = (
    '{"categoryId":"1784","x":1,"l1CategoryId":1784,"l1CategoryName":"Postzegels en Munten",'
    '"l2CategoryId":1789,"l2CategoryName":"Bankbiljetten | Afrika","y":2}'
)


def test_de_echte_categorie_wordt_van_de_pagina_gelezen():
    from backend.services.mp_enrich import categorie_uit_html
    assert categorie_uit_html(ECHTE_PAGINA) == {
        "l1": 1784, "l1_naam": "Postzegels en Munten",
        "l2": 1789, "l2_naam": "Bankbiljetten | Afrika",
    }


def test_een_half_paar_telt_niet():
    """Met alleen een hoofdcategorie kun je geen plaatsformulier openen — en half
    raden is precies wat dit moet stoppen."""
    from backend.services.mp_enrich import categorie_uit_html
    assert categorie_uit_html('{"l1CategoryId":1784}') == {}
    assert categorie_uit_html("") == {}


def _mp_url_js() -> str:
    """MP_CATEGORIES + getMpSyiUrl, letterlijk uit background.js gesneden."""
    stukken = []
    for tabel in ("const MP_BABY_SIZES = {", "const MP_KIDS_SIZES = {", "const MP_CATEGORIES = {"):
        i = BG.index(tabel)
        stukken.append(BG[i:BG.index("{", i)] + _body_vanaf(BG, i) + ";")
    for naam in ("mpCategorieOpNummer", "mpKidsSizeCat3", "getMpSyiUrl"):
        m = re.search(rf"^function {naam}\(", BG, flags=re.M)
        assert m, naam
        stukken.append(BG[m.start():BG.index("{", m.start())] + _body_vanaf(BG, m.start()))
    m = re.search(r"^let _mpOpNummer[^\n]*", BG, flags=re.M)
    assert m, "_mpOpNummer"
    return (m.group(0) + "\n"
            + "class CategoryUnresolvedError extends Error {}\n"
            + "\n".join(stukken))


def _syi(item: dict, bron: str | None = None) -> str:
    driver = (f"{bron if bron is not None else _mp_url_js()}\n"
              f"try {{ console.log(getMpSyiUrl('marktplaats', {json.dumps(item)})); }}"
              f" catch (e) {{ console.log('FOUT: ' + e.message); }}")
    r = subprocess.run([NODE, "-e", driver], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.mark.skipif(NODE is None, reason="node is niet geïnstalleerd")
def test_een_categorie_buiten_onze_lijst_gaat_op_de_nummers_van_marktplaats():
    """Postzegels en Munten staat niet in onze lijst — en hoeft dat ook niet."""
    url = _syi({
        "title": "Libisch 1 Dinar biljet - Zeldzaam verzamelobject",
        "category": "antiek curiosa en brocante",   # de geraden categorie
        "gender": "antiek",
        "mp_category": {"l1": 1784, "l2": 1789, "l2_naam": "Bankbiljetten | Afrika"},
    })
    assert url == "https://www.marktplaats.nl/plaats/1784/1789?title="


@pytest.mark.skipif(NODE is None, reason="node is niet geïnstalleerd")
def test_de_oude_versie_zette_hem_in_de_geraden_categorie():
    """Tegenbewijs: zonder deze reparatie meet de test hierboven niets."""
    oud = subprocess.run(["git", "show", "HEAD:extension/background.js"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    bron = "class CategoryUnresolvedError extends Error {}\n"
    for tabel in ("const MP_BABY_SIZES = {", "const MP_KIDS_SIZES = {", "const MP_CATEGORIES = {"):
        i = oud.index(tabel)
        bron += oud[i:oud.index("{", i)] + _body_vanaf(oud, i) + ";\n"
    for naam in ("mpKidsSizeCat3", "getMpSyiUrl"):
        m = re.search(rf"^function {naam}\(", oud, flags=re.M)
        bron += oud[m.start():oud.index("{", m.start())] + _body_vanaf(oud, m.start()) + "\n"
    url = _syi({
        "title": "Libisch 1 Dinar biljet - Zeldzaam verzamelobject",
        "category": "antiek curiosa en brocante",
        "gender": "antiek",
        "mp_category": {"l1": 1784, "l2": 1789},
    }, bron=bron)
    assert url != "https://www.marktplaats.nl/plaats/1784/1789?title=", \
        "de oude versie deed dit al — dan is het tegenbewijs weg"
    assert "1784" not in url, url


@pytest.mark.skipif(NODE is None, reason="node is niet geïnstalleerd")
def test_een_categorie_die_we_wel_kennen_houdt_zijn_eigen_regel():
    """Daar hangt het bucketId aan; dat adres is bewezen en blijft leidend."""
    kleding = _syi({"title": "Grijze trui", "category": "jeans", "gender": "dames"})
    assert kleding == "https://www.marktplaats.nl/plaats/621/636?bucketId=162&title="
    # Nu hetzelfde paar, maar aangereikt door Marktplaats zelf: zelfde adres,
    # inclusief bucketId — niet de kale tweenummervorm.
    zelfde = _syi({"title": "Grijze trui", "category": "", "gender": "",
                   "mp_category": {"l1": 621, "l2": 636}})
    assert zelfde == kleding, zelfde


@pytest.mark.skipif(NODE is None, reason="node is niet geïnstalleerd")
def test_zonder_categorie_van_marktplaats_verandert_er_niets():
    assert _syi({"title": "Grijze trui", "category": "jeans", "gender": "dames"}) \
        == "https://www.marktplaats.nl/plaats/621/636?bucketId=162&title="
    assert _syi({"title": "Iets", "category": "", "gender": ""}).startswith("FOUT: ")


def test_de_categorie_wordt_opgehaald_voor_het_verwijderen():
    """Na het verwijderen is de advertentiepagina 410 en is de categorie weg —
    en een mislukte herplaatsing kost de advertentie."""
    relist = (ROOT / "backend/services/relist.py").read_text(encoding="utf-8")
    assert "categorie_van_advertentie" in relist
    voorbereiden = relist.index("---- 1. Alles voorbereiden")
    wegschrijven = relist.index("---- 2. Nu pas wegschrijven")
    assert voorbereiden < relist.index("categorie_van_advertentie") < wegschrijven


def test_de_extensie_legt_de_categorie_ook_zelf_vast():
    """Tweede bron: de extensie staat ingelogd op die pagina, de server niet —
    Marktplaats geeft een server nog weleens een 403."""
    snap = BG.split("async function mpAdvertentieSnapshot(tabId)")[1].split("\n}\n")[0]
    assert "l1CategoryId" in snap and "l2CategoryId" in snap
    assert "mp_category," in snap, "de categorie moet ook echt teruggegeven worden"


def test_de_opgevangen_categorie_overschrijft_de_geraden_categorie():
    jobs = (ROOT / "backend/api/jobs.py").read_text(encoding="utf-8")
    blok = jobs.split('cap_cat = captured.get("mp_category")')[1][:400]
    assert 'payload["mp_category"] = cap_cat' in blok
    assert 'cap_cat.get("l1") and cap_cat.get("l2")' in blok
