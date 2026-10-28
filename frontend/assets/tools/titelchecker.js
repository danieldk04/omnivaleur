/* Titel-tekenteller. Grenzen: Marktplaats en 2dehands 60 (extension/content/marktplaats.js
 * en tweedehands.js), eBay 80 (backend/platforms/ebay.py), Facebook Marketplace 100
 * (extension/content/facebook.js). Gecontroleerd 28-10-2026. Vinted staat er bewust niet
 * in: de grens daar is niet gemeten. */
(function (root) {
  'use strict';
  var KANALEN = [
    { key: 'marktplaats', naam: 'Marktplaats', max: 60 },
    { key: '2dehands', naam: '2dehands', max: 60 },
    { key: 'ebay', naam: 'eBay', max: 80 },
    { key: 'facebook', naam: 'Facebook Marketplace', max: 100 }
  ];
  function schoon(s) { return String(s || '').replace(/\s*[\r\n]+\s*/g, ' '); }
  function tel(s) { return Array.from(schoon(s)).length; }
  // Zo kapt Omnivaleur af (smartTrunc in extension/content/shared.js): eerst hele " - "-stukken, anders op een heel woord.
  function afkap(s, max) {
    s = schoon(s).trim();
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
  var api = { KANALEN: KANALEN, tel: tel, afkap: afkap };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.Titelchecker = api;
  if (typeof document === 'undefined') return;

  var G = root.ToolsGedeeld, nl = G.taal === 'nl';
  var T = nl ? { tekens: 'tekens', over: 'te lang', past: 'past', toon: 'Zo kapt Omnivaleur hem af:', leeg: 'Typ of plak hierboven je titel.', nog: 'nog' }
             : { tekens: 'characters', over: 'too long', past: 'fits', toon: 'Omnivaleur would cut it to:', leeg: 'Type or paste your title above.', nog: 'left' };
  function teken() {
    var s = G.el('tc-titel').value, n = tel(s), uit = G.el('tc-resultaten');
    G.el('tc-teller').textContent = n + ' ' + T.tekens;
    if (!n) { uit.innerHTML = '<p class="kr-leeg">' + T.leeg + '</p>'; return; }
    uit.innerHTML = '<div class="table-wrap"><table class="kr-tabel"><tbody>' + KANALEN.map(function (k) {
      var over = n > k.max, pct = Math.min(100, Math.round(n / k.max * 100));
      var status = over ? '<span class="kr-slecht">' + (n - k.max) + ' ' + T.over + '</span>' : '<span class="kr-ok">' + (k.max - n) + ' ' + T.nog + '</span>';
      var kap = over ? '<div class="kr-hint">' + T.toon + ' <em></em></div>' : '';
      return '<tr data-k="' + k.key + '"><th scope="row">' + k.naam + '</th><td class="kr-num">' + n + ' / ' + k.max +
        '<div class="kr-balk"><i class="' + (over ? 'over' : '') + '" style="width:' + pct + '%"></i></div></td><td>' + status + kap + '</td></tr>';
    }).join('') + '</tbody></table></div>';
    KANALEN.forEach(function (k) {
      var em = uit.querySelector('tr[data-k="' + k.key + '"] em');
      if (em) em.textContent = afkap(s, k.max);   // textContent: nooit html uit een titel
    });
  }
  G.bijWijziging(['tc-titel'], teken);
})(typeof window !== 'undefined' ? window : globalThis);
