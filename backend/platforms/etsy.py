"""
Etsy v3 API integration.
Requires ETSY_API_KEYSTRING + ETSY_SHARED_SECRET env vars and an OAuth2 user token.
"""
from __future__ import annotations
import base64
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

    async def create_listing(self, item: dict, credentials: dict) -> dict:
        """Maakt een CONCEPT (draft) in de winkel van de verkoper. Alleen vintage:
        zonder bouwjaar van 20+ jaar geleden weigeren we, Etsy verbiedt het anders."""
        when_made = vintage_when_made(item.get("year"))
        token = self._token(credentials)
        shop_id = await self._get_shop_id(token)

        async with httpx.AsyncClient(timeout=60) as c:
            verzend, gereed = await self._zorg_voor_profielen(c, token, shop_id, item)
            payload = {
                "title": item["title"][:140],
                "description": (item.get("description") or "")[:65000],
                "price": float(item["price"]),
                "quantity": 1,
                "who_made": "someone_else",
                "when_made": when_made,
                "is_supply": "false",
                "taxonomy_id": int(item["etsy_taxonomy_id"]),
                "shipping_profile_id": verzend,
                "readiness_state_id": gereed,
                "type": "physical",
            }
            r = await c.post(
                f"{ETSY_BASE}/application/shops/{shop_id}/listings",
                data=payload,
                headers={"Authorization": f"Bearer {token}", "x-api-key": _api_key()},
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Etsy create listing failed {r.status_code}: {r.text}")
            listing_id = str(r.json()["listing_id"])

            for photo_url in (item.get("photo_urls") or [])[:10]:
                try:
                    await self._upload_image(c, shop_id, listing_id, photo_url, token)
                except Exception as e:
                    logger.warning(f"Etsy image upload failed: {e}")

        return {
            "platform_listing_id": listing_id,
            "platform_listing_url": f"https://www.etsy.com/listing/{listing_id}",
            "state": "draft",
        }

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
        token = self._token(credentials)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.delete(
                f"{ETSY_BASE}/application/listings/{platform_listing_id}",
                headers=self._headers(token),
            )
            return r.status_code in (200, 204)

    async def renew_listing(self, platform_listing_id: str, credentials: dict) -> dict:
        """
        Official Etsy renewal: PATCH the listing's state to 'active'. Etsy charges the
        normal listing fee and gives the listing a fresh "listed" timestamp — this is
        Etsy's own renewal mechanism (same one their web UI "Renew" button uses), not
        a workaround. Works for 'sold_out' and 'expired' listings; a currently-active
        listing doesn't need renewing.
        """
        token = self._token(credentials)
        shop_id = await self._get_shop_id(token)
        async with httpx.AsyncClient() as c:
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
        token = self._token(credentials)
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{ETSY_BASE}/application/listings/{platform_listing_id}",
                headers=self._headers(token),
            )
            if r.status_code == 404:
                return "not_found"
            data = r.json()
            state = data.get("state", "")
            if state == "active":
                return "active"
            if state == "sold_out":
                return "sold"
            return state
