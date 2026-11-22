---
name: omnivaleur-mieneke-2dehands-nameting
description: Eenmalig: meten of Mienekes 2dehands-zoekertjes op zelf verzenden voor 0,01 staan
---

Je werkt aan Omnivaleur in /Users/Danie/Documents/omnivaleur. Antwoord in het Nederlands volgens de vier blokjes uit CLAUDE.md (wat er aan de hand was, wat er veranderd is, zekerheid in procenten, actiepunten met urgentielabel). Nooit een gedachtestreepje.

Achtergrond: op 30-10-2026 is voor Mieneke (Voordeelsieraden, user_id 09e089ec-e233-40c1-a5fa-7a56b6dea575, info@voordeelsieraden.nl) op Daniels ja een verzendronde gestart (backend/services/verzending_2dh_ronde.py): al haar 558 actieve 2dehands-zoekertjes moeten op "zelf versturen voor EUR 0,01" (instelling verzending_2dh_modus vast, verzending_2dh_vast_cents 1). De ronde zet per zoekertje een content_refresh-opdracht (payload _verzending_bijwerken) klaar die haar extensie uitvoert. Server draait commit 49199092 of nieuwer. Extensie 1.0.409 (bieden standaard aan) wacht op Web Store-upload door Daniel; dat is los hiervan.

Meet, python3.13 vanuit de repo-root, gebruik backend.database.get_db en backend.services.verzending_2dh_ronde._lees_rij (platform RIJ_RONDE) voor de stand:
1. Rondestand: status, bekeken van aantal, tel (aangepast, al_goed, onderweg, bpost, ophalen, weg), blokkades, niet_gelezen_ids. Loopt hij nog, is hij gestopt of stilgevallen (bijgewerkt_op oud)?
2. Haar 2dehands content_refresh-opdrachten met _verzending_bijwerken, per status (pending, claimed, done, failed). Bij failed: de foutteksten gegroepeerd, vooral of het formulier 0,01 weigerde. Valt de noodrem (_bijwerken_2dh_staat_stil in backend/api/jobs.py) in werking, meld dat.
3. Steekproef van ten minste 10 zoekertjes met status done: lees de openbare 2dehands-pagina (verzending_van_advertentie in backend/services/mp_enrich.py of lees_2dehands in verzending_2dh_ronde.py) en bevestig dat er echt zelf versturen voor 1 cent staat. Wantrouw een lege uitkomst: controleer eerst of de meting zelf klopt, bijvoorbeeld op een zoekertje waarvan je het antwoord al kent.
4. Haar extensieversie en laatste hartslag (tabel extension_heartbeat): staat Chrome aan?

Wijzig niets aan haar advertenties of instellingen, start geen nieuwe ronde en mail niemand. Is er een aantoonbare fout in onze code, meld dat met het bewijs en repareer niets zonder Daniels ja. Schrijf het resultaat als korte dagboekregel onder aan docs/team-notes.md en commit en push alleen dat bestand. Staat er nog werk open (ronde nog bezig), zeg dan eerlijk hoeveel en wat dat betekent in plaats van "waarschijnlijk goed".