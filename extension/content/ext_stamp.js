// Draait op omnivaleur.com bij het ALLEREERSTE moment van de pagina.
//
// WAAROM DIT ER IS (03-09-2026, Amanda Haas). "Ook geeft hij dan wel/dan weer
// niet aan dat de extensie niet is gevonden (als je bijvoorbeeld bezig bent met
// het dashboard), terwijl deze up-to-date is."
//
// Het dashboard vroeg de extensie of ze er was en wachtte op antwoord. Dat
// antwoord komt pas na twee heen-en-weertjes met de service worker, en die
// moet in Chrome eerst koud opstarten — juist terwijl ze publiceert is hij druk
// of net weer afgesloten. Kwam er binnen ~8,8 seconde niets terug, dan
// concludeerde het scherm "niet gevonden" en zette er een blokkerend
// installatievenster overheen. Bij iemand die alles goed had staan.
//
// Dit stempeltje heeft de service worker niet nodig: een content script kent
// zijn eigen manifest en zet het meteen op de pagina. Staat het er, dan IS de
// extensie geïnstalleerd — daar valt niets meer over te concluderen. Het
// vraag-en-antwoord blijft bestaan voor wat het stempel niet weet: of ze ook
// is ingelogd.
(() => {
  try {
    const v = chrome.runtime.getManifest().version;
    const el = document.documentElement;
    if (el) el.setAttribute("data-omnivaleur-ext", v);
  } catch (_) { /* liever geen stempel dan een kapotte pagina */ }
})();
