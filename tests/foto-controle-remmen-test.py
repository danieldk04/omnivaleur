"""De remmen van de fotocontrole. Draaien: python3 tests/foto-controle-remmen-test.py

WAAROM DEZE PROEF ER IS (13-09-2026)

Elke reparatie van deze ronde haalt een ECHTE advertentie weg en zet hem terug.
Gaat de teller mis, dan doet hij dat elke zes uur opnieuw, of juist nooit. Beide
kwamen tijdens het bouwen voor: de eerste versie telde de plaatsing mee die de
advertentie zelf maakte (en blokkeerde dus de lederhosen die nog nul reparaties
had gehad), en de tweede versie begon bij nul zodra een reparatie een nieuw
advertentienummer opleverde (en zou dus eeuwig door zijn gegaan).

Hier wordt de echte _pogingen_op gedraaid tegen nagemaakte opdrachtenlijsten,
zodat er geen advertentie aan te pas komt.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SUPABASE_URL", "https://proef.invalid")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "proef")
os.environ.setdefault("SUPABASE_KEY", "proef")

from datetime import datetime, timedelta, timezone
import backend.database as database
from backend.services import foto_controle as fc

NU = datetime.now(timezone.utc)
def t(dagen_geleden, uren=0):
    return (NU - timedelta(days=dagen_geleden, hours=uren)).isoformat()

class NepDb:
    """Levert één vaste opdrachtenlijst terug, hoe de vraag ook is opgebouwd."""
    def __init__(self, opdrachten): self.opdrachten = opdrachten
    def table(self, _): return self
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def order(self, *a, **k): return self
    def execute(self):
        class R: pass
        r = R(); r.data = self.opdrachten; return r

async def _direct(f, *a, **k):
    uit = f(*a, **k)
    return await uit if hasattr(uit, "__await__") else uit
fc.naast_de_lus = _direct

mislukt = 0
def check(naam, gekregen, verwacht):
    global mislukt
    if gekregen == verwacht:
        print(f"  ok   {naam}  ({gekregen})")
    else:
        mislukt += 1
        print(f"  FOUT {naam}: {gekregen}, verwacht {verwacht}")

def plaatsing(dagen, nummer=None):
    return {"created_at": t(dagen), "done_at": t(dagen, -1),
            "result": {"platform_listing_id": nummer} if nummer else {}}

async def tel(opdrachten, nummer):
    return await fc._pogingen_op(NepDb(opdrachten), "item", "marktplaats", nummer)

async def main():
    print("De remmen van de fotocontrole:")

    # 1. Gewone advertentie: één plaatsing, die het huidige nummer opleverde.
    #    Nul reparaties, dus repareren mag. Dit is het geval dat de eerste
    #    versie ten onrechte blokkeerde.
    check("verse advertentie, nog nooit gerepareerd",
          await tel([plaatsing(1, "mA")], "mA"), 0)

    # 2. Een afgebroken poging VOOR de geslaagde plaatsing telt niet mee.
    #    Precies de lederhosen: een geannuleerde opdracht op 09-09 en de echte
    #    plaatsing op 12-09.
    check("afgebroken poging ervoor telt niet mee",
          await tel([plaatsing(4), plaatsing(1, "mA")], "mA"), 0)

    # 3. Eén reparatie klaargezet na de plaatsing: telt als één.
    check("één reparatie klaargezet",
          await tel([plaatsing(3, "mA"), plaatsing(0)], "mA"), 1)

    # 4. Twee reparaties: op, dus niet nog eens.
    check("twee reparaties: budget op",
          await tel([plaatsing(5, "mA"), plaatsing(1), plaatsing(0)], "mA"),
          fc.MAX_POGINGEN)

    # 5. DE LUS. Reparatie gelukt, nieuw nummer, en de nieuwe advertentie is
    #    weer kaal. De teller vanaf het huidige nummer staat dan op nul; alleen
    #    de tweede rem ziet dat er al drie plaatsingen in veertien dagen waren.
    check("hernummerd na elke reparatie: toch gestopt",
          await tel([plaatsing(8, "mA"), plaatsing(4, "mB"), plaatsing(1, "mC")], "mC"),
          fc.MAX_POGINGEN)

    # 6. Dezelfde drie plaatsingen, maar oud: buiten het venster telt het niet
    #    mee, anders zou een artikel dat een half jaar meedraait nooit meer
    #    gerepareerd mogen worden.
    check("drie oude plaatsingen buiten het venster: mag weer",
          await tel([plaatsing(200, "mA"), plaatsing(150, "mB"), plaatsing(100, "mC")], "mC"), 0)

    # 7. Nummer onbekend (opdracht opgeruimd): terugvallen op het venster, niet
    #    stilletjes alles doorlaten.
    check("nummer niet terug te vinden: venster beslist",
          await tel([plaatsing(1), plaatsing(0)], "mX"), 2)

    # 8. DE VERKEERDE METING. Lijkt een groot deel van een account zonder foto,
    #    dan is het veld hernoemd en niet het account leeggehaald. Er mag dan
    #    niets worden herplaatst. Hier getoetst op dezelfde drempels die de
    #    ronde gebruikt, met de gemeten werkelijkheid ernaast.
    def verdacht(zonder, van_ons):
        return zonder > fc.VERDACHT_AANTAL and zonder / max(1, van_ons) > fc.VERDACHT_AANDEEL

    check("gemeten werkelijkheid (2 van 645) telt gewoon mee", verdacht(2, 645), False)
    check("2 van 5 bij een piepklein account telt ook mee", verdacht(2, 5), False)
    check("een heel account ineens kaal: geblokkeerd", verdacht(600, 645), True)
    check("40 van 645 is al te veel om te geloven", verdacht(40, 645), True)

    # 9. DE AFKOELING. Een advertentie die twee dagen geleden is herplaatst mag
    #    normaal niet opnieuw, maar een reparatie moet er wel langs. Precies
    #    Toons konijnenvacht.
    from datetime import datetime as _dt
    from backend.services.relist import _check_cooldown, RefreshError
    import inspect
    from backend.services.relist import refresh_listing
    twee_dagen = {"last_refreshed_at": t(2), "platform": "marktplaats"}
    try:
        _check_cooldown(twee_dagen, "marktplaats"); geblokkeerd = False
    except RefreshError:
        geblokkeerd = True
    check("gewoon verversen blijft geblokkeerd na 2 dagen", geblokkeerd, True)
    check("refresh_listing kent negeer_afkoeling",
          "negeer_afkoeling" in inspect.signature(refresh_listing).parameters, True)
    bron = inspect.getsource(fc.controleer_fotos_op_advertenties)
    check("de fotocontrole gebruikt hem ook", "negeer_afkoeling=True" in bron, True)

    print(f"\n{mislukt} controle(s) mislukt" if mislukt else "\nAlles in orde")
    sys.exit(1 if mislukt else 0)

asyncio.run(main())
