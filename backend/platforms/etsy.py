"""
Etsy v3 API integration.
Requires ETSY_API_KEYSTRING + ETSY_SHARED_SECRET env vars and an OAuth2 user token.
"""
from __future__ import annotations
import base64
import re
import hashlib
import hmac
import logging
import os
import time
from datetime import datetime, timedelta, timezone
import httpx
from backend.platforms.base import PlatformBase

logger = logging.getLogger(__name__)

ETSY_BASE = "https://openapi.etsy.com/v3"
ETSY_SCOPES = "listings_r listings_w listings_d transactions_r shops_r shops_w"
STATE_GELDIG_SECONDEN = 15 * 60


def _keystring() -> str:
    # Eerst de nieuwe naam, daarna de oude variabele uit de eerste opzet.
    from backend.config import settings
    return settings.etsy_api_keystring or os.getenv("ETSY_CLIENT_ID", "")


def _api_key() -> str:
    """Etsy verwacht in x-api-key 'keystring:shared_secret' (OpenAPI-spec 2026)."""
    ks, sec = _keystring(), _secret()
    return f"{ks}:{sec}" if ks and sec else ks


def _secret() -> str:
    from backend.config import settings
    return settings.etsy_shared_secret


def _redirect_uri() -> str:
    from backend.config import settings
    return os.getenv("ETSY_REDIRECT_URI") or settings.etsy_redirect_uri


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def maak_state(user_id: str, nu: int | None = None) -> str:
    """Ondertekende state: user_id.tijd.handtekening. Geen opslag nodig tussen
    het starten en de terugkeer van Etsy."""
    sleutel = _secret()
    if not sleutel:
        raise RuntimeError("Etsy is not configured on this server (ETSY_SHARED_SECRET missing)")
    t = str(int(nu if nu is not None else time.time()))
    basis = f"{user_id}.{t}"
    sig = _b64(hmac.new(sleutel.encode(), basis.encode(), hashlib.sha256).digest())
    return f"{basis}.{sig}"


def lees_state(state: str, nu: int | None = None) -> str:
    """Geeft de user_id terug of gooit ValueError bij een vervalste of oude state."""
    sleutel = _secret()
    if not sleutel:
        raise ValueError("Etsy is not configured")
    try:
        user_id, t, sig = state.rsplit(".", 2)
        verwacht = _b64(hmac.new(sleutel.encode(), f"{user_id}.{t}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, verwacht):
            raise ValueError("bad signature")
        leeftijd = (nu if nu is not None else time.time()) - int(t)
    except (ValueError, TypeError) as e:
        raise ValueError("invalid state") from e
    if leeftijd < 0 or leeftijd > STATE_GELDIG_SECONDEN:
        raise ValueError("state expired")
    return user_id


def _verifier(state: str) -> str:
    # 43 tekens, afgeleid van de state: zo hoeft er niets bewaard te worden.
    return _b64(hmac.new(_secret().encode(), ("v:" + state).encode(), hashlib.sha256).digest())


def _met_verloop(data: dict) -> dict:
    verloopt = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3600)) - 60)
    return {**data, "token_expires_at": verloopt.isoformat()}


def vintage_when_made(year) -> str:
    """Etsy: vintage = 20+ jaar oud. Jonger dan dat gaat niet naar Etsy."""
    try:
        jaar = int(year)
    except (TypeError, ValueError):
        raise ValueError("Etsy needs the item's year to prove it is vintage (20+ years old)")
    if jaar > datetime.now(timezone.utc).year - 20:
        raise ValueError("Etsy only allows vintage items (20+ years old)")
    if jaar >= 2000:
        return "2000_2006"
    if jaar >= 1900:
        return f"{jaar // 10 * 10}s"
    return "1800s" if jaar >= 1800 else "before_1700" if jaar < 1700 else "1700s"


_JAAR = re.compile(r"(?<!\d)(19\d{2}|200[0-6])(?!\d)")
_DECENNIUM = re.compile(r"(?<!\d)(?:19)?([2-9]0)['’]?s\b|jaren\s*(?:19)?([2-9]0)\b", re.I)


