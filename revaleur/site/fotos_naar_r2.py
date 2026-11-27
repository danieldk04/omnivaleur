"""Revaleur: productfoto's van de Shopify-CDN naar het eigen R2-bucket (Cloudflare), en de foto-URL's in de database bijwerken.

Gratis limieten (Cloudflare R2): 10 GB opslag, 1 miljoen schrijfacties, 10 miljoen leesacties per maand. De 2130 foto's zijn
ca. 0,4 GB; dit script schrijft elke foto één keer (hervatbaar: wat er al staat wordt overgeslagen).

Vraagt CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN (Pages en R2 bewerken), REVALEUR_FOTO_BASE (openbaar adres van het bucket),
REVALEUR_SUPABASE_URL en REVALEUR_SUPABASE_SERVICE_KEY. Gebruik: python3 -m revaleur.site.fotos_naar_r2 [--max N]
"""
import hashlib
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BUCKET = "revaleur-fotos"
STAAT = os.path.expanduser("~/.revaleur/fotos_klaar.json")


def _api(pad, **kw):
    acc = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    return urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{acc}/r2/buckets/{BUCKET}/{pad}",
                                  headers={"Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"], **kw.pop("headers", {})}, **kw)


def _download(url: str) -> bytes:
    for poging in range(6):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read()
            if data:
                return data
        except Exception:  # noqa: BLE001 — CDN geeft af en toe een 502
            pass
        time.sleep(1.5 * (poging + 1))
    raise RuntimeError("download mislukt: " + url[-70:])


def _sleutel(pid: str, n: int, url: str) -> str:
    return f"fotos/{pid}/{n}-{hashlib.sha1(url.split('?')[0].encode()).hexdigest()[:10]}.jpg"


def _zet_over(taak):
    pid, n, url, base = taak
    sleutel = _sleutel(pid, n, url)
    data = _download(url)
    urllib.request.urlopen(_api(f"objects/{sleutel}", data=data, method="PUT",
                                headers={"Content-Type": "image/jpeg", "Cache-Control": "public, max-age=31536000, immutable"}), timeout=60).read()
    return url, f"{base}/{sleutel}"


def main(maximum: int | None = None) -> None:
    from supabase import create_client
    base = os.environ["REVALEUR_FOTO_BASE"].rstrip("/")
    db = create_client(os.environ["REVALEUR_SUPABASE_URL"], os.environ["REVALEUR_SUPABASE_SERVICE_KEY"])
    klaar = json.load(open(STAAT)) if os.path.exists(STAAT) else {}
    producten = db.table("producten").select("id,fotos").execute().data
    taken = [(p["id"], i, f["src"], base) for p in producten for i, f in enumerate(p["fotos"])
             if f["src"] not in klaar and not f["src"].startswith(base)]
    if maximum:
        taken = taken[:maximum]
    print(len(taken), "foto's over te zetten")
    fout = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, res in enumerate(pool.map(lambda t: _veilig(t), taken), 1):
            if res:
                klaar[res[0]] = res[1]
            else:
                fout += 1
            if i % 100 == 0:
                json.dump(klaar, open(STAAT, "w"))
                print(i, "klaar,", fout, "mislukt", flush=True)
    json.dump(klaar, open(STAAT, "w"))
    bijgewerkt = 0
    for p in producten:                       # alleen producten waarvan ALLE foto's over zijn: nooit een half kapot product
        if all(f["src"] in klaar or f["src"].startswith(base) for f in p["fotos"]):
            nieuw = [{**f, "src": klaar.get(f["src"], f["src"]), "orig": f["src"]} for f in p["fotos"]]
            if nieuw != p["fotos"]:
                db.table("producten").update({"fotos": nieuw}).eq("id", p["id"]).execute()
                bijgewerkt += 1
    print(f"{len(klaar)} foto's in R2, {fout} mislukt, {bijgewerkt} producten bijgewerkt")


def _veilig(t):
    try:
        return _zet_over(t)
    except Exception as e:  # noqa: BLE001
        print("MISLUKT", t[0], t[1], str(e)[:80], flush=True)
        return None


if __name__ == "__main__":
    main(int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else None)
