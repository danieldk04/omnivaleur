#!/usr/bin/env python3
"""
Verhuis de advertentiefoto's van Supabase Storage naar Cloudflare R2.

Onderweg wordt elke foto meteen verkleind (max 1600 px), dus dit lost twee
dingen tegelijk op: de bucket die op 346% van het gratis plan stond, en het
dataverkeer dat elke keer dat iemand een foto bekijkt meetelde. Bij R2 telt
verkeer niet mee en past het geheel ruim binnen de gratis 10 GB.

VEILIGHEID — een foto kan hier niet verdwijnen:

  * Vooraf wordt de hele keten getest: een proefbestand wordt geüpload, via
    img.omnivaleur.com weer opgehaald én weer verwijderd. Lukt daar iets niet,
    dan stopt het script voordat er ook maar één echte foto is aangeraakt.
  * Per foto: uploaden naar R2, dan controleren dat het nieuwe adres publiek
    op te halen is, en pas dan het item laten wijzen naar het nieuwe adres.
    Struikelt er iets, dan blijft de oude url gewoon staan.
  * De oude foto in Supabase blijft staan. Die wordt daarmee alleen nog maar
    ongebruikt, en pas als jij later cleanup_orphan_photos.py draait ook echt
    weggegooid. Tot dat moment kun je altijd nog terug.
  * Droogloop tenzij --apply, en een verkeersbudget (--budget-mb) omdat het
    terúglezen uit Supabase nog wél egress kost.

Gebruik:
    python3 scripts/migrate_photos_to_r2.py                 # alleen rapporteren
    python3 scripts/migrate_photos_to_r2.py --apply         # 400 MB per keer
    python3 scripts/migrate_photos_to_r2.py --apply --budget-mb 1000
"""
import argparse
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PAGE = 1000
TIMEOUT = 60.0


def _paged(query_factory):
    rows, start = [], 0
    while True:
        chunk = query_factory().range(start, start + PAGE - 1).execute().data or []
        rows.extend(chunk)
        if len(chunk) < PAGE:
            return rows
        start += PAGE