def jaar_uit_item(item: dict):
    """Het bouwjaar waarmee de verkoper laat zien dat het artikel vintage is.

    Eerst een uitdrukkelijk veld (year), daarna een jaartal of decennium in titel of
    omschrijving ("vintage 1992", "80s", "jaren 70"). Niets gevonden: None, en dan
    plaatsen we niet op Etsy: een geraden jaar maakt van tweedehands geen vintage."""
    if item.get("year"):
        return item["year"]
    tekst = f"{item.get('title') or ''} {item.get('description') or ''}"
    m = _JAAR.search(tekst)
    if m:
        return int(m.group(1))
    m = _DECENNIUM.search(tekst)
    if m:
        d = int(m.group(1) or m.group(2))
        return 1900 + d + 5
    return None


_taxonomie_cache: dict = {"tot": 0.0, "bladeren": []}


def _bladeren(knopen: list, pad: tuple = ()) -> list:
    uit = []
    for k in knopen:
        naam = (k.get("name") or "")
        nieuw = pad + (naam,)
        kinderen = k.get("children") or []
        if kinderen:
            uit += _bladeren(kinderen, nieuw)
        else:
            uit.append((k["id"], nieuw))
    return uit


def _woorden(tekst: str) -> set:
    uit = set()
    for w in re.findall(r"[a-zà-ÿ]+", (tekst or "").lower()):
        if len(w) > 2:
            uit.add(w[:-1] if w.endswith("s") and len(w) > 3 else w)
    return uit


# Nederlandse en Engelse woorden naar de woorden die Etsy zelf gebruikt.
_SYNONIEM = {"vest": "cardigan", "trui": "sweater", "jas": "jacket", "jack": "jacket",
             "broek": "pant", "rok": "skirt", "jurk": "dress", "overhemd": "shirt",
             "heren": "men", "dames": "women", "dame": "women", "man": "men", "vrouw": "women",
             "hoodie": "sweatshirt", "gilet": "vest", "tas": "bag", "schoen": "shoe"}


def kies_taxonomie(bladeren: list, item: dict):
    """Kiest het Etsy-blad dat het best bij categorie, titel en doelgroep past, of None."""
    vraag = _woorden(f"{item.get('category') or ''} {item.get('title') or ''} {item.get('gender') or ''}")
    vraag |= {_SYNONIEM[w] for w in list(vraag) if w in _SYNONIEM}
    if not vraag:
        return None
    beste, beste_score = None, 0.0
    for tid, pad in bladeren:
        naam_w = _woorden(pad[-1])
        pad_w = _woorden(" ".join(pad[:-1]))
        if not naam_w:
            continue
        hit_naam = len(vraag & naam_w)
        if hit_naam == 0:
            continue
        score = hit_naam / len(naam_w) * 2 + len(vraag & pad_w) * 0.5
        if score > beste_score:
            beste, beste_score = tid, score
    return beste


