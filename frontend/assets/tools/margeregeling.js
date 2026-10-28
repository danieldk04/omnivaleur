/* Btw-margeregeling: btw wordt berekend over de marge (verkoop min inkoop), en de marge is
 * inclusief btw, dus de btw is 21/121 van de marge. Gewone btw is 21/121 van de verkoopprijs
 * (prijs inclusief btw). Alleen 21%; geen btw bij verlies. */
(function (root) {
  'use strict';
  var TARIEF = 0.21;
  function marge(inkoop, verkoop) { return verkoop - inkoop; }
  function btwMarge(inkoop, verkoop) { var m = marge(inkoop, verkoop); return m > 0 ? m * TARIEF / (1 + TARIEF) : 0; }
  function btwGewoon(verkoop) { return verkoop * TARIEF / (1 + TARIEF); }
  var api = { TARIEF: TARIEF, marge: marge, btwMarge: btwMarge, btwGewoon: btwGewoon };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.Margeregeling = api;
  if (typeof document === 'undefined') return;

  var G = root.ToolsGedeeld, nl = G.taal === 'nl';
  var T = nl ? { fout: 'Dit is geen bedrag.', leeg: 'Vul je inkoopprijs en verkoopprijs in.', marge: 'Marge (verkoop min inkoop)', btwM: 'Btw over de marge (margeregeling)', btwG: 'Btw bij gewone btw over de hele prijs', scheelt: 'Verschil', na: 'Marge na btw (margeregeling)', verlies: 'Geen marge, dus geen btw af te dragen.' }
             : { fout: 'This is not an amount.', leeg: 'Enter your purchase price and selling price.', marge: 'Margin (selling minus purchase)', btwM: 'VAT on the margin (margin scheme)', btwG: 'VAT on the full price (normal VAT)', scheelt: 'Difference', na: 'Margin after VAT (margin scheme)', verlies: 'No margin, so no VAT to pay.' };
  function teken() {
    var i = G.veld('mr-inkoop', T.fout), v = G.veld('mr-verkoop', T.fout), uit = G.el('mr-resultaten');
    if (i === null || v === null || isNaN(i) || isNaN(v)) { uit.innerHTML = '<p class="kr-leeg">' + T.leeg + '</p>'; return; }
    var m = marge(i, v), bm = btwMarge(i, v), bg = btwGewoon(v);
    uit.innerHTML = '<div class="table-wrap"><table class="kr-tabel"><tbody>' +
      '<tr><th scope="row">' + T.marge + '</th><td class="kr-num' + (m < 0 ? ' kr-neg' : '') + '">' + G.euro(m) + '</td></tr>' +
      '<tr><th scope="row">' + T.btwM + '</th><td class="kr-num kr-groot">' + G.euro(bm) + '</td></tr>' +
      '<tr><th scope="row">' + T.btwG + '</th><td class="kr-num">' + G.euro(bg) + '</td></tr>' +
      '<tr><th scope="row">' + T.scheelt + '</th><td class="kr-num kr-ok">' + G.euro(bg - bm) + '</td></tr>' +
      '<tr><th scope="row">' + T.na + '</th><td class="kr-num">' + G.euro(m - bm) + '</td></tr></tbody></table></div>' +
      (m <= 0 ? '<p class="meta">' + T.verlies + '</p>' : '');
  }
  G.bijWijziging(['mr-inkoop', 'mr-verkoop'], teken);
})(typeof window !== 'undefined' ? window : globalThis);
