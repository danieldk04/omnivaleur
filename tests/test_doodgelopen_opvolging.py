"""Reeks C: opvolging voor doodgelopen leads (scripts/doodgelopen_opvolging.py)."""
from datetime import datetime, timedelta

import scripts.doodgelopen_opvolging as d

NU = datetime(2026, 11, 20, 10, 0)
GOED = {"afgesloten": "2026-10-01T10:00:00", "laatste": "2026-10-01T09:00:00",
        "verstuurd": [{"beurt": "mail1"}, {"beurt": "mail2"}, {"beurt": "mail3"}]}
EERSTE = {"onderwerp": "Vraagje over jullie Marktplaats-aanbod", "message_id": "<abc@omnivaleur.nl>",
          "references": "", "datum": "20-09-2026 om 10:15", "tekst": "Hi,\n\nEven kort.\n\nGroetjes,\nDaniel"}


def check(st=None, adres="info@bedrijf.nl", **kw):
    args = dict(antwoorden_adressen=set(), antwoorden_stammen=set(), eigen_na={},
                gestopt=set(), al_verstuurd=set())
    args.update(kw)
    return d.waarom_niet(adres, {**GOED, **(st or {})}, NU, **args)


def test_doodgelopen_lead_mag():
    assert check() is None


def test_wie_zich_afmeldde_of_nee_zei_krijgt_nooit_mail():
    for vlag in ("afgemeld", "afgewezen", "concurrent", "bounce", "auto_antwoord",
                 "beantwoord", "met_de_hand", "soort", "video_op"):
        assert check({vlag: True if vlag != "soort" else "warm"}), vlag


def test_wie_ooit_terugschreef_krijgt_geen_mail_ook_niet_via_een_ander_adres():
    assert check(antwoorden_adressen={"info@bedrijf.nl"})
    assert check(antwoorden_stammen={"bedrijf"}, adres="verkoop@bedrijf.nl")


def test_gratis_mail_telt_niet_als_zelfde_bedrijf():
    assert d.domeinstam("iemand@gmail.com") is None
    assert check(antwoorden_stammen={"gmail"}, adres="iemand@gmail.com") is None


def test_te_vers_of_te_kort_of_door_daniel_zelf_gemaild_of_gestopt():
    vers = (NU - timedelta(days=10)).isoformat()
    assert check({"laatste": vers})
    assert check({"verstuurd": [{"beurt": "mail1"}]})
    assert check(eigen_na={"info@bedrijf.nl": datetime(2026, 10, 5).timestamp()})
    assert check(gestopt={"info@bedrijf.nl"})
    assert check(al_verstuurd={"info@bedrijf.nl"})
    assert check({"afgesloten": None})


def test_variant_is_vast_en_beide_komen_voor():
    adressen = [f"a{i}@bedrijf{i}.nl" for i in range(60)]
    assert d.variant_van(adressen[0]) == d.variant_van(adressen[0].upper())
    assert {d.variant_van(a) for a in adressen} == {"link", "vraag"}


def test_bericht_is_een_antwoord_in_de_draad_met_afmelding():
    msg = d.maak_bericht("info@bedrijf.nl", "vraag", EERSTE, "daniel@omnivaleur.nl")
    assert msg["Subject"] == "Re: Vraagje over jullie Marktplaats-aanbod"
    assert msg["In-Reply-To"] == "<abc@omnivaleur.nl>"
    assert "<abc@omnivaleur.nl>" in msg["References"]
    assert "mailto:daniel@omnivaleur.nl" in msg["List-Unsubscribe"]
    plat = msg.get_body(("plain",)).get_content()
    assert 'Stuur gewoon "stop"' in plat
    assert "> Even kort." in plat                       # de eerste mail staat geciteerd
    assert "Zal ik jullie het filmpje" in plat
    assert "/t/k/" not in plat


def test_linkvariant_heeft_een_getelde_link_en_een_pixel():
    msg = d.maak_bericht("info@bedrijf.nl", "link", EERSTE, "daniel@omnivaleur.nl")
    plat = msg.get_body(("plain",)).get_content()
    html = msg.get_body(("html",)).get_content()
    assert "https://omnivaleur.com/t/k/" in plat and "Zal ik" not in plat
    assert '<a href="' in html and "/t/o/" in html


def test_eigen_tekst_heeft_geen_streepjes_geen_sorry_en_je_jullie_klopt():
    for variant in ("link", "vraag"):
        for onderwerp, woord in (("Vraagje over je Marktplaats-aanbod", " je "),
                                 ("Vraagje over jullie Marktplaats-aanbod", "jullie")):
            e = {**EERSTE, "onderwerp": onderwerp}
            plat = d.maak_bericht("x@y.nl", variant, e, "daniel@omnivaleur.nl") \
                .get_body(("plain",)).get_content()
            eigen = plat.split("Op 20-09-2026")[0]
            assert "—" not in eigen and "–" not in eigen and " - " not in eigen
            assert "sorry" not in eigen.lower() and "*" not in eigen
            assert woord in eigen
            if woord == " je ":
                assert "jullie" not in eigen


def test_noodrem_stopt_bij_te_veel_afmeldingen_of_bounces():
    rec = {"verstuurd": {f"a{i}@x.nl": {} for i in range(25)}}
    gezond = {a: {} for a in rec["verstuurd"]}
    assert d.noodrem(rec, gezond) is None
    slecht = {a: ({"afgemeld": True} if i < 3 else {}) for i, a in enumerate(rec["verstuurd"])}
    assert d.noodrem(rec, slecht)
    bounces = {a: ({"bounce": True} if i < 5 else {}) for i, a in enumerate(rec["verstuurd"])}
    assert d.noodrem(rec, bounces)
    assert d.noodrem({"verstuurd": {"a@x.nl": {}}}, {"a@x.nl": {"afgemeld": True}}) is None  # te weinig om te oordelen


def test_klik_route_kent_het_doel_alleen_uit_een_vaste_lijst():
    from backend.api import tracking
    assert tracking._KLIK_DOELEN["doodgelopen"] == "https://omnivaleur.com/mp"
    assert all(v.startswith("https://omnivaleur.com/") for v in tracking._KLIK_DOELEN.values())
