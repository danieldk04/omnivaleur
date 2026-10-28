/* Winstmarge en opslag. Marge = winst / verkoopprijs, opslag = winst / inkoopprijs.
 * Winst = verkoopprijs min kanaalkosten (percentage van de verkoopprijs) min inkoop min vaste kosten. */
(function (root) {
  'use strict';
  function afrond(n) { return Math.round(n * 100) / 100; }
  // fee en doelen zijn breuken (0.1 = 10%). Geeft null als er niet te rekenen valt.
  function bereken(inkoop, verkoop, kosten, fee) {
    if (!(verkoop > 0) || inkoop == null) return null;
    kosten = kosten || 0; fee = fee || 0;
    var winst = verkoop * (1 - fee) - inkoop - kosten;
    return { winst: afrond(winst), marge: winst / verkoop, opslag: inkoop > 0 ? winst / inkoop : null };
  }
  // Prijs waarbij de winst precies het gewenste deel van de verkoopprijs is.
  function prijsVoorMarge(inkoop, kosten, fee, marge) {
    var noemer = 1 - (fee || 0) - marge;
    if (!(noemer > 0) || marge < 0) return null;
    return Math.ceil(((inkoop + (kosten || 0)) / noemer) * 100 - 1e-9) / 100;
  }
  // Prijs waarbij de winst het gewenste deel van de inkoopprijs is.
  function prijsVoorOpslag(inkoop, kosten, fee, opslag) {
    var noemer = 1 - (fee || 0);
    if (!(noemer > 0) || opslag < 0 || !(inkoop > 0)) return null;
    return Math.ceil(((inkoop * (1 + opslag) + (kosten || 0)) / noemer) * 100 - 1e-9) / 100;
  }
  var api = { bereken: bereken, prijsVoorMarge: prijsVoorMarge, prijsVoorOpslag: prijsVoorOpslag };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.Winstmarge = api;
  if (typeof document === 'undefined') return;

  var G = root.ToolsGedeeld, nl = G.taal === 'nl';
  var T = nl ? { fout: 'Dit is geen getal.', winst: 'Winst', marge: 'Marge (van de verkoopprijs)', opslag: 'Opslag (op de inkoopprijs)',
                 doelMarge: 'Prijs voor je gewenste marge', doelOpslag: 'Prijs voor je gewenste opslag', verlies: 'Verlies',
                 leeg: 'Vul je inkoop en verkoopprijs in, of je inkoop en een gewenste marge.', onmogelijk: 'Niet te halen: kosten en marge samen zijn 100% of meer.',
                 uitleg: 'Marge en opslag zijn niet hetzelfde. Dezelfde winst geeft een lager marge- dan opslagpercentage.' }
             : { fout: 'This is not a number.', winst: 'Profit', marge: 'Margin (of the selling price)', opslag: 'Markup (on the purchase price)',
                 doelMarge: 'Price for your target margin', doelOpslag: 'Price for your target markup', verlies: 'Loss',
                 leeg: 'Fill in your purchase and selling price, or your purchase price and a target margin.', onmogelijk: 'Not possible: costs and margin together are 100% or more.',
                 uitleg: 'Margin and markup are not the same. The same profit gives a lower margin than markup percentage.' };
  function pct(x) { return x == null ? '-' : new Intl.NumberFormat(nl ? 'nl-NL' : 'en-GB', { maximumFractionDigits: 1 }).format(x * 100) + '%'; }
  var ids = ['wm-inkoop', 'wm-verkoop', 'wm-kosten', 'wm-fee', 'wm-doelmarge', 'wm-doelopslag'];
  function teken() {
    var w = {}, slecht = false;
    ids.forEach(function (id) { w[id] = G.veld(id, T.fout); if (isNaN(w[id])) slecht = true; });
    var uit = G.el('wm-resultaten');
    if (slecht) return;
    var fee = w['wm-fee'] == null ? 0 : w['wm-fee'] / 100;
    var delen = [], inkoop = w['wm-inkoop'];
    var r = inkoop != null && w['wm-verkoop'] ? bereken(inkoop, w['wm-verkoop'], w['wm-kosten'], fee) : null;
    if (r) {
      delen.push('<div class="kr-kpis"><div class="kr-kpi"><span>' + (r.winst < 0 ? T.verlies : T.winst) + '</span><strong class="' + (r.winst < 0 ? 'kr-neg' : '') + '">' + G.euro(r.winst) + '</strong></div>' +
        '<div class="kr-kpi"><span>' + T.marge + '</span><strong>' + pct(r.marge) + '</strong></div>' +
        '<div class="kr-kpi"><span>' + T.opslag + '</span><strong>' + pct(r.opslag) + '</strong></div></div><p class="meta">' + T.uitleg + '</p>');
    }
    var rijen = [];
    if (inkoop != null && w['wm-doelmarge'] != null) {
      var p = prijsVoorMarge(inkoop, w['wm-kosten'], fee, w['wm-doelmarge'] / 100);
      rijen.push('<tr><th scope="row">' + T.doelMarge + ' (' + pct(w['wm-doelmarge'] / 100) + ')</th><td class="kr-num kr-groot">' + (p == null ? T.onmogelijk : G.euro(p)) + '</td></tr>');
    }
    if (inkoop != null && w['wm-doelopslag'] != null) {
      var q = prijsVoorOpslag(inkoop, w['wm-kosten'], fee, w['wm-doelopslag'] / 100);
      rijen.push('<tr><th scope="row">' + T.doelOpslag + ' (' + pct(w['wm-doelopslag'] / 100) + ')</th><td class="kr-num kr-groot">' + (q == null ? T.onmogelijk : G.euro(q)) + '</td></tr>');
    }
    if (rijen.length) delen.push('<div class="table-wrap"><table class="kr-tabel"><tbody>' + rijen.join('') + '</tbody></table></div>');
    uit.innerHTML = delen.length ? delen.join('') : '<p class="kr-leeg">' + T.leeg + '</p>';
  }
  G.bijWijziging(ids, teken);
})(typeof window !== 'undefined' ? window : globalThis);
