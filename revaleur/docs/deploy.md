# Revaleur: uitrollen (Cloudflare Pages + API)

## 1. Site: Cloudflare Pages
Project koppelen aan de GitHub-repo `danieldk04/omnivaleur`, productiebranch `main`. Instellingen:
- Framework preset: None
- Root directory: (leeg, de hele repo)
- Build command: `pip install -r revaleur/requirements-build.txt && python -m revaleur.site.catalogus_uit_db && python -m revaleur.site.bouw`
- Build output directory: `revaleur/site/dist`
- Environment variables (Production en Preview): `PYTHON_VERSION=3.12`, `REVALEUR_SUPABASE_URL=https://pwptworlzhgcombgearz.supabase.co`, `REVALEUR_SUPABASE_PUBLISHABLE_KEY=<publishable key van het Revaleur-project>`
- Eerst alleen de `*.pages.dev`-URL; het domein revaleur.com pas bij de omzetting.
- Een deploy hook (Settings, Builds) komt als `REVALEUR_DEPLOY_HOOK` bij de API, zodat de site opnieuw bouwt na een verkoop.
Mislukt het lezen van de database, dan stopt de build met een fout en blijft de vorige werkende site staan.

## 2. API (afrekenen, Stripe-webhook, koppeling): eigen Railway-dienst
Start command: `uvicorn revaleur.shop_api.main:app --host 0.0.0.0 --port $PORT`, pakketten uit `revaleur/requirements.txt`.
Variabelen: `REVALEUR_SUPABASE_URL`, `REVALEUR_SUPABASE_SERVICE_KEY`, `REVALEUR_STRIPE_SECRET_KEY`, `REVALEUR_STRIPE_WEBHOOK_SECRET`,
`REVALEUR_RESEND_API_KEY`, `REVALEUR_KOPPELING_GEHEIM`, `REVALEUR_DEPLOY_HOOK`, `REVALEUR_SITE_URL` en `REVALEUR_EXTRA_ORIGINS` (de pages.dev-URL).
Stripe-webhook: `https://<api-adres>/api/revaleur/stripe-webhook`, events `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
`checkout.session.async_payment_failed`, `checkout.session.expired`.
De site wijst naar `API` in `revaleur/site/bouw.py` (nu https://api.revaleur.com/api/revaleur); voor de test het echte adres invullen.

## 3. Stripe
Eerst alleen de sandbox (sleutels `sk_test_`). Geen Stripe Tax: Revaleur werkt onder de margeregeling, dus geen btw op de factuur
(`automatic_tax` blijft uit; de factuur krijgt de tekst "Bijzondere regeling - gebruikte goederen").

## Stand 27-11-2026
- Cloudflare Pages-project `revaleur` bestaat (aangemaakt via de API, **directe upload**, zonder GitHub-koppeling). Testadres: https://revaleur.pages.dev
  Opnieuw uploaden: `set -a; . ~/.revaleur/env; set +a; python3 -m revaleur.site.catalogus_uit_db && python3 -m revaleur.site.bouw && npx wrangler pages deploy revaleur/site/dist --project-name revaleur --branch main`
- Een project met directe upload kan GEEN deploy hook hebben. Voor de omzetting moet het een Git-gekoppeld project worden (Cloudflare vraagt dan eenmalig GitHub-toestemming, dat kan alleen Daniel in de browser) of de API bouwt en uploadt zelf na een verkoop.
- Foto's staan nog op de Shopify-CDN (af en toe een 502 vanuit de testomgeving). Naar R2 voordat Shopify stopt; R2 moet eerst aan in het Cloudflare-dashboard.

## Stand 27-11-2026 (avond)
- API draait: https://api-production-a52c044e.up.railway.app (Railway-project `revaleur-api`, account van Daniel). Opnieuw uitrollen: kopieer `revaleur/__init__.py` en `revaleur/shop_api/` naar een lege map met `requirements.txt`, een `Procfile` (`web: uvicorn revaleur.shop_api.main:app --host 0.0.0.0 --port $PORT`) en `railway up --service api`.
- Stripe-webhook (sandbox) staat, naar de API hierboven. Voor live: nieuw webhook met de live sleutel en nieuwe `REVALEUR_STRIPE_*` op Railway.
- Mail: nu van `onboarding@resend.dev` (alleen naar het eigen adres van de Resend-eigenaar). Voor klanten: domein revaleur.com verifiëren in Resend (DNS) en `REVALEUR_MAIL_VAN` op `Daniel van Revaleur <info@revaleur.com>` zetten.
- Omnivaleur-kant van de koppeling staat uit tot op Omnivaleurs Railway `REVALEUR_KOPPELING_GEHEIM` (zelfde waarde als op de Revaleur-API) en `REVALEUR_API_URL` (het API-adres) staan.
