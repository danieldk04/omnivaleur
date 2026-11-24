import { chip, stamp, bubble, badge, hoodie, line } from '../kit.js';
import { character, SKIN } from '../char.js';
import { wall, mkPill, ctaPill, urlTag, card, rel, finger } from '../common.js';

export const hotColor = '#ffd23f';
export const hotWords = ['hundred', 'zero', 'twenty', 'hours', 'import', 'everywhere', 'free', 'photos', 'titles', 'sizes'];
export const mood = t => ({ a: '#1b2038', b: 'rgba(150,200,90,.22)', dots: 0 });

export function build(K) {
  const { punch, cue, capOff, scene, at, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tHad = 0, tZero = at('zero'), tRel = at('Relisting') - .1, tTwenty = at('twenty'), tOr = at('Or...') - .1, tImp = at('import.'), tOmni = at('Omnivaleur') - .1, tPh = at('Photos,'), tTi = at('titles,'), tSz = at('sizes.'), tThen = at('Then') - .1, tEvery = at('everywhere.'), tSeven = at('Seven') - .1;
  [tZero, tTwenty, tImp, tPh, tTi, tSz, tEvery, tSeven].forEach(t => punch(t, .045));
  cue(tZero, 'buzz'); cue(tTwenty, 'hit'); cue(tImp, 'ding'); cue(tOmni + .4, 'whoosh'); cue(tPh, 'pop'); cue(tTi, 'pop'); cue(tSz, 'pop'); cue(tEvery, 'ding'); cue(tSeven, 'pop');
  capOff(at('Seven') + .4, DURATION);
  const mini = (g, n, s = 40) => Array.from({ length: n }, (_, i) => { const e = node(g, `width:${s}px;height:${s}px;border-radius:9px;background:#dfe5f2;overflow:hidden`); const h = hoodie(e, ['#3c4b73', '#e58aa8', '#2f6f7a', '#e8872a', '#6b4630'][i % 5], s - 2); h.style.left = s / 2 + 'px'; h.style.top = s / 2 + 2 + 'px'; h.style.transform = 'translate(-50%,-50%)'; return e; });

  // S1: 200 on Shopify, 0 on Vinted
  scene(0, tRel, (g, up) => {
    wall(g, '#1b2038', '#2a3050', '#2a2030');
    const me = character(g, { skin: SKIN.e, hair: '#5a3a2a', hoodie: '#e58aa8', style: 'bun', w: 400 });
    const sh = chip(g, 'shop', 130), vi = chip(g, 'vinted', 130); const cs = badge(g, '200', { bg: '#85edbc', size: 54, pad: '10px 30px' }), cv = badge(g, '0', { bg: '#ff4d4d', fg: '#fff', size: 54, pad: '10px 36px' });
    const T = mini(g, 60, 36);
    up((t, T_) => {
      me.pose({ eye: .8, mouth: T_ > tZero ? 'frown' : 'flat', brow: 6, sweat: prog(T_, tZero, tZero + .6), lSh: 8, rSh: -8 }, t); place(me, { x: 360, y: 790, s: .95 });
      place(sh, { x: 150, y: 130, s: pop(t, 0, .4) }); place(cs, { x: 150, y: 235, s: pop(t, .3, .3) });
      place(vi, { x: 570, y: 130, s: pop(T_, tZero - .3, .4) }); place(cv, { x: 570, y: 235, s: pop(T_, tZero, .3) });
      T.forEach((e, i) => place(e, { x: 40 + (i % 10) * 44, y: 300 + Math.floor(i / 10) * 44, s: pop(t, .2 + i * .02, .2) * (i < 45 || t > .2 ? 1 : 0) }));
    });
  });

  // S2: twenty hours
  scene(tRel, tOr, (g, up) => {
    wall(g, '#2a1d2a', '#3a2c3a', '#2a2030');
    const me = character(g, { skin: SKIN.e, hair: '#5a3a2a', hoodie: '#e58aa8', style: 'bun', w: 400 });
    const big = node(g, 'font:900 250px/1 Montserrat;color:#ff4d4d;text-shadow:0 10px 40px rgba(255,77,77,.4)', '20h'); const lb = badge(g, 'copy and paste', { bg: '#fff', size: 38 });
    const ck = node(g, 'font:900 120px Montserrat', '⏳');
    up((t, T) => {
      me.pose({ eye: .45, mouth: 'frown', bags: 1, brow: 4, headY: 14, headRot: -5, lSh: 8, rSh: -8 }, t); place(me, { x: 360, y: 790, s: .95 });
      place(big, { x: 360, y: 260, s: T < tTwenty ? .5 : E.slam(cl((T - tTwenty) / .5)) }); place(lb, { x: 360, y: 440, s: pop(T, at('copy') - .2, .35) }); place(ck, { x: 360, y: 560, s: pop(t, .3, .4), r: t * 220 });
    });
  });

  // S3: or... one import
  scene(tOr, tOmni, (g, up) => {
    wall(g, '#18326e', '#25488f', '#2a3f78');
    const me = character(g, { skin: SKIN.e, hair: '#5a3a2a', hoodie: '#e58aa8', style: 'bun', w: 400 });
    const btn = node(g, 'padding:30px 70px;border-radius:999px;background:#0649c7;color:#fff;font:900 70px Montserrat;box-shadow:0 14px 40px rgba(6,73,199,.6);white-space:nowrap', 'Import');
    up((t, T) => {
      const k = prog(t, .2, .8, E.out);
      me.pose({ eye: 1, mouth: 'smile', brow: -6 * (1 - k), lSh: 8, rSh: -8, headRot: 3 }, t); place(me, { x: 360, y: 790, s: .95 });
      place(btn, { x: 360, y: 350, s: pop(T, tImp - .6, .45) * (T > tImp - .1 ? .94 : 1 + .03 * Math.sin(t * 8)) });
    });
  });

  // S4: shop -> Omnivaleur -> list
  scene(tOmni, tThen, (g, up) => {
    wall(g, '#18326e', '#25488f', '#2a3f78');
    const me = character(g, { skin: SKIN.e, hair: '#5a3a2a', hoodie: '#e58aa8', style: 'bun', w: 400 });
    const sh = chip(g, 'shop', 120); const hub = node(g, 'width:170px;height:170px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 12px rgba(133,237,188,.35)', '<img src="assets/mark.png" style="width:120px">');
    const fly = mini(g, 14, 50); const ui = card(g, 560, 'height:300px;padding:18px 22px;font:800 28px Montserrat;color:#0a1936');
    const rows = ['Photos', 'Titles', 'Sizes'].map(l => rel(ui, 'display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:3px dashed #e1e6ee', `<span>${l}</span><b style="color:#00a368">✓ imported</b>`));
    const cnt = badge(g, '200 items in', { bg: '#85edbc', size: 36 });
    const l1 = line(g, 220, 150, 280, 150), l2 = line(g, 440, 150, 500, 150);
    up((t, T) => {
      me.pose({ happy: 1, mouth: 'smile', lSh: 8, rSh: -8 }, t); place(me, { x: 360, y: 810, s: .95 });
      place(sh, { x: 110, y: 150, s: pop(t, 0, .4) }); place(hub, { x: 360, y: 150, s: pop(t, .15, .45) * (1 + .03 * Math.sin(t * 6)) });
      fly.forEach((e, i) => { const tt = .5 + i * .18; const k = prog(t, tt, tt + .9, E.inOut); place(e, { x: mix(110, 610, k), y: mix(150, 190 - 40 * Math.sin(k * Math.PI), k), s: t > tt && k < .98 ? 1 : 0, r: k * 180 }); });
      place(ui, { x: 360, y: 450, s: pop(t, .2, .45) });
      rows.forEach((r, i) => { r.style.opacity = T > [tPh, tTi, tSz][i] - .2 ? 1 : .15; });
      place(cnt, { x: 360, y: 640, s: pop(T, tSz, .35) });
    });
  });

  // S5: list everywhere + CTA
  scene(tThen, DURATION + .5, (g, up) => {
    wall(g, '#2f4a8a', '#4a6fb5', '#3a4f80');
    const me = character(g, { skin: SKIN.e, hair: '#5a3a2a', hoodie: '#e58aa8', style: 'bun', w: 400 });
    const ch = ['vinted', 'marktplaats', 'ebay', 'shop'].map(k => chip(g, k, 120)); const ok = ch.map(() => badge(g, '✓', { size: 30 }));
    const mk = mkPill(g), cta = ctaPill(g, '7 days free'), url = urlTag(g), share = badge(g, 'Send this to a reseller', { bg: '#ffd23f', fg: '#0a1936', size: 28, pad: '12px 26px' });
    up((t, T) => {
      const fin = T > tSeven;
      me.pose({ happy: 1, mouth: 'grin', blush: .6, lSh: 150, rSh: -150, lEl: 20, rEl: -20, bob: -Math.abs(Math.sin(t * 5)) * 5 }, t); place(me, { x: 360, y: 740, s: 1.15 });
      ch.forEach((c, i) => { const x = 105 + i * 170; place(c, { x, y: mix(330, 490, prog(T, tSeven, tSeven + .4)), s: pop(t, .1 + i * .12, .35) * (fin ? .8 : 1) }); place(ok[i], { x: x + 40, y: mix(380, 530, prog(T, tSeven, tSeven + .4)), s: pop(T, tEvery - .3 + i * .12, .3) }); });
      place(mk, { x: 360, y: 105, s: pop(T, tSeven, .4) }); place(cta, { x: 360, y: 200, s: pop(T, tSeven + .05, .4) * (1 + .03 * Math.sin(T * 7)) });
      place(url, { x: 360, y: 275, s: pop(T, tSeven + .25, .4) }); place(share, { x: 360, y: 340, s: pop(T, tSeven + .45, .4) });
    });
  });
}
