# Revaleur-herbouw: wettelijk en fiscaal (27-11-2026)

Alleen wat met een bron is vastgelegd. Alles met "TE CONTROLEREN" legt Daniel (of zijn boekhouder) voor de omzetting vast.

## Margeregeling (tweedehands kleding)
- Bij verkoop onder de margeregeling staat GEEN btw op de factuur; wel de aanduiding "bijzondere regeling - gebruikte goederen". Wie toch btw vermeldt, mag de regeling niet toepassen. Bron: Belastingdienst, [Margeregeling](https://belastingdienst.nl/wps/wcm/connect/bldcontentnl/belastingdienst/zakelijk/btw/bijzondere_regelingen/margeregeling) en [Ondernemersplein](https://ondernemersplein.overheid.nl/margeregeling-voor-de-btw).
- Gevolg voor de bouw: de orderbevestiging/factuur van Revaleur toont geen btw-bedrag en krijgt de regel "Bijzondere regeling - gebruikte goederen / Margin scheme - second-hand goods". Dat staat nog NIET in `backend/services/revaleur_mail.py` (er gaat nu een bevestiging, geen factuur). TE DOEN voor de omzetting: factuur als pdf of in de mail met die tekst en een doorlopend factuurnummer (`revaleur_bestellingen.nummer`).
- Margegoed hoeft per artikel de inkoopprijs te kennen (`items.purchase_price`); hij is bij Revaleur vaak 0,00 ingevuld. TE CONTROLEREN met de boekhouder: welke methode (per artikel of globalisatie) Daniel nu gebruikt in Shopify-tijd.
- Verkoop naar andere EU-landen onder de margeregeling: btw-afdracht blijft in Nederland; OSS speelt voor deze goederen volgens mijn kennis niet. TE CONTROLEREN bij de Belastingdienst voor die lijn in `docs/routines/oss-aangifte.md` aangepast wordt; geen bron gevonden in deze sessie.

## Herroeping en voorwaarden
- 14 dagen herroepingsrecht bij verkoop op afstand; terugbetaling inclusief standaard-verzendkosten. De bestaande tekst op revaleur.com (docs/revaleur/policies_refund-policy.txt) is overgenomen zoals die nu staat. TE CONTROLEREN: het wettelijke modelformulier voor herroeping en de herroepingsinformatie ontbreken op de huidige site; voor de omzetting toevoegen.
- Risico van verlies bij transport ligt bij de verkoper (staat al in het verzendbeleid).

## Bewaarplicht
- Administratie (facturen, bestellingen) 7 jaar. TE CONTROLEREN met bron (AWR art. 52). `revaleur_bestellingen` blijft staan, nooit verwijderen.

## Cookies en privacy
- De nieuwe site zet zelf geen cookies; de winkelmand zit in localStorage (strikt noodzakelijk). Geen banner nodig zolang er geen Meta-pixel of analytics bij komt. Komt de Meta-pixel er wel (fase 5), dan is vooraf toestemming nodig en komt er een banner.
- De privacytekst is de huidige Shopify-tekst; die noemt Shopify als verwerker en moet bij de omzetting Stripe, Resend, Cloudflare en Supabase noemen. TE DOEN voor de omzetting.
