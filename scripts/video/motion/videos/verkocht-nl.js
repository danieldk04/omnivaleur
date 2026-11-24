import { hoodie, chip, stamp, bubble, badge, check, textBlock, line, phone } from '../kit.js';

export const mood = t => (t < 6.1 ? { a: '#1a2a5e', b: 'rgba(255,200,61,.22)' } : { a: '#0d2f73', b: 'rgba(133,237,188,.28)' });

export function build(K) {
  const { capOff, cue, scene, at, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tVerk = at('Verkocht', 0), tMp = at('Marktplaats'), tDan = at('Dan') - .1, tTwee = at('twee'), tSorry = at('sorry');
  const tOmni = at('Omnivaleur') - .1, tWeg = at('weg'), tEen = at('Eén') - .1, tZeven = at('Zeven') - .1;
  cue(tVerk + .3, 'hit'); cue(tMp, 'pop'); cue(tTwee, 'buzz'); cue(tSorry, 'pop'); cue(tOmni + .5, 'whoosh'); cue(tWeg + .1, 'tick'); cue(tWeg + .5, 'tick'); cue(tWeg + .9, 'tick');
  capOff(tEen + .1, tZeven - .05); cue(tEen + .3, 'ding'); cue(tZeven, 'pop');
  const listing = (scr, status, color) => { scr.innerHTML = `<div style="padding:22px 20px"><div style="height:200px;border-radius:20px;background:linear-gradient(135deg,#ffe3ec,#dbe8ff);position:relative;overflow:hidden"></div><div style="font:800 28px Montserrat;color:#0a1936;margin-top:16px">Nike Tech Fleece, M</div><div style="font:900 40px Montserrat;color:#0649c7">€45</div><div class="st" style="display:inline-block;margin-top:12px;padding:8px 18px;border-radius:999px;background:${color};font:800 24px Montserrat;color:#0a1936">${status}</div></div>`; const h = hoodie(scr.firstChild.firstChild, '#3c4b73', 190); h.style.left = '50%'; h.style.top = '50%'; h.style.transform = 'translate(-50%,-50%)'; return scr.querySelector('.st'); };

  // A: sold on Vinted, still online on Marktplaats
  scene(0, tDan + .15, (g, up) => {
    const pv = phone(g, 300, 560), pm = phone(g, 300, 560);
    listing(pv.scr, 'Te koop', '#d8f7e6'); const stM = listing(pm.scr, 'Te koop', '#d8f7e6');
    const cv = chip(g, 'vinted', 120), cm = chip(g, 'marktplaats', 120);
    const sv = stamp(g, 'VERKOCHT', '#ff4d4d', 36);
    const q = bubble(g, 'Is deze nog beschikbaar?', { w: 300, size: 26, me: true });
    up((t, T) => {
      const a = T - tVerk, b = T - tMp;
      place(pv, { x: 190, y: 470, s: pop(t, 0, .45), r: -3 });
      place(pm, { x: 530, y: 470, s: pop(T, tMp - .5, .45), r: 3 });
      place(cv, { x: 190, y: 150, s: pop(t, .2, .35) });
      place(cm, { x: 530, y: 150, s: pop(T, tMp - .3, .35) });
      place(sv, { x: 190, y: 520, s: a < .2 ? 0 : E.slam(cl((a - .2) / .5)), r: -14 });
      place(q, { x: 530, y: 700, s: pop(T, tMp + .7, .35) });
      pm.style.filter = ''; stM.style.transform = `scale(${1 + .05 * Math.sin(T * 8)})`;
    });
  });

  // B: two receipts, one hoodie, a sorry message
  scene(tDan, tOmni, (g, up) => {
    const h = hoodie(g, '#3c4b73', 260);
    const rc = (name, c) => node(g, `width:300px;padding:20px 24px;border-radius:24px;background:#fff;box-shadow:0 14px 40px rgba(0,0,0,.4);font:700 24px Montserrat;color:#485363`, `<div style="display:flex;align-items:center;gap:12px"><div style="font:900 30px Montserrat;color:#0a1936">${name}</div></div><div style="font:900 54px Montserrat;color:#0a1936;margin-top:6px">€45</div><div style="margin-top:6px;color:#005f3a;font:800 26px Montserrat">Betaald ✓</div>`);
    const r1 = rc('Vinted'), r2 = rc('Marktplaats');
    const two = badge(g, '2× verkocht, 1 hoodie', { bg: '#ff4d4d', fg: '#fff', size: 38, pad: '16px 32px' });
    const sorry = bubble(g, 'Sorry, het is al weg…', { w: 440, me: true, size: 34 });
    up((t, T) => {
      place(h, { x: 360, y: 250 + Math.sin(t * 2.4) * 6, s: pop(t, 0, .45) });
      place(r1, { x: 190, y: 550, s: pop(t, .3, .4), r: -4 });
      place(r2, { x: 530, y: 550, s: pop(T, tTwee - .2, .4), r: 4 });
      place(two, { x: 360, y: 730, s: pop(T, tTwee + .3, .4), r: -2 });
      place(sorry, { x: 400, y: 830, s: pop(T, tSorry, .35) });
    });
  });

  // C: Omnivaleur pulls the listing everywhere, left to right
  scene(tOmni, tEen, (g, up) => {
    const src = chip(g, 'vinted', 150), sSold = stamp(g, 'VERKOCHT', '#ff4d4d', 26);
    const hub = node(g, 'width:210px;height:210px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 14px rgba(133,237,188,.35),0 18px 50px rgba(0,0,0,.4)', '<img src="assets/mark.png" style="width:150px">');
    const D = [['marktplaats', 220], ['ebay', 430], ['shop', 640]].map(([k, y], i) => ({ c: chip(g, k, 150), ok: badge(g, 'Verwijderd ✓', { size: 24 }), y, i }));
    const l0 = line(g, 200, 430, 255, 430), L = D.map(d => line(g, 465, 430, 540, d.y));
    up((t, T) => {
      place(src, { x: 110, y: 430, s: pop(t, 0, .4) });
      place(sSold, { x: 120, y: 520, s: t < .4 ? 0 : E.slam(cl((t - .4) / .5)), r: -12 });
      l0.set(prog(t, .6, 1.1, E.inOut), t > .6 ? 1 : 0);
      place(hub, { x: 360, y: 430, s: pop(t, .2, .45) * (1 + .03 * Math.sin(t * 6)) });
      D.forEach((d, i) => {
        const tt = tWeg - .3 + i * .4;
        L[i].set(prog(T, tt, tt + .45, E.inOut), T > tt ? 1 : 0);
        const gone = prog(T, tt + .45, tt + .7, E.lin);
        place(d.c, { x: 590, y: d.y, s: pop(t, .4 + i * .1, .35) * mix(1, .88, gone) });
        d.c.style.filter = `grayscale(${gone}) opacity(${mix(1, .5, gone)})`;
        place(d.ok, { x: 580, y: d.y + 100, s: pop(T, tt + .5, .3) });
      });
    });
  });

  // D: once, everywhere, CTA
  scene(tEen, DURATION + .5, (g, up) => {
    const ck = check(g, 200);
    const big = textBlock(g, 'Eén keer plaatsen.<br>Overal verkopen.', { size: 70, w: 680 });
    const cta = node(g, 'padding:22px 44px;border-radius:999px;background:#85edbc;color:#0a1936;font:900 44px/1 Montserrat;box-shadow:0 14px 40px rgba(0,0,0,.4);white-space:nowrap', '7 dagen gratis');
    const mk = node(g, 'width:420px', '<div style="display:flex;align-items:center;gap:14px;justify-content:center"><img src="assets/mark.png" style="width:100px"><span style="font:900 42px Montserrat;color:#fff;letter-spacing:-1px">Omnivaleur</span></div>');
    up((t, T) => {
      place(mk, { x: 360, y: 105, s: pop(t, .15, .4) });
      place(ck, { x: 360, y: 300, s: pop(t, 0, .5) }); ck.setCk(prog(t, .2, .7, E.out));
      place(big, { x: 360, y: 540, s: pop(t, .3, .45) });
      place(cta, { x: 360, y: 730, s: pop(T, tZeven + .1, .4) * (1 + .03 * Math.sin(T * 7)) });
    });
  });
}
