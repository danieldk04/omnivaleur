/* Omnivaleur vertaallaag: het dashboard in het Nederlands, zonder de code om te bouwen.
 *
 * Alles wordt in het Engels geschreven, zoals altijd. Dit script vertaalt wat er
 * op het scherm verschijnt: elke tekst en elk title/placeholder-veld wordt
 * opgezocht in /i18n/nl.json. Ook tekst die later verschijnt (een lijst die
 * herladen wordt, een melding, een venster) wordt direct vertaald, doordat een
 * MutationObserver elke wijziging aan de pagina ziet.
 *
 * Woordenboek:
 *   "Save": "Opslaan"                      letterlijk
 *   "{0} items selected": "{0} items geselecteerd"   patroon; {0} is een
 *                                           getal, naam of stuk tekst dat blijft
 *                                           staan (en zelf vertaald wordt als
 *                                           het ook in het woordenboek staat)
 *   "{0} day{1} left": "nog {0} {1|dag|dagen}"      meervoud: {1} is "" of "s";
 *                                           leeg geeft het eerste woord
 *
 * Wat NIET vertaald wordt: alles binnen translate="no" of class="notranslate"
 * (titels en omschrijvingen van klanten, merken, berichten van kopers), de
 * inhoud van invulvelden (input-waarden, textarea, contenteditable: dat is
 * data van de klant), script en style. Alleen de knopteksten van
 * <input type=button|submit|reset> en de placeholder (de grijze hulptekst in
 * een leeg veld) worden vertaald; wat de klant typt of wat wij in een veld
 * zetten nooit.
 *
 * Tekst die er Engels uitziet maar niet in het woordenboek staat wordt gemeld
 * aan /api/i18n/ontbrekend, zodat de volgende sessie hem kan toevoegen.
 * Zie scripts/i18n_extract.py en tests/test_i18n_compleet.py.
 */
