---
name: mp-video-meting-week-1
description: Eenmalig 11-10-2026: meet autonoom wat de videometing en cta_location op /mp-video opleverden en rapporteert in vier blokjes.
---

Je werkt aan Omnivaleur in /Users/Danie/Documents/omnivaleur. Werk volgens CLAUDE.md (repo en ~): Nederlands, gewone taal, vier blokjes, geen gedachtestreepjes, geen subagents, batch, lees gericht. Begin met kijken wat er veranderd is (git log --since="30 hours ago" en onderaan docs/team-notes.md).

Opdracht: meet de eerste week van de videometing op https://omnivaleur.com/mp-video, ingebouwd op 04-10-2026 (commit 17646ba1, 675610a8). Context staat in docs/team-notes.md onder "04-10-2026: Analyse /mp-video".

De GA4-sleutels staan niet op de Mac, dus scripts/mp_video_rapport.py werkt hier niet. Meet via Claude in Chrome (laad de mcp__claude-in-chrome__ tools met ToolSearch) in Daniels ingelogde Analytics, property Omnivaleur (a400015242p545466811), periode 04-10 tot en met gisteren. Werkende route: reports/explorer met r=all-pages-and-screens, filter op Paginapad bevat mp-video (URL-param _r..dataFilters met fieldName unifiedPagePathScreen, evaluationType 3), tweede dimensie Naam gebeurtenis; en r=lifecycle-traffic-acquisition-v2 met filter Landingspagina + querytekenreeks bevat mp-video, dimensie Sessiebron/-medium. Voor cta_location (aangepaste dimensie, aangemaakt 04-10, vult pas vanaf dan): gebruik secundaire dimensie Aangepast > cta_location bij events.

Meet en vergelijk: (1) sessies per bron/medium: komt er nu koude-mail/email binnen (de korte link /mp werkt sinds de fix; Daniel moet het Gemini-brein wel opnieuw hebben geplakt); (2) video_start, video_progress (25/50/75), video_complete: aantal events en gebruikers, plus wat dat is van het aantal bezoekers; (3) cta_click per cta_location; (4) bezoekers, apparaat desktop/mobiel. Eerdere basislijn (30 dagen): 21 bezoekers, 54 weergaven, 4 cta_click, 5 scroll, 0 koude-mail. Wantrouw lege uitkomsten: controleer eerst of de meting zelf klopt (bv. staat de datum goed, bestaan de events überhaupt). Eigen bezoeken van Daniel en testbezoek van 04-10 zitten in de data; noem dat. Bij minder dan ongeveer 10 bezoekers: zeg eerlijk dat er niets te concluderen valt en stel geen wijzigingen voor op losse cijfers.

Rapporteer in vier blokjes met zekerheid en actiepunten met urgentielabel. Voeg een kort gedateerd blok toe aan docs/team-notes.md met de cijfers en commit en push dat (alleen die file). Sluit je Chrome-tabblad af als je er een opende. Stuur geen mail en verander niets aan de site of aan Analytics.