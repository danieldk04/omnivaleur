import { chip, stamp, bubble, badge, line, hoodie } from '../kit.js';
import { character, SKIN } from '../char.js';
import { wall, mkPill, ctaPill, urlTag } from '../common.js';

export const hotColor = '#ffd23f';
export const hotWords = ['betaald', 'wie', 'teleurstellen', 'overal', 'weggehaald', 'twee', 'allebei'];
export const mood = t => ({ a: '#161b3a', b: 'rgba(255,160,90,.18)', dots: 0 });

export function build(K) {
  const { punch, cue, capOff, scene, at, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tAll = at('allebei'), tBet = at('betaald'), tTril = at('trilt'), tEerste = at('Eerste'), tWanneer = at('wanneer'), tTweede = at('Tweede'), tIk = at('ik', 0);
  const tMoet = at('ik', 1) - .1, tWie = at('wie'), tOmni = at('Omnivaleur') - .1, tWeg = at('weggehaald'), tDat = at('Dat') - .1, tZeven = at('Zeven') - .1;
  [tAll, tBet, tTril, tWanneer, tIk, tWie, tWeg, tZeven].forEach(t => punch(t, .04));
  cue(tBet, 'ding'); cue(tBet + .3, 'ding'); cue(tTril, 'buzz'); cue(tTril + .5, 'buzz'); cue(tWanneer, 'pop'); cue(tIk, 'pop'); cue(tWie, 'hit'); cue(tOmni + .5, 'whoosh'); cue(tWeg, 'tick'); cue(tDat, 'ding'); cue(tZeven, 'pop');
  capOff(tDat + .8, tZeven - .05);

  // S1 + S2: two rooms stacked, both buyers waiting
  scene(0, tMoet, (g, up) => {
    const room = (y0, c1, c2, fl) => { const r = node(g, `left:0;top:${y0}px;width:720px;height:440px;transform:none;overflow:hidden;background:linear-gradient(${c1},${c2})`); node(r, `left:0;top:330px;width:720px;height:120px;transform:none;background:${fl}`); return r; };
    const r1 = room(0, '#6a8f7a', '#7fa68d', '#5a4030'), r2 = room(440, '#d7c3a0', '#e6d3b0', '#8a5a36');
    node(g, 'left:0;top:436px;width:720px;height:10px;transform:none;background:#2a1f1a');
    node(r1, 'left:520px;top:60px;width:130px;height:150px;transform:none;background:#e9edf5;border:8px solid #fff;border-radius:6px');
    node(r2, 'left:60px;top:60px;width:130px;height:150px;transform:none;background:#1c2b57;border:8px solid #fff;border-radius:6px');
    const a = character(g, { skin: SKIN.e, hair: '#5a3a2a', hoodie: '#e58aa8', style: 'bun', w: 400 });
    const b = character(g, { skin: SKIN.c, hair: '#14141a', hoodie: '#2f6f7a', style: 'cap', w: 400 });
    const l1 = badge(g, 'Betaald ✓', { size: 32, pad: '12px 26px' }), l2 = badge(g, 'Betaald ✓', { size: 32, pad: '12px 26px' });
    const jas = hoodie(g, '#3c4b73', 150); const jtag = badge(g, '€45', { bg: '#ffc83d', size: 30, pad: '8px 20px' });
    const sellerPh = node(g, 'width:150px;height:260px;border-radius:28px;background:#0b1224;padding:8px;box-shadow:0 14px 40px rgba(0,0,0,.6)', '<div style="width:100%;height:100%;border-radius:20px;background:#fff;padding:12px;font:800 20px Montserrat;color:#0a1936"><div style="background:#ffe1e1;border-radius:10px;padding:8px;margin-bottom:8px">Koper 1: wanneer verstuur je hem?</div><div style="background:#ffe1e1;border-radius:10px;padding:8px">Koper 2: ik wacht nog steeds…</div></div>');
    const q1 = bubble(g, 'Wanneer verstuur je hem?', { w: 300, size: 26 }), q2 = bubble(g, 'Ik wacht nog steeds...', { w: 280, size: 26, me: true });
    up((t, T) => {
      const wa = prog(T, tWanneer - .2, tWanneer + .3), wb = prog(T, tIk - .2, tIk + .3);
      a.pose({ mouth: T > tWanneer ? 'frown' : 'smile', brow: 22 * wa, lSh: 8, rSh: -8, eye: 1, happy: 0, sweat: 0 }, t); place(a, { x: 220, y: 285, s: .66 });
      b.pose({ mouth: T > tIk ? 'frown' : 'smile', brow: 18 * wb, sweat: wb * .5, lSh: 8, rSh: -8, eye: 1 }, t); place(b, { x: 500, y: 725, s: .66 });
      place(l1, { x: 560, y: 70, s: pop(T, tBet - .1, .35) }); place(l2, { x: 160, y: 510, s: pop(T, tBet + .2, .35) });
      place(jas, { x: 360, y: 440, s: pop(t, .2, .45) }); place(jtag, { x: 430, y: 385, s: pop(t, .5, .3), r: 6 });
      const sh = T > tTril ? Math.sin(T * 60) * 5 * Math.exp(-(T - tTril) * .6) : 0;
      place(sellerPh, { x: 360 + sh, y: 440, s: prog(T, tTril - .1, tTril + .3, E.back) * (1 - prog(T, tTweede + 3, tTweede + 3.4, E.lin)), r: sh });
      place(q1, { x: 440, y: 150, s: pop(T, tWanneer, .3) }); place(q2, { x: 250, y: 600, s: pop(T, tIk, .3) });
      sellerPh.style.opacity = 1;
    });
  });

  // S3: seller must choose
  scene(tMoet, tOmni, (g, up) => {
    wall(g, '#3a2342', '#2a1d3a', '#2a2030');
    const s = character(g, { skin: SKIN.b, hair: '#2a1d16', hoodie: '#3c4b73', style: 'short', w: 400 });
    const a = node(g, 'width:150px;height:150px;border-radius:50%;background:#e58aa8;border:8px solid #fff;display:flex;align-items:center;justify-content:center;font:900 70px Montserrat;color:#fff', '1');
    const b = node(g, 'width:150px;height:150px;border-radius:50%;background:#2f6f7a;border:8px solid #fff;display:flex;align-items:center;justify-content:center;font:900 70px Montserrat;color:#fff', '2');
    const q = node(g, 'font:900 200px Montserrat;color:#ffd23f;text-shadow:0 8px 30px rgba(0,0,0,.6)', '?');
    up((t, T) => {
      const gx = Math.sin(t * 2.6) > 0 ? 1 : -1;
      s.pose({ sweat: 1, eye: 1, brow: -16, browY: -6, gx: gx * .9, mouth: 'wavy', headRot: gx * 4, lSh: 8, rSh: -8 }, t);
      place(s, { x: 360, y: 640 - t * 8, s: 1.2 + t * .03 });
      place(a, { x: 110, y: 330, s: pop(t, .1, .35) * (1 + .06 * Math.sin(t * 5)) }); place(b, { x: 610, y: 330, s: pop(t, .3, .35) * (1 + .06 * Math.sin(t * 5 + 2)) });
      place(q, { x: 360, y: 250, s: pop(T, tWie - .1, .4), r: Math.sin(T * 8) * 4 });
    });
  });

  // S4: Omnivaleur pulls it after the first sale
  scene(tOmni, tDat, (g, up) => {
    wall(g, '#18326e', '#25488f', '#2a3f78');
    const s = character(g, { skin: SKIN.b, hair: '#2a1d16', hoodie: '#3c4b73', style: 'short', w: 400 });
    const hub = node(g, 'width:190px;height:190px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 12px rgba(133,237,188,.35),0 18px 50px rgba(0,0,0,.4)', '<img src="assets/mark.png" style="width:135px">');
    const src = chip(g, 'vinted', 130), sSold = stamp(g, 'VERKOCHT', '#ff4d4d', 24);
    const mp = chip(g, 'marktplaats', 130), ok = badge(g, 'Weggehaald ✓', { size: 24 });
    const l0 = line(g, 180, 170, 270, 190), l1 = line(g, 450, 190, 560, 230);
    up((t, T) => {
      s.pose({ happy: 1, mouth: 'smile', lSh: 12, rSh: -12, blush: .5 }, t); place(s, { x: 360, y: 790, s: 1.0 });
      place(hub, { x: 360, y: 190, s: pop(t, 0, .45) * (1 + .03 * Math.sin(t * 6)) });
      place(src, { x: 110, y: 160, s: pop(t, .2, .35) }); place(sSold, { x: 135, y: 205, s: t < .5 ? 0 : E.slam(cl((t - .5) / .5)), r: -12 });
      l0.set(prog(t, .6, 1.1, E.inOut), t > .6 ? 1 : 0);
      const tt = tWeg - tOmni - .6; l1.set(prog(t, tt, tt + .6, E.inOut), t > tt ? 1 : 0);
      const gone = prog(t, tt + .6, tt + .9, E.lin);
      place(mp, { x: 610, y: 230, s: pop(t, .4, .35) * mix(1, .88, gone) }); mp.style.filter = `grayscale(${gone}) opacity(${mix(1, .5, gone)})`;
      place(ok, { x: 600, y: 330, s: pop(T, tWeg + .2, .3) });
    });
  });

  // S5: relaxed + CTA (share bait)
  scene(tDat, DURATION + .5, (g, up) => {
    wall(g, '#2f4a8a', '#4a6fb5', '#3a4f80');
    const s = character(g, { skin: SKIN.b, hair: '#2a1d16', hoodie: '#3c4b73', style: 'short', w: 400 });
    const mk = mkPill(g), cta = ctaPill(g, '7 dagen gratis'), url = urlTag(g);
    const share = badge(g, 'Stuur dit naar een verkoper', { bg: '#ffd23f', fg: '#0a1936', size: 28, pad: '12px 26px' });
    up((t, T) => {
      s.pose({ happy: 1, mouth: 'grin', blush: .6, lSh: 150, rSh: -150, lEl: 20, rEl: -20, bob: -Math.abs(Math.sin(t * 5)) * 5 }, t); place(s, { x: 360, y: 700, s: 1.2 });
      place(mk, { x: 360, y: 105, s: pop(t, .1, .4) }); place(cta, { x: 360, y: 200, s: pop(T, tZeven, .4) * (1 + .03 * Math.sin(T * 7)) });
      place(url, { x: 360, y: 275, s: pop(T, tZeven + .2, .4) }); place(share, { x: 360, y: 340, s: pop(T, tZeven + .4, .4) });
    });
  });
}
