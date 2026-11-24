import { hoodie, chip, stamp, bubble, avatar, badge, check, cross, textBlock, line } from '../kit.js';

export const mood = t => (t < 9.8
  ? { a: '#1a2d63', b: 'rgba(255,77,77,.28)' }
  : { a: '#0d2a66', b: 'rgba(133,237,188,.30)' });

export function build(K) {
  const { capOff, cue, scene, at, endOf, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tTwo = at('Two'), tSold1 = at('sold', 0) - .1, tSold2 = at('sold', 1) - .1, tNow = at('Now') - .1;
  const tOmni = at('Omnivaleur') - .1, tSees = at('sees'), tNo = at('No'), tTry = at('Try') - .2;

  capOff(tNo - .1, tTry - .1); cue(tTwo, 'pop'); cue(tTwo + .25, 'pop'); cue(tSold1 + .55, 'hit'); cue(tSold2 + .55, 'hit'); cue(tSold2 + 1.5, 'buzz'); cue(tNow + 1.9, 'pop'); cue(tSees, 'tick'); cue(tSees + .9, 'tick'); cue(tSees + 1.25, 'tick'); cue(tSees + 1.6, 'tick'); cue(tNo - .1 + .35, 'ding'); cue(tTry, 'pop');
  // A: one hoodie, two buyers
  scene(0, tSold1 + .2, (g, up) => {
    const h = hoodie(g, '#3c4b73', 360), tag = badge(g, '€45', { bg: '#ffc83d', size: 40, pad: '12px 26px' });
    const a1 = avatar(g, 'A', '#e0568a'), a2 = avatar(g, 'M', '#2f9e8f');
    const b1 = bubble(g, 'I\'ll take it!', { w: 270, size: 34 }), b2 = bubble(g, 'I\'ll take it!', { w: 270, me: true, size: 34 });
    up(t => {
      place(h, { x: 360, y: 400 + Math.sin(t * 2.4) * 8, s: pop(t, 0, .5) * 1.0 });
      place(tag, { x: 500, y: 290, s: pop(t, .3, .3), r: -8 + Math.sin(t * 3) * 3 });
      const k = prog(t, tTwo, tTwo + .4, E.back);
      place(a1, { x: mix(-80, 110, k), y: 760, s: 1 });
      place(a2, { x: mix(800, 610, k), y: 760, s: 1 });
      place(b1, { x: mix(-200, 190, k), y: 640, s: pop(t, tTwo + .25, .3) });
      place(b2, { x: mix(900, 530, k), y: 640, s: pop(t, tTwo + .4, .3) });
    });
  });

  // B: sold on Vinted at 9, on Marktplaats at 9:15
  scene(tSold1, tNow, (g, up) => {
    const h = hoodie(g, '#3c4b73', 330);
    const cv = chip(g, 'vinted', 190), cm = chip(g, 'marktplaats', 190);
    const sv = stamp(g, 'SOLD', '#ff4d4d', 38), sm = stamp(g, 'SOLD', '#ff4d4d', 38);
    const t1 = badge(g, '09:00', { bg: '#fff', size: 38 }), t2 = badge(g, '09:15', { bg: '#fff', size: 38 });
    const bang = badge(g, '2 sales, 1 hoodie', { bg: '#ff4d4d', fg: '#fff', size: 40, pad: '16px 30px' });
    const x1 = cross(g, 100);
    const l1 = line(g, 250, 420, 330, 420, { color: '#ffffff' }), l2 = line(g, 470, 420, 390, 420, { color: '#ffffff' });
    up((t, T) => {
      const a = T - tSold1, b = T - tSold2;
      place(cv, { x: 130, y: 380, s: pop(a, 0, .35) });
      place(cm, { x: 590, y: 380, s: pop(b, 0, .35) });
      place(t1, { x: 130, y: 520, s: pop(a, .12, .3) });
      place(t2, { x: 590, y: 520, s: pop(b, .12, .3) });
      const ks = a < 0 ? 0 : E.slam(cl((a - .25) / .5));
      place(sv, { x: 175, y: 450, s: a < .25 ? 0 : ks, r: -14 });
      const km = b < 0 ? 0 : E.slam(cl((b - .25) / .5));
      place(sm, { x: 545, y: 450, s: b < .25 ? 0 : km, r: 12 });
      const hb = T > tSold2 + .5 ? Math.sin((T - tSold2 - .5) * 30) * 5 * Math.exp(-(T - tSold2 - .5) * 3) : 0;
      place(h, { x: 360 + hb, y: 450, s: pop(a, .1, .4) });
      const kb = prog(T, tSold2 + 1.5, tSold2 + 1.9, E.back);
      place(bang, { x: 360, y: 760, s: kb, r: -3 });
      place(x1, { x: 360, y: 400, s: 0 });
      l1.set(0, 0); l2.set(0, 0);
    });
  });

  // C: sorry message + refund
  scene(tNow, tOmni, (g, up) => {
    const av = avatar(g, 'M', '#2f9e8f', 96);
    const b1 = bubble(g, 'Is my hoodie still coming?', { w: 470, size: 32 });
    const b2 = bubble(g, '', { w: 480, me: true, size: 32 });
    const rc = node(g, 'width:560px;padding:26px 34px;border-radius:28px;background:#fff;box-shadow:0 14px 40px rgba(0,0,0,.4);display:flex;align-items:center;justify-content:space-between',
      '<div><div style="font:700 24px Montserrat;color:#485363">Refund to buyer</div><div style="font:900 56px/1.1 Montserrat;color:#ff4d4d">−€45</div></div><div style="font:900 80px Montserrat;color:#ff4d4d">↩</div>');
    const msg = 'Hi! So sorry, it\'s already sold. I\'ll refund you right away…';
    up(t => {
      place(av, { x: 90, y: 330, s: pop(t, 0, .3) });
      place(b1, { x: 360, y: 330, s: pop(t, .1, .3) });
      place(b2, { x: 345, y: 520, s: pop(t, .6, .3) });
      const n = Math.floor(cl((t - .8) / 1.8) * msg.length);
      b2.innerHTML = msg.slice(0, n) + '<span style="opacity:.6">|</span>';
      place(rc, { x: 360, y: 760, s: pop(t, 1.9, .4), r: -2 });
    });
  });

  // D: Omnivaleur sees the sale and pulls it everywhere else
  scene(tOmni, tNo - .1, (g, up) => {
    const hub = node(g, 'width:230px;height:230px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 14px rgba(133,237,188,.35),0 18px 50px rgba(0,0,0,.4)', '<img src="assets/mark.png" style="width:165px">');
    const src = chip(g, 'vinted', 150), sSold = stamp(g, 'SOLD', '#ff4d4d', 30);
    const dest = [['marktplaats', 150, 640], ['ebay', 360, 660], ['shop', 570, 640]].map(([k, x, y]) => ({ k, x, y, c: chip(g, k, 150), ok: badge(g, 'Removed ✓', { size: 24 }) }));
    const lines = dest.map(d => line(g, 360, 400, d.x, d.y - 90));
    const lsrc = line(g, 150, 220, 300, 350);
    const tLine = tSees - tOmni;
    up((t, T) => {
      place(hub, { x: 360, y: 380, s: pop(t, 0, .45) * (1 + .03 * Math.sin(t * 6)) });
      place(src, { x: 150, y: 180, s: pop(t, .2, .35) });
      place(sSold, { x: 175, y: 215, s: t < .5 ? 0 : E.slam(cl((t - .5) / .5)), r: -12 });
      lsrc.set(prog(t, tLine, tLine + .5, E.inOut), t > tLine ? 1 : 0);
      dest.forEach((d, i) => {
        const tD = tLine + .6 + i * .35;
        const k = prog(t, tD, tD + .5, E.inOut);
        lines[i].set(k, t > tD ? 1 : 0);
        const gone = prog(t, tD + .5, tD + .75, E.lin);
        place(d.c, { x: d.x, y: d.y, s: pop(t, .4 + i * .08, .35) * mix(1, .88, gone) });
        d.c.style.filter = `grayscale(${gone}) opacity(${mix(1, .5, gone)})`;
        place(d.ok, { x: d.x, y: d.y + 112, s: pop(t, tD + .5, .3) });
      });
    });
  });

  // E: result + CTA
  scene(tNo - .1, DURATION + .5, (g, up) => {
    const ck = check(g, 220);
    const big = textBlock(g, 'No double<br>sales.', { size: 92, w: 680 });
    const cta = node(g, 'padding:22px 44px;border-radius:999px;background:#85edbc;color:#0a1936;font:900 44px/1 Montserrat;box-shadow:0 14px 40px rgba(0,0,0,.4);white-space:nowrap', '7 days free');
    const mk = node(g, 'width:420px', '<div style="display:flex;align-items:center;gap:14px;justify-content:center"><img src="assets/mark.png" style="width:110px"><span style="font:900 46px Montserrat;color:#fff;letter-spacing:-1px">Omnivaleur</span></div>');
    mk.style.textAlign = 'center';
    up((t, T) => {
      place(ck, { x: 360, y: 290, s: pop(t, .1, .5) });
      ck.setCk(prog(t, .3, .8, E.out));
      place(big, { x: 360, y: 540, s: pop(t, .35, .45) });
      const e = T - tTry;
      place(cta, { x: 360, y: 730, s: pop(e, 0, .4) * (1 + .03 * Math.sin(e * 7)) });
      place(mk, { x: 360, y: 105, s: pop(e, .1, .4) });
    });
  });
}
