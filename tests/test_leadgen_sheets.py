"""De spreadsheet als werkoverzicht en tekstbron van de mailmachine.

WAAROM DIT ER IS (14-09-2026)
De Notion-Leadlist is verhuisd naar Google Sheets, en Daniel past de mailteksten
daar voortaan zelf aan. Twee dingen mogen daarbij nooit gebeuren:

  * een mail met een half invulveld of een lege alinea de deur uit, omdat er in
    een cel iets verkeerd getypt is;
  * een gebeurtenis in de rij van iemand anders, omdat Daniel de lijst sorteerde
    tussen het lezen en het schrijven, of zijn Notities die overschreven worden.

De Google-kant is hier nagebouwd; de echte controle- en schrijfcode draait.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import leadgen_sheets as ls  # noqa: E402
import leadgen_sheets_opzetten as op  # noqa: E402


def _teksten():
    return [list(r) for r in op.mailteksten()]


def _rij(rijen, sleutel):
    return next(r for r in rijen if r[0] == sleutel)


# ── Mailteksten ───────────────────────────────────────────────────────────


def test_de_begintekst_komt_zelf_door_de_controle():
    teksten = ls.controleer_teksten(_teksten())
    assert set(teksten) == {s for s, _ in ls.TEKST_RIJEN}
    assert "[openingszin]" in teksten["A1"]["tekst_je"]
    assert "zie je" in teksten["A1"]["tekst_je"] and "zien jullie" in teksten["A1"]["tekst_jullie"]


def test_een_onbekend_invulveld_houdt_alles_tegen():
    rijen = _teksten()
    _rij(rijen, "A2")[4] = "[aanhef],\n\nHoi [naam], nog even over mijn mailtje van vorige week."
    with pytest.raises(ls.TekstenFout, match=r"\[naam\]"):
        ls.controleer_teksten(rijen)


def test_alle_fouten_komen_in_een_keer_in_de_melding():
    rijen = _teksten()
    _rij(rijen, "B1")[5] = ""                                   # jullie-tekst leeg
    _rij(rijen, "A3")[2] = "Laatste {jouw} bericht"             # oud codeteken
    rijen.remove(_rij(rijen, "V2"))                             # rij weg
    with pytest.raises(ls.TekstenFout) as fout:
        ls.controleer_teksten(rijen)
    melding = str(fout.value)
    assert "B1" in melding and "A3" in melding and "V2" in melding


def test_een_hernoemde_kolom_houdt_alles_tegen():
    rijen = _teksten()
    rijen[0][4] = "Tekst"
    with pytest.raises(ls.TekstenFout, match="Tekst \\(je\\)"):
        ls.controleer_teksten(rijen)


def test_video_opvolging_zonder_jullie_tekst_mag():
    rijen = _teksten()
    assert _rij(rijen, "V1")[5] == ""
    ls.controleer_teksten(rijen)


def test_invullen_negeert_hoofdletters():
    assert ls.vul_in("[Aanhef], op [PLATFORM]", {"[aanhef]": "Hi", "[platform]": "2dehands"}) \
        == "Hi, op 2dehands"


# ── De tab Leads ──────────────────────────────────────────────────────────


class NepSheets:
    """Een spreadsheet in het geheugen, met dezelfde vier handelingen als Sheets."""

    def __init__(self, leads, log=None):
        self.tabs = {ls.TAB_LEADS: [list(r) for r in leads], ls.TAB_LOG: [ls.LOG_KOLOMMEN]}
        self.verzoeken = 0

    def lees(self, bestand, bereik):
        self.verzoeken += 1
        return [list(r) for r in self.tabs[bereik.split("!")[0]]]

    def schrijf(self, bestand, blokken):
        self.verzoeken += 1
        for blok in blokken:
            tab, cel = blok["range"].split("!")
            kolom = ord(cel[0]) - 65
            rij = int(cel[1:]) - 1
            regel = self.tabs[tab][rij]
            regel += [""] * (kolom + 1 - len(regel))
            regel[kolom] = blok["values"][0][0]

    def voeg_toe(self, bestand, tab, rijen):
        self.verzoeken += 1
        self.tabs[tab] += [list(r) for r in rijen]


KOP = ls.LEADS_KOLOMMEN


def _leadrij(bedrijf, adres, notities=""):
    rij = [""] * len(KOP)
    rij[KOP.index("Bedrijf")], rij[KOP.index("E-mail")] = bedrijf, adres
    rij[KOP.index("Notities")], rij[KOP.index(ls.STOP_KOLOM)] = notities, False
    return rij


def _cel(nep, adres, kolom):
    rij = next(r for r in nep.tabs[ls.TAB_LEADS][1:] if r[KOP.index("E-mail")] == adres)
    return rij[KOP.index(kolom)] if KOP.index(kolom) < len(rij) else ""


def test_schrijft_in_de_rij_van_het_adres_ook_na_sorteren():
    """DE KERN. Tussen noteren en wegschrijven sorteert Daniel de lijst om."""
    nep = NepSheets([KOP, _leadrij("Anna", "anna@x.nl"), _leadrij("Bram", "bram@y.nl", "belt vrijdag")])
    blad = ls.Leadblad(nep)
    blad.noteer({"email": "anna@x.nl"}, "mail 1 verstuurd", {"Fase": "2. Benaderd"})
    nep.tabs[ls.TAB_LEADS][1:] = list(reversed(nep.tabs[ls.TAB_LEADS][1:]))   # Daniel sorteert
    blad.wegschrijven()
    assert _cel(nep, "anna@x.nl", "Fase") == "2. Benaderd"
    assert _cel(nep, "bram@y.nl", "Fase") == ""
    assert _cel(nep, "bram@y.nl", "Notities") == "belt vrijdag"


def test_notities_en_stopvinkje_blijven_van_daniel():
    nep = NepSheets([KOP, _leadrij("Anna", "anna@x.nl", "wil bellen")])
    blad = ls.Leadblad(nep)
    blad.noteer({"email": "anna@x.nl"}, "heeft geantwoord", {"Fase": "4. Gereageerd"})
    blad.wegschrijven()
    assert _cel(nep, "anna@x.nl", "Notities") == "wil bellen"
    assert _cel(nep, "anna@x.nl", ls.STOP_KOLOM) is False
    assert "heeft geantwoord" in _cel(nep, "anna@x.nl", "Laatste gebeurtenis")
    assert nep.tabs[ls.TAB_LOG][-1][2:] == ["anna@x.nl", "heeft geantwoord"]


def test_een_lead_die_er_nog_niet_staat_komt_onderaan():
    nep = NepSheets([KOP, _leadrij("Anna", "anna@x.nl")])
    blad = ls.Leadblad(nep)
    blad.noteer({"email": "Nieuw@Z.be", "handelsnaam": "Zolder BV", "platform": "2dehands",
                 "ads": 120}, "mail 1 verstuurd", {"Fase": "2. Benaderd", "Mails verstuurd": 1})
    blad.wegschrijven()
    nieuw = nep.tabs[ls.TAB_LEADS][-1]
    assert nieuw[KOP.index("E-mail")] == "nieuw@z.be"
    assert nieuw[KOP.index("Platform")] == "2dehands"
    assert nieuw[KOP.index("Fase")] == "2. Benaderd" and nieuw[KOP.index("Advertenties")] == 120
    assert blad.nieuw == 1


def test_een_verdwenen_kolom_wordt_gemeld_niet_verzonnen():
    kop = [k for k in KOP if k != "Status"]
    rij = [""] * len(kop)
    rij[kop.index("E-mail")] = "anna@x.nl"
    nep = NepSheets([kop, rij])
    blad = ls.Leadblad(nep)
    blad.noteer({"email": "anna@x.nl"}, "warm", {"Status": "Interesse", "Fase": "⚡ Jij bent aan zet"})
    blad.wegschrijven()
    assert blad.gemist == {"Status"}
    assert nep.tabs[ls.TAB_LEADS][1][kop.index("Fase")] == "⚡ Jij bent aan zet"


def test_mislukt_wegschrijven_bewaart_de_gebeurtenissen():
    class Kapot(NepSheets):
        def schrijf(self, bestand, blokken):
            raise ls.SheetsFout("503")
    nep = Kapot([KOP, _leadrij("Anna", "anna@x.nl")])
    blad = ls.Leadblad(nep)
    blad.noteer({"email": "anna@x.nl"}, "mail 2 verstuurd", {"Fase": "T2. Tekst follow-up 1"})
    with pytest.raises(ls.SheetsFout):
        blad.wegschrijven()
    assert len(blad._wachtend) == 1


def test_gestopt_leest_het_vinkje():
    aan = _leadrij("Bram", "bram@y.nl")
    aan[KOP.index(ls.STOP_KOLOM)] = True
    nep = NepSheets([KOP, _leadrij("Anna", "anna@x.nl"), aan])
    assert ls.Leadblad(nep).gestopt() == {"bram@y.nl"}


def test_zonder_stopkolom_is_er_geen_stoplijst_maar_een_fout():
    kop = [k for k in KOP if k != ls.STOP_KOLOM]
    with pytest.raises(ls.SheetsFout, match=ls.STOP_KOLOM):
        ls.Leadblad(NepSheets([kop])).gestopt()


def test_kolomletters():
    assert [ls.kolomletter(i) for i in (0, 18, 25, 26, 51)] == ["A", "S", "Z", "AA", "AZ"]


def test_nieuwe_leads_komen_klaar_te_staan_zonder_bestaande_aan_te_raken():
    nep = NepSheets([KOP, _leadrij("Anna", "anna@x.nl", "al gebeld")])
    toegevoegd, al = ls.Leadblad(nep).zet_klaar([
        {"email": "ANNA@x.nl", "handelsnaam": "Anna"},              # stond er al
        {"email": "piet@y.nl", "handelsnaam": "Piet", "ads": 40},
        {"email": "piet@y.nl", "handelsnaam": "Piet dubbel"},       # twee keer gevonden
        {"tel": "0612345678", "handelsnaam": "Zonder mail"},        # niet te mailen
    ])
    assert (toegevoegd, al) == (1, 1)
    assert [r[KOP.index("E-mail")] for r in nep.tabs[ls.TAB_LEADS][1:]] == ["anna@x.nl", "piet@y.nl"]
    assert _cel(nep, "piet@y.nl", "Fase") == "1. Te benaderen"
    assert _cel(nep, "anna@x.nl", "Notities") == "al gebeld"


def test_het_logboek_toont_nederlandse_tijd_ook_op_een_server_in_utc(monkeypatch):
    """14-09-2026: de server draait op UTC, dus een mail van 12:27 stond als
    10:27 in het logboek. Daniel leest die tijden als Nederlandse tijd."""
    import time as _time
    from datetime import datetime
    from zoneinfo import ZoneInfo
    monkeypatch.setenv("TZ", "UTC")
    _time.tzset()
    try:
        blad = ls.Leadblad(NepSheets([KOP, _leadrij("Anna", "anna@x.nl")]))
        blad.noteer({"email": "anna@x.nl"}, "mail 1 verstuurd", {})
        verwacht = datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%d-%m-%Y %H:%M")
        assert blad._wachtend[0][3] == verwacht
    finally:
        monkeypatch.delenv("TZ")
        _time.tzset()
