#!/usr/bin/env python3
"""Draait in .github/workflows/bronfotos.yml: foto's van webshops die onze server
tegenhouden ophalen en bij de server afleveren.

Waarom (De Juiste Toon, 15-10-2026): SiteGround geeft onze server en Daniels Mac
een captcha, een GitHub-machine kreeg dezelfde foto gewoon. Rustig aan: één foto
per keer met een pauze, en bij de eerste captcha stopt de ronde helemaal. De
volgende geplande ronde gaat verder; nooit harder aandringen.

Deze repo is openbaar en daarmee ook dit logboek: druk geen adressen, artikelen
of klanten af, alleen aantallen.

Alleen standaardbibliotheek, zodat de taak niets hoeft te installeren.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

SERVER = os.environ.get("OMNIVALEUR_URL", "https://omnivaleur.com")
PUBLIEK = "omnivaleur-bronfotos"
BUDGET_S = 15 * 60
PAUZE_S = 1.5
MAX_ARTIKELEN = 40
ACCEPT = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/141.0 Safari/537.36")


class Dicht(Exception):
    """De bron zet een captcha of blokkade op: stoppen."""


def _bewijs() -> str:
    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=" + PUBLIEK
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["value"]


def _server(pad: str, body=None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(SERVER + pad, data=data, method="GET" if data is None else "POST",
                                 headers={"Authorization": "Bearer " + _bewijs(),
                                          "Content-Type": "application/json",
                                          # Cloudflare weigert de standaardnaam "Python-urllib" met
                                          # foutcode 1010 nog voor onze server het verzoek ziet
                                          # (gemeten 15-10-2026, eerste ronde gaf daardoor 403).
                                          "User-Agent": "omnivaleur-bronfotos/1.0 (+https://omnivaleur.com)"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def _foto(url: str):
    """(bytes, type) of None als deze ene foto niet bestaat. Gooit Dicht bij een captcha."""
    for kop in ({"Accept": ACCEPT}, {"Accept": ACCEPT, "User-Agent": CHROME}):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=kop), timeout=30) as r:
                if r.status != 200 or r.headers.get("sg-captcha"):
                    raise Dicht()
                soort = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
                data = r.read()
                if not soort.startswith("image/"):
                    raise Dicht()
                return data, soort
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                continue            # sommige hosts weigeren een van de twee koppen
            if e.code == 429 or e.code >= 500:
                raise Dicht() from e
            return None             # 404 en dergelijke: deze foto bestaat niet meer
        except (urllib.error.URLError, TimeoutError) as e:
            raise Dicht() from e
    raise Dicht()


def _kenmerken_van_het_bewijs() -> dict:
    """Wat GitHub over deze taak zegt (niet geheim), om een weigering te verklaren."""
    deel = _bewijs().split(".")[1]
    inhoud = json.loads(base64.urlsafe_b64decode(deel + "=" * (-len(deel) % 4)))
    return {k: inhoud.get(k) for k in ("repository", "ref", "workflow_ref", "event_name")}


def main() -> int:
    begin = time.time()
    try:
        artikelen = _server(f"/api/intern/bronfotos?max_artikelen={MAX_ARTIKELEN}")["artikelen"]
    except urllib.error.HTTPError as e:
        print(f"server weigerde ({e.code}); deze taak zegt over zichzelf: {_kenmerken_van_het_bewijs()}")
        return 1
    print(f"wachtrij: {len(artikelen)} artikelen")
    klaar = fotos_tel = 0
    reden = "alles bekeken"
    try:
        for a in artikelen:
            if time.time() - begin > BUDGET_S:
                reden = "tijd op"
                break
            fotos = []
            for url in a["urls"]:
                f = _foto(url)
                time.sleep(PAUZE_S)
                if f:
                    fotos.append({"url": url, "type": f[1], "b64": base64.b64encode(f[0]).decode()})
            if fotos:
                uit = _server(f"/api/intern/bronfotos/{a['item_id']}", {"user_id": a["user_id"], "fotos": fotos})
                fotos_tel += uit.get("vervangen", 0)
                klaar += 1 if not uit.get("over") else 0
    except Dicht:
        reden = "bron zette een captcha of blokkade op, gestopt"
    print(f"artikelen klaar: {klaar}, foto's in onze opslag: {fotos_tel}, {reden}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
