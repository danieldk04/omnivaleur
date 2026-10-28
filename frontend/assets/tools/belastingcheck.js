/* Belastingcheck voor online verkopen. Bron: Belastingdienst, "Ik verkoop spullen op een online
 * platform. Moet ik inkomstenbelasting betalen?" (gecontroleerd 28-10-2026):
 *  - spullen inkopen en met winst doorverkopen is een bron van inkomen, er geldt geen minimumbedrag aan winst;
 *  - verkopen als hobby of in de privésfeer is geen bron van inkomen;
 *  - verkopen voor minder dan je betaalde is geen bron van inkomen;
 *  - verpakkings- en verzendkosten zijn aftrekbaar.
 * De uitslag is een richting en geen advies; bij twijfel beslist de Belastingdienst. */
(function (root) {
  'use strict';
  // herkomst: 'eigen' | 'inkoop' | 'mix'; prijs: 'minder' | 'meer'. inkoop/omzet/kosten zijn bedragen of null.
  function beoordeel(a) {
    var uit = { uitslag: null, winst: null };
    if (!a || !a.herkomst) return uit;
    if (a.omzet != null || a.inkoop != null) uit.winst = Math.round(((a.omzet || 0) - (a.inkoop || 0) - (a.kosten || 0)) * 100) / 100;
    if (a.herkomst === 'eigen') uit.uitslag = 'geen';
    else if (a.herkomst === 'mix') uit.uitslag = 'twijfel';
    else if (a.prijs === 'minder') uit.uitslag = 'geen';
    else if (uit.winst != null && uit.winst <= 0) uit.uitslag = 'geen';
    else uit.uitslag = 'wel';
    return uit;
  }
  var api = { beoordeel: beoordeel };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.Belastingcheck = api;
  if (typeof document === 'undefined') return;

  var G = root.ToolsGedeeld, nl = G.taal === 'nl';
  var T = nl ? {
    fout: 'Dit is geen getal.', leeg: 'Kies hierboven waar je spullen vandaan komen.',
    geen: ['Waarschijnlijk geen bron van inkomen', 'Volgens de Belastingdienst is verkopen als hobby, in de privésfeer of voor minder dan je betaalde geen bron van inkomen. Je hoeft er dan geen inkomstenbelasting over te betalen.'],
    wel: ['Waarschijnlijk wel een bron van inkomen', 'Spullen inkopen om ze met winst door te verkopen is volgens de Belastingdienst een bron van inkomen. Er geldt geen minimumbedrag aan winst.'],
    twijfel: ['Gemengd: splits het uit elkaar', 'Verkoop je eigen spullen en koop je ook in om door te verkopen, dan telt alleen dat tweede deel. Reken ze apart door met deze check, en neem bij twijfel contact op met je belastingkantoor.'],
    winst: 'Winst volgens jouw cijfers', verlies: 'Verlies volgens jouw cijfers',
    wat: 'Wat je kunt doen',
    stappen: ['Bewaar je inkoop- en verkoopbewijzen, zodat je je cijfers kunt laten zien.', 'Verpakkings- en verzendkosten mag je aftrekken, dat noemt de Belastingdienst zelf.', 'Je winst hoort in je aangifte inkomstenbelasting. Vraag je belastingkantoor hoe je dat het beste doet.'],
    los: 'Los hiervan: Marktplaats, Vinted en eBay geven je door bij 30 verkopen of meer, of meer dan € 2.000 omzet, per platform. Dat zegt niets over belasting. ',
    dac: 'DAC7-check', btw: 'Voor btw gelden aparte regels. ', marge: 'Margeregeling rekenhulp',
    slot: 'Dit is een richting en geen belastingadvies. De Belastingdienst beslist, en je situatie kan afwijken.'
  } : {
    fout: 'This is not a number.', leeg: 'Choose above where your items come from.',
    geen: ['Probably not a source of income', 'According to the Belastingdienst, selling as a hobby, in your private life or for less than you paid is not a source of income. You do not pay income tax on it.'],
    wel: ['Probably a source of income', 'Buying items to resell at a profit is a source of income according to the Belastingdienst. There is no minimum amount of profit.'],
    twijfel: ['Mixed: separate the two', 'If you sell your own things and also buy items to resell, only the second part counts. Check them separately with this tool, and contact your tax office if in doubt.'],
    winst: 'Profit based on your numbers', verlies: 'Loss based on your numbers',
    wat: 'What you can do',
    stappen: ['Keep your purchase and sales receipts so you can show your numbers.', 'You may deduct packaging and shipping costs, the Belastingdienst says so itself.', 'Your profit belongs in your income tax return. Ask your tax office how to do that best.'],
    los: 'Separately: Marktplaats, Vinted and eBay report you at 30 sales or more, or more than EUR 2,000 revenue, per platform. That says nothing about tax. ',
    dac: 'DAC7 checker', btw: 'VAT has separate rules. ', marge: 'VAT margin scheme calculator',
    slot: 'This is a direction, not tax advice. The Belastingdienst decides, and your situation may differ.'
  };
  var ids = ['bc-herkomst', 'bc-prijs', 'bc-inkoop', 'bc-omzet', 'bc-kosten'];
  function teken() {
    var w = {}, slecht = false;
    ['bc-inkoop', 'bc-omzet', 'bc-kosten'].forEach(function (id) { w[id] = G.veld(id, T.fout); if (isNaN(w[id])) slecht = true; });
    if (slecht) return;
    var herkomst = G.el('bc-herkomst').value;
    var uit = G.el('bc-resultaten');
    if (!herkomst) { uit.innerHTML = '<p class="kr-leeg">' + T.leeg + '</p>'; return; }
    var r = beoordeel({ herkomst: herkomst, prijs: G.el('bc-prijs').value, inkoop: w['bc-inkoop'], omzet: w['bc-omzet'], kosten: w['bc-kosten'] });
    var k = r.uitslag === 'geen' ? 'goed' : r.uitslag === 'wel' ? 'let' : 'twijfel';
    var tekst = T[r.uitslag], html = '<div class="kr-uitslag ' + k + '"><strong>' + tekst[0] + '</strong><p>' + tekst[1] + '</p></div>';
    if (r.winst != null && herkomst !== 'eigen') html += '<p><strong>' + (r.winst < 0 ? T.verlies : T.winst) + ':</strong> ' + G.euro(r.winst) + '</p>';
    if (r.uitslag === 'wel') html += '<h3>' + T.wat + '</h3><ul>' + T.stappen.map(function (s) { return '<li>' + s + '</li>'; }).join('') + '</ul>';
    html += '<p class="meta">' + T.los + T.btw + '</p><p class="meta">' + T.slot + '</p>';
    uit.innerHTML = html;
  }
  G.bijWijziging(ids, teken);
})(typeof window !== 'undefined' ? window : globalThis);