(function () {
  'use strict';

  var OPSLAG = 'omni_taal';
  var TALEN = ['en', 'nl'];
  // Sinds 24-09-2026 (Daniel: "knop voor iedereen") ziet elke klant EN · NL.
  // Op false zetten verbergt hem weer voor wie nooit zelf een taal koos.
  var KNOP_VOOR_IEDEREEN = true;

  function kiesTaal() {
    try {
      var q = new URLSearchParams(location.search).get('taal');
      if (TALEN.indexOf(q) >= 0) { localStorage.setItem(OPSLAG, q); return q; }
      var t = localStorage.getItem(OPSLAG);
      if (TALEN.indexOf(t) >= 0) return t;
    } catch (e) { /* geen opslag: Engels */ }
    // Bewust geen automatische keuze op browsertaal (Daniel, 24-09-2026): het
    // Nederlands gaat alleen aan voor wie zelf op NL klikt, tot het bewezen is.
    return 'en';
  }

  var taal = kiesTaal();
  var api = {
    taal: taal,
    t: function (s) { return s; },
    zetTaal: function (t) {
      if (TALEN.indexOf(t) < 0) return;
      try { localStorage.setItem(OPSLAG, t); } catch (e) { /* alleen deze sessie */ }
      location.reload();
    },
    klaar: Promise.resolve(),
  };
  window.OmniI18n = api;

  // Taalknop: elk element met data-taalkeuze krijgt "EN · NL". Staat bewust
  // buiten de vertaling (translate="no"), zodat hij in beide talen gelijk is.
  function knopZichtbaar() {
    if (KNOP_VOOR_IEDEREEN) return true;
    try { return localStorage.getItem(OPSLAG) !== null; } catch (e) { return taal !== 'en'; }
  }

  function tekenKeuze() {
    var plekken = document.querySelectorAll('[data-taalkeuze]');
    if (!knopZichtbaar()) {
      for (var k = 0; k < plekken.length; k++) plekken[k].style.display = 'none';
      return;
    }
    for (var i = 0; i < plekken.length; i++) {
      var el = plekken[i];
      el.setAttribute('translate', 'no');
      el.innerHTML = '';
      [['en', 'EN', 'English'], ['nl', 'NL', 'Nederlands']].forEach(function (t, j) {
        if (j) el.appendChild(document.createTextNode(' · '));
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = t[1];
        b.title = t[2];
        b.setAttribute('aria-pressed', String(taal === t[0]));
        b.style.cssText = 'background:none;border:none;padding:2px 3px;cursor:pointer;font:inherit;color:inherit;'
          + (taal === t[0] ? 'font-weight:700;text-decoration:underline' : 'opacity:.7');
        b.onclick = function () {
          if (taal !== t[0]) api.zetTaal(t[0]);
          else { try { localStorage.setItem(OPSLAG, t[0]); } catch (e) { /* niets */ } weg(); }
        };
        el.appendChild(b);
      });
    }
    tip();
  }

  // Eenmalige wijzer naar EN · NL in het dashboard (Daniel, 24-09-2026), voor
  // wie nog nooit zelf een taal koos. Weg na een klik op EN, NL of het kruisje,
  // en komt daarna niet terug. Tweetalig en buiten de vertaling, want wie hem
  // ziet staat per definitie nog in het Engels.
  // z-index 150: boven de zijbalk (100), onder elk venster van het dashboard
  // (200 en hoger), zodat hij nooit over het betaalslot of een melding ligt.
  var TIP = 'omni_taal_tip';
  var PIJL = 'position:absolute;width:14px;height:14px;background:#2563eb;transform:rotate(45deg);';
  var tipEl = null;
  function weg() {
    try { localStorage.setItem(TIP, '1'); } catch (e) { /* niets */ }
    if (tipEl) { tipEl.remove(); tipEl = null; }
    window.removeEventListener('resize', plaats);
  }
  function plaats() {
    var doel = document.querySelector('.sidebar-bottom [data-taalkeuze]');
    if (!tipEl || !doel) return;
    var r = doel.getBoundingClientRect();
    // Zijbalk dicht (telefoon): wachten tot hij in beeld is, niets wegzetten.
    tipEl.style.display = r.right > 40 && r.height ? 'block' : 'none';
    var pijl = tipEl.firstChild;
    if (window.innerWidth - r.right >= 300) {
      // Rechts naast de knop. De knop staat onderaan: de wijzer mag niet onder
      // de rand wegvallen, en het pijltje blijft naar het midden van de knop wijzen.
      var midden = r.top + r.height / 2;
      var boven = Math.max(8, Math.min(midden - 24, window.innerHeight - tipEl.offsetHeight - 12));
      tipEl.style.left = (r.right + 14) + 'px';
      tipEl.style.top = boven + 'px';
      pijl.style.cssText = PIJL + 'left:-7px;top:' + (midden - boven - 7) + 'px';
    } else {
      // Te smal (telefoon, zijbalk open): boven de knop, pijltje omlaag.
      var links = Math.max(8, r.left);
      tipEl.style.left = links + 'px';
      tipEl.style.top = Math.max(8, r.top - tipEl.offsetHeight - 12) + 'px';
      pijl.style.cssText = PIJL + 'bottom:-7px;left:' + Math.max(12, Math.min(r.left + 30 - links, 230)) + 'px';
    }
  }
  function tip() {
    if (!knopZichtbaar() || tipEl) return;
    try {
      if (localStorage.getItem(OPSLAG) !== null || localStorage.getItem(TIP)) return;
    } catch (e) { return; }
    if (!document.querySelector('.sidebar-bottom [data-taalkeuze]')) return;
    tipEl = document.createElement('div');
    tipEl.setAttribute('translate', 'no');
    tipEl.setAttribute('role', 'status');
    tipEl.style.cssText = 'position:fixed;z-index:150;width:264px;max-width:calc(100vw - 16px);box-sizing:border-box;background:#2563eb;color:#fff;'
      + 'border-radius:10px;padding:11px 32px 11px 14px;font:13px/1.4 system-ui,-apple-system,sans-serif;'
      + 'box-shadow:0 8px 24px rgba(15,23,42,.25)';
    tipEl.innerHTML = '<div></div>'
      + '<b>Nieuw: Omnivaleur in het Nederlands.</b> Klik op NL.'
      + '<div style="opacity:.75;font-size:11.5px;margin-top:4px">Prefer English? Click EN and we won’t ask again.</div>'
      + '<button type="button" aria-label="Sluiten" style="position:absolute;top:6px;right:8px;background:none;'
      + 'border:none;color:#fff;font-size:17px;line-height:1;cursor:pointer;opacity:.8">×</button>';
    tipEl.querySelector('button').onclick = weg;
    document.body.appendChild(tipEl);
    plaats();
    window.addEventListener('resize', plaats);
    // Op een telefoon schuift de zijbalk open en dicht; de wijzer gaat mee.
    var zijbalk = document.querySelector('.sidebar');
    if (zijbalk) zijbalk.addEventListener('transitionend', plaats);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', tekenKeuze);
  else tekenKeuze();

  if (taal === 'en') return;

  document.documentElement.lang = taal;

  // Tot het woordenboek er is blijft de pagina onzichtbaar, anders flitst het
  // Engels even voorbij. Komt het woordenboek niet binnen 2,5 s, dan toont hij
  // de pagina gewoon in het Engels in plaats van leeg te blijven.
  var wacht = document.createElement('style');
  wacht.textContent = 'html.i18n-laden body{visibility:hidden}';
  document.head.appendChild(wacht);
  document.documentElement.classList.add('i18n-laden');
  function toon() { document.documentElement.classList.remove('i18n-laden'); }
  var noodrem = setTimeout(toon, 2500);

  // ── Woordenboek ────────────────────────────────────────────────────────
  var exact = new Map();
  var patronen = [];            // {re, nl, volgorde, letterlijk, vast, meervoud}
  var perBegin = new Map();     // eerste woord -> [patroon]
  var perEind = new Map();      // laatste woord -> [patroon]
  var overige = [];             // begint en eindigt met een plek
  var cache = new Map();

  function norm(s) { return s.replace(/\s+/g, ' ').trim(); }
  function esc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function eersteWoord(s) { return s.split(' ')[0]; }
  function laatsteWoord(s) { var w = s.split(' '); return w[w.length - 1]; }

  function laad(wb) {
    Object.keys(wb).forEach(function (en) {
      var nl = wb[en];
      if (typeof nl !== 'string' || !nl) return;
      if (!/\{\d+\}/.test(en)) { exact.set(en, nl); return; }
      var delen = en.split(/(\{\d+\})/);
      var volgorde = [];
      var letterlijk = {};
      var bron = delen.map(function (d, i) {
        var m = /^\{(\d+)\}$/.exec(d);
        if (m) {
          volgorde.push(+m[1]);
          // Tussen aanhalingstekens staat data van de klant ("{0}" = een
          // titel): die wordt nooit vertaald, ook niet als hij toevallig
          // gelijk is aan een woord uit het woordenboek.
          if (/["'“‘]$/.test(delen[i - 1] || '') || /^["'”’]/.test(delen[i + 1] || '')) letterlijk[m[1]] = true;
          return '(.*?)';
        }
        return esc(d).replace(/ /g, '\\s+');
      }).join('');
      var p = { re: new RegExp('^' + bron + '$'), nl: nl, volgorde: volgorde, letterlijk: letterlijk,
                vast: en.replace(/\{\d+\}/g, '').length, meervoud: {} };
      nl.replace(/\{(\d+)\|/g, function (_, nr) { p.meervoud[nr] = true; return _; });
      patronen.push(p);
      // Indexeren op het eerste of laatste woord, maar alleen als dat woord
      // helemaal vast is ('"{0}" has …' begint met een titel, niet met '"').
      var w = en.split(' ');
      var begin = w[0].indexOf('{') < 0 ? w[0] : '';
      var eind = w[w.length - 1].indexOf('}') < 0 ? w[w.length - 1] : '';
      if (begin) (perBegin.get(begin) || perBegin.set(begin, []).get(begin)).push(p);
      else if (eind) (perEind.get(eind) || perEind.set(eind, []).get(eind)).push(p);
      else overige.push(p);
    });
  }

  // Het specifiekste patroon eerst: "Not possible here — {0} →" vóór
  // "Not possible here — {0}".
  function sorteer() {
    var opLengte = function (a, b) { return b.vast - a.vast; };
    [perBegin, perEind].forEach(function (map) { map.forEach(function (l) { l.sort(opLengte); }); });
    overige.sort(opLengte);
  }

  function viaPatroon(s) {
    var lijsten = [perBegin.get(eersteWoord(s)), perEind.get(laatsteWoord(s)), overige];
    for (var i = 0; i < lijsten.length; i++) {
      var l = lijsten[i];
      if (!l) continue;
      for (var j = 0; j < l.length; j++) {
        var m = l[j].re.exec(s);
        if (!m) continue;
        var waarden = {};
        var weiger = false;
        // Een meervoudsplek ({1|dag|dagen}) is in het Engels alleen "" of "s".
        var meervoud = l[j].meervoud;
        l[j].volgorde.forEach(function (nr, k) {
          var ruw = m[k + 1];
          waarden[nr] = l[j].letterlijk[nr] ? ruw : vertaalStuk(ruw);
          // Een invulling is een getal, naam of melding, geen halve zin. Blijft
          // er een lang Engels stuk onvertaald over, dan past dit patroon niet
          // ("{0} removed{1}." mag geen hele alinea opslokken).
          if (!l[j].letterlijk[nr] && waarden[nr] === ruw && ruw.length > 30 && lijktEngels(ruw)) weiger = true;
          if (meervoud[nr] && !/^(e?s)?$/.test(ruw)) weiger = true;
        });
        if (weiger) continue;
        return l[j].nl
          // {1|dag|dagen}: enkelvoud als {1} leeg is ("1 day" / "3 days").
          .replace(/\{(\d+)\|([^|}]*)\|([^}]*)\}/g, function (_, nr, een, meer) {
            return waarden[nr] ? meer : een;
          })
          .replace(/\{(\d+)\}/g, function (_, nr) { return nr in waarden ? waarden[nr] : ''; });
      }
    }
    return null;
  }

  // Een ingevuld stuk ("Could not save: {0}" met {0} = een foutmelding) wordt
  // zelf ook vertaald als het woordenboek het kent; namen en getallen niet.
  function vertaalStuk(s) {
    var n = norm(s);
    if (!/[A-Za-z]{2}/.test(n)) return s;
    var v = vertaalNorm(n);
    // Een opsomming ("Vinted (publishing a listing), Marktplaats (…)") deel
    // voor deel; wat onbekend is (namen) blijft staan.
    if (v === null && n.indexOf(', ') >= 0) {
      var delen = n.split(', ');
      var los = delen.map(vertaalNorm);
      if (los.some(function (x) { return x !== null; })) {
        v = delen.map(function (d, i) { return los[i] === null ? d : los[i]; }).join(', ');
      }
    }
    if (v === null) return s;
    return /^\s*/.exec(s)[0] + v + /\s*$/.exec(s)[0];
  }

  // Zinnen splitsen zonder lookbehind (oudere Safari kent die niet).
  function zinnen(s) {
    var uit = [], re = /[.!?…]\s+(?=[A-Z"'(“‘0-9])/g, van = 0, m;
    while ((m = re.exec(s))) { uit.push(s.slice(van, m.index + 1)); van = re.lastIndex; }
    uit.push(s.slice(van));
    return uit;
  }

  function vertaalNorm(s) {
    if (cache.has(s)) return cache.get(s);
    var uit = exact.has(s) ? exact.get(s) : viaPatroon(s);
    if (uit === null) {
      // Aan elkaar geplakte zinnen ("Could not save. Try again.") één voor één.
      var delen = zinnen(s);
      if (delen.length > 1) {
        var los = delen.map(function (z) { return vertaalNorm(z); });
        if (los.every(function (z) { return z !== null; })) uit = los.join(' ');
      }
    }
    if (uit === null) {
      // "Sign in to your marketplaces." en "…click publish..": de slotpunt(en)
      // of dubbele punt hoort niet bij de sleutel.
      var slot = /^(.*[^.:])(\.\.?|:)$/.exec(s);
      if (slot && slot[1].length > 2) {
        var pogingen = slot[2] === '..' ? [slot[1] + '.', slot[1]] : [slot[1]];
        for (var q = 0; q < pogingen.length && uit === null; q++) {
          var kern = exact.has(pogingen[q]) ? exact.get(pogingen[q]) : viaPatroon(pogingen[q]);
          if (kern !== null) uit = kern.replace(/[.:]$/, '') + slot[2].slice(0, 1);
        }
      }
    }
    if (uit === null && s.indexOf(' | ') > 0) {
      // Foutmeldingen van de extensie dragen soms een technische staart
      // ("… | Buttons on that page: …"). Die blijft staan; de zin ervoor niet.
      var knip = s.indexOf(' | ');
      var kop0 = vertaalNorm(s.slice(0, knip));
      if (kop0 !== null) uit = kop0 + s.slice(knip);
    }
    if (uit === null) {
      // "Vinted: Could not ..." en "⚠️ Could not ...": voorvoegsel laten staan.
      var m = /^(\d{1,2}\.\s+|[^:]{1,30}:\s+|[^\w\s"'(]{1,4}\s*)(.+)$/.exec(s);
      if (m) {
        var rest = vertaalNorm(m[2]);
        // Het voorvoegsel zelf blijft letterlijk: het is vaak een titel of kanaal.
        if (rest !== null) uit = m[1] + rest;
      }
    }
    if (uit === null && s.indexOf(' · ') > 0) {
      // "Levi's · M · 30 days online": per stuk; merk en maat blijven staan.
      var stukken = s.split(' · ');
      var klaar = stukken.map(function (d) { return exact.has(d) ? exact.get(d) : viaPatroon(d); });
      var ok = klaar.some(function (d) { return d !== null; }) &&
        stukken.every(function (d, i) { return klaar[i] !== null || !lijktEngels(d); });
      if (ok) uit = stukken.map(function (d, i) { return klaar[i] === null ? d : klaar[i]; }).join(' · ');
    }
    if (cache.size > 20000) cache.clear();
    cache.set(s, uit);
    return uit;
  }

  // Vertaalt een losse tekst met behoud van witruimte eromheen. null = onbekend.
  var rauw = new Map();  // exacte tekst van het scherm -> uitkomst (lijsten herhalen zich)
  function vertaal(tekst) {
    if (rauw.has(tekst)) return rauw.get(tekst);
    var uit = vertaalRauw(tekst);
    if (rauw.size > 20000) rauw.clear();
    rauw.set(tekst, uit);
    return uit;
  }
  function vertaalRauw(tekst) {
    if (!tekst || !/[A-Za-z]{2}/.test(tekst)) return null;
    var n = norm(tekst);
    var uit = vertaalNorm(n);
    if (uit === null) {
      // Meerdere regels (alert/confirm): per regel.
      if (tekst.indexOf('\n') >= 0) {
        var regels = tekst.split('\n');
        var klaar = regels.map(function (r) {
          if (!/[A-Za-z]{2}/.test(r)) return r;
          var v = vertaalNorm(norm(r));
          return v === null ? null : r.match(/^\s*/)[0] + v;
        });
        if (klaar.every(function (r) { return r !== null; })) return klaar.join('\n');
      }
      return null;
    }
    if (uit === n) return tekst;
    var voor = /^\s*/.exec(tekst)[0], na = /\s*$/.exec(tekst)[0];
    // " — the form …" wordt ": het formulier …": zonder spatie vóór de dubbele punt.
    if (/^[:;,.)]/.test(uit)) voor = '';
    return voor + uit + (na.length < tekst.length - voor.length ? na : '');
  }

  // Bedragen op z'n Nederlands: "€1,234.50" wordt "€1.234,50". Alleen in tekst
  // op het scherm; invulvelden (waar het dashboard het bedrag weer uitleest)
  // komen hier nooit langs.
  var BEDRAG = /€(\s?)(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})(?!\d)/g;
  function bedragen(s) {
    return s.indexOf('€') < 0 ? s : s.replace(BEDRAG, function (_, sp, heel, cent) {
      return '€' + sp + heel.replace(/,/g, '.') + ',' + cent;
    });
  }

  api.t = function (s) {
    if (typeof s !== 'string') return s;
    var v = vertaal(s);
    return v === null ? s : v;
  };

  // ── Melden wat ontbreekt ───────────────────────────────────────────────
  var ENGELS = /\b(the|you|your|to|is|are|not|could|couldn't|can't|and|of|for|this|was|has|have|be|with|on|no|please|try|again|will|it|in|from|here|what|when|failed|click|items?|listings?|platforms?)\b/gi;
  var gemeld = new Set();
  var teMelden = [];
  var meldTimer = null;
  var NEDERLANDS = /\b(de|het|een|en|je|jouw|niet|geen|van|voor|zijn|wordt|naar|bij|deze|dit|dat|die|met|op|er|ook|nog|al|kan|moet|staat|om|wat)\b/gi;
  function lijktEngels(s) {
    if (s.length < 6) return false;
    var m = s.match(ENGELS);
    return !!m && m.length >= 2 && m.length > (s.match(NEDERLANDS) || []).length;
  }
  function meld(s, plek) {
    if (s.length > 300) s = s.slice(0, 300);
    if (gemeld.has(s) || gemeld.size > 60 || !lijktEngels(s)) return;
    gemeld.add(s);
    teMelden.push({ tekst: s, plek: plek || '' });
    clearTimeout(meldTimer);
    meldTimer = setTimeout(stuurMeldingen, 4000);
  }
  function stuurMeldingen() {
    var lijst = teMelden.splice(0, 40);
    if (!lijst.length) return;
    try {
      fetch('/api/i18n/ontbrekend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ taal: taal, pagina: location.pathname, teksten: lijst }),
        keepalive: true,
      }).catch(function () { /* melden is een gunst, nooit een fout */ });
    } catch (e) { /* idem */ }
  }
  api.ontbrekend = function () { return Array.from(gemeld); };

  // ── De pagina vertalen ─────────────────────────────────────────────────
  // Geen alt: dat is onzichtbaar en bevat soms de titel van een klant.
  var ATTR = ['title', 'placeholder', 'aria-label', 'data-tip'];
  var OVERSLAAN = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, NOSCRIPT: 1, CODE: 1, PRE: 1, SVG: 1, svg: 1 };
  // Klassen waarin het dashboard titels van klanten zet. Alleen hun eigen tekst
  // blijft staan; een badge ("↓ Imported") erin wordt wel vertaald.
  var DATA_KLASSEN = ['item-title', 'an-sales-title', 'imp-kant-t'];
  function dicht(e) {
    return e.getAttribute('translate') === 'no' || e.classList.contains('notranslate') || e.isContentEditable;
  }
  function isData(e) {
    for (var i = 0; i < DATA_KLASSEN.length; i++) if (e.classList.contains(DATA_KLASSEN[i])) return true;
    return false;
  }
  var geschreven = new WeakMap();    // tekstknoop -> wat wij erin zetten
  var geschrevenAttr = new WeakMap(); // element -> {attr: waarde}

  // stil(el, tekst): mag er aan (de tekst van) dit element niets veranderen?
  function stil(el, tekst) {
    if (tekst && el.classList && isData(el)) return true;
    for (var e = el; e && e.nodeType === 1; e = e.parentElement) {
      if (OVERSLAAN[e.nodeName] && (tekst || e !== el)) return true;
      if (e.classList && dicht(e)) return true;
    }
    return false;
  }

  function schrijf(node, data, v) {
    var uit = bedragen(v === null ? data : v);
    if (uit === data) return;
    geschreven.set(node, uit);
    node.data = uit;
  }

  function tekstknoop(node) {
    var data = node.data;
    if (geschreven.get(node) === data) return;
    var letters = /[A-Za-z]{2}/.test(data);
    if (!letters && data.indexOf('€') < 0) return;
    var ouder = node.parentElement;
    if (!ouder || stil(ouder, true)) return;
    var v = letters ? vertaal(data) : null;
    if (v === null && letters) meld(norm(data), ouder.id || ouder.className || ouder.nodeName);
    schrijf(node, data, v);
  }

  var IS_ATTR = {};
  ATTR.forEach(function (a) { IS_ATTR[a] = true; });
  function attributen(el) {
    var klaar = geschrevenAttr.get(el);
    var lijst = el.attributes;
    for (var i = 0; i < lijst.length; i++) {
      var a = lijst[i].name;
      if (!IS_ATTR[a]) continue;
      var w = lijst[i].value;
      if (!w || (klaar && klaar[a] === w)) continue;
      var v = vertaal(w);
      if (v === null || v === w) continue;
      if (!klaar) { klaar = {}; geschrevenAttr.set(el, klaar); }
      klaar[a] = v;
      el.setAttribute(a, v);
    }
    if (el.nodeName === 'INPUT' && /^(button|submit|reset)$/i.test(el.type) && el.value) {
      var vv = vertaal(el.value);
      if (vv !== null && vv !== el.value) el.value = vv;
    }
  }

  function boom(wortel) {
    if (wortel.nodeType === 3) { tekstknoop(wortel); return; }
    if (wortel.nodeType !== 1 && wortel.nodeType !== 9 && wortel.nodeType !== 11) return;
    if (wortel.nodeType === 1) {
      if (stil(wortel)) return;
      attributen(wortel);
      if (OVERSLAAN[wortel.nodeName]) return;
    }
    var w = document.createTreeWalker(wortel, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (n.nodeType === 1) {
          if (dicht(n)) return NodeFilter.FILTER_REJECT;
          if (OVERSLAAN[n.nodeName]) { attributen(n); return NodeFilter.FILTER_REJECT; }
          return NodeFilter.FILTER_ACCEPT;
        }
        return isData(n.parentElement) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      },
    });
    var n;
    var teksten = [];
    while ((n = w.nextNode())) {
      if (n.nodeType === 1) attributen(n);
      else teksten.push(n);
    }
    for (var i = 0; i < teksten.length; i++) {
      var node = teksten[i];
      var data = node.data;
      if (geschreven.get(node) === data) continue;
      var letters = /[A-Za-z]{2}/.test(data);
      if (!letters && data.indexOf('€') < 0) continue;
      var v = letters ? vertaal(data) : null;
      if (v === null && letters) { var o = node.parentElement; meld(norm(data), o && (o.id || o.className || o.nodeName)); }
      schrijf(node, data, v);
    }
  }

  var observer = new MutationObserver(function (lijst) {
    for (var i = 0; i < lijst.length; i++) {
      var m = lijst[i];
      if (m.type === 'childList') {
        for (var j = 0; j < m.addedNodes.length; j++) {
          var a = m.addedNodes[j];
          if (a.nodeType === 3) tekstknoop(a);
          else if (a.nodeType === 1) boom(a);
        }
      } else if (m.type === 'characterData') {
        tekstknoop(m.target);
      } else if (m.type === 'attributes') {
        if (!stil(m.target)) attributen(m.target);
      }
    }
  });

  // ── Wat niet in de pagina staat: dialogen, datums, grafieken ──────────
  ['alert', 'confirm', 'prompt'].forEach(function (naam) {
    var orig = window[naam];
    if (typeof orig !== 'function') return;
    window[naam] = function (bericht) {
      var args = Array.prototype.slice.call(arguments);
      if (typeof bericht === 'string') {
        var v = vertaal(bericht);
        if (v === null) meld(norm(bericht), naam);
        args[0] = bedragen(v === null ? bericht : v);
      }
      return orig.apply(window, args);
    };
  });

  // Datums: het dashboard formatteert met 'en-GB' ("24 Sept 2026"). In het
  // Nederlands wordt dat "24 sep 2026". Alleen weergave; niets leest het terug.
  var LOC = 'nl-NL';
  function wissel(loc) { return (loc === undefined || loc === null || /^en\b/i.test(String(loc))) ? LOC : loc; }
  ['toLocaleDateString', 'toLocaleTimeString', 'toLocaleString'].forEach(function (f) {
    var orig = Date.prototype[f];
    Date.prototype[f] = function (loc, opts) { return orig.call(this, wissel(loc), opts); };
  });
  var OrigDTF = Intl.DateTimeFormat;
  var NieuwDTF = function (loc, opts) { return new OrigDTF(wissel(loc), opts); };
  NieuwDTF.prototype = OrigDTF.prototype;
  NieuwDTF.supportedLocalesOf = OrigDTF.supportedLocalesOf;
  Intl.DateTimeFormat = NieuwDTF;
  var OrigRTF = Intl.RelativeTimeFormat;
  if (OrigRTF) {
    var NieuwRTF = function (loc, opts) { return new OrigRTF(wissel(loc), opts); };
    NieuwRTF.prototype = OrigRTF.prototype;
    NieuwRTF.supportedLocalesOf = OrigRTF.supportedLocalesOf;
    Intl.RelativeTimeFormat = NieuwRTF;
  }

  // Grafieken tekenen op een canvas; daar komt de observer niet. Labels en
  // titels gaan daarom bij elke update door het woordenboek.
  function vertaalGrafiek(chart) {
    try {
      var d = chart.data || (chart.config && chart.config.data);
      if (d && Array.isArray(d.labels)) d.labels = d.labels.map(api.t);
      if (d && Array.isArray(d.datasets)) d.datasets.forEach(function (ds) { if (ds.label) ds.label = api.t(ds.label); });
      var o = chart.options || {};
      var pl = o.plugins || {};
      if (pl.title && typeof pl.title.text === 'string') pl.title.text = api.t(pl.title.text);
      Object.keys(o.scales || {}).forEach(function (k) {
        var t = o.scales[k] && o.scales[k].title;
        if (t && typeof t.text === 'string') t.text = api.t(t.text);
      });
    } catch (e) { /* een grafiek in het Engels is beter dan geen grafiek */ }
  }
  function haakGrafiek() {
    var C = window.Chart;
    if (!C || !C.prototype || C.prototype.__omniI18n) return;
    var upd = C.prototype.update;
    C.prototype.update = function () { vertaalGrafiek(this); return upd.apply(this, arguments); };
    C.prototype.__omniI18n = true;
  }

  // ── Starten ────────────────────────────────────────────────────────────
  function start(wb) {
    laad(wb);
    sorteer();
    haakGrafiek();
    if (document.title) { var tt = vertaal(document.title); if (tt !== null && tt !== document.title) document.title = tt; }
    boom(document.body || document.documentElement);
    observer.observe(document.documentElement, {
      childList: true, subtree: true, characterData: true,
      attributes: true, attributeFilter: ATTR.concat(['value']),
    });
    clearTimeout(noodrem);
    toon();
  }

  var mijnSrc = (document.currentScript && document.currentScript.src) || '';
  var v = (/[?&]v=([\w.-]+)/.exec(mijnSrc) || [])[1] || '';
  api.klaar = fetch('/i18n/' + taal + '.json' + (v ? '?v=' + v : ''))
    .then(function (r) { if (!r.ok) throw new Error('woordenboek ' + r.status); return r.json(); })
    .then(function (wb) {
      if (document.body) start(wb);
      else document.addEventListener('DOMContentLoaded', function () { start(wb); });
    })
    .catch(function () { clearTimeout(noodrem); toon(); });
  // Voor tests en de extractor: dezelfde vertaalregels zonder pagina.
  api._laad = laad;
  api._vertaal = vertaal;
})();
