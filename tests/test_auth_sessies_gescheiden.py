"""Het wachtwoord van de een mag nooit op het account van de ander landen.

Aanleiding (28-08-2026). Egbert Brouwer (info@papas-plectrums.nl) vloog er eerst
een paar keer uit vlak na het inloggen en kwam er daarna helemaal niet meer in:
"Invalid email or password". Hij had zijn wachtwoord nooit gewijzigd en nooit een
herstelmail aangevraagd, maar zijn account was om 07:51:07 UTC wél bijgewerkt —
tien seconden na zijn eigen geslaagde inlog.

De oorzaak zit in de Supabase-client: `auth.update_user({"password": ...})` kijkt
niet naar wie het verzoek doet, maar naar de sessie die IN DE CLIENT staat
(`self.get_session()`). Alles liep over één gedeelde client, en elke inlog of
tokenvernieuwing — van welke klant dan ook — overschreef die sessie. Klikte er op
dat moment iemand anders zijn herstellink af, dan kreeg de laatste inlogger dat
wachtwoord. En omdat een wachtwoordwijziging alle sessies intrekt, vloog die er
ook nog uit.

Deze test bootst dat na met een nagemaakte client die zich net zo gedraagt, en
eist dat de auth-endpoints elk hun eigen verse verbinding pakken.
"""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import auth as auth_api  # noqa: E402


class NepAuth:
    """Doet precies wat supabase_auth doet: onthoudt de laatste sessie, en zet
    het wachtwoord op wie er in díé sessie staat."""

    def __init__(self, boek, tussendoor=None):
        self.boek = boek          # gedeeld "Supabase": e-mail -> wachtwoord
        self.sessie = None        # per client, net als echt
        # Wat er GELIJKTIJDIG gebeurt. Inloggen en verversen draaien via
        # asyncio.to_thread in een eigen werkdraad, dus die kunnen wél tussen
        # set_session en update_user door schuiven — anders dan gewone
        # async-code op één lus. Precies dat gaatje was de bug.
        self.tussendoor = tussendoor

    def sign_in_with_password(self, gegevens):
        email = gegevens["email"]
        if self.boek.get(email) != gegevens["password"]:
            raise RuntimeError("Invalid login credentials")
        self.sessie = email
        return type("R", (), {
            "user": type("U", (), {"id": email, "email": email})(),
            "session": type("S", (), {"access_token": "at-" + email,
                                      "refresh_token": "rt-" + email})(),
        })()

    def refresh_session(self, refresh_token):
        email = refresh_token.removeprefix("rt-")
        self.sessie = email
        return type("R", (), {
            "session": type("S", (), {"access_token": "at-" + email,
                                      "refresh_token": "rt-" + email})(),
        })()

    def set_session(self, access_token, refresh_token):
        self.sessie = access_token.removeprefix("at-")
        if self.tussendoor:
            self.tussendoor()

    def update_user(self, velden):
        # DE KERN: schrijft naar de sessie van de client, niet naar de aanvrager.
        if self.sessie is None:
            raise RuntimeError("Auth session missing")
        self.boek[self.sessie] = velden["password"]


class NepClient:
    def __init__(self, boek, tussendoor=None):
        self.auth = NepAuth(boek, tussendoor)


def _maak_boek(monkeypatch, tussendoor=None):
    b = {"egbert@example.com": "egbert-oud", "anders@example.com": "anders-oud"}
    monkeypatch.setattr(auth_api, "verse_auth_client", lambda: NepClient(b, tussendoor))
    monkeypatch.setattr(auth_api, "get_db", lambda: None)
    return b


@pytest.fixture
def boek(monkeypatch):
    return _maak_boek(monkeypatch)


def _reset_door_anders():
    asyncio.run(auth_api.reset_password(
        auth_api.PasswordUpdate(password="anders-nieuw",
                                refresh_token="rt-anders@example.com"),
        authorization="Bearer at-anders@example.com",
    ))


def test_inloggen_van_egbert_kaapt_de_wachtwoordreset_van_een_ander_niet(monkeypatch):
    """Precies het scenario van Egbert: hij logt in op het moment dat een ander
    zijn herstellink afklikt. Op één gedeelde verbinding kreeg híj daardoor het
    wachtwoord van die ander, en kon hij er zelf niet meer in."""
    boek = _maak_boek(monkeypatch, tussendoor=lambda: (
        auth_api.verse_auth_client().auth.sign_in_with_password(
            {"email": "egbert@example.com", "password": "egbert-oud"})
    ))
    _reset_door_anders()
    assert boek["anders@example.com"] == "anders-nieuw"
    assert boek["egbert@example.com"] == "egbert-oud", (
        "het wachtwoord van de aanvrager belandde op het account van iemand anders"
    )


def test_tokenvernieuwing_van_egbert_kaapt_de_reset_niet(monkeypatch):
    """Elke extensie ververst haar bewijs zelf; dat gebeurt tientallen keren per
    minuut en was daarmee de drukste sessie-schrijver van de hele server."""
    boek = _maak_boek(monkeypatch, tussendoor=lambda: (
        auth_api.verse_auth_client().auth.refresh_session("rt-egbert@example.com")
    ))
    _reset_door_anders()
    assert boek["anders@example.com"] == "anders-nieuw"
    assert boek["egbert@example.com"] == "egbert-oud"


