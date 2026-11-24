import { chip, stamp, bubble, badge, hoodie } from '../kit.js';
import { character, SKIN } from '../char.js';
import { wall, mkPill, ctaPill, urlTag, card, rel, finger } from '../common.js';

export const hotColor = '#ffd23f';
export const hotWords = ['seventeen', 'zero', 'months', 'buried', 'stale', 'refreshes', 'free', 'again'];
export const mood = t => ({ a: '#1a1d36', b: 'rgba(130,140,200,.22)', dots: 0 });

export function build(K) {
  const { punch, cue, capOff, scene, at, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tZero = at('Zero'), tMonths = at('months.'), tThey = at('They') - .1, tBuried = at('buried'), tSo = at('So') - .1, tOmni = at('Omnivaleur') - .1, tFlags = at('flags'), tRef = at('refreshes'), tAgain = at('again.'), tSeven = at('Seven') - .1;
  [tZero, tMonths, tBuried, tFlags, tRef, tSeven].forEach(t => punch(t, .045));
  cue(tZero, 'buzz'); cue(tBuried, 'hit'); cue(tFlags, 'tick'); cue(tRef, 'whoosh'); cue(tRef + .4, 'ding'); cue(tSeven, 'pop');
  capOff(at('Seven') + .4, DURATION);
  const tiles = (g, n, size = 66) => Array.from({ length: n }, (_, i) => { const e = node(g, `width:${size}px;height:${size}px;border-radius:14px;background:#dfe5f2;overflow:hidden;box-shadow:0 6px 14px rgba(0,0,0,.35)`); const h = hoodie(e, ['#3c4b73', '#e58aa8', '#2f6f7a', '#e8872a', '#6b4630'][i % 5], size - 4); h.style.left = size / 2 + 'px'; h.style.top = size / 2 + 3 + 'px'; h.style.transform = 'translate(-50%,-50%)'; return e; });
  const gx = i => 90 + (i % 6) * 108, gy = i => 250 + Math.floor(i / 6) * 100;

  // S1: 17 forgotten items
  scene(0, tThey, (g, up) => {
    wall(g, '#1a1d36', '#262a4a', '#2a2030');
    const me = character(g, { skin: SKIN.b, hair: '#2a1d16', hoodie: '#3c4b73', style: 'short', w: 400 });
    const T17 = tiles(g, 17); const big = badge(g, '17 items', { bg: '#fff', size: 44, pad: '12px 30px' }); const zero = badge(g, '0 views', { bg: '#ff4d4d', fg: '#fff', size: 56, pad: '16px 38px' });
    up((t, T) => {
      me.pose({ eye: .6, mouth: 'flat', brow: 8, bags: .8, lSh: 8, rSh: -8, headY: 10 }, t); place(me, { x: 360, y: 790, s: .95 });
      T17.forEach((e, i) => { place(e, { x: gx(i), y: gy(i), s: pop(t, .05 + i * .06, .3) }); e.style.filter = `grayscale(${prog(T, tZero, tZero + .4)}) brightness(${mix(1, .65, prog(T, tZero, tZero + .4))})`; });
      place(big, { x: 360, y: 150, s: pop(t, 0, .4) }); place(zero, { x: 360, y: 640, s: pop(T, tZero, .4), r: -3 });
    });
  });

  // S2: buried by newer listings
  scene(tThey, tSo, (g, up) => {
    wall(g, '#1a1d36', '#262a4a', '#2a2030');
    const me = character(g, { skin: SKIN.b, hair: '#2a1d16', hoodie: '#3c4b73', style: 'short', w: 400 });
    const old = tiles(g, 17); const fresh = Array.from({ length: 14 }, (_, i) => node(g, 'width:100px;height:100px;border-radius:18px;background:linear-gradient(135deg,#ffe3ec,#dbe8ff);border:4px solid #fff;box-shadow:0 8px 18px rgba(0,0,0,.4)'));
    const lb = badge(g, 'NEW', { bg: '#ffd23f', fg: '#0a1936', size: 30 });
    up((t, T) => {
      me.pose({ eye: .7, mouth: 'wavy', brow: -8, sweat: .6, lSh: 8, rSh: -8 }, t); place(me, { x: 360, y: 790, s: .95 });
      old.forEach((e, i) => { place(e, { x: gx(i), y: gy(i) + prog(T, tBuried - .3, tBuried + 1.6) * 40, s: 1 }); e.style.filter = 'grayscale(1) brightness(.6)'; });
      fresh.forEach((e, i) => { const tt = tBuried - .7 + i * .12; const k = prog(T, tt, tt + .45, E.out); place(e, { x: 70 + (i % 7) * 96, y: mix(-100, 200 + Math.floor(i / 7) * 140, k), s: 1, r: (i % 3 - 1) * 4 }); });
      place(lb, { x: 360, y: 120, s: pop(T, tBuried - .6, .3) });
    });
  });

  // S3: decision beat
  scene(tSo, tOmni, (g, up) => {
    wall(g, '#262a4a', '#34385e', '#2a2030');
    const me = character(g, { skin: SKIN.b, hair: '#2a1d16', hoodie: '#3c4b73', style: 'short', w: 400 });
    up((t) => {
      const k = prog(t, 1.2, 2.2, E.out);
      me.pose({ eye: 1, mouth: k > .5 ? 'smile' : 'flat', brow: mix(0, 20, k), lSh: mix(8, 30, k), lEl: mix(4, -90, k), rSh: -8, headRot: mix(0, 4, k) }, t); place(me, { x: 360, y: 640, s: 1.25 + t * .02 });
    });
  });

  // S4: stale stock flagged, refreshed
  scene(tOmni, tSeven, (g, up) => {
    wall(g, '#18326e', '#25488f', '#2a3f78');
    const me = character(g, { skin: SKIN.b, hair: '#2a1d16', hoodie: '#3c4b73', style: 'short', w: 400 });
    const ui = card(g, 580, 'height:200px;font:800 30px Montserrat;color:#0a1936');
    rel(ui, 'display:flex;justify-content:space-between;align-items:center', '<div><div style="font:900 34px Montserrat">Stale stock</div><div style="font:800 24px Montserrat;color:#a65d00">17 items not seen for weeks</div></div><div style="padding:10px 20px;border-radius:14px;background:#fbe9c6;color:#7b4800;font:900 46px Montserrat">17</div>');
    const btn = rel(ui, 'margin-top:18px;padding:18px;border-radius:999px;background:#0649c7;color:#fff;font:900 32px Montserrat;text-align:center', 'Refresh all');
    const T17 = tiles(g, 17); const f = finger(g);
    up((t, T) => {
      const done = T > tRef + .2; const climb = prog(T, tRef, tRef + 1.4, E.out);
      me.pose({ happy: done ? 1 : 0, mouth: done ? 'grin' : 'smile', lSh: done ? 150 : 8, rSh: done ? -150 : -8, lEl: done ? 20 : 4, rEl: done ? -20 : -4, blush: done ? .5 : 0, eye: 1 }, t); place(me, { x: 360, y: 810, s: .95 });
      place(ui, { x: 360, y: 190, s: pop(t, 0, .45) });
      btn.style.background = done ? '#00a368' : '#0649c7'; btn.textContent = done ? 'Refreshed ✓' : 'Refresh all';
      T17.forEach((e, i) => { place(e, { x: gx(i), y: mix(gy(i) + 170, gy(i) + 120 - Math.floor(i / 6) * 0 , climb) , s: pop(t, .2 + i * .03, .25) * (1 + (done ? .12 * Math.sin(cl((T - tRef) / 1.2) * Math.PI) : 0)) }); const gr = T < tFlags ? 1 : 1 - climb; e.style.filter = `grayscale(${gr}) brightness(${mix(1, .65, gr)})`; });
      const k = prog(T, tRef - .9, tRef - .05, E.inOut); place(f, { x: mix(600, 360, k), y: mix(420, 276, k), s: T > tFlags && !done ? 1 : 0 });
    });
  });

  // S5: CTA
  scene(tSeven, DURATION + .5, (g, up) => {
    wall(g, '#2f4a8a', '#4a6fb5', '#3a4f80');
    const me = character(g, { skin: SKIN.b, hair: '#2a1d16', hoodie: '#3c4b73', style: 'short', w: 400 });
    const mk = mkPill(g), cta = ctaPill(g, '7 days free'), url = urlTag(g), share = badge(g, 'Send this to a reseller', { bg: '#ffd23f', fg: '#0a1936', size: 28, pad: '12px 26px' });
    up((t) => {
      me.pose({ happy: 1, mouth: 'grin', blush: .6, lSh: 150, rSh: -150, lEl: 20, rEl: -20, bob: -Math.abs(Math.sin(t * 5)) * 5 }, t); place(me, { x: 360, y: 700, s: 1.2 });
      place(mk, { x: 360, y: 105, s: pop(t, .1, .4) }); place(cta, { x: 360, y: 200, s: pop(t, .15, .4) * (1 + .03 * Math.sin(t * 7)) });
      place(url, { x: 360, y: 275, s: pop(t, .3, .4) }); place(share, { x: 360, y: 340, s: pop(t, .45, .4) });
    });
  });
}
