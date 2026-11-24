import { chip, stamp, bubble, badge, hoodie } from '../kit.js';
import { character, SKIN } from '../char.js';
import { envKitchen, envPost, wall, mkPill, ctaPill, urlTag, card, rel, finger } from '../common.js';

export const hotColor = '#ffd23f';
export const hotWords = ['forty', 'fortyfive', 'twenty', 'seven', 'five', 'ten', 'three', 'euros', 'profit', 'skip', 'free'];
export const mood = t => ({ a: '#14301f', b: 'rgba(80,200,120,.25)', dots: 0 });

export function build(K) {
  const { cam, punch, cue, capOff, scene, at, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tSold = at('sold'), tThen = at('Then') - .1, tTwenty = at('twenty.'), tShip = at('Shipping,'), tPack = at('Packaging,'), tTrip = at('trip'), tMade = at('made') - .2, tThree = at('Three.'), tOmni = at("Omnivaleur's") - .1, tProfit = at('profit'), tSkip = at('Skip') - .1, tSeven = at('Seven') - .1;
  [tTwenty, tShip, tPack, at('ten.'), at('three'), tThree, tProfit, tSeven].forEach(t => punch(t, .045));
  cue(tSold + .3, 'ding'); cue(tTwenty, 'tick'); cue(tShip, 'tick'); cue(tPack, 'tick'); cue(at('ten.'), 'tick'); cue(at('three'), 'hit'); cue(tThree, 'buzz'); cue(tProfit, 'ding'); cue(tSeven, 'pop');
  capOff(at('Seven') + .4, DURATION);
  cam(0, 1.6, { s: 1.35, fx: 360, fy: 520 }); cam(1.6, 3.8, { s: 1 }); cam(5.4, 7.0, { s: 1.3, fx: 360, fy: 340 }); cam(7.0, 9.0, { s: 1.2, fx: 360, fy: 780 }); cam(9.0, 11.0, { s: 1.0 }); cam(11.0, 12.5, { s: 1.5, fx: 360, fy: 800 }); cam(12.5, 16.0, { s: 1.6, fx: 360, fy: 650 }); cam(16.7, 19.5, { s: 1.0 });

  // S1: proud
  scene(0, tThen, (g, up) => {
    envKitchen(g);
    const me = character(g, { skin: SKIN.c, hair: '#c9c9c9', hoodie: '#2f6f7a', style: 'short', glasses: true, w: 400 });
    const big = badge(g, '€45', { bg: '#ffd23f', fg: '#0a1936', size: 110, pad: '16px 50px' });
    const bills = Array.from({ length: 14 }, (_, i) => node(g, 'width:90px;height:44px;border-radius:6px;background:#5ac47a;border:3px solid #2c8a50;color:#1c4a2c;font:900 26px/38px Montserrat;text-align:center', '€'));
    up((t, T) => {
      me.pose({ happy: 1, mouth: 'grin', blush: .6, lSh: 150, rSh: -150, lEl: 20, rEl: -20, bob: -Math.abs(Math.sin(t * 6)) * 8 }, t); place(me, { x: 360, y: 700, s: 1.2 });
      place(big, { x: 360, y: 230, s: pop(T, tSold, .45), r: -4 });
      bills.forEach((b, i) => { const k = (t * .35 + i * .19) % 1; place(b, { x: 60 + (i * 53) % 640, y: -40 + k * 940, r: i * 40 + t * 120 * (i % 2 ? 1 : -1), s: t > .3 ? 1 : 0 }); });
    });
  });

  // S2: the maths
  scene(tThen, tMade, (g, up) => {
    envPost(g);
    const me = character(g, { skin: SKIN.c, hair: '#c9c9c9', hoodie: '#2f6f7a', style: 'short', glasses: true, w: 400 });
    const ct = card(g, 560, 'height:430px;padding:26px 30px;font:800 34px Montserrat;color:#0a1936');
    const rows = [['Sold for', '€45', 0], ['Bought for', '−€20', tTwenty], ['Shipping', '−€7', tShip], ['Packaging', '−€5', tPack], ['Trip to post point', '−€10', at('ten.')]].map(([l, v, tt]) => ({ tt, e: rel(ct, 'display:flex;justify-content:space-between;padding:10px 0;border-bottom:3px dashed #e1e6ee', `<span>${l}</span><b style="color:${tt ? '#ff4d4d' : '#00a368'}">${v}</b>`) }));
    const tot = rel(ct, 'margin-top:14px;display:flex;justify-content:space-between;font:900 52px Montserrat', '<span>Profit</span><b class="t">€45</b>');
    up((t, T) => {
      let val = 45; rows.forEach(r => { if (T > r.tt && r.tt) val -= Number(r.e.querySelector('b').textContent.replace('−€', '')); r.e.style.opacity = r.tt ? (T > r.tt - .15 ? 1 : 0) : 1; });
      tot.querySelector('.t').textContent = '€' + val; tot.querySelector('.t').style.color = val > 20 ? '#00a368' : '#ff4d4d';
      const worry = prog(T, tTwenty, at('ten.'));
      me.pose({ happy: 1 - worry, mouth: worry > .6 ? 'frown' : 'smile', brow: -14 * worry, sweat: worry, lSh: 8, rSh: -8, eye: 1 }, t); place(me, { x: 360, y: 810, s: .95 });
      place(ct, { x: 360, y: 340, s: pop(t, .05, .4) });
    });
  });

  // S3: three euros
  scene(tMade, tOmni, (g, up) => {
    envPost(g);
    const me = character(g, { skin: SKIN.c, hair: '#c9c9c9', hoodie: '#2f6f7a', style: 'short', glasses: true, w: 400 });
    const big = node(g, 'font:900 300px/1 Montserrat;color:#ff4d4d;text-shadow:0 10px 40px rgba(255,77,77,.4)', '€3'); const lb = badge(g, 'one whole evening', { bg: '#fff', size: 38 });
    up((t, T) => {
      me.pose({ eye: .5, mouth: 'frown', brow: -8, lSh: 8, rSh: -8, headY: 14, headRot: -4, bags: .8 }, t); place(me, { x: 360, y: 770, s: 1.1 });
      place(big, { x: 360, y: 280, s: T < at('three') ? 0 : E.slam(cl((T - at('three')) / .5)) });
      place(lb, { x: 360, y: 470, s: pop(T, at('evening.') - .6, .35) });
    });
  });

  // S4: margin calculator
  scene(tOmni, tSkip, (g, up) => {
    wall(g, '#18326e', '#25488f', '#2a3f78');
    const me = character(g, { skin: SKIN.c, hair: '#c9c9c9', hoodie: '#2f6f7a', style: 'short', glasses: true, w: 400 });
    const ui = card(g, 580, 'height:420px;font:800 30px Montserrat;color:#0a1936');
    rel(ui, 'font:900 36px Montserrat;margin-bottom:12px', 'Margin calculator');
    const f = (l, v) => rel(ui, 'display:flex;justify-content:space-between;padding:8px 0;border-bottom:3px dashed #e1e6ee', `<span>${l}</span><b>${v}</b>`);
    f('Bought for', '€20'); f('Shipping + packaging', '€12'); f('Travel', '€10'); f('Selling price', '€45');
    const res = rel(ui, 'margin-top:14px;padding:14px 18px;border-radius:18px;background:#ffe7e3;display:flex;justify-content:space-between;font:900 40px Montserrat;color:#a51f1b', '<span>Profit</span><b>€3 ⚠</b>');
    const ok = badge(g, 'Low margin: skip', { bg: '#ffd23f', fg: '#0a1936', size: 32, pad: '12px 28px' });
    up((t, T) => {
      me.pose({ happy: prog(T, tProfit, tProfit + .5), mouth: T > tProfit ? 'smile' : 'flat', brow: -6, lSh: 8, rSh: -8, eye: 1 }, t); place(me, { x: 360, y: 810, s: .95 });
      place(ui, { x: 360, y: 320, s: pop(t, 0, .45) }); place(ok, { x: 360, y: 590, s: pop(T, tProfit, .4), r: -2 });
    });
  });

  // S5: skip + CTA
  scene(tSkip, DURATION + .5, (g, up) => {
    wall(g, '#2f4a8a', '#4a6fb5', '#3a4f80');
    const me = character(g, { skin: SKIN.c, hair: '#c9c9c9', hoodie: '#2f6f7a', style: 'short', glasses: true, w: 400 });
    const x3 = badge(g, '€3 items', { bg: '#fff', fg: '#0a1936', size: 44, pad: '16px 40px' }); const strike = node(g, 'width:300px;height:10px;background:#ff4d4d;border-radius:5px');
    const mk = mkPill(g), cta = ctaPill(g, '7 days free'), url = urlTag(g), share = badge(g, 'Send this to a reseller', { bg: '#ffd23f', fg: '#0a1936', size: 28, pad: '12px 26px' });
    up((t, T) => {
      me.pose({ happy: 1, mouth: 'grin', blush: .6, lSh: 150, rSh: -150, lEl: 20, rEl: -20, bob: -Math.abs(Math.sin(t * 5)) * 5 }, t); place(me, { x: 360, y: 740, s: 1.15 });
      place(x3, { x: 360, y: 500, s: pop(t, .05, .4) }); place(strike, { x: 360, y: 500, s: 1, sx: prog(t, .45, .8) });
      place(mk, { x: 360, y: 105, s: pop(t, .1, .4) }); place(cta, { x: 360, y: 200, s: pop(T, tSeven, .4) * (1 + .03 * Math.sin(T * 7)) });
      place(url, { x: 360, y: 275, s: pop(T, tSeven + .2, .4) }); place(share, { x: 360, y: 340, s: pop(T, tSeven + .4, .4) });
    });
  });
}
