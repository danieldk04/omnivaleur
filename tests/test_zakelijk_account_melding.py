"""
Een zakelijk account mag geen inlogverwijt meer krijgen, en geen vraag.

GEMETEN 15-09-2026 (Egbert Brouwer, Papa's Plectrums). Het persoonlijke
advertentieoverzicht bestaat alleen voor een particulier account; bij een
zakelijk account geeft het 401 en verwijst het door naar de inlogpagina, precies
zoals bij een uitgelogde bezoeker. Juist die pagina gebruikt de extensie als
inlogcontrole. Zijn openbare advertentiepagina op 2dehands zegt
"sellerType":"TRADER", een particuliere verkoper ernaast "CONSUMER".

De extensie is gerepareerd in 1.0.332, maar die is pas na de Web Store bij hem
binnen. Tot die tijd moet de server het verschil zien, en dat kan: het staat
openbaar op zijn eigen advertentie, zonder inlog en zonder hem iets te vragen.

Draaien: python3 tests/test_zakelijk_account_melding.py
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api import jobs as J

VOOR_DE_REPARATIE = "b7097dbd"   # laatste commit vóór deze wijziging

VERWIJT = ("You are not signed in to 2dehands (2dehands.be) in this browser, so nothing was "
           "published. We checked twice: once in the background and once in a tab on 2dehands "
           "itself, and the site refused both times (HTTP 401). [extensie 1.0.329]")
JOB = {"action": "create", "platform": "2dehands", "item_id": "x"}

mislukt = 0


def check(naam, voorwaarde, uitleg=""):
    global mislukt
    if voorwaarde:
        print(f"  ok   {naam}")
        return
    mislukt += 1
    print(f"  FOUT {naam}{' — ' + uitleg if uitleg else ''}")


def test_zakelijk_krijgt_geen_inlogverwijt():
    uit = J._rechtgezette_foutmelding(JOB, {"error": VERWIJT}, (1, 0, 329), False, True)
    tekst = uit["error"]
    # Het letterlijke citaat van de meting blijft er bewust onder staan, zoals
    # overal in dit bestand. Wat NIET meer mag, is dat wij zelf het verwijt maken.
    ons = tekst.split("word for word")[0]
    check("zakelijk: wij verwijten hem niets meer", "not signed in" not in ons.lower(), ons[:140])
    check("zakelijk: er staat wat er echt aan de hand is", "business account" in tekst)
    check("zakelijk: er wordt niets meer gevraagd", "?" not in tekst, tekst[:120])
    check("zakelijk: de wachtrij blijft staan", "queue is still there" in tekst)
    check("zakelijk: de oorspronkelijke meting blijft bewaard",
          uit["error_oorspronkelijk"] == VERWIJT and VERWIJT in tekst)


def test_particulier_en_onbekend_veranderen_niet():
    # zakelijk=None is bit voor bit wat de vorige versie deed: die kende de
    # parameter niet, dus die tak bestond daar niet.
    oud = J._rechtgezette_foutmelding(JOB, {"error": VERWIJT}, (1, 0, 329), False, None)
    check("onbekend: melding onveranderd", oud.get("error") == VERWIJT,
          "zonder dit bewijst deze test niets")
    part = J._rechtgezette_foutmelding(JOB, {"error": VERWIJT}, (1, 0, 329), False, False)
    check("particulier: melding onveranderd", part.get("error") == VERWIJT)


class _NepAntwoord:
    def __init__(self, data=None, tekst=""):
        self._data, self.text = data, tekst

    def json(self):
        return self._data


class _NepClient:
    """De echte antwoorden van 15-09-2026, ingekort."""
    ZOEK = {"listings": [
        {"itemId": "m9999999999", "vipUrl": "/v/ander/m9999999999-iets"},
        {"itemId": "m2442213317", "vipUrl": "/v/muziek/m2442213317-gitaar"},
    ]}
    PAGINA = ('...,"activeYears":13,"isAsqEnabled":true,"phoneNumberHidden":false,'
              '"sellerType":"TRADER","showMap":true,...')

    def __init__(self, *a, **k):
        self.bezocht = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None, headers=None):
        self.bezocht.append(url)
        if "lrp/api/search" in url:
            return _NepAntwoord(data=self.ZOEK)
        return _NepAntwoord(tekst=self.PAGINA if "m2442213317" in url else "geen type hier")


class _NepTabel:
    def __init__(self, rijen):
        self._r = rijen

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return type("R", (), {"data": self._r})()


class _NepDb:
    def __init__(self, rijen):
        self._r = rijen

    def table(self, naam):
        return _NepTabel(self._r)


def test_verkoperstype_wordt_bewezen_niet_geraden(monkeypatch=None):
    import httpx
    echt = httpx.Client
    httpx.Client = _NepClient
    try:
        J._VERKOPERSOORT.clear()
        goed = _NepDb([{"payload": {"title": "Miniatuur replica Fender basgitaar"},
                        "result": {"platform_listing_id": "m2442213317"}}])
        check("nummer klopt: TRADER gevonden",
              J._verkoper_soort(goed, "u1", "2dehands") == "TRADER")

        J._VERKOPERSOORT.clear()
        mis = _NepDb([{"payload": {"title": "Miniatuur replica Fender basgitaar"},
                       "result": {"platform_listing_id": "m1111111111"}}])
        check("nummer klopt niet: geen oordeel",
              J._verkoper_soort(mis, "u2", "2dehands") is None,
              "we mogen nooit het type van een andere advertentie overnemen")

        J._VERKOPERSOORT.clear()
        leeg = _NepDb([])
        check("niets geplaatst: geen oordeel", J._verkoper_soort(leeg, "u3", "2dehands") is None)
    finally:
        httpx.Client = echt
        J._VERKOPERSOORT.clear()


def test_de_vorige_versie_kon_dit_niet():
    oud = subprocess.run(["git", "show", f"{VOOR_DE_REPARATIE}:backend/api/jobs.py"],
                         capture_output=True, text=True).stdout
    check("1.0.331-server kende het verkoperstype niet", "_verkoper_soort" not in oud,
          "zonder dit bewijst deze test niets")
    check("en gaf het inlogverwijt gewoon door",
          not re.search(r"business account\b.*My adverts", oud, re.S))


if __name__ == "__main__":
    print("\n1. De melding bij een zakelijk account")
    test_zakelijk_krijgt_geen_inlogverwijt()
    print("\n2. Voor iedereen anders verandert er niets")
    test_particulier_en_onbekend_veranderen_niet()
    print("\n3. Het type wordt bewezen, niet geraden")
    test_verkoperstype_wordt_bewezen_niet_geraden()
    print("\n4. De versie ervoor")
    test_de_vorige_versie_kon_dit_niet()
    print("\nAlles goed.\n" if not mislukt else f"\n{mislukt} controle(s) mislukt.\n")
    raise SystemExit(1 if mislukt else 0)
