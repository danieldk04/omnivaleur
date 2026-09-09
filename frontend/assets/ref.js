/* Onthoudt welke creator een bezoeker heeft gestuurd.
 *
 * Een creator deelt omnivaleur.com/r/CODE. De server telt die klik en stuurt
 * door naar de landingspagina met ?ref=CODE. Hier slaan we de code op, zodat
 * hij er bij het aanmelden nog is, ook als de bezoeker eerst nog rondkijkt of
 * pas dagen later terugkomt.
 *
 * Bewust localStorage en niet sessionStorage: bij sessionStorage is elk nieuw
 * tabblad een schone lei, en dan raakt precies de bezoeker die er even over
 * nadenkt zijn herkomst kwijt.
 */
(function () {
  var SLEUTEL = 'omnivaleur_ref';

  try {
    var code = new URLSearchParams(window.location.search).get('ref');
    if (code) {
      code = code.trim().toLowerCase().slice(0, 40);
      // Alleen precies wat de server ook accepteert. Half opgeschoonde codes
      // koppelen stilletjes aan de verkeerde creator.
      if (/^[a-z0-9_-]+$/.test(code)) {
        window.localStorage.setItem(SLEUTEL, code);
        window.localStorage.setItem(SLEUTEL + '_op', new Date().toISOString());
      }
    }
  } catch (e) {
    /* Privémodus of geblokkeerde opslag mag de pagina nooit breken. */
  }

  window.omnivaleurRef = function () {
    try {
      return window.localStorage.getItem(SLEUTEL) || null;
    } catch (e) {
      return null;
    }
  };
})();
