# Facebook-reactiebot: dagelijks verversen (07:30)

Daniel, 07-11-2026. Doel: het Claude Project "Facebook-reactiebot" antwoordt op actuele informatie en leert van
Daniels echte reacties. Het Project "Facebook-reactiebot v2" (claude.ai/code/project/chan_01RSDHcESSnzUiKX9YCrKkDg) heeft de repo danieldk04/omnivaleur als context en leest `docs/facebook-actueel.md` zelf bij elk gesprek. De opdracht zelf staat in `docs/facebook-reactiebot.md`.

Harde afspraak (14-09 en 08-10): niets plaatst of reageert namens Daniel. Alleen LEZEN, één keer per dag, in
Daniels eigen Chrome.

Stappen:
1. Open in Claude in Chrome (nieuw tabblad) https://www.facebook.com/me/allactivity?category_key=COMMENTSCLUSTER
   en lees met get_page_text. Alleen regels "Daniel Koning heeft een opmerking geplaatst" of "heeft geantwoord".
   Niet scrollen, niet klikken, geen berichten openen. Sluit het tabblad.
2. Voeg nieuwe reacties (op datum+tijd) toe aan `data/facebook-leren/reacties.jsonl`. Dit bestand blijft buiten git.
   Sla over: berichten van hemzelf als bericht (promotie), en niets van anderen opslaan behalve de tekst van Daniel.
3. Zoek per platform (Vinted, Marktplaats/2dehands, eBay Europa) op nieuws van de laatste 30 dagen. Standaardzoekopdracht.
   Alleen wat een bron zelf zegt; twijfel = markeren als onbevestigd.
4. Herschrijf `docs/facebook-actueel.md` in dezelfde opbouw: platformnieuws, wat er bij Omnivaleur veranderde
   (uit `git log --since="21 days ago"`, alleen wat verkopers merken), laatste vijf tot tien echte reacties.
5. Commit en push `docs/facebook-actueel.md`: de repo is de bron, het Project leest hem daar. (Het oude Drive-bestand mag je laten liggen.)
6. Melden alleen als iets niet lukte (niet ingelogd, Facebook toont een controle of checkpoint: dan stoppen en niets herhalen).