class EtsyPlatform(PlatformBase):
    platform_name = "etsy"

    def _token(self, credentials: dict) -> str:
        return credentials.get("access_token") or (credentials.get("extra_data") or {}).get("access_token", "")

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "x-api-key": _api_key(),
            "Content-Type": "application/json",
        }

    def get_authorization_url(self, user_id: str) -> str:
        """OAuth 2.0 met PKCE S256. Etsy weigert de methode 'plain'."""
        from urllib.parse import urlencode
        if not _keystring():
            raise RuntimeError("Etsy is not configured on this server (ETSY_API_KEYSTRING missing)")
        state = maak_state(user_id)
        challenge = _b64(hashlib.sha256(_verifier(state).encode()).digest())
        params = {
            "response_type": "code",
            "client_id": _keystring(),
            "redirect_uri": _redirect_uri(),
            "scope": ETSY_SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"https://www.etsy.com/oauth/connect?{urlencode(params)}"

    async def exchange_code(self, code: str, state: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.etsy.com/v3/public/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": _keystring(),
                    "redirect_uri": _redirect_uri(),
                    "code": code,
                    "code_verifier": _verifier(state),
                },
            )
            r.raise_for_status()
            return _met_verloop(r.json())

    async def refresh_credentials(self, credentials: dict) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.etsy.com/v3/public/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": _keystring(),
                    "refresh_token": credentials.get("refresh_token"),
                },
            )
            r.raise_for_status()
            data = _met_verloop(r.json())
            return {**credentials, "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token") or credentials.get("refresh_token"),
                    "token_expires_at": data["token_expires_at"]}

    async def _vers(self, credentials: dict) -> dict:
        """Geeft inloggegevens met een geldig access token (1 uur) en bewaart het
        verse token in de database. Zonder koppeling: duidelijke fout."""
        if not self._token(credentials):
            raise RuntimeError("Etsy isn't connected")
        if not self.verlopen(credentials):
            return credentials
        nieuw = await self.refresh_credentials(credentials)
        uid = credentials.get("user_id")
        if uid:
            try:
                from backend.database import get_db
                get_db().table("platform_credentials").update({
                    "access_token": nieuw.get("access_token"),
                    "refresh_token": nieuw.get("refresh_token"),
                    "token_expires_at": nieuw.get("token_expires_at"),
                }).eq("user_id", uid).eq("platform", "etsy").execute()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Kon ververste Etsy-token niet opslaan: {e}")
        return nieuw

    async def taxonomie_voor(self, item: dict):
        if item.get("etsy_taxonomy_id"):
            return int(item["etsy_taxonomy_id"])
        if time.time() > _taxonomie_cache["tot"]:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.get(f"{ETSY_BASE}/application/seller-taxonomy/nodes",
                                headers={"x-api-key": _api_key()})
                r.raise_for_status()
                _taxonomie_cache["bladeren"] = _bladeren(r.json().get("results") or [])
                # Etsy: andere inhoud maximaal 24 uur bewaren (API-voorwaarden §5).
                _taxonomie_cache["tot"] = time.time() + 20 * 3600
        return kies_taxonomie(_taxonomie_cache["bladeren"], item)

    def verlopen(self, credentials: dict) -> bool:
        t = credentials.get("token_expires_at")
        if not t:
            return True
        try:
            return datetime.fromisoformat(str(t)) <= datetime.now(timezone.utc)
        except ValueError:
            return True

    async def _get_shop_id(self, token: str) -> str:
        async with httpx.AsyncClient(timeout=30) as c:
            # user_id staat vooraan in het access token: "<user_id>.<token>"
            user_id = token.split(".")[0]
            r = await c.get(f"{ETSY_BASE}/application/users/{user_id}/shops", headers=self._headers(token))
            r.raise_for_status()
            data = r.json()
            shops = data.get("results") or ([data] if data.get("shop_id") else [])
            if not shops:
                raise RuntimeError("No Etsy shop found for this account")
            return str(shops[0]["shop_id"])

    async def _zorg_voor_profielen(self, c, token: str, shop_id: str, item: dict) -> tuple[int, int]:
        """Geeft (shipping_profile_id, readiness_state_id). Bestaat er geen, dan
        maken we een eenvoudig profiel aan; de verkoper kan het later aanpassen."""
        h = {"Authorization": f"Bearer {token}", "x-api-key": _api_key()}
        r = await c.get(f"{ETSY_BASE}/application/shops/{shop_id}/shipping-profiles", headers=h)
        r.raise_for_status()
        profielen = r.json().get("results") or []
        if profielen:
            verzend = profielen[0]["shipping_profile_id"]
        else:
            if not item.get("origin_postal_code"):
                raise RuntimeError("Your Etsy shop has no shipping profile yet. Create one on Etsy "
                                   "(Shop Manager, Settings, Shipping settings) and try again.")
            r = await c.post(f"{ETSY_BASE}/application/shops/{shop_id}/shipping-profiles", headers=h, data={
                "title": "Omnivaleur standard shipping",
                "origin_country_iso": item.get("origin_country_iso", "NL"),
                "origin_postal_code": item.get("origin_postal_code", ""),
                "primary_cost": float(item.get("shipping_price", 5.0)),
                "secondary_cost": 0.0,
                "destination_region": "eu",
                "min_delivery_days": 2,
                "max_delivery_days": 7,
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Etsy shipping profile failed {r.status_code}: {r.text}")
            verzend = r.json()["shipping_profile_id"]
        r = await c.get(f"{ETSY_BASE}/application/shops/{shop_id}/readiness-state-definitions", headers=h)
        r.raise_for_status()
        klaar = r.json().get("results") or []
        if klaar:
            gereed = klaar[0]["readiness_state_id"]
        else:
            r = await c.post(f"{ETSY_BASE}/application/shops/{shop_id}/readiness-state-definitions", headers=h, data={
                "readiness_state": "ready_to_ship",
                "min_processing_time": 1,
                "max_processing_time": 3,
                "processing_time_unit": "days",
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Etsy readiness state failed {r.status_code}: {r.text}")
            gereed = r.json()["readiness_state_id"]
        return int(verzend), int(gereed)

    async def _retourbeleid(self, c, token: str, shop_id: str) -> int:
        h = {"Authorization": f"Bearer {token}", "x-api-key": _api_key()}
        r = await c.get(f"{ETSY_BASE}/application/shops/{shop_id}/policies/return", headers=h)
        r.raise_for_status()
        bestaand = r.json().get("results") or []
        if bestaand:
            return int(bestaand[0]["return_policy_id"])
        # Vintage: geen retour en geen ruil. De verkoper kan dit op Etsy aanpassen.
        r = await c.post(f"{ETSY_BASE}/application/shops/{shop_id}/policies/return", headers=h,
                         data={"accepts_returns": "false", "accepts_exchanges": "false"})
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Etsy return policy failed {r.status_code}: {r.text}")
        return int(r.json()["return_policy_id"])

    async def create_listing(self, item: dict, credentials: dict) -> dict:
        """Vintage-listing in de winkel van de verkoper. Concept eerst; daarna foto's
        en pas dan actief (dat kost de verkoper de gewone Etsy-plaatsingskosten).
        `_etsy_concept` in het artikel houdt het bij een concept (voor tests)."""
        credentials = await self._vers(credentials)
        when_made = vintage_when_made(jaar_uit_item(item))
        if not (item.get("photo_urls") or item.get("_etsy_concept")):
            raise RuntimeError("Etsy needs at least one photo")
        token = self._token(credentials)
        shop_id = await self._get_shop_id(token)
        taxonomy_id = await self.taxonomie_voor(item)
        if not taxonomy_id:
            raise RuntimeError("Could not match this item to an Etsy category. "
                               "Fill in the category (for example jacket or dress) and try again.")
        item = {**item, **{k: v for k, v in (credentials.get("extra_data") or {}).get("etsy", {}).items()
                           if k not in item}}

        async with httpx.AsyncClient(timeout=60) as c:
            verzend, gereed = await self._zorg_voor_profielen(c, token, shop_id, item)
            tags = [t for t in {(item.get("brand") or "").strip().lower(), "vintage",
                                (item.get("category") or "").strip().lower()} if t and len(t) <= 20][:13]
            payload = {
                "title": item["title"][:140],
                "description": (item.get("description") or "")[:65000],
                "price": float(item["price"]),
                "quantity": 1,
                "who_made": "someone_else",
                "when_made": when_made,
                "is_supply": "false",
                "taxonomy_id": int(taxonomy_id),
                "shipping_profile_id": verzend,
                "readiness_state_id": gereed,
                "type": "physical",
            }
            if tags:
                payload["tags"] = ",".join(tags)
            headers = {"Authorization": f"Bearer {token}", "x-api-key": _api_key()}
            r = await c.post(f"{ETSY_BASE}/application/shops/{shop_id}/listings", data=payload, headers=headers)
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Etsy create listing failed {r.status_code}: {r.text}")
            listing_id = str(r.json()["listing_id"])
            uitkomst = {
                "platform_listing_id": listing_id,
                "platform_listing_url": f"https://www.etsy.com/listing/{listing_id}",
            }
            try:
                fouten = 0
                for foto in (item.get("photo_urls") or [])[:10]:
                    try:
                        await self._upload_image(c, shop_id, listing_id, foto, token)
                    except Exception as e:  # noqa: BLE001
                        fouten += 1
                        logger.warning(f"Etsy image upload failed: {e}")
                if item.get("_etsy_concept"):
                    return {**uitkomst, "state": "draft"}
                if fouten == len(item.get("photo_urls") or []):
                    raise RuntimeError("Etsy accepted none of the photos")
                beleid = await self._retourbeleid(c, token, shop_id)
                r = await c.patch(f"{ETSY_BASE}/application/shops/{shop_id}/listings/{listing_id}",
                                  data={"state": "active", "return_policy_id": beleid}, headers=headers)
                if r.status_code not in (200, 201):
                    raise RuntimeError(f"Etsy activate failed {r.status_code}: {r.text}")
            except Exception:
                # Geen half werk achterlaten: een concept dat we niet kunnen afmaken weg.
                try:
                    await c.delete(f"{ETSY_BASE}/application/listings/{listing_id}", headers=headers)
                except Exception:  # noqa: BLE001
                    pass
                raise
        return {**uitkomst, "state": "active"}

    async def _upload_image(self, client, shop_id, listing_id, photo_url, token):
        img_resp = await client.get(photo_url)
        img_resp.raise_for_status()
        r = await client.post(
            f"{ETSY_BASE}/application/shops/{shop_id}/listings/{listing_id}/images",
            headers={"Authorization": f"Bearer {token}", "x-api-key": _api_key()},
            files={"image": ("photo.jpg", img_resp.content, "image/jpeg")},
        )
        r.raise_for_status()

    async def delete_listing(self, platform_listing_id: str, credentials: dict) -> bool:
        credentials = await self._vers(credentials)
        token = self._token(credentials)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.delete(
                f"{ETSY_BASE}/application/listings/{platform_listing_id}",
                headers=self._headers(token),
            )
            # 404: bestaat niet meer, dus weg. Net als bij de andere API-kanalen.
            return r.status_code in (200, 204, 404)

    async def renew_listing(self, platform_listing_id: str, credentials: dict) -> dict:
        """
        Official Etsy renewal: PATCH the listing's state to 'active'. Etsy charges the
        normal listing fee and gives the listing a fresh "listed" timestamp — this is
        Etsy's own renewal mechanism (same one their web UI "Renew" button uses), not
        a workaround. Works for 'sold_out' and 'expired' listings; a currently-active
        listing doesn't need renewing.
        """
        credentials = await self._vers(credentials)
        token = self._token(credentials)
        shop_id = await self._get_shop_id(token)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.patch(
                f"{ETSY_BASE}/application/shops/{shop_id}/listings/{platform_listing_id}",
                json={"state": "active", "quantity": 1},
                headers=self._headers(token),
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Etsy renew failed {r.status_code}: {r.text}")
            data = r.json()
            return {
                "platform_listing_id": str(data.get("listing_id", platform_listing_id)),
                "state": data.get("state"),
            }

    async def get_listing_status(self, platform_listing_id: str, credentials: dict) -> str:
        credentials = await self._vers(credentials)
        token = self._token(credentials)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                f"{ETSY_BASE}/application/listings/{platform_listing_id}",
                headers=self._headers(token),
            )
            if r.status_code == 404:
                return "not_found"
            if r.status_code != 200:
                raise RuntimeError(f"Etsy status check failed {r.status_code}")
            data = r.json()
            state = data.get("state", "")
            if state == "active":
                return "active"
            if state == "sold_out":
                return "sold"
            return state
