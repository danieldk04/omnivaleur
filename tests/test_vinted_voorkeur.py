"""De drie lijsten met Vinted-categoriegroepen moeten woordelijk gelijk zijn.

Ze staan op drie plekken omdat ze drie dingen doen: welke vinkjes de verkoper
ziet (frontend), wat er bij opslaan bewaard mag blijven (instellingen.py) en
waarop de server een artikel blokkeert (platformregels.py).

Lopen ze uiteen, dan krijg je de vervelendste storing die er is: het dashboard
zegt dat een artikel op Vinted mag, de server weigert het, en de reden verwijst
naar een instelling die de verkoper nooit heeft kunnen aanvinken. Dat was op
27-08-2026 het geval voor "wonen" — die groep bestond sinds augustus in de
categorieboom maar in geen van de twee voorkeurslijsten, dus voor iedereen met
een ingestelde voorkeur werd elk woon-artikel stil van Vinted geweerd.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.instellingen import VINTED_GROEPEN_GELDIG  # noqa: E402
from backend.services.platformregels import GROEPEN  # noqa: E402


def _frontend(naam: str) -> set[str]:
    src = (ROOT / "frontend" / "app.html").read_text(encoding="utf-8")
    regel = re.search(rf"const {naam} = \[(.*?)\];", src, re.S)
    assert regel, f"{naam} niet gevonden in app.html"
    return set(re.findall(r"'([^']+)'", regel.group(1)))


def _frontend_labels() -> set[str]:
    src = (ROOT / "frontend" / "app.html").read_text(encoding="utf-8")
    blok = re.search(r"const VINTED_GROEP_LABELS = \{(.*?)\};", src, re.S)
    assert blok, "VINTED_GROEP_LABELS niet gevonden"
    return set(re.findall(r"(\w+)\s*:", blok.group(1)))


def test_de_drie_lijsten_zijn_gelijk():
    frontend = _frontend("VINTED_GROEPEN")
    backend = set(VINTED_GROEPEN_GELDIG)
    server = set(GROEPEN)
    assert frontend == backend == server, (
        f"lijsten lopen uiteen —\n"
        f"  alleen in het dashboard: {sorted(frontend - backend - server)}\n"
        f"  alleen in instellingen : {sorted(backend - frontend - server)}\n"
        f"  alleen in platformregels: {sorted(server - frontend - backend)}")


def test_elke_groep_heeft_een_leesbaar_label():
    """Zonder label toont het vinkje de kale sleutel ('wonen' in plaats van
    'Home & garden'), en dat is precies de plek waar iemand niet naar zoekt."""
    ontbreekt = _frontend("VINTED_GROEPEN") - _frontend_labels()
    assert not ontbreekt, f"geen label voor: {sorted(ontbreekt)}"


def test_elke_groep_bestaat_ook_echt_in_de_categorieboom():
    """Een voorkeursvinkje voor een groep die niemand kan kiezen is dood gewicht."""
    app = (ROOT / "frontend" / "app.html").read_text(encoding="utf-8")
    start = app.index("const CATEGORIES = {")
    blok = app[start:app.index("\n};", start)]
    sleutels = re.findall(r'\["([^"]+)"\s*,\s*"[^"]*"\]', blok)
    voorvoegsels = {k.split()[0] for k in sleutels}
    # Kleding zit zonder voorvoegsel in de boom ("jeans", "rokken"): die groepen
    # zijn niet uit een sleutel af te leiden en worden hier overgeslagen.
    kleding = {"dames", "heren", "kinderen", "unisex"}
    for groep in set(VINTED_GROEPEN_GELDIG) - kleding:
        assert groep in voorvoegsels, f"groep '{groep}' heeft geen categorieen in de boom"
