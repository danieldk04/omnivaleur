# Videoformats en hooks (catalogus)

Bijgehouden door de wekelijkse routine `docs/routines/social-videos.md`. Doel (Daniel, 12-11-2026): grote variatie, leren van de echte cijfers op Instagram, TikTok, YouTube en Facebook, en over tijd vanzelf bij de best werkende formats uitkomen. Nooit iets wat als "weer een AI-video" voelt.

## Formats (elke week minstens drie verschillende, nooit twee keer hetzelfde twee weken achter elkaar zonder reden)
| Code | Format | Wat het is | Gebouwd? |
|---|---|---|---|
| STORY | Storytime | Mens met inzet, keerpunt en einde dat telt (vA) | ja |
| DEMO | Demo eerst | Resultaat in beeld in seconde 1, echt dashboard, één functie, duidelijke oproep (vB) | ja |
| SKIT | Komedie met personage | Een ding met een gezicht of een absurde situatie rond een echte pijn (vC, rechtszaal, kookshow, ruimte) | ja |
| ANALOGIE | Vergelijking | "Crosslisten is als ..." één beeld, één vergelijking, geen poppetje nodig | nee |
| UITLEG | Uitleg in drie stappen | Eén vraag ("Waarom verkoop je dubbel?"), antwoord in drie korte beelden | nee |
| DIRECT | Directe aanspreking | Eén stem, "jij", één harde belofte of waarschuwing, snel tempo | nee |
| MYTHE | Mythe of fout | "Stop met X" of "Dit kost je geld": herkenbare fout, correctie, oplossing | nee |
| POV | Ik als jij | "POV: je bent een hoodie / je koper / je buurman die twee keer kocht" | gedeeltelijk |
| LIJST | Lijst of ranglijst | "3 dingen die elke reseller fout doet", elk één beeld | nee |
| VOORNA | Voor en na | Zelfde avond met en zonder de tool, split of snelle wissel | nee |
| ECHT | Echt gezicht of stem | Daniels eigen stem of een echt iemand (telefoonbeeld of opname), nooit gegenereerd | nee, vraagt Daniel |

## Hooktypes (de eerste 1 tot 2 seconden)
RESULTAAT (laat het eindresultaat zien), INZET (iets staat op het spel), VRAAG (een herkenbare vraag), BEWERING (stellig, een beetje fout), PIJN (de ergernis in de woorden van de kijker), ABSURD (iets wat niet kan), GETAL (concreet cijfer). Noteer per video het hooktype; de cijfers wijzen uit welke werkt.

## Hoe de routine kiest
`python3 scripts/video/format_scores.py` leest `docs/social-video-metingen.csv`, normaliseert per platform (een Facebook-weergave is iets anders dan een TikTok-weergave), weegt aanmeldingen en betalende klanten het zwaarst, dan bewaard en gedeeld, dan kijkduur en percentage bekeken, dan weergaven. Het advies: ongeveer 60% van de nieuwe video's uit de best scorende formats en hooks (alleen met minstens 3 geplaatste video's, anders staat er "onzeker"), 40% proberen: het format met de minste data, plus één mutatie van de winnaar (andere hook, andere stem, andere lengte). Zo komt de routine vanzelf bij de beste opties uit, en blijft hij verrassen.

## Menselijkheidspoort (voor elke video, zie de routine)
1. `python3 scripts/video/slop_check.py <script.json>` moet groen zijn (geen reclamewoorden, geen drie-delige opsommingen in vast ritme, geen uitroeptekens, geen gedachtestreepjes).
2. Stem: `intonatie.py` toonspreiding minstens 4,5 halve tonen en wisselende pauzes; liever Daniels eigen stem als hij die inspreekt.
3. Beeld: handheld wiebel aan, filmkorrel, minstens één hard cut, geen perfecte symmetrie, dikke duidelijke bijschriften, echt dashboard met echte cijfers van Daniel.
4. Eerlijk over wat er niet te beoordelen is: ik kan niet horen. Daniel luistert als eerste.
