# Building in public: Engels, op X, Bluesky en Facebook

Daniel, 07-11-2026. Doel: het verhaal van Omnivaleur openbaar vertellen zoals Starter Story: concreet, met echte
cijfers en echte fouten. Eén soort bericht per keer. Engels. Indie Hackers komt later (eerst aanwarmen via
`docs/routines/social-reageren.md`, geen eigen berichten daar tot Daniel het zegt).

Voorbeeld van de toon (Daniels eigen post van 07-11): "POV: You go from 0 to 89 users in 154 days purely organic. No big
social account. No crazy hype app. And definitely no big budget (living with my parents lol). Just the art of solving
problems you encounter while doing." Plat, eerlijk, een beetje zelfspot, een beeld erbij.

## Kanalen en tempo
- X (@DanieldeKoning_): 1 bericht per dag, een draadje (3 tot 5 posts) hooguit 1 keer per week.
- Bluesky (@danieldekoning...): hetzelfde bericht, andere dag of ander uur mag; kopie is prima.
- Facebook: eigen profiel, 3 keer per week, dezelfde tekst, iets langer mag. Geen groepen: in groepen reageert
  de Facebook-reactiebot niet autonoom en promotie is er verboden.
- Plaats niet op alle drie op exact hetzelfde moment: spreid minstens 30 minuten.

## Soorten berichten (wissel af, nooit twee dezelfde achter elkaar)
1. Cijfer: aanmeldingen, betalende klanten, aantal gekoppelde artikelen, Search Console. Alleen echte, nagemeten getallen.
2. Fout en les: wat mis ging en wat het leerde. Voorbeelden staan in `docs/team-notes.md` en `docs/kennisbank.md`
   (Vinted-formulier veranderd, database plat, SEPA-incasso duurt negen werkdagen, vertaling die stil faalde).
3. Wat er is gebouwd deze week, uit `git log --since="7 days ago"`, in gewone taal en met het gevolg voor een verkoper.
4. Beslissing: waarom iets wel of niet (alleen tweedehands, alleen Europa, Bol niet bouwen, prijs 19,99).
5. Vraag aan het publiek: een echte vraag waar Daniel antwoord op wil.

## Harde regels
- Nooit een getal dat je niet hebt nagemeten (Supabase, Stripe, Search Console, Railway, de kostensheet). Staat de
  bron er niet bij in het rapport, dan plaats je het niet. Omzet en bedragen alleen als ze in `docs/team-notes.md`
  of de kostensheet staan en Daniel ze daar zelf noemde.
- Nooit namen, mailadressen, winkels of data van klanten, ook niet half. "A customer" is genoeg.
- Geen gedachtestreepjes, geen hashtags, geen emoji-reeksen, geen "excited to announce", geen threadkoppen als
  "A thread 🧵". Geen link behalve in 1 op de 5 berichten (dan naar omnivaleur.com).
- Niets over concurrenten of platformen dat een belediging of een bewering zonder bron is.
- Niet liegen over de situatie: "living with my parents" is Daniels eigen grap, anderen verzinnen mag niet.
- Een screenshot of beeld mag alleen van het eigen dashboard met neutrale of nagebootste gegevens, of een grafiek.

## Uitvoering
1. Lees `data/social/gedaan.jsonl` (kanaal "bip") om herhaling te voorkomen en het soort van gisteren te zien.
2. Kies het soort, haal het feit en het getal er zelf bij (Bash en scripts in de repo, `git log`, team-notes), schrijf
   het bericht en controleer elk getal tegen de bron.
3. Plaats in Daniels Chrome, controleer dat het zichtbaar staat, log het (kanaal, tekst, bron van elk getal).
4. Stoppen en melden bij: niet ingelogd, captcha, beperking, of twijfel over een feit.
5. Na 72 uur: weergaven, likes, reacties per bericht in `data/social/laatste-rapport.txt`. Elke week, op maandag:
   welk soort scoorde, wat flopte, pas de verdeling aan in dit bestand.
6. Bij een echte mijlpaal (100 gebruikers, eerste betalende klant van een nieuw kanaal): meld het Daniel zodat hij
   er zelf een goed beeld bij maakt. Een mijlpaalbericht plaatst de routine niet zonder.
