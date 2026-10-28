/* Aanmeldformulier voor de spreadsheet: POST /api/tools/aanmelden, daarna de downloadlink. */
(function () {
  'use strict';
  if (typeof document === 'undefined') return;
  var G = window.ToolsGedeeld, nl = G.taal === 'nl';
  var T = nl ? { ok: 'Gelukt. Hier is je spreadsheet:', knop: 'Download de spreadsheet', mail: 'Vul een geldig e-mailadres in.', toest: 'Vink aan dat je akkoord bent, anders kunnen we de download niet geven.', vaak: 'Je hebt dit te vaak geprobeerd. Probeer het over een uur nog eens.', stuk: 'Er ging iets mis aan onze kant. Mail info@omnivaleur.com, dan sturen we hem je toe.', bezig: 'Even geduld…' }
             : { ok: 'Done. Here is your spreadsheet:', knop: 'Download the spreadsheet', mail: 'Enter a valid email address.', toest: 'Tick the box to agree, otherwise we cannot give you the download.', vaak: 'You tried this too often. Try again in an hour.', stuk: 'Something went wrong on our side. Email info@omnivaleur.com and we will send it to you.', bezig: 'One moment…' };
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
          if (x.r.ok && x.j.download) {
            var a = document.createElement('a'); a.href = x.j.download; a.className = 'kr-knop'; a.textContent = T.knop;
            var m = G.el('vs-melding'); m.className = 'kr-melding goed'; m.textContent = T.ok + ' '; m.appendChild(a); m.style.display = 'block';
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
