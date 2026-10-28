"""Strijkemblemen en stropdassen krijgen vanzelf een rubriek (gollem.joukes
f0291981, 28-10-2026).

Van zijn 243 artikelen bleven er 149 zonder rubriek, dus kon hij ze niet naar
Marktplaats of 2dehands sturen: 123 strijkemblemen (geen plek in onze indeling)
en 14 stropdassen, terwijl Google die nacht alleen 429 gaf. Marktplaats zet
strijkemblemen zelf in Hobby en Vrije tijd > Kledingapplicaties en Hotfix.
"""
from backend.api.imports import _TAXONOMY, _infer_attributes

HOBBY = "hobby kledingapplicaties en strijkemblemen"


def test_zijn_strijkemblemen_krijgen_de_hobbyrubriek():
    for titel in ("M3.2  Mooie  pailletten palmboom  strijkembleem / patch / iron-on / op",
                  "M1.17  2x cookies / koekjes met hap eruit strijk embleem /  patch",
                  "Strijkletter X",
                  "M2.2  katten / poezen 2x  emblemen /. strijkapplicatie",
                  "Naaiapplicatie van Maria met rode rozen om haar heen.  NR 2",
                  "025 Naai applicatie / patch Jezus Christus"):
        uit = _infer_attributes(titel)
        assert uit.get("category") == HOBBY, titel
        assert uit.get("gender") == "hobby", titel


def test_stropdassen_zijn_accessoires_ook_met_patches():
    for titel in ("Work hard play hard stropdas", "Stopdas \"Need More\"",
                  "Vintage stropdas met patches Nasa"):
        assert _infer_attributes(titel).get("category") == "heren accessoires", titel


def test_geen_valse_treffers():
    # Gemeten op titels van andere klanten: dit zijn geen strijkemblemen.
    for titel in ("Spijkerjas met strijkemblemen maat M",
                  "Blondie Punk Logo Patch Sleutelhanger officiële merchandise",
                  "Korn - Black Logo - Opstrijk Patch - officiële merchandise",
                  "Militair embleem Limburgse Jagers",
                  "Geweven kleed heldere blauwe kleuren vogel applicatie 219/172 cm",
                  "Philips strijkijzer stoomstrijkijzer",
                  "Granny patchwork kleed grandfoulard sprei 270/175 cm"):
        assert _infer_attributes(titel).get("category") != HOBBY, titel


def test_de_rubriek_staat_in_de_indeling():
    assert HOBBY in _TAXONOMY["hobby"]


def test_marktplaats_en_2dehands_krijgen_de_nummers_mee_ook_op_een_oude_kopie():
    from backend.api import jobs
    opdrachten = [{"platform": p, "action": "create", "payload": {"category": HOBBY}}
                  for p in ("marktplaats", "2dehands")]
    for j in opdrachten:
        assert jobs._minimale_versie_voor_rubriek(j) is None
    assert jobs._mp_nummers_van_de_server(opdrachten) == 2
    for j in opdrachten:
        assert (j["payload"]["mp_category"]["l1"], j["payload"]["mp_category"]["l2"]) == (1099, 2855)


def test_vinted_wacht_op_de_kopie_die_de_tak_kent():
    from backend.api import jobs
    j = {"platform": "vinted", "action": "create", "payload": {"category": HOBBY}}
    assert jobs._minimale_versie_voor_rubriek(j) == (1, 0, 406)
    assert jobs._mp_nummers_van_de_server([j]) == 0


def test_eigen_rubriek_van_marktplaats_gaat_voor():
    from backend.api import jobs
    eigen = {"l1": 895, "l2": 926}
    j = {"platform": "marktplaats", "action": "create",
         "payload": {"category": HOBBY, "mp_category": eigen}}
    assert jobs._mp_nummers_van_de_server([j]) == 0
    assert j["payload"]["mp_category"] is eigen
