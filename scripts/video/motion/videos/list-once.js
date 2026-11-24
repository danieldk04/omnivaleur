import { hoodie, chip, badge, check, textBlock, line, window_, ring } from '../kit.js';

export const mood = t => ({ a: '#0d2a66', b: 'rgba(133,237,188,.28)' });

export function build(K) {
  const { capOff, cue, scene, at, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tOne = 0, tFour = at('Four') - .05, tTen = at('Ten') - .05, tYou = at('You') - .1, tOmni = at('Omnivaleur') - .1;
  const tVinted = at('Vinted'), tMp = at('Marktplaats'), tEbay = at('eBay'), tShop = at('shop'), tSame = at('Same') - .1, tList = at('List') - .2, tSeven = at('Seven');
  cue(0.1, 'pop'); cue(tFour + .1, 'pop'); cue(tTen + .1, 'pop');
  cue(at('photos'), 'tick'); cue(at('title'), 'tick'); cue(tYou + 2.6, 'hit');
  [tVinted, tMp, tEbay, tShop].forEach(t => cue(t + .5, 'ding'));
  capOff(tList - .05, tSeven - .05); cue(tList + .3, 'ding');

  // A: three stat tiles
  scene(0, tYou + .2, (g, up) => {
    const tile = (big, small, y, extra) => {
      const e = node(g, 'width:600px;height:210px;border-radius:36px;background:#fff;box-shadow:0 18px 50px rgba(0,0,0,.4);display:flex;align-items:center;padding:0 40px;gap:30px',
        `<div style="font:900 120px/1 Montserrat;color:#0649c7;min-width:150px;text-align:center">${big}</div><div style="font:800 46px/1.05 Montserrat;color:#0a1936">${small}</div>`);
      return e;
    };
    const t1 = tile('1', 'listing', 0), t2 = tile('4', 'marketplaces', 0), t3 = tile('10', 'seconds', 0);
    up((t, T) => {
      place(t1, { x: 360, y: 230, s: pop(T, tOne + .05, .45) });
      place(t2, { x: 360, y: 470, s: pop(T, tFour, .45) });
      place(t3, { x: 360, y: 710, s: pop(T, tTen, .45) });
    });
  });

  // B: one listing form being filled in
  scene(tYou, tOmni, (g, up) => {
    const w = window_(g, 600, 700, 'New item');
    const photo = node(g, 'width:230px;height:230px;border-radius:24px;background:linear-gradient(135deg,#ffe3ec,#dbe8ff);overflow:hidden');
    const hd = hoodie(photo, '#3c4b73', 210); hd.style.left = '115px'; hd.style.top = '125px'; hd.style.transform = 'translate(-50%,-50%)';
    const thumbs = ['#e58aa8', '#2f6f7a', '#e8872a'].map(c => { const e = node(g, 'width:100px;height:100px;border-radius:18px;background:#eaf1f6;overflow:hidden'); const h = hoodie(e, c, 92); h.style.left = '50px'; h.style.top = '54px'; h.style.transform = 'translate(-50%,-50%)'; return e; });
    const f1 = node(g, 'width:520px;padding:18px 24px;border-radius:16px;background:#eaf1f6;font:700 34px/1.1 Montserrat;color:#0a1936');
    const f2 = node(g, 'width:240px;padding:18px 24px;border-radius:16px;background:#eaf1f6;font:800 38px/1.1 Montserrat;color:#0a1936');
    const lbl = (txt, y) => node(g, 'font:700 22px Montserrat;color:#485363;text-transform:uppercase;letter-spacing:2px', txt);
    const l1 = lbl('Title'), l2 = lbl('Price'), l3 = lbl('Photos');
    const btn = node(g, 'width:520px;padding:22px;border-radius:999px;background:#0649c7;color:#fff;text-align:center;font:900 38px Montserrat;box-shadow:0 10px 30px rgba(6,73,199,.5)', 'Publish');
    const title = 'Nike Tech Fleece, M';
    up((t, T) => {
      place(w, { x: 360, y: 470, s: pop(t, 0, .45) });
      place(photo, { x: 215, y: 375, s: pop(t, .2, .4) });
      place(l3, { x: 545, y: 282, s: pop(t, .2, .3) });
      thumbs.forEach((e, i) => place(e, { x: 475 + (i % 2) * 112, y: 355 + Math.floor(i / 2) * 112, s: pop(T, at('photos') - .15 + i * .22, .35) }));
      place(l1, { x: 160, y: 540, s: pop(t, .5, .3) });
      const n = Math.floor(cl((T - at('title') + .25) / .9) * title.length);
      f1.textContent = title.slice(0, n) + (n < title.length ? '|' : '');
      place(f1, { x: 360, y: 600, s: pop(t, .5, .3) });
      place(l2, { x: 140, y: 670, s: pop(t, .8, .3) });
      f2.textContent = T > at('title') + .9 ? '€68' : '';
      place(f2, { x: 240, y: 730, s: pop(t, .8, .3) });
      const press = T > tOmni - .55;
      place(btn, { x: 360, y: 765, s: pop(t, 1.0, .35) * (press ? .93 : 1 + .02 * Math.sin(t * 6)) });
    });
  });

  // C: one tap, four marketplaces
  scene(tOmni, tSame, (g, up) => {
    const card = node(g, 'width:540px;padding:18px 26px;border-radius:26px;background:#fff;box-shadow:0 14px 40px rgba(0,0,0,.4);display:flex;align-items:center;gap:22px',
      '<div style="width:80px;height:80px;border-radius:16px;background:linear-gradient(135deg,#ffe3ec,#dbe8ff)"></div><div><div style="font:800 28px Montserrat;color:#0a1936">Nike Tech Fleece, M</div><div style="font:900 34px Montserrat;color:#0649c7">€68</div></div>');
    const hubm = node(g, 'width:120px;height:120px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 10px rgba(133,237,188,.35)', '<img src="assets/mark.png" style="width:84px">');
    const D = [['vinted', 215, 570, tVinted], ['marktplaats', 505, 570, tMp], ['ebay', 215, 790, tEbay], ['shop', 505, 790, tShop]].map(([k, x, y, tt]) => ({ k, x, y, tt, c: chip(g, k, 160), ok: badge(g, 'Live ✓', { size: 26 }), rg: ring(g, 190, '#85edbc', 'rgba(255,255,255,.2)') }));
    const lines = D.map(d => line(g, 360, 400, d.x, d.y - 50));
    up((t, T) => {
      place(card, { x: 360, y: 180, s: pop(t, 0, .4) });
      place(hubm, { x: 360, y: 400, s: pop(t, .25, .4) });
      D.forEach((d, i) => {
        const start = Math.min(d.tt - .6, tOmni + .5 + i * .15);
        const k = prog(T, start, d.tt + .1, E.inOut);
        lines[i].set(k, T > start ? 1 : 0);
        place(d.c, { x: d.x, y: d.y, s: pop(t, .4 + i * .1, .35) });
        const done = T > d.tt + .35;
        d.rg.set(prog(T, d.tt - .1, d.tt + .35, E.inOut));
        place(d.rg, { x: d.x, y: d.y, s: pop(t, .4 + i * .1, .35) * (done ? 1.04 : 1), o: done ? 0 : 1 });
        place(d.ok, { x: d.x + 38, y: d.y + 90, s: done ? pop(T, d.tt + .35, .3) : 0 });
      });
    });
  });

  // D: real dashboard crop, then CTA
  scene(tSame, DURATION + .5, (g, up) => {
    const dash = node(g, 'width:540px;height:520px;border-radius:30px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.5);background:#fff url(assets/items-crosslisted.webp) no-repeat;background-size:2880px auto;background-position:-1776px -456px');
    const tag = badge(g, 'Live everywhere', { size: 30, pad: '14px 28px' });
    const big = textBlock(g, 'List once.<br>Sell everywhere.', { size: 76, w: 680 });
    const cta = node(g, 'padding:22px 44px;border-radius:999px;background:#85edbc;color:#0a1936;font:900 44px/1 Montserrat;box-shadow:0 14px 40px rgba(0,0,0,.4);white-space:nowrap', '7 days free');
    const mk = node(g, 'width:420px', '<div style="display:flex;align-items:center;gap:14px;justify-content:center"><img src="assets/mark.png" style="width:110px"><span style="font:900 46px Montserrat;color:#fff;letter-spacing:-1px">Omnivaleur</span></div>');
    up((t, T) => {
      const toCta = prog(T, tList, tList + .5, E.inOut);
      place(dash, { x: 360, y: 400, s: pop(t, 0, .45) * mix(1, .85, toCta), o: 1 - toCta });
      place(tag, { x: 360, y: 720, s: pop(t, .6, .35) * (1 - toCta) });
      place(big, { x: 360, y: 520, s: pop(T, tList, .45) });
      place(cta, { x: 360, y: 730, s: pop(T, tSeven - .2, .4) * (1 + .03 * Math.sin(T * 7)) });
      place(mk, { x: 360, y: 90, s: pop(T, tList + .1, .4) });
    });
  });
}