def preflight(client) -> bool:
    """Bewijs dat de hele keten werkt voordat er echte foto's in gaan."""
    from backend.services import r2_storage

    if not r2_storage.is_configured():
        print("R2 is niet ingesteld. Zet r2_account_id, r2_access_key_id,\n"
              "r2_secret_access_key, r2_bucket en r2_public_base_url in .env.")
        return False

    proef = f"_preflight/{int(time.time())}.txt"
    print(f"Ketentest via {r2_storage.public_base()} …")
    try:
        url = r2_storage.upload(b"omnivaleur preflight", proef)
    except Exception as e:  # noqa: BLE001
        print(f"  ! uploaden naar R2 lukt niet: {e}")
        print("    Controleer de sleutel en of de bucket bestaat.")
        return False

    try:
        r2_storage.ensure_cors()
        print("  CORS-regel gezet (de extensie mag de foto's ophalen)")
    except Exception as e:  # noqa: BLE001
        print(f"  ! CORS zetten lukt niet: {e}")
        print("    Zonder die regel publiceren items zónder foto's. Gestopt.")
        r2_storage.delete([proef])
        return False

    ok = False
    for poging in range(6):
        try:
            r = client.get(url)
            if r.status_code == 200:
                ok = True
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5)

    r2_storage.delete([proef])
    if not ok:
        print(f"  ! {url} is niet publiek op te halen.")
        print("    Koppel het eigen domein aan de bucket (R2 > Settings > Custom domain)")
        print("    en wacht tot Cloudflare het certificaat klaar heeft. Gestopt.")
        return False
    print("  uploaden, publiek ophalen en verwijderen werken alle drie\n")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="daadwerkelijk verhuizen")
    ap.add_argument("--budget-mb", type=int, default=400,
                    help="stop na zoveel MB downloaden uit Supabase (standaard 400)")
    ap.add_argument("--user", default=None)
    args = ap.parse_args()

    import httpx
    from backend.database import get_db
    from backend.services import r2_storage
    from backend.services.image_optimize import optimize_image
    from backend.services.image_upload import storage_path_from_url

    db = get_db()
    budget = args.budget_mb * 1024 * 1024

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        if not preflight(client):
            return 1

        def rijen(tabel, kolom):
            q = (lambda: db.table(tabel).select(f"id,user_id,{kolom}")) if not args.user else \
                (lambda: db.table(tabel).select(f"id,user_id,{kolom}").eq("user_id", args.user))
            return [r for r in _paged(q) if r.get(kolom)]

        # (tabel, kolom, rij, is_enkel) — import_candidates.photo_url is één url
        # in plaats van een lijst, en moet ook weer als één url terug.
        werk = [("items", "photo_urls", r, False) for r in rijen("items", "photo_urls")]
        werk += [("import_candidates", "photo_urls", r, False)
                 for r in rijen("import_candidates", "photo_urls")]
        werk += [("import_candidates", "photo_url", r, True)
                 for r in rijen("import_candidates", "photo_url")]

        te_doen = sum(
            1 for _, kolom, r, enkel in werk
            for u in ([r[kolom]] if enkel else (r[kolom] or []))
            if storage_path_from_url(u)
        )
        print(f"{te_doen} foto's staan nog op Supabase, verdeeld over {len(werk)} rijen")
        print(f"Budget deze ronde: {args.budget_mb} MB"
              + ("" if args.apply else "   — DROOGLOOP, er wordt niets geschreven") + "\n")

        gelezen = bespaard = 0
        verhuisd = rijen_bij = mislukt = 0

        for tabel, kolom, rij, enkel in werk:
            if gelezen >= budget:
                print(f"\nBudget van {args.budget_mb} MB op — hier gestopt. "
                      f"Draai het morgen opnieuw om verder te gaan.")
                break

            oud = [rij[kolom]] if enkel else list(rij[kolom])
            nieuw = list(oud)
            veranderd = False

            for i, url in enumerate(oud):
                if gelezen >= budget:
                    break
                if not storage_path_from_url(url):
                    continue  # al op R2, of een marktplaats-url
                try:
                    r = client.get(url)
                    if r.status_code != 200 or not r.content:
                        print(f"  ! {url[:90]} geeft HTTP {r.status_code} — overgeslagen")
                        mislukt += 1
                        continue
                    data = r.content
                    gelezen += len(data)

                    ext = (url.rsplit(".", 1)[-1].split("?")[0] or "jpg").lower()
                    klein, ext_uit = optimize_image(data, ext)
                    pad = f"{rij['user_id']}/{hashlib.sha256(klein).hexdigest()[:32]}.{ext_uit}"

                    if args.apply:
                        nieuwe_url = r2_storage.upload(klein, pad)
                        # Pas geloven als het nieuwe adres echt te openen is.
                        controle = client.get(nieuwe_url, headers={"Range": "bytes=0-0"})
                        if controle.status_code not in (200, 206):
                            print(f"  ! {nieuwe_url} niet op te halen — oude url blijft staan")
                            mislukt += 1
                            continue
                        nieuw[i] = nieuwe_url

                    bespaard += len(data) - len(klein)
                    verhuisd += 1
                    veranderd = True
                except Exception as e:  # noqa: BLE001
                    mislukt += 1
                    print(f"  ! {tabel} {rij['id']} foto {i}: {e}")

            if veranderd:
                if args.apply:
                    try:
                        # Vanaf hier wijst de rij naar R2. Tot deze regel is er
                        # aan het item zelf niets veranderd.
                        db.table(tabel).update({kolom: nieuw}).eq("id", rij["id"]).execute()
                        rijen_bij += 1
                    except Exception as e:  # noqa: BLE001
                        mislukt += 1
                        print(f"  ! {tabel} {rij['id']} niet bijgewerkt: {e} — foto's ongewijzigd")
                else:
                    rijen_bij += 1
                if rijen_bij and rijen_bij % 25 == 0:
                    print(f"  {rijen_bij} rijen, {verhuisd} foto's, "
                          f"{gelezen / 1e6:.0f} MB gelezen")

    print(f"\n{'Verhuisd' if args.apply else 'Zou verhuizen'}: {verhuisd} foto's "
          f"over {rijen_bij} rijen")
    print(f"  gedownload uit Supabase : {gelezen / 1e6:.0f} MB (dit telt mee als egress)")
    print(f"  krimp door verkleinen   : {bespaard / 1e9:.2f} GB")
    if mislukt:
        print(f"  mislukt                 : {mislukt} (die foto's staan onveranderd)")
    if args.apply:
        print("\nDe oude bestanden staan nog in Supabase en zijn nu ongebruikt.\n"
              "Als alles er goed uitziet ruim je ze op met:\n"
              "  python3 scripts/cleanup_orphan_photos.py --apply --include-root")
    else:
        print("\nDroogloop — draai opnieuw met --apply om het echt te doen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
