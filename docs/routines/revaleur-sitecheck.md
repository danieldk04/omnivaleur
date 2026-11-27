# Revaleur-winkel: wekelijkse gezondheidscheck (sinds 27-11-2026, Daniel; herschreven voor de eigen webshop)

Doel: Daniel hoeft niets aan de webshop revaleur.com te onderhouden. Deze routine kijkt elke maandag of alles nog werkt en
meldt alleen wat aandacht nodig heeft. De webshop staat los van Omnivaleur: lees eerst `revaleur/README.md`. Sleutels staan NIET
in git; alleen met wat de taak zelf op de omgeving heeft mag je bij de Revaleur-database of Stripe. Wijzig niets; alleen kijken.

Controleer:
1. Bereikbaarheid, met een gewone browser-User-Agent (Cloudflare weigert kale scripts): `https://revaleur.com/`, `/nl/`, een
   productpagina, `/collections/all`, `/cart` geven 200 en laden binnen 3 s. Zolang het testadres nog het enige is: `https://revaleur.pages.dev`.
2. API: `GET <api>/api/revaleur/health` geeft `{"ok":true}`. Een POST naar `/api/revaleur/checkout` met een bestaand, beschikbaar
   product-id geeft een Stripe-checkoutlink (NIET betalen) en de reservering verloopt daarna vanzelf; met een verkocht id geeft het 409.
3. Foto's: steekproef van 10 producten uit `/search-index.json`, elke foto-URL geeft 200 met het juiste type (image/jpeg, png of webp).
4. Database en koppeling: het aantal beschikbare producten in de site klopt met de Revaleur-database (`producten`, status beschikbaar);
   in `bestellingen` staat geen rij met `omnivaleur_gemeld_op` leeg die ouder is dan een uur (dan is de verkoop niet bij Omnivaleur
   aangekomen en staat het artikel nog op andere kanalen: melden aan Daniel met sku en bestelnummer); `mail_bevestiging_op` leeg: idem.
5. Bestellingen van de afgelopen week: elke betaalde Stripe-sessie met `metadata.bron=revaleur` heeft een rij in `bestellingen`
   (webhook werkt), en elke rij heeft een factuur in Stripe.
6. Mobiel: homepage en een productpagina in een smal venster (390 px), kapotte afbeeldingen of overlappende tekst melden.
7. Gratis limieten: Cloudflare R2 (10 GB opslag, 1 miljoen schrijf- en 10 miljoen leesacties per maand), Supabase (500 MB database, en
   het project pauzeert na een week zonder verkeer), Resend (3.000 mails per maand, 100 per dag), Railway (de API kost geld, kijk of het
   tegoed niet opraakt). Meld alleen als iets boven 70% van een limiet zit of gepauzeerd is.
8. Zoekmachines: `/sitemap.xml` en `/feeds/google-merchant.xml` geven 200 en bevatten alle beschikbare producten.

Verbeterpunten (snelheid, UX, SEO) alleen noemen als ze echt iets opleveren, met label volgens CLAUDE.md. Schrijf het resultaat in
`docs/team-notes.md` alleen als er iets gevonden of gerepareerd is; anders geen bericht aan Daniel.
