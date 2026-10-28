/* Afprijsplanner. Zelfde ladder als "Stale stock" in het dashboard (frontend/app.html:
 * STALE_LADDER, stalePctFor, round99): -5% vanaf 30 dagen, -10% vanaf 60, -15% vanaf 90,
 * -20% vanaf 180, afgerond op ,99, en nooit onder de inkoopprijs. */
(function (root) {
  'use strict';
  var LADDER = [[180, 0.20], [90, 0.15], [60, 0.10], [30, 0.05]];
  function pct(dagen) { for (var i = 0; i < LADDER.length; i++) if (dagen >= LADDER[i][0]) return LADDER[i][1]; return 0; }
  function round99(v) { return Math.max(0.99, Math.round(v) - 0.01); }
  // { pct, voorstel (null = geen voorstel), onderInkoop }
  function advies(prijs, dagen, inkoop) {
    var p = pct(dagen), voorstel = p ? round99(prijs * (1 - p)) : null, onder = false;
    if (voorstel !== null && inkoop != null && voorstel < inkoop) { onder = true; voorstel = null; }
    return { pct: p, voorstel: voorstel, onderInkoop: onder };
  }
  var api = { LADDER: LADDER, pct: pct, round99: round99, advies: advies };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.Afprijsplanner = api;
  if (typeof document === 'undefined') return;

  var G = root.ToolsGedeeld, nl = G.taal === 'nl';
  var T = nl ? { fout: 'Dit is geen getal.', leeg: 'Vul de huidige prijs en het aantal dagen in.', nog: 'Nog niet afprijzen: onder 30 dagen online verandert er niets.', voorstel: 'Voorgestelde nieuwe prijs', korting: 'korting', onder: 'Afprijzen zou onder je inkoopprijs komen. Laat de prijs staan of bied hem op een ander kanaal aan.', dagen: 'dagen', trap: 'De ladder' }
             : { fout: 'This is not a number.', leeg: 'Enter the current price and the days online.', nog: 'Do not drop the price yet: under 30 days online nothing changes.', voorstel: 'Suggested new price', korting: 'off', onder: 'Dropping the price would go below your purchase price. Leave it or offer it on another marketplace.', dagen: 'days', trap: 'The ladder' };
  function teken() {
    var p = G.veld('ap-prijs', T.fout), d = G.veld('ap-dagen', T.fout), i = G.veld('ap-inkoop', T.fout), uit = G.el('ap-resultaten');
    if (p === null || d === null || isNaN(p) || isNaN(d) || isNaN(i)) { uit.innerHTML = '<p class="kr-leeg">' + T.leeg + '</p>'; return; }
    var a = advies(p, Math.floor(d), i), tekst;
    if (!a.pct) tekst = '<p>' + T.nog + '</p>';
    else if (a.onderInkoop) tekst = '<p class="kr-neg">' + T.onder + '</p>';
    else tekst = '<table class="kr-tabel"><tbody><tr><th scope="row">' + T.voorstel + '</th><td class="kr-num kr-groot">' + G.euro(a.voorstel) + '</td><td>' + Math.round(a.pct * 100) + '% ' + T.korting + '</td></tr></tbody></table>';
    uit.innerHTML = tekst;
  }
  G.bijWijziging(['ap-prijs', 'ap-dagen', 'ap-inkoop'], teken);
})(typeof window !== 'undefined' ? window : globalThis);
