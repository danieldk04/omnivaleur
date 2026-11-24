import { hoodie, chip, stamp, bubble, badge, line, textBlock } from '../kit.js';
import { character, SKIN } from '../char.js';

export const mood = t => ({ a: '#161b3a', b: 'rgba(255,160,90,.2)', dots: 0 });

export function build(K) {
  const { cue, capOff, scene, at, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tBuyer = at('buyer'), tHood = at('hoodie') - .1, tBecause = at('Because') - .1, tSold = at('sold'), tOmni = at('Omnivaleur') - .1, tPulls = at('pulls'), tNever = at('Never') - .1, tSeven = at('Seven') - .1;
  cue(tBuyer + .6, 'hit'); cue(tBuyer + .85, 'hit'); cue(tBuyer + 1.1, 'hit'); cue(tHood + .2, 'pop'); cue(tSold + .1, 'hit'); cue(tSold + .45, 'hit'); cue(tPulls, 'tick'); cue(tPulls + .6, 'tick'); cue(tPulls + 1.0, 'tick'); cue(tNever + .2, 'ding'); cue(tSeven, 'pop');
  const wall = (g, c1, c2, floor = '#3a2a22') => { node(g, `left:0;top:0;width:720px;height:900px;transform:none;background:linear-gradient(${c1},${c2})`); node(g, `left:0;top:740px;width:720px;height:220px;transform:none;background:${floor}`); };
  const mkBadge = g => node(g, 'width:440px', '<div style="display:flex;align-items:center;gap:14px;justify-content:center;background:#fff;padding:14px 30px;border-radius:999px;box-shadow:0 14px 40px rgba(0,0,0,.35)"><img src="assets/mark.png" style="width:92px"><span style="font:900 42px Montserrat;color:#0a1936;letter-spacing:-1px">Omnivaleur</span></div>');

  // S1: the angry buyer at the door
  scene(0, tHood, (g, up) => {
    wall(g, '#2a2342', '#3d2f4e');
    node(g, 'left:90px;top:170px;width:240px;height:580px;transform:none;border-radius:14px 14px 0 0;background:linear-gradient(90deg,#7a4a2c,#8a5733);border:10px solid #5a3820');
    node(g, 'left:285px;top:430px;width:20px;height:20px;transform:none;border-radius:50%;background:#e8c36a');
    node(g, 'left:150px;top:230px;width:120px;height:52px;transform:none;background:#e8c36a;border-radius:8px;text-align:center;font:900 40px/52px Montserrat;color:#4a3010', '12');
    node(g, 'left:60px;top:735px;width:300px;height:36px;transform:none;border-radius:10px;background:#9a3b3b');
    const b = character(g, { skin: SKIN.c, hair: '#14141a', hoodie: '#2f6f7a', style: 'cap', w: 400 });
    const bub = bubble(g, 'Where is my hoodie?', { w: 330, size: 30 });
    const dots = node(g, 'font:900 70px Montserrat;color:#ff6b6b;transform:none', '!');
    up(t => {
      const sh = Math.sin(t * 9) * 1.5;
      b.pose({ brow: 22, browY: 2, mouth: 'frown', eye: .85, lSh: 14, lEl: -98, rSh: -14, rEl: 98, headRot: sh, bob: Math.abs(Math.sin(t * 7)) * -5, lean: 0, gx: -.4 }, t);
      place(b, { x: 440, y: 650, s: 1.2 });
      place(bub, { x: 460, y: 300, s: pop(t, .5, .3) });
      place(dots, { x: 600, y: 410, s: pop(t, .6, .3), r: 10 });
    });
  });

  // S2: someone else has it
  scene(tHood, tBecause, (g, up) => {
    wall(g, '#5a3d5e', '#7a5070', '#4a3340');
    node(g, 'left:60px;top:200px;width:240px;height:550px;transform:none;border-radius:14px 14px 0 0;background:linear-gradient(90deg,#3c7a57,#4a8f67);border:10px solid #2c5a40');
    node(g, 'left:130px;top:260px;width:100px;height:100px;transform:none;border-radius:50%;background:#f2c078;opacity:.8');
    const c = character(g, { skin: SKIN.e, hair: '#5a3a2a', hoodie: '#e58aa8', style: 'bun', w: 400 });
    const h = hoodie(g, '#3c4b73', 260);
    const tag = badge(g, 'Marktplaats', { bg: '#fff', size: 28, pad: '12px 24px' });
    up((t, T) => {
      const k = prog(t, .15, .6, E.out);
      c.pose({ happy: 1, mouth: 'grin', blush: .7, lSh: mix(8, 150, k), rSh: mix(-8, -150, k), lEl: mix(5, 22, k), rEl: mix(-5, -22, k), bob: -Math.abs(Math.sin(t * 6)) * 8 * k }, t);
      place(c, { x: 400, y: 650, s: 1.2 });
      place(h, { x: 400, y: mix(560, 305, k) - Math.abs(Math.sin(t * 6)) * 8 * k, s: .98, r: Math.sin(t * 6) * 4 });
      place(tag, { x: 540, y: 190, s: pop(t, .6, .35), r: 4 });
    });
  });

  // S3: it sold twice
  scene(tBecause, tOmni, (g, up) => {
    const h = hoodie(g, '#3c4b73', 330);
    const cv = chip(g, 'vinted', 190), cm = chip(g, 'marktplaats', 190);
    const sv = stamp(g, 'SOLD', '#ff4d4d', 38), sm = stamp(g, 'SOLD', '#ff4d4d', 38);
    const t1 = badge(g, '€45', { bg: '#fff', size: 38 }), t2 = badge(g, '€45', { bg: '#fff', size: 38 });
    const bang = badge(g, '2 sales, 1 hoodie', { bg: '#ff4d4d', fg: '#fff', size: 40, pad: '16px 30px' });
    up((t, T) => {
      const a = T - tSold;
      place(h, { x: 360, y: 430, s: pop(t, 0, .45) });
      place(cv, { x: 130, y: 370, s: pop(t, .15, .35) }); place(cm, { x: 590, y: 370, s: pop(t, .45, .35) });
      place(t1, { x: 130, y: 510, s: pop(t, .3, .3) }); place(t2, { x: 590, y: 510, s: pop(t, .6, .3) });
      place(sv, { x: 175, y: 440, s: t < .5 ? 0 : E.slam(cl((t - .5) / .5)), r: -14 }); place(sm, { x: 545, y: 440, s: t < .85 ? 0 : E.slam(cl((t - .85) / .5)), r: 12 });
      place(bang, { x: 360, y: 760, s: pop(t, 1.0, .4), r: -3 });
    });
  });

  // S4: Omnivaleur pulls it, seller relaxes
  scene(tOmni, tNever, (g, up) => {
    wall(g, '#18326e', '#25488f', '#2a3f78');
    const s = character(g, { skin: SKIN.a, hair: '#2a1d16', hoodie: '#1f2a55', style: 'short', glasses: true, w: 400 });
    const hub = node(g, 'width:190px;height:190px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 12px rgba(133,237,188,.35),0 18px 50px rgba(0,0,0,.4)', '<img src="assets/mark.png" style="width:135px">');
    const src = chip(g, 'vinted', 120), sSold = stamp(g, 'SOLD', '#ff4d4d', 26);
    const D = [['marktplaats', 200], ['ebay', 360], ['shop', 520]].map(([k, x], i) => ({ x, i, c: chip(g, k, 120), ok: badge(g, 'Removed ✓', { size: 22 }) }));
    const L = D.map(d => line(g, 360, 230, d.x, 380));
    const l0 = line(g, 170, 150, 270, 200);
    up((t, T) => {
      s.pose({ happy: 1, mouth: 'smile', lSh: 12, lEl: 6, rSh: -12, rEl: -6, blush: .5, headRot: Math.sin(t * 1.5) * 3 }, t);
      place(s, { x: 360, y: 770, s: 1.0 });
      place(hub, { x: 360, y: 170, s: pop(t, 0, .45) * (1 + .03 * Math.sin(t * 6)) });
      place(src, { x: 100, y: 140, s: pop(t, .2, .35) }); place(sSold, { x: 125, y: 180, s: t < .5 ? 0 : E.slam(cl((t - .5) / .5)), r: -12 });
      l0.set(prog(t, .5, 1, E.inOut), t > .5 ? 1 : 0);
      D.forEach((d, i) => {
        const tt = tPulls - tOmni - .1 + i * .4; const k = prog(t, tt, tt + .45, E.inOut); L[i].set(k, t > tt ? 1 : 0);
        const gone = prog(t, tt + .45, tt + .7, E.lin);
        place(d.c, { x: d.x, y: 420, s: pop(t, .4 + i * .1, .35) * mix(1, .88, gone) }); d.c.style.filter = `grayscale(${gone}) opacity(${mix(1, .5, gone)})`;
        place(d.ok, { x: d.x, y: 505, s: pop(t, tt + .5, .3) });
      });
    });
  });

  // S5: happy buyer, hoodie arrived
  scene(tNever, DURATION + .5, (g, up) => {
    wall(g, '#2f4a8a', '#4a6fb5', '#3a4f80');
    node(g, 'left:70px;top:210px;width:230px;height:540px;transform:none;border-radius:14px 14px 0 0;background:linear-gradient(90deg,#7a4a2c,#8a5733);border:10px solid #5a3820');
    const c = character(g, { skin: SKIN.c, hair: '#14141a', hoodie: '#2f6f7a', style: 'cap', w: 400 });
    const h = hoodie(g, '#3c4b73', 240);
    const mk = mkBadge(g);
    const cta = node(g, 'padding:22px 44px;border-radius:999px;background:#85edbc;color:#0a1936;font:900 46px/1 Montserrat;box-shadow:0 14px 40px rgba(0,0,0,.4);white-space:nowrap', '7 days free');
    up((t, T) => {
      const k = prog(t, .1, .5, E.out);
      c.pose({ happy: 1, mouth: 'grin', blush: .6, lSh: mix(14, 150, k), rSh: mix(-14, -150, k), lEl: mix(-98, 22, k), rEl: mix(98, -22, k), bob: -Math.abs(Math.sin(t * 5)) * 6 * k }, t);
      place(c, { x: 420, y: 650, s: 1.2 });
      place(h, { x: 420, y: mix(560, 315, k) - Math.abs(Math.sin(t * 5)) * 6 * k, s: .92 });
      place(mk, { x: 360, y: 105, s: pop(t, .2, .4) });
      place(cta, { x: 360, y: 190, s: pop(T, tSeven, .4) * (1 + .03 * Math.sin(T * 7)) });
    });
  });
}
