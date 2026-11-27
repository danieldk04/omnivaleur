# Koppeling Revaleur en Omnivaleur

De enige verbinding. Twee berichten, beide met HMAC-SHA256 over de ruwe body in de header `X-Revaleur-Signature`, gedeeld geheim in
`REVALEUR_KOPPELING_GEHEIM` (Revaleur) en `REVALEUR_KOPPELING_GEHEIM` (Omnivaleur, in `backend/config.py` als `revaleur_koppeling_geheim`). Zonder geheim weigert elke kant alles.

| Richting | Adres | Body | Doel |
|---|---|---|---|
| Revaleur naar Omnivaleur | `POST https://omnivaleur.com/api/koppeling/revaleur/verkocht` | `{sku, bestelling, prijs}` | verkocht op revaleur.com: artikel van Marktplaats, Vinted, eBay af (`handle_item_sold`, platform `revaleur`) |
| Omnivaleur naar Revaleur | `POST https://api.revaleur.com/api/revaleur/koppeling/afmelden` | `{sku}` | elders verkocht: artikel van revaleur.com af (status `verkocht`, site opnieuw bouwen) |

Code: `revaleur/shop_api/koppeling.py` en `checkout.py` (Revaleur), `backend/api/revaleur_koppeling.py` (Omnivaleur).

- Mislukt de melding naar Omnivaleur, dan blijft `bestellingen.omnivaleur_gemeld_op` leeg; de bestelling zelf staat vast. Een herhaalronde (nog te bouwen) probeert die opnieuw.
- Omnivaleur naar Revaleur is gebouwd (27-11-2026): `handle_item_sold` roept `meld_aan_revaleur` aan (`backend/api/revaleur_koppeling.py`). Het doet niets zolang `REVALEUR_API_URL` of `REVALEUR_KOPPELING_GEHEIM` op Omnivaleurs Railway ontbreekt, en alleen voor artikelen van de Revaleur-klant.
- Artikelen zijn gekoppeld op `sku` (artikelnummer, uniek per artikel; Omnivaleur: `items.sku` van de Revaleur-klant).
