/* DAC7-check. Regel (Belastingdienst, gecontroleerd 28-10-2026): voor goederen melden platforms
 * verkopers die in een kalenderjaar 30 keer of vaker verkopen, of voor meer dan 2.000 euro, per platform. */
(function (root) {
  'use strict';
  var PLATFORMS = [
    { key: 'marktplaats', naam: 'Marktplaats' }, { key: '2dehands', naam: '2dehands' },
    { key: 'vinted', naam: 'Vinted' }, { key: 'ebay', naam: 'eBay' }, { key: 'anders', naam: null }
  ];
  var GRENS_AANTAL = 30, GRENS_OMZET = 2000;
  // 'gemeld' | 'dichtbij' (vanaf 80% van een grens) | 'onder' | null (niets ingevuld)
  function beoordeel(aantal, omzet) {
    if (aantal == null && omzet == null) return null;
    aantal = aantal || 0; omzet = omzet || 0;
    if (aantal >= GRENS_AANTAL || omzet > GRENS_OMZET) return 'gemeld';
    if (aantal >= GRENS_AANTAL * 0.8 || omzet >= GRENS_OMZET * 0.8) return 'dichtbij';
    return 'onder';
  }
  var api = { GRENS_AANTAL: GRENS_AANTAL, GRENS_OMZET: GRENS_OMZET, beoordeel: beoordeel };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.Dac7 = api;
  if (typeof document === 'undefined') return;

  var G = root.ToolsGedeeld, nl = G.taal === 'nl';
  var T = nl ? { fout: 'Dit is geen getal.', gemeld: 'Wordt doorgegeven', dichtbij: 'Dichtbij de grens', onder: 'Onder de grens', anders: 'Een ander platform', leeg: 'Vul bij minstens één platform je verkopen in.', slot: 'Doorgegeven betekent niet dat je belasting betaalt. Het platform stuurt je gegevens naar de Belastingdienst; of je ondernemer bent en winst moet opgeven, is een aparte vraag.' }
             : { fout: 'This is not a number.', gemeld: 'Gets reported', dichtbij: 'Close to the limit', onder: 'Under the limit', anders: 'Another platform', leeg: 'Fill in your sales for at least one platform.', slot: 'Being reported does not mean you pay tax. The platform sends your data to the tax authority; whether you count as a business and must declare profit is a separate question.' };
  var ids = [];
  PLATFORMS.forEach(function (p) { ids.push('d7-' + p.key + '-n', 'd7-' + p.key + '-o'); });
  function teken() {
    var rijen = [], iets = false;
    PLATFORMS.forEach(function (p) {
      var n = G.veld('d7-' + p.key + '-n', T.fout), o = G.veld('d7-' + p.key + '-o', T.fout);
      if (isNaN(n) || isNaN(o)) return;
      var b = beoordeel(n, o);
      if (!b) return;
      iets = true;
      var klasse = b === 'gemeld' ? 'kr-slecht' : b === 'dichtbij' ? 'kr-neg' : 'kr-ok';
      rijen.push('<tr><th scope="row">' + (p.naam || T.anders) + '</th><td class="kr-num">' + G.getal(n || 0) + ' · ' + G.euro(o || 0) +
        '</td><td class="' + klasse + '">' + T[b] + '</td></tr>');
    });
    G.el('d7-resultaten').innerHTML = iets
      ? '<div class="table-wrap"><table class="kr-tabel"><tbody>' + rijen.join('') + '</tbody></table></div><p class="meta">' + T.slot + '</p>'
      : '<p class="kr-leeg">' + T.leeg + '</p>';
  }
  G.bijWijziging(ids, teken);
})(typeof window !== 'undefined' ? window : globalThis);