def test_auth_endpoints_gebruiken_nooit_de_gedeelde_verbinding():
    """Vangnet voor de volgende keer: wie hier get_auth_db() terugzet, zet het
    lek terug. `auth.get_user(token)` mag dat wél, maar die staat in deps.py."""
    bron = (ROOT / "backend" / "api" / "auth.py").read_text()
    assert "get_auth_db" not in bron


def test_verkeerd_wachtwoord_blijft_gewoon_verkeerd_wachtwoord(boek):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth_api.login(auth_api.AuthRequest(email="egbert@example.com",
                                                        password="fout")))
    assert e.value.status_code == 401


def test_te_veel_pogingen_heet_niet_verkeerd_wachtwoord(monkeypatch):
    """Stond alles onder één noemer, dan las de verkoper "verkeerd wachtwoord"
    terwijl Supabase "te veel pogingen" zei — en probeerde hij het nog eens."""
    from fastapi import HTTPException

    class Geblokkeerd:
        class auth:
            @staticmethod
            def sign_in_with_password(_):
                raise RuntimeError("Request rate limit reached")

    monkeypatch.setattr(auth_api, "verse_auth_client", lambda: Geblokkeerd())
    monkeypatch.setattr(auth_api, "get_db", lambda: None)
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth_api.login(auth_api.AuthRequest(email="x@example.com", password="y")))
    assert e.value.status_code == 429


# ---------------------------------------------------------------------------
# Een weggevallen verbinding is geen verkeerd wachtwoord
#
# Supabase verbreekt af en toe een hergebruikte verbinding — voor gegevens werd
# dat allang opgevangen, voor auth niet. Daar werd élke fout vertaald naar
# "verkeerd wachtwoord" of "je sessie is verlopen", en op dat laatste gooit het
# dashboard je eruit en wist de extensie haar inlogbewijs. Zo raakte iemand met
# een goed wachtwoord zijn toegang kwijt.
# ---------------------------------------------------------------------------
import httpx  # noqa: E402

from backend import database as db_mod  # noqa: E402
from backend.api import deps as deps_api  # noqa: E402


class ValtWeg:
    """Doet het pas bij de zoveelste poging — zoals een verbinding die wegvalt."""

    def __init__(self, mislukt: int, resultaat="goed"):
        self.over = mislukt
        self.resultaat = resultaat
        self.pogingen = 0

    def __call__(self):
        self.pogingen += 1
        if self.over > 0:
            self.over -= 1
            raise httpx.RemoteProtocolError("Server disconnected without sending a response")
        return self.resultaat


def test_een_hik_wordt_gewoon_opnieuw_geprobeerd():
    aanroep = ValtWeg(mislukt=2)
    assert db_mod.auth_met_herkansing(aanroep) == "goed"
    assert aanroep.pogingen == 3


def test_blijft_het_weg_dan_heet_dat_onbereikbaar_en_niet_ongeldig():
    with pytest.raises(db_mod.AuthTijdelijkOnbereikbaar):
        db_mod.auth_met_herkansing(ValtWeg(mislukt=99))


def test_verkeerd_wachtwoord_wordt_niet_eindeloos_herhaald():
    """Een echt antwoord van Supabase (4xx) moet meteen door, niet 3x opnieuw."""
    class Afgewezen(Exception):
        status = 400

    aanroep = ValtWeg(mislukt=0)

    def fout():
        aanroep.pogingen += 1
        raise Afgewezen("Invalid login credentials")

    with pytest.raises(Afgewezen):
        db_mod.auth_met_herkansing(fout)
    assert aanroep.pogingen == 1


def test_onbereikbaar_gooit_de_verkoper_niet_uit_zijn_sessie(monkeypatch):
    """De kern van "ik werd er uitgegooid vlak nadat ik was ingelogd": deze
    controle draait op zo goed als elk verzoek, en 401 = terug naar het
    inlogscherm. Een weggevallen verbinding mag dus nooit 401 worden."""
    from fastapi import HTTPException

    def kapot(*_a, **_k):
        raise db_mod.AuthTijdelijkOnbereikbaar("Server disconnected")

    monkeypatch.setattr(deps_api, "auth_met_herkansing", kapot)
    with pytest.raises(HTTPException) as e:
        asyncio.run(deps_api.get_current_user_full(authorization="Bearer wat-dan-ook"))
    assert e.value.status_code == 503, "een hik in de verbinding logde de verkoper uit"


def test_onbereikbaar_bij_inloggen_heet_niet_verkeerd_wachtwoord(monkeypatch):
    from fastapi import HTTPException

    def kapot(*_a, **_k):
        raise db_mod.AuthTijdelijkOnbereikbaar("Server disconnected")

    monkeypatch.setattr(auth_api, "auth_met_herkansing", kapot)
    monkeypatch.setattr(auth_api, "get_db", lambda: None)
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth_api.login(auth_api.AuthRequest(email="egbert@example.com", password="goed")))
    assert e.value.status_code == 503
    assert "password is fine" in e.value.detail


