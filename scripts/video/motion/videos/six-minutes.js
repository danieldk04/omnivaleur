import { hoodie, chip, badge, check, textBlock, ring } from '../kit.js';

export const mood = t => ({ a: '#13306f', b: 'rgba(255,200,61,.20)' });

export function build(K) {
  const { cue, scene, at, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tFour = at('Four') - .1, tFifty = at('Fifty') - .1, tOmni = at('Omnivaleur') - .1, tGet = at('Get') - .1, tSeven = at('Seven') - .1;
  cue(tFour + .1, 'pop'); cue(at('ninety'), 'pop'); cue(at('Six'), 'hit'); cue(tFifty + .2, 'whoosh'); cue(at('five', 0), 'buzz');
  cue(at('tap'), 'hit'); cue(at('tap') + .5, 'ding'); cue(tGet + .2, 'ding'); cue(tSeven, 'pop');

  // A: the stopwatch
  scene(0, tFour + .15, (g, up) => {
    const rg = ring(g, 360, '#ffc83d', 'rgba(255,255,255,.18)', '?');
    const lb = badge(g, 'time per listing', { bg: '#fff', size: 38, pad: '16px 34px' });
    up((t, T) => {
      place(rg, { x: 360, y: 400, s: pop(t, 0, .5) });
      rg.set(prog(t, .2, Math.max(1, tFour), E.inOut) * .92, '?');
      place(lb, { x: 360, y: 690, s: pop(t, .45, .4) });
    });
  });

  // B: 4 x 90 s = 6 min
  scene(tFour, tFifty, (g, up) => {
    const row = (html, bg, fg = '#0a1936') => node(g, `width:600px;height:150px;border-radius:32px;background:${bg};color:${fg};box-shadow:0 18px 50px rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;gap:24px;font:900 70px/1 Montserrat`, html);
    const r1 = row('4 <span style="font:800 44px Montserrat">apps</span>', '#fff');
    const r2 = row('90 s <span style="font:800 44px Montserrat">each</span>', '#fff');
    const r3 = row('6 min <span style="font:800 44px Montserrat">per item</span>', '#ff4d4d', '#fff');
    const ops = ['×', '='].map(c => node(g, 'font:900 80px Montserrat;color:#fff', c));
    const mini = ['vinted', 'marktplaats', 'ebay', 'shop'].map(k => chip(g, k, 80));
    up((t, T) => {
      place(r1, { x: 360, y: 220, s: pop(t, .05, .4) });
      mini.forEach((m, i) => place(m, { x: 120 + i * 160, y: 360, s: pop(t, .25 + i * .08, .3) }));
      place(ops[0], { x: 360, y: 455, s: pop(T, at('ninety') - .25, .3) });
      place(r2, { x: 360, y: 590, s: pop(T, at('ninety') - .2, .4) });
      place(ops[1], { x: 360, y: 700, s: pop(T, at('Six') - .3, .3) });
      place(r3, { x: 360, y: 810, s: pop(T, at('Six') - .2, .45) });
    });
  });

  // C: fifty items = five hours
  scene(tFifty, tOmni, (g, up) => {
    const ct = node(g, 'font:900 150px/1 Montserrat;color:#ff6b6b;white-space:nowrap;text-shadow:0 0 40px #ff6b6b66;font-variant-numeric:tabular-nums', '0h 00m');
    const cells = [];
    for (let i = 0; i < 50; i++) { const e = node(g, 'width:54px;height:54px;border-radius:14px;background:#fff;overflow:hidden;box-shadow:0 6px 16px rgba(0,0,0,.3)'); const h = hoodie(e, ['#3c4b73', '#e58aa8', '#2f6f7a', '#e8872a', '#6b4630'][i % 5], 52); h.style.left = '27px'; h.style.top = '29px'; h.style.transform = 'translate(-50%,-50%)'; cells.push(e); }
    const lb = badge(g, 'copy + paste', { bg: '#ff4d4d', fg: '#fff', size: 36, pad: '14px 32px' });
    const sub = badge(g, '50 items', { bg: '#fff', size: 34 });
    up((t, T) => {
      const k = prog(T, tFifty + .3, at('five', 0) + .3, E.inOut);
      const mins = Math.round(k * 300);
      ct.textContent = Math.floor(mins / 60) + 'h ' + String(mins % 60).padStart(2, '0') + 'm';
      place(ct, { x: 360, y: 200, s: pop(t, 0, .4) });
      place(sub, { x: 360, y: 340, s: pop(t, .1, .35) });
      cells.forEach((e, i) => place(e, { x: 90 + (i % 10) * 60.5, y: 440 + Math.floor(i / 10) * 66, s: pop(t, .15 + i * .022, .25) }));
      place(lb, { x: 360, y: 810, s: pop(T, at('copy') - .2, .4), r: -2 });
    });
  });

  // D: one tap
  scene(tOmni, tGet, (g, up) => {
    const cells = [];
    for (let i = 0; i < 50; i++) { const e = node(g, 'width:54px;height:54px;border-radius:14px;background:#fff;overflow:hidden;box-shadow:0 6px 16px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;font:900 34px Montserrat;color:#0a1936', '·'); cells.push(e); }
    const btn = node(g, 'padding:30px 56px;border-radius:999px;background:#0649c7;color:#fff;font:900 54px/1 Montserrat;box-shadow:0 14px 40px rgba(6,73,199,.55);white-space:nowrap', 'Publish to all');
    const fin = node(g, 'width:90px;height:90px;border-radius:50%;background:rgba(255,255,255,.55);border:6px solid #fff');
    const ct = node(g, 'font:900 130px/1 Montserrat;color:#85edbc;white-space:nowrap;text-shadow:0 0 40px #85edbc66', '10 s');
    const mk = node(g, 'width:420px', '<div style="display:flex;align-items:center;gap:14px;justify-content:center"><img src="assets/mark.png" style="width:100px"><span style="font:900 42px Montserrat;color:#fff;letter-spacing:-1px">Omnivaleur</span></div>');
    const tTap = at('tap');
    up((t, T) => {
      place(mk, { x: 360, y: 100, s: pop(t, 0, .4) });
      place(ct, { x: 360, y: 250, s: pop(T, tTap + .15, .45) });
      cells.forEach((e, i) => {
        const d = tTap + .1 + (i % 10) * .025 + Math.floor(i / 10) * .06;
        const k = T > d ? 1 : 0;
        e.innerHTML = k ? '✓' : '·'; e.style.background = k ? '#85edbc' : '#fff';
        place(e, { x: 90 + (i % 10) * 60.5, y: 400 + Math.floor(i / 10) * 66, s: pop(t, .1 + i * .01, .25) * (k ? 1 + .15 * Math.sin(cl((T - d) / .3) * Math.PI) : 1) });
      });
      const press = prog(T, tTap - .15, tTap, E.out);
      place(btn, { x: 360, y: 790, s: pop(t, .2, .4) * mix(1, .92, press) });
      place(fin, { x: mix(520, 440, press), y: mix(900, 810, press), s: T > tTap + .4 ? 0 : pop(t, .3, .3) });
    });
  });

  // E: five hours back
  scene(tGet, DURATION + .5, (g, up) => {
    const big = node(g, 'font:900 210px/1 Montserrat;color:#85edbc;white-space:nowrap;text-shadow:0 0 60px #85edbc66', '+5 h');
    const sub = textBlock(g, 'back in your week', { size: 50, w: 680 });
    const cta = node(g, 'padding:22px 44px;border-radius:999px;background:#85edbc;color:#0a1936;font:900 44px/1 Montserrat;box-shadow:0 14px 40px rgba(0,0,0,.4);white-space:nowrap', '7 days free');
    const mk = node(g, 'width:420px', '<div style="display:flex;align-items:center;gap:14px;justify-content:center"><img src="assets/mark.png" style="width:100px"><span style="font:900 42px Montserrat;color:#fff;letter-spacing:-1px">Omnivaleur</span></div>');
    up((t, T) => {
      place(mk, { x: 360, y: 110, s: pop(t, .2, .4) });
      place(big, { x: 360, y: 330, s: pop(t, 0, .5) });
      place(sub, { x: 360, y: 490, s: pop(t, .25, .4) });
      place(cta, { x: 360, y: 720, s: pop(T, tSeven + .1, .4) * (1 + .03 * Math.sin(T * 7)) });
    });
  });
}
