/* Aanmeldformulier voor de spreadsheet: POST /api/tools/aanmelden. De spreadsheet komt per mail; het adres wordt pas bewaard als de link in die mail wordt geopend. */
(function () {
  'use strict';
  if (typeof document === 'undefined') return;
  var G = window.ToolsGedeeld, nl = G.taal === 'nl';
  var T = nl ? { ok: 'Gelukt. We hebben de spreadsheet gemailed naar', na: 'Kijk ook in je spam als hij er niet staat.', mail: 'Vul een geldig e-mailadres in.', toest: 'Vink aan dat je akkoord bent, anders kunnen we de spreadsheet niet mailen.', vaak: 'Je hebt dit te vaak geprobeerd. Probeer het over een uur nog eens.', stuk: 'Het versturen lukte niet. Probeer het zo nog eens, of mail info@omnivaleur.com, dan sturen we hem je toe.', bezig: 'Even geduld…' }
             : { ok: 'Done. We emailed the spreadsheet to', na: 'Check your spam if you do not see it.', mail: 'Enter a valid email address.', toest: 'Tick the box to agree, otherwise we cannot email you the spreadsheet.', vaak: 'You tried this too often. Try again in an hour.', stuk: 'Sending failed. Try again in a moment, or email info@omnivaleur.com and we will send it to you.', bezig: 'One moment…' };
  function melding(klasse, html) { var m = G.el('vs-melding'); m.className = 'kr-melding ' + klasse; m.innerHTML = html; m.style.display = 'block'; }
  function start() {
    var f = G.el('vs-form');
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var email = G.el('vs-email').value.trim(), toest = G.el('vs-toestemming').checked;
      if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(email)) return melding('fout', T.mail);
      if (!toest) return melding('fout', T.toest);
      var knop = G.el('vs-knop'); knop.disabled = true; var oud = knop.textContent; knop.textContent = T.bezig;
      fetch('/api/tools/aanmelden', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, taal: G.taal, bron: 'voorraadsheet', toestemming: true, website: G.el('vs-website').value }) })
        .then(function (r) { return r.json().then(function (j) { return { r: r, j: j }; }, function () { return { r: r, j: {} }; }); })
        .then(function (x) {
          if (x.r.ok && x.j.verstuurd) {
            var m = G.el('vs-melding'); m.className = 'kr-melding goed'; m.textContent = T.ok + ' ' + email + '. ' + T.na; m.style.display = 'block';
          } else if (x.r.status === 429) melding('fout', T.vaak);
          else if (x.r.status === 422) melding('fout', x.j.detail === 'toestemming' ? T.toest : T.mail);
          else melding('fout', T.stuk);
        })
        .catch(function () { melding('fout', T.stuk); })
        .then(function () { knop.disabled = false; knop.textContent = oud; });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
