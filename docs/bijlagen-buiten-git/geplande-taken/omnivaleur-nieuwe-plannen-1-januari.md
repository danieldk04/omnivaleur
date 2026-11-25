---
name: omnivaleur-nieuwe-plannen-1-januari
description: Op 1 januari 2027 de tekstwissel voor de nieuwe plannen doorvoeren en Daniel de vlag laten aanzetten.
---

Je werkt aan Omnivaleur in /Users/danieldekoning/Projects/omnivaleur. Antwoord in het Nederlands, in de vier blokjes van CLAUDE.md, kort, geen streepjes als leesteken. Lees eerst docs/overdracht.md (onderaan) en docs/team-notes.md, en doe `git log --since="30 days ago" --oneline`.

Doel: vandaag, 1 januari 2027, gaan de nieuwe plannen live (Light 9,99 tot 20 artikelen, Pro 19,99 tot 250, Plus 29,99 tot 1.500, Ultra 49 onbeperkt; jaarlijks 2 maanden gratis; grenzen van Pro en Plus gelden pas vanaf 15 januari; Light strikt 20; de vriendenactie met 10 euro korting loopt tot 1 januari en wie daarvoor binnenkwam houdt 10 euro). De server en alle prijs-id's staan al klaar; alleen de vlag NIEUWE_PLANNEN_AAN in Railway staat uit en alleen Daniel kan die aanzetten.

Doe dit, zelf en zonder te vragen:
1. Controleer via https://omnivaleur.com/health dat config.plan_prijzen overal true is (zeven sleutels) en noteer of nieuwe_plannen_aan nog false is. Draai `python3.13 -m pytest tests/test_plannen.py tests/test_referral_korting.py tests/test_omnivaleur_light.py tests/test_updates_log.py tests/test_i18n_compleet.py -q` en meld rood.
2. Zet de teksten om van "From 1 January" naar de dan geldende stand, in BEIDE talen: frontend/app.html (#komt-eraan, #plannen-vanaf-januari boven Account, het updatelogbericht en de popup), frontend/index.html en frontend/nl.html (blok #plans-next). Verwijder wat over de vriendenactie "tot 1 januari" als lopende actie spreekt en zet het in de verleden tijd of laat weg wat niet meer klopt, zonder de 10 euro voor wie vóór 1 januari kwam te schrappen. Draai python3 scripts/i18n_extract.py, vul nl.json aan en draai --versie. Tests hierboven moeten groen blijven. Commit en push (volg docs/routines/kennisoverdracht.md), wacht tot het live staat (curl op https://omnivaleur.com/app), nooit het ?v=-adres vroeg pollen.
3. Werk docs/overdracht.md, de bouwlijst (scripts/te_bouwen.py, regels 68, 69 en 73) en docs/team-notes.md bij.
4. Meld Daniel in de actiepunten als [NU, 2 min]: zet in Railway NIEUWE_PLANNEN_AAN=true. Zeg erbij dat daarna jij (een nieuwe sessie) controleert via /health en via het dashboard dat Plus en Ultra als keuze verschijnen op de Account-pagina.
Verstuur geen mails en zet zelf geen vlag aan (kan ook niet). Raak geen Stripe aan.