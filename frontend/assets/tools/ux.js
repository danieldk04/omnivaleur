/* Gedeeld gedrag voor elke tool (28-10-2026): je invoer staat in de link, je uitkomst is te
 * kopiëren, delen, printen en naar jezelf te mailen. Geen afhankelijkheden; de rekentools zelf
 * blijven los hiervan werken. Een uitkomstvak is elk element met een id dat op -resultaten eindigt. */
(function (root) {
  'use strict';
  if (typeof document === 'undefined') return;
  var huidig = document.currentScript;
  var tool = huidig ? huidig.getAttribute('data-tool') : '';
  var nl = (document.documentElement.lang || 'en').slice(0, 2) === 'nl';
  var T = nl ? {
    kopieer: 'Kopieer resultaat', link: 'Kopieer link met mijn invoer', print: 'Print', mail: 'Mail mij dit',
    gekopieerd: 'Gekopieerd', linkOk: 'Link gekopieerd', mislukt: 'Kopiëren lukte niet, selecteer de tekst zelf.',
    emailLabel: 'Je e-mailadres', tips: 'Stuur mij ook af en toe tips over tweedehands verkopen (je kunt altijd stoppen)',
    stuur: 'Mail het naar mij', ok: 'Verstuurd. Staat het er niet? Kijk in je spam.', fout: 'Dit lijkt geen e-mailadres.',
    veel: 'Je hebt dit net al een paar keer gedaan. Probeer het later opnieuw.', algemeen: 'Het versturen lukte niet. Probeer het zo nog eens.',
    uitleg: 'We sturen je uitkomst één keer naar dit adres. Je adres bewaren we alleen als je het vakje voor tips aanvinkt.',
    na: 'Liever niet alles met de hand doen? Omnivaleur zet een artikel in één keer op al je kanalen.', proef: '7 dagen gratis proberen'
  } : {
    kopieer: 'Copy result', link: 'Copy link with my input', print: 'Print', mail: 'Email me this',
    gekopieerd: 'Copied', linkOk: 'Link copied', mislukt: 'Copying failed, select the text yourself.',
    emailLabel: 'Your email address', tips: 'Also send me the occasional tip about selling second-hand (you can stop any time)',
    stuur: 'Email it to me', ok: 'Sent. Not there? Check your spam.', fout: 'This does not look like an email address.',
    veel: 'You just did this a few times. Try again later.', algemeen: 'Sending failed. Please try again in a moment.',
    uitleg: 'We send your result once to this address. We only keep your address if you tick the box for tips.',
    na: 'Rather not do everything by hand? Omnivaleur puts an item on all your channels in one go.', proef: 'Try it free for 7 days'
  };

  function alle(sel) { return [].slice.call(document.querySelectorAll(sel)); }
  function velden() {
    return alle('.kr-kaart input[id], .kr-kaart select[id], .kr-kaart textarea[id]').filter(function (f) {
      return f.type !== 'email' && f.type !== 'hidden' && f.type !== 'file' && !f.hasAttribute('data-geen-status');
    });
  }
  function meld(e) { e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); }
  function zoekreeks() {
    var p = new URLSearchParams();
    velden().forEach(function (f) {
      if (f.type === 'checkbox') { if (f.checked) p.set(f.id, '1'); return; }
      var v = (f.value || '').trim();
      if (v && v.length <= 200) p.set(f.id, v);
    });
    return p.toString();
  }

  // 1. Invoer uit de link terug in de velden
  function vul() {
    var p;
    try { p = new URLSearchParams(location.search); } catch (e) { return; }
    velden().forEach(function (f) {
      if (!p.has(f.id)) return;
      var v = p.get(f.id);
      if (f.type === 'checkbox') f.checked = v === '1'; else f.value = v.slice(0, 200);
      meld(f);
    });
  }
  // 2. Invoer in de link zetten, zonder een nieuwe historiestap
  var timer;
  function bewaar() {
    clearTimeout(timer);
    timer = setTimeout(function () {
      var qs = zoekreeks();
      try { history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash); } catch (e) { /* oud browsertje */ }
    }, 400);
  }

  // 3. Balk onder het uitkomstvak
  function bouw(res) {
    var bar = document.createElement('div');
    bar.className = 'kr-acties'; bar.hidden = true;
    bar.innerHTML = '<button type="button" data-a="kopieer">' + T.kopieer + '</button>' +
      '<button type="button" data-a="link">' + T.link + '</button>' +
      '<button type="button" data-a="print">' + T.print + '</button>' +
      '<button type="button" data-a="mail" class="kr-hoofd">' + T.mail + '</button>' +
      '<span class="kr-toast" role="status" aria-live="polite"></span>';
    var form = document.createElement('form');
    form.className = 'kr-mail'; form.hidden = true; form.noValidate = true;
    form.innerHTML = '<label for="kr-mail-adres">' + T.emailLabel + '</label>' +
      '<input id="kr-mail-adres" type="email" autocomplete="email" inputmode="email" required>' +
      '<label class="kr-aanvink"><input type="checkbox" id="kr-mail-tips"><span>' + T.tips + '</span></label>' +
      '<div class="kr-pot" aria-hidden="true"><label>Website<input type="text" id="kr-mail-pot" tabindex="-1" autocomplete="off"></label></div>' +
      '<button type="submit" class="kr-knop">' + T.stuur + '</button>' +
      '<div class="kr-melding" style="display:none" aria-live="polite"></div>' +
      '<p class="kr-hint">' + T.uitleg + '</p>';
    var na = document.createElement('p');
    na.className = 'kr-na'; na.hidden = true;
    na.innerHTML = T.na + ' <a href="/register">' + T.proef + '</a>';
    res.insertAdjacentElement('afterend', na);
    res.insertAdjacentElement('afterend', form);
    res.insertAdjacentElement('afterend', bar);
    return { bar: bar, form: form, na: na };
  }
  function uitkomstTekst(res) {
    var weg = alle('[data-uitsluiten]').filter(function (e) { return res.contains(e); });
    weg.forEach(function (e) { e.style.display = 'none'; });
    var t = (res.innerText || res.textContent || '').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
    weg.forEach(function (e) { e.style.display = ''; });
    var h = document.querySelector('h1');
    return (h ? h.textContent.trim() + '\n\n' : '') + t;
  }
  function kopieer(tekst, ok, toast) {
    function klaar(goed) { toast.textContent = goed ? ok : T.mislukt; setTimeout(function () { toast.textContent = ''; }, 2500); }
    function terugval() {
      var ta = document.createElement('textarea');
      ta.value = tekst; ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta);
      ta.select(); var goed = false;
      try { goed = document.execCommand('copy'); } catch (e) { goed = false; }
      document.body.removeChild(ta); klaar(goed);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(tekst).then(function () { klaar(true); }, terugval);
    } else terugval();
  }
  function heeftUitkomst(res) { return !!res.textContent.trim() && !res.querySelector('.kr-leeg'); }

  function start() {
    vul();
    document.addEventListener('input', bewaar); document.addEventListener('change', bewaar);
    var res = document.querySelector('[id$="-resultaten"]');
    if (!res) return;
    var d = bouw(res), toast = d.bar.querySelector('.kr-toast');
    function ververs() { var an = heeftUitkomst(res); d.bar.hidden = !an; d.na.hidden = !an; if (!an) d.form.hidden = true; }
    new MutationObserver(ververs).observe(res, { childList: true, subtree: true, characterData: true });
    ververs();
    d.bar.addEventListener('click', function (ev) {
      var a = ev.target.getAttribute && ev.target.getAttribute('data-a');
      if (a === 'kopieer') kopieer(uitkomstTekst(res) + '\n\n' + location.origin + location.pathname + (zoekreeks() ? '?' + zoekreeks() : ''), T.gekopieerd, toast);
      else if (a === 'link') kopieer(location.origin + location.pathname + (zoekreeks() ? '?' + zoekreeks() : ''), T.linkOk, toast);
      else if (a === 'print') window.print();
      else if (a === 'mail') { d.form.hidden = !d.form.hidden; if (!d.form.hidden) document.getElementById('kr-mail-adres').focus(); }
    });
    d.form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var mel = d.form.querySelector('.kr-melding'), knop = d.form.querySelector('button[type=submit]');
      function zeg(tekst, goed) { mel.style.display = 'block'; mel.className = 'kr-melding ' + (goed ? 'goed' : 'fout'); mel.textContent = tekst; }
      var adres = document.getElementById('kr-mail-adres').value.trim();
      if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(adres)) { zeg(T.fout, false); return; }
      knop.disabled = true;
      fetch('/api/tools/mail-resultaat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: adres, taal: nl ? 'nl' : 'en', bron: tool, tekst: uitkomstTekst(res),
          link: location.origin + location.pathname + (zoekreeks() ? '?' + zoekreeks() : ''),
          tips: document.getElementById('kr-mail-tips').checked, website: document.getElementById('kr-mail-pot').value })
      }).then(function (r) {
        knop.disabled = false;
        if (r.ok) zeg(T.ok, true); else zeg(r.status === 422 ? T.fout : r.status === 429 ? T.veel : T.algemeen, false);
      }, function () { knop.disabled = false; zeg(T.algemeen, false); });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})(window);
