#!/usr/bin/env python3
"""
Genereer een GA4 refresh token voor het wekelijkse marketingrapport.

Hergebruikt de bestaande Google OAuth-client van Search Console (gsc_client_id /
gsc_client_secret uit .env) — je hoeft dus GEEN nieuwe client aan te maken. Vraagt
eenmalig toestemming voor de scope `analytics.readonly` en print het refresh token
dat je als `ga4_refresh_token` in Railway/.env zet.

Vereisten:
  1. In Google Cloud Console (zelfde project als GSC): APIs & Services → Enable APIs
     → "Google Analytics Data API" → Enable.
  2. Bij de OAuth-client moet als "Authorized redirect URI" http://localhost:8765/
     staan (voeg toe als die er nog niet is: APIs & Services → Credentials →
     jouw OAuth 2.0 Client ID → Authorized redirect URIs).
  3. Draaien op je eigen machine (opent een browser):  python scripts/ga4_get_refresh_token.py

Het account waarmee je inlogt moet minstens Viewer-toegang hebben op de GA4-property.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings  # noqa: E402

REDIRECT_PORT = 8765
# Eén token dekt zowel het GA4-rapport als Search Console (blogperformance), zodat je
# hetzelfde token voor GSC_REFRESH_TOKEN én GA4_REFRESH_TOKEN kunt gebruiken.
SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]


def _get_credentials() -> tuple[str, str]:
    """Client id/secret ophalen zonder ze in .env te hoeven zetten: eerst uit
    settings (.env), dan uit losse env-vars, anders interactief vragen. Zo kun je
    de waarden gewoon uit Railway kopiëren en plakken."""
    import os

    cid = settings.gsc_client_id or settings.google_ads_client_id or os.environ.get("GSC_CLIENT_ID", "")
    csec = settings.gsc_client_secret or settings.google_ads_client_secret or os.environ.get("GSC_CLIENT_SECRET", "")
    if not cid:
        cid = input("Plak je Google OAuth Client ID (uit Railway = GOOGLE_ADS_CLIENT_ID): ").strip()
    if not csec:
        from getpass import getpass
        csec = getpass("Plak je Google OAuth Client Secret (= GOOGLE_ADS_CLIENT_SECRET): ").strip()
    return cid, csec


def main() -> int:
    client_id, client_secret = _get_credentials()
    if not (client_id and client_secret):
        print("❌ Geen client id/secret opgegeven.")
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("❌ google-auth-oauthlib ontbreekt. Installeer:  pip install google-auth-oauthlib")
        return 1

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [f"http://localhost:{REDIRECT_PORT}/"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    # access_type=offline + prompt=consent forceert dat Google een refresh token teruggeeft.
    creds = flow.run_local_server(
        port=REDIRECT_PORT,
        access_type="offline",
        prompt="consent",
        authorization_prompt_message="Open deze URL en geef toestemming:\n{url}",
    )

    if not creds.refresh_token:
        print("❌ Geen refresh token ontvangen. Trek de app-toegang in via "
              "https://myaccount.google.com/permissions en probeer opnieuw "
              "(Google geeft alleen bij de eerste consent een refresh token).")
        return 1

    print("\n✅ Gelukt! Zet deze twee waarden in Railway (of .env):\n")
    print(f"ga4_property_id=544205472")
    print(f"ga4_refresh_token={creds.refresh_token}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