def test_onbereikbaar_bij_verversen_wist_het_inlogbewijs_niet(monkeypatch):
    """De extensie gooit haar bewijs weg bij 401/403. Bij 503 houdt ze het."""
    from fastapi import HTTPException

    def kapot(*_a, **_k):
        raise db_mod.AuthTijdelijkOnbereikbaar("Server disconnected")

    monkeypatch.setattr(auth_api, "auth_met_herkansing", kapot)
    monkeypatch.setattr(auth_api, "get_db", lambda: None)
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth_api.refresh(auth_api.RefreshRequest(refresh_token="rt-egbert@example.com")))
    assert e.value.status_code == 503


# ---------------------------------------------------------------------------
# "Ik word steeds uitgelogd op de extensie"
#
# Eén account, meerdere partijen die het inlogbewijs verversen: het
# dashboard-tabblad, de extensie op diezelfde pc, soms een tweede computer.
# Supabase roteert bij elke vernieuwing het refresh-token en verklaart het
# vorige meteen dood. Ververst het dashboard (token A -> B), dan zit de extensie
# een tel later met het dode token A; Supabase' hergebruikdetectie trekt daarop
# de HELE sessiefamilie in en alles vliegt er tegelijk uit.
#
# De server geeft nu binnen een kort venster hetzelfde verse paar terug als
# hetzelfde oude token nog een keer wordt aangeboden, zonder Supabase opnieuw te
# bellen. Zo presenteert niemand ooit een geroteerd token.
# ---------------------------------------------------------------------------
class RoterendeAuth:
    """Bootst Supabase' token-rotatie mét hergebruikdetectie na."""

    def __init__(self):
        self.geldig = {"rt-start"}      # levende refresh-tokens
        self.familie_dood = False
        self.teller = 0
        self.supabase_calls = 0

    def refresh_session(self, refresh_token):
        self.supabase_calls += 1
        if self.familie_dood or refresh_token not in self.geldig:
            # Een geroteerd/onbekend token: hele sessiefamilie eruit.
            self.familie_dood = True
            self.geldig.clear()
            raise RuntimeError("Invalid Refresh Token: Already Used")
        self.geldig.discard(refresh_token)
        self.teller += 1
        nieuw = f"rt-{self.teller}"
        self.geldig.add(nieuw)
        return type("R", (), {
            "session": type("S", (), {"access_token": f"at-{self.teller}",
                                      "refresh_token": nieuw})(),
        })()


@pytest.fixture
def schone_refresh_cache():
    auth_api._refresh_cache.clear()
    auth_api._refresh_locks.clear()
    yield
    auth_api._refresh_cache.clear()
    auth_api._refresh_locks.clear()


def test_tweede_verversing_met_hetzelfde_token_trekt_de_sessie_niet_in(monkeypatch, schone_refresh_cache):
    nep = RoterendeAuth()
    monkeypatch.setattr(auth_api, "verse_auth_client", lambda: type("C", (), {"auth": nep})())
    monkeypatch.setattr(auth_api, "get_db", lambda: None)

    # Het dashboard ververst eerst.
    eerste = asyncio.run(auth_api.refresh(auth_api.RefreshRequest(refresh_token="rt-start")))
    # De extensie ververst kort daarna met hetzelfde oude token.
    tweede = asyncio.run(auth_api.refresh(auth_api.RefreshRequest(refresh_token="rt-start")))

    assert eerste["refresh_token"] == tweede["refresh_token"], "beide partijen horen op hetzelfde nieuwe token te landen"
    assert eerste["access_token"] == tweede["access_token"]
    assert nep.supabase_calls == 1, "de tweede vraag mag Supabase niet opnieuw bellen"
    assert not nep.familie_dood, "de sessiefamilie is ingetrokken — precies de klacht"

    # En het nieuwe token werkt daarna gewoon om verder te verversen.
    derde = asyncio.run(auth_api.refresh(auth_api.RefreshRequest(refresh_token=tweede["refresh_token"])))
    assert derde["refresh_token"] != tweede["refresh_token"]


def test_zonder_de_cache_zou_dezelfde_situatie_de_sessie_wel_intrekken(monkeypatch):
    """Tegenmeting: exact hetzelfde scenario, cache uitgeschakeld, laat de oude
    fout zien. Zonder dit bewijst de test hierboven niets."""
    nep = RoterendeAuth()
    monkeypatch.setattr(auth_api, "verse_auth_client", lambda: type("C", (), {"auth": nep})())
    monkeypatch.setattr(auth_api, "get_db", lambda: None)
    monkeypatch.setattr(auth_api, "_refresh_cache_get", lambda _s: None)
    monkeypatch.setattr(auth_api, "_refresh_cache_put", lambda *_a: None)

    from fastapi import HTTPException
    asyncio.run(auth_api.refresh(auth_api.RefreshRequest(refresh_token="rt-start")))
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth_api.refresh(auth_api.RefreshRequest(refresh_token="rt-start")))
    assert e.value.status_code == 401
    assert nep.familie_dood
