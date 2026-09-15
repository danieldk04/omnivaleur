# Overzicht: alle automatische opvolgmail (15-09-2026)

Drie aparte systemen sturen automatisch mail. Ze draaien onafhankelijk van
elkaar en niemand had ze tot nu toe naast elkaar gezet. Dit bestand is dat
overzicht.

## 1. Koude mailreeks (mail 1, 2, 3)

- **Voor wie:** koude leads uit Marktplaats/2dehands, nog geen klant.
- **Waar:** Google Sheet "E-mail outreach", tabs Leads / Logboek / Mailteksten / Uitleg.
- **Ritme:** mail 1 op een willekeurig moment, mail 2 na 2 dagen, mail 3 na 4 dagen daarna.
  Reageert of meldt iemand zich af, dan stopt het meteen. Na mail 3 en 10 dagen
  stilte gaat de lead naar Doodgelopen.
- **Wie past de tekst aan:** jij, in de tab Mailteksten. Wijziging geldt binnen 10 minuten.

## 2. Video-opvolging

- **Voor wie:** dezelfde leads, maar alleen nadat jij zelf een mail met de
  videolink hebt gestuurd.
- **Waar:** zelfde Google Sheet, zelfde tabs.
- **Ritme:** geen reactie op jouw video-mail, dan tekst V1 na 3 dagen en V2 na
  7 dagen, in hetzelfde mailgesprek. Op een video ouder dan 10 dagen komt geen
  opvolging meer.
- **Wie past de tekst aan:** jij, in de tab Mailteksten.

## 3. Proefperiode-opvolging

- **Voor wie:** echte aangemelde gebruikers in de app, geen leads.
- **Waar draait het:** in de code van de site zelf (`backend/services/billing.py`),
  niet in Google Sheets.
- **Ritme:** 2 dagen voor het einde van de proefperiode een herinneringsmail,
  daarna 2 dagen respijt, daarna een melding dat het account op pauze staat.
  Draait elke dag om 09:00 Nederlandse tijd.
- **Wie past de tekst aan:** alleen ik, in de code.
- **Overzicht (sinds 15-09-2026):** dezelfde spreadsheet als de leads heeft nu
  ook een tab **Proefperiode**. Elke dag om 09:10 (net na de herinneringsronde)
  wordt die tab herschreven met wie er nog in de proef of respijt zit, en wie
  net gepauzeerd is. Betalende klanten staan er expres niet in, en wie langer
  dan 14 dagen geleden is gepauzeerd valt er ook weer af: dit is een
  momentopname van wie nog opvolging nodig heeft, geen archief.

## Zekerheid per systeem

| Systeem | Bevestigd | Hoe bevestigd |
|---|---|---|
| Koude reeks + video-opvolging | Ja, draait | `/health` toont leadgen_tick, leadgen_resend en leadgen_sheets alle op "aan", en in de sheet staat vandaag (15-09-2026) nog een echte binnengekomen reactie van een lead |
| Proefperiode-opvolging | Ja, draait | Rechtstreeks nagekeken in Supabase: van 48 abonnementen hebben 34 een gezette `trial_reminder_sent_at` en 31 een gezette `final_reminder_sent_at`, allemaal om 07:00 UTC (09:00 NL-tijd), precies het moment waarop de dagelijkse taak draait. De code zet die tijdstempel pas ná een geslaagde verzending, dus dit zijn echte verstuurde mails, geen pogingen |

**Openstaand punt:** ik zag dat Resend de mail heeft geaccepteerd om te
versturen, niet of hij ook echt in iemands inbox is aangekomen (geen bounce).
De Resend-sleutel staat alleen op de server, niet lokaal, dus dat laatste kon
ik hier niet natrekken.

## Wat er van jou verwacht wordt

Niets structureels. De drie systemen draaien zelf. Jij hoeft alleen:

1. In de sheet de kolom Notities te gebruiken als je iets wilt onthouden, en
   Niet meer mailen aan te vinken als iemand geen mail meer moet krijgen.
2. Mailteksten in de tab Mailteksten aan te passen als je de toon wilt
   wijzigen, voor zowel de koude reeks als de video-opvolging.
3. Mij toegang te geven tot Supabase of het Resend-postvak als je zeker wilt
   weten dat er ook echt een proefperiode-mail is aangekomen bij een klant,
   dan kan ik dat alsnog aantonen.
