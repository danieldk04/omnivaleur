/* Advertentietekst-generator. Geen AI: de tekst wordt uit jouw invoer opgebouwd, dus er wordt niets
 * bijverzonnen. De titelgrenzen zijn die van titelchecker.js (Marktplaats/2dehands 60, eBay 80, Facebook 100);
 * Vinted heeft geen gemeten grens en wordt dus niet afgekapt. */
(function (root) {
  'use strict';
  var TAAL = {
    nl: { staat: 'Staat', maat: 'Maat', kleur: 'Kleur', afm: 'Afmetingen', merk: 'Merk', gebreken: 'Gebreken', extra: 'Erbij', vragen: 'Vragen? Stuur gerust een bericht.',
          st: { nieuw: 'Nieuw, met label', alsnieuw: 'Als nieuw', goed: 'Goed', redelijk: 'Redelijk', gebruikt: 'Duidelijk gebruikt' },
          lev: { verzenden: 'Verzenden is mogelijk.', ophalen: 'Ophalen is mogelijk.', beide: 'Verzenden of ophalen is mogelijk.' } },
    en: { staat: 'Condition', maat: 'Size', kleur: 'Colour', afm: 'Dimensions', merk: 'Brand', gebreken: 'Flaws', extra: 'Included', vragen: 'Questions? Send me a message.',
          st: { nieuw: 'New with tags', alsnieuw: 'Like new', goed: 'Good', redelijk: 'Fair', gebruikt: 'Well used' },
          lev: { verzenden: 'Shipping is possible.', ophalen: 'Pickup is possible.', beide: 'Shipping or pickup is possible.' } },
    fr: { staat: 'État', maat: 'Taille', kleur: 'Couleur', afm: 'Dimensions', merk: 'Marque', gebreken: 'Défauts', extra: 'Inclus', vragen: 'Des questions ? N’hésitez pas à m’écrire.',
          st: { nieuw: 'Neuf avec étiquette', alsnieuw: 'Comme neuf', goed: 'Bon état', redelijk: 'État correct', gebruikt: 'Usagé' },
          lev: { verzenden: 'Envoi possible.', ophalen: 'Retrait sur place possible.', beide: 'Envoi ou retrait sur place possible.' } },
    de: { staat: 'Zustand', maat: 'Größe', kleur: 'Farbe', afm: 'Maße', merk: 'Marke', gebreken: 'Mängel', extra: 'Dabei', vragen: 'Fragen? Schreib mir gerne.',
          st: { nieuw: 'Neu mit Etikett', alsnieuw: 'Wie neu', goed: 'Gut', redelijk: 'Akzeptabel', gebruikt: 'Gebraucht' },
          lev: { verzenden: 'Versand ist möglich.', ophalen: 'Abholung ist möglich.', beide: 'Versand oder Abholung ist möglich.' } }
  };
  var LIMIET = { marktplaats: 60, '2dehands': 60, ebay: 80, facebook: 100, vinted: null };
  function schoon(s) { return String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); }
  // Zelfde afkapregel als tools/titelchecker.js (een test houdt ze gelijk); die pagina-code laden we hier niet.
  function afkap(s, max) {
    s = schoon(s);
    var tekens = Array.from(s);
    if (tekens.length <= max) return s;
    var SEP = ' - ';
    if (s.indexOf(SEP) >= 0) {
      var delen = s.split(SEP);
      while (delen.length > 1 && Array.from(delen.join(SEP)).length > max) delen.pop();
      var kept = delen.join(SEP);
      if (Array.from(kept).length <= max) return kept;
    }
    var stuk = tekens.slice(0, max + 1).join('');
    var cut = stuk.lastIndexOf(' ');
    return cut > 0 ? stuk.slice(0, cut) : tekens.slice(0, max).join('');
  }

  // inv: product, merk, model, maat, kleur, staat, afm, extra, gebreken, levering. Geeft { titel, tekens, limiet, beschrijving }.
  function maak(inv, kanaal, taal) {
    var L = TAAL[taal] || TAAL.en;
    var delen = [inv.merk, inv.product, inv.model, inv.maat, inv.kleur].map(schoon).filter(Boolean);
    var titel = delen.join(' '), limiet = LIMIET[kanaal] == null ? null : LIMIET[kanaal];
    var afgekapt = limiet ? afkap(titel, limiet) : titel;
    var regels = [];
    var kop = [inv.product, inv.merk, inv.model].map(schoon).filter(Boolean).join(' ');
    if (kop) regels.push(kop, '');
    function regel(naam, w) { w = schoon(w); if (w) regels.push(naam + ': ' + w); }
    regel(L.staat, L.st[inv.staat] || '');
    regel(L.merk, inv.merk); regel(L.maat, schoon(inv.maat).replace(/^(maat|size|taille|gr[öo]ße|gr[öo]sse)\s+/i, '')); regel(L.kleur, inv.kleur); regel(L.afm, inv.afm);
    regel(L.gebreken, inv.gebreken); regel(L.extra, inv.extra);
    if (L.lev[inv.levering]) regels.push('', L.lev[inv.levering]);
    regels.push('', L.vragen);
    return { titel: afgekapt, volledig: titel, afgekapt: afgekapt !== titel, tekens: Array.from(afgekapt).length, limiet: limiet,
             beschrijving: regels.join('\n').replace(/\n{3,}/g, '\n\n').trim(), zonderGebreken: !schoon(inv.gebreken) };
  }
  var api = { maak: maak, afkap: afkap, TAAL: TAAL, LIMIET: LIMIET };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.Advertentietekst = api;
  if (typeof document === 'undefined') return;

  var G = root.ToolsGedeeld, nl = G.taal === 'nl';
  var T = nl ? { leeg: 'Vul minstens wat het is in (bijvoorbeeld "jas").', titel: 'Titel', beschr: 'Beschrijving', kopieer: 'Kopieer', ok: 'Gekopieerd', tekens: 'tekens',
                 afgekapt: 'Je titel was langer dan de grens van dit kanaal en is op een heel woord afgekapt.', geengrens: 'Voor Vinted is de titelgrens niet gemeten, houd hem kort.',
                 gebreken: 'Tip: vul gebreken in. Kopers vragen er altijd naar, en een eerlijke omschrijving voorkomt discussie achteraf.' }
             : { leeg: 'Fill in at least what it is (for example "jacket").', titel: 'Title', beschr: 'Description', kopieer: 'Copy', ok: 'Copied', tekens: 'characters',
                 afgekapt: 'Your title was longer than this channel allows and was cut at a whole word.', geengrens: 'We have not measured the title limit for Vinted, keep it short.',
                 gebreken: 'Tip: fill in flaws. Buyers always ask, and an honest description prevents arguments afterwards.' };
  var ids = ['at-kanaal', 'at-taal', 'at-product', 'at-merk', 'at-model', 'at-maat', 'at-kleur', 'at-staat', 'at-afm', 'at-extra', 'at-gebreken', 'at-levering'];
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function teken() {
    var inv = {};
    ['product', 'merk', 'model', 'maat', 'kleur', 'staat', 'afm', 'extra', 'gebreken', 'levering'].forEach(function (k) { inv[k] = G.el('at-' + k).value; });
    var uit = G.el('at-resultaten');
    if (!schoon(inv.product)) { uit.innerHTML = '<p class="kr-leeg">' + T.leeg + '</p>'; return; }
    var kanaal = G.el('at-kanaal').value, r = maak(inv, kanaal, G.el('at-taal').value);
    var html = '<h3>' + T.titel + '</h3><p class="kr-uit" id="at-uit-titel">' + esc(r.titel) + '</p>' +
      '<p class="kr-hint">' + (r.limiet ? r.tekens + ' / ' + r.limiet + ' ' + T.tekens : r.tekens + ' ' + T.tekens) + '</p>' +
      '<button type="button" class="kr-klein" data-uitsluiten data-kopieer="at-uit-titel">' + T.kopieer + '</button>' +
      '<h3>' + T.beschr + '</h3><pre class="kr-uit" id="at-uit-tekst">' + esc(r.beschrijving) + '</pre>' +
      '<button type="button" class="kr-klein" data-uitsluiten data-kopieer="at-uit-tekst">' + T.kopieer + '</button>';
    if (r.afgekapt) html += '<p class="meta">' + T.afgekapt + '</p>';
    if (!r.limiet) html += '<p class="meta">' + T.geengrens + '</p>';
    if (r.zonderGebreken) html += '<p class="meta">' + T.gebreken + '</p>';
    uit.innerHTML = html;
  }
  document.addEventListener('click', function (ev) {
    var id = ev.target.getAttribute && ev.target.getAttribute('data-kopieer');
    if (!id) return;
    var tekst = G.el(id).textContent, knop = ev.target;
    function klaar() { var oud = knop.textContent; knop.textContent = T.ok; setTimeout(function () { knop.textContent = oud; }, 1800); }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(tekst).then(klaar);
  });
  G.bijWijziging(ids, teken);
})(typeof window !== 'undefined' ? window : globalThis);
