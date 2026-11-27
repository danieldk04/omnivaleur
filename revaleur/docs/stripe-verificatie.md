# Stripe live activeren voor Revaleur (checklist voor Daniel)

Live account: `acct_1UgN3zB31GM6PwWd` (Chrome "Browser 1"). Status 27-11-2026: niets ingevuld; vier stappen staan open
(Je bedrijf verifiëren, Je bank toevoegen, Extra's toevoegen, Controleren en indienen). Dashboard:
https://dashboard.stripe.com/acct_1UgN3zB31GM6PwWd/account/onboarding . Het sandbox-account is `acct_1UfIBePetYvl0Q7t`.

## Wat je nodig hebt
| Stap | Invullen |
|---|---|
| Bedrijf | Eenmanszaak, Nederland. Naam en adres zoals bij de KvK (KvK 86792423), btw NL004117227B97 |
| Branche | Kleding en accessoires, tweedehands (webwinkel) |
| Website | https://revaleur.com (tot de omzetting staat hier nog Shopify; vermeld dat de nieuwe winkel binnenkort komt, zie hieronder) |
| Persoon | Jij: naam, geboortedatum, adres, telefoon; Stripe vraagt een identiteitsbewijs (paspoort of ID-kaart, foto) |
| Bank | IBAN van de zakelijke rekening, op naam van de eenmanszaak |
| Extra's | Omschrijving op afschrift: REVALEUR (max. 22 tekens); supporttelefoon en -mail: info@revaleur.com |
| Productomschrijving | Tweedehands designerkleding voor heren (Ralph Lauren, Stone Island, Suitsupply e.a.), verzending binnen NL en EU |

## Let op
- Stripe checkt de site. Op revaleur.com staat nu Shopify; de proefsite revaleur.pages.dev bevat de nieuwe winkel. Geef revaleur.com op; komt er een vraag naar productpagina, voorwaarden en privacy: die staan op de nieuwe site (revaleur/docs/beleid) en in Shopify.
- Zet NOOIT Stripe Tax aan (margeregeling). iDEAL en kaart aan; PayPal/Klarna alleen als Shopify die nu ook had.
- Na goedkeuring: live secret key en live webhook (events checkout.session.completed, async_payment_succeeded, async_payment_failed, expired) naar `https://api-production-a52c044e.up.railway.app/api/revaleur/stripe-webhook`. De sleutels maakt Daniel in het dashboard; zet ze alleen op Railway (`REVALEUR_STRIPE_SECRET_KEY`, `REVALEUR_STRIPE_WEBHOOK_SECRET`), nooit in git.
- Daarna: de echte proefbestelling van €1 (Daniel betaalt, later terugbetalen).
