// Home en /nl: de rondleiding door de echte schermen en het verkoopvoorbeeld.
(function () {
  const tabs = [...document.querySelectorAll('.tour-item')];
  const panels = [...document.querySelectorAll('.tour-panel')];
  if (tabs.length) {
    function show(i, focus) {
      tabs.forEach((t, n) => {
        const on = n === i;
        t.classList.toggle('active', on);
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        t.tabIndex = on ? 0 : -1;
      });
      panels.forEach((p, n) => { p.hidden = n !== i; });
      if (focus) { tabs[i].focus(); tabs[i].scrollIntoView({ block: 'nearest', inline: 'nearest' }); }
    }
    tabs.forEach((t, i) => {
      t.addEventListener('click', () => show(i));
      t.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowRight') { e.preventDefault(); show((i + 1) % tabs.length, true); }
        if (e.key === 'ArrowLeft') { e.preventDefault(); show((i - 1 + tabs.length) % tabs.length, true); }
      });
    });
    show(0);
  }

  const demo = document.getElementById('sale-demo');
  if (!demo) return;
  const rows = [...demo.querySelectorAll('tbody tr')];
  const out = document.getElementById('sale-status');
  const reset = document.getElementById('sale-reset');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const tekst = demo.dataset;
  let timers = [];

  function zet(row, klasse, label) {
    row.classList.remove('is-sold', 'is-down');
    if (klasse) row.classList.add(klasse);
    row.querySelector('.state').textContent = label;
  }
  function herstel() {
    timers.forEach(clearTimeout);
    timers = [];
    rows.forEach((r) => { zet(r, '', tekst.live); r.querySelector('.sale-btn').disabled = false; });
    out.textContent = tekst.start;
  }
  rows.forEach((row) => {
    row.querySelector('.sale-btn').addEventListener('click', () => {
      herstel();
      rows.forEach((r) => { r.querySelector('.sale-btn').disabled = true; });
      zet(row, 'is-sold', tekst.sold);
      const rest = rows.filter((r) => r !== row);
      rest.forEach((r, i) => {
        const klaar = () => zet(r, 'is-down', tekst.down);
        if (reduced) klaar(); else timers.push(setTimeout(klaar, 260 * (i + 1)));
      });
      out.textContent = tekst.done.replace('{kanaal}', row.dataset.kanaal).replace('{n}', rest.length);
    });
  });
  reset.addEventListener('click', herstel);
})();
