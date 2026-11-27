# Revaleur (revaleur.com): eigen webshop, los van Omnivaleur

Alles wat bij Revaleur hoort staat in deze map. Omnivaleur (de map `backend/`, `frontend/`, `extension/`) kent Revaleur alleen als
verkoopkanaal via één ondertekende melding ([docs/koppeling.md](docs/koppeling.md)).

| Onderdeel | Revaleur | Omnivaleur |
|---|---|---|
| Code | `revaleur/` | rest van de repo |
| Database | eigen Supabaseproject (`sql/schema.sql`) | eigen project |
| Stripe | eigen account, `REVALEUR_STRIPE_*` | eigen account |
| Mail | eigen Resend-domein, `REVALEUR_RESEND_API_KEY` | eigen |
| Server | eigen dienst (`shop_api`, api.revaleur.com) | Railway `backend` |
| Site | statisch, Cloudflare Pages (`site/`) | Railway |
| Variabelen | alles met `REVALEUR_` ervoor | zonder |

Gedeeld is alleen het artikelnummer (sku) en één geheim voor de ondertekening. Nooit een database, sleutel of gebruikers-id van de ander.

## Mappen
- `site/` bouwt de statische winkel (`python3 -m revaleur.site.bouw`) en importeert uit Shopify (`python3 -m revaleur.site.import_shopify`).
- `shop_api/` de kleine API voor afrekenen, Stripe-webhook en de koppeling (`uvicorn revaleur.shop_api.main:app`).
- `sql/schema.sql` draai je in het Supabaseproject VAN REVALEUR, nooit in dat van Omnivaleur.
- `docs/` inventaris, ontwerp, wettelijk, koppeling, beleidsteksten. `tests/` draai met `python3 -m pytest revaleur/tests`.

## Eigen afspraken
Zelfde uitgangspunten als Omnivaleur (kort rapporteren, tweetalig, nooit "sorry" in klantmail), maar eigen gegevens. Deze map kan
later zonder aanpassing naar een eigen repo (`git subtree split --prefix=revaleur`).
