# Verhuizing naar de MacBook M1 Max (32 GB)

Daniel, 23-11-2026: de oude Mac (Air M2, 8 GB) wordt binnenkort verkocht. Alles gaat over naar
de M1 Max. Claude regelt alles wat zonder Daniels handen kan; dit bestand is de stand en de gids.

## Stand 23-11-2026 (oude Mac)
- Manifest gemaakt met `bash scripts/verhuis_controle.sh maak` (staat in `~/.omnivaleur/verhuis-manifest.txt`,
  133 regels: 14 repo's, 8 mappen, achtergrondprogramma's, 40 geplande taken, Chrome-profielen, apps, tools).
- Op de oude Mac staat geen Time Machine en geen externe schijf. Er is dus nu nergens een tweede kopie.
- Alleen de repo `omnivaleur` is bewezen gelijk aan GitHub. Open, nog te meten: `garmin-coach` (1 wijziging,
  2 niet verstuurd), de repo's ZENbtw, revaleur-blog en nexus-market-terminal (git antwoordt traag).
  Geen git: `garmin-tracker`, `porsche-monitor`, `Handige Scripts Mac` (videoknipper, Google-koppeling).

## Wat Daniel doet (alleen zijn handen)
1. Nieuwe Mac aanzetten, in Setup Assistent kiezen: "Overzetten van een Mac". Beide Macs aan de stroom,
   liefst met een Thunderbolt-kabel (140 GB over wifi duurt uren). Zelfde Apple-account.
2. Aan de oude Mac niets meer doen tijdens de overdracht.
3. Klaar? Claude desktop openen op de nieuwe Mac, deze map openen en zeggen "ik ben klaar".

## Wat Claude daarna doet
1. `bash scripts/verhuis_controle.sh check`: alles wat ontbreekt staat in het rapport.
2. Python 3.13 (`/usr/local/bin/python3`), node, brew-pakketten opnieuw laden voor M1 (de oude installatie
   zat onder `/usr/local`, de nieuwe Mac gebruikt `/opt/homebrew`). Geplande taken en LaunchAgents laten lopen.
3. Chrome: extensie 1.0.x opnieuw koppelen (inlogbewijs is apparaatgebonden), inlogs van Daniel zelf.
4. Overschakelen: op de oude Mac alle LaunchAgents uit (`launchctl bootout`) en geplande taken uit,
   pas daarna op de nieuwe aan. Nooit allebei tegelijk: dubbele mails naar klanten.
5. Een week parallel gemeten (klantfouten- en onboardingronde komen op de nieuwe Mac), daarna pas
   de oude Mac leegmaken.

## Voor de verkoop (pas na het bewijs, niet eerder)
Uitloggen bij iCloud en Zoek mijn, Claude, Chrome, GitHub; WhatsApp, Spotify en Windows App
afmelden; Surfshark, Grammarly en TeamViewer deautoriseren; daarna wissen via Instellingen,
Algemeen, Zet terug. Dat laatste kan alleen Daniel.
