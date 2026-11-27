# Revaleur-winkel: wekelijkse gezondheidscheck (sinds 27-11-2026, Daniel)

Doel: Daniel hoeft niets aan de webshop revaleur.com te onderhouden. Deze routine kijkt
elke maandag of alles nog werkt en meldt alleen wat aandacht nodig heeft.

Controleer, zonder iets te wijzigen:
1. revaleur.com, een productpagina, de winkelpagina en /cart geven 200 en laden binnen 3 s.
2. Checkout bereikbaar (alleen de pagina openen, nooit bestellen).
3. Omnivaleur-koppeling: `https://omnivaleur.com/health`, en of de Shopify-koppeling van
   Revaleur (ywqad3-xb.myshopify.com) geen koppelalarm heeft (`backend/services/shopify_koppelalarm.py`).
4. Verkopen van de afgelopen week: elke betaalde Shopify-bestelling heeft het artikel op de
   andere kanalen afgemeld.
5. Foto's, prijzen en voorraad: steekproef van 5 producten, tegen de Omnivaleur-database.
6. Mobiel: homepage en een productpagina in een smal venster, kapotte afbeeldingen of
   overlappende tekst melden.
7. Apps: staat er een app met een afgelopen abonnement, een waarschuwing of nieuwe kosten.

Verbeterpunten (snelheid, UX, SEO) alleen noemen als ze echt iets opleveren, met label
volgens CLAUDE.md. Schrijf het resultaat in `docs/team-notes.md` alleen als er iets
gevonden of gerepareerd is; anders geen bericht aan Daniel.
