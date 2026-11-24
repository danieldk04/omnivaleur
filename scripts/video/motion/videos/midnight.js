import { hoodie, chip, badge, check, textBlock, line, laptop, clockText } from '../kit.js';

let tNowG = 999;
export const mood = t => (t < tNowG
  ? { a: '#0b1026', b: 'rgba(120,70,190,.35)', dots: .4 }
  : { a: '#0d3a8a', b: 'rgba(255,200,61,.30)' });

export function build(K) {
  const { cue, scene, at, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tS0 = at('Same', 0) - .1, tNow = at('Now') - .1, tYou = at('You') - .1, tLap = at('Laptop') - .1, tSeven = at('Seven') - .1;
  tNowG = tNow;
  cue(at('listing') + .1, 'tick'); cue(tS0 + .4, 'pop'); cue(at('photos') + .1, 'pop'); cue(at('title') + .1, 'pop'); cue(at('Fourth') + .2, 'buzz');
  cue(tNow + .3, 'whoosh'); cue(at('Omnivaleur') + .1, 'ding'); cue(tYou + 1.2, 'hit'); cue(at('live') + .1, 'ding'); cue(at('closed') + .1, 'hit'); cue(tSeven, 'pop');
  const miniCard = (g, color) => { const e = node(g, 'width:150px;height:190px;border-radius:20px;background:#fff;box-shadow:0 10px 28px rgba(0,0,0,.4);overflow:hidden'); const h = hoodie(e, color, 130); h.style.left = '75px'; h.style.top = '70px'; h.style.transform = 'translate(-50%,-50%)'; node(e, 'left:14px;top:140px;width:100px;height:12px;border-radius:6px;background:#d0d8e1'); node(e, 'left:14px;top:160px;width:60px;height:12px;border-radius:6px;background:#85edbc'); return e; };
  const moon = (g) => node(g, 'width:110px;height:110px', '<svg viewBox="0 0 100 100" width="110" height="110"><path d="M62 10 A42 42 0 1 0 90 62 A34 34 0 0 1 62 10Z" fill="#ffe9a8"/></svg>');
  const sun = (g) => node(g, 'width:130px;height:130px', '<svg viewBox="0 0 100 100" width="130" height="130"><g stroke="#ffc83d" stroke-width="6" stroke-linecap="round">' + [0, 45, 90, 135, 180, 225, 270, 315].map(a => `<line x1="50" y1="12" x2="50" y2="2" transform="rotate(${a} 50 50)"/>`).join('') + '</g><circle cx="50" cy="50" r="26" fill="#ffc83d"/></svg>');

  // A: 00:40, still listing
  scene(0, tS0 + .15, (g, up) => {
    const mn = moon(g), ck = clockText(g, 130, '#ffe9a8');
    const lp = laptop(g, 560);
    const tabs = ['vinted', 'marktplaats', 'ebay', 'shop'].map(k => chip(g, k, 90));
    const zz = [0, 1, 2].map(i => node(g, `font:900 ${40 + i * 14}px Montserrat;color:#9aa5ff`, 'z'));
    const bar = node(lp.scr, 'left:30px;top:40px;width:70%;height:20px;border-radius:10px;background:#d0d8e1');
    const bar2 = node(lp.scr, 'left:30px;top:90px;width:45%;height:20px;border-radius:10px;background:#d0d8e1');
    const photo = node(lp.scr, 'left:30px;top:150px;width:120px;height:120px;border-radius:16px;background:linear-gradient(135deg,#ffe3ec,#dbe8ff)');
    up((t, T) => {
      place(mn, { x: 95, y: 150, s: pop(t, 0, .5) });
      ck.setTime(40 + (T > at('listing') ? 1 : 0)); place(ck, { x: 440, y: 160, s: pop(t, .1, .45) });
      lp.open(1); place(lp, { x: 360, y: 560, s: pop(t, .25, .45) });
      tabs.forEach((e, i) => { const act = T > at('Fourth') - .05 && i === 3; place(e, { x: 160 + i * 130, y: 330, s: pop(t, .6 + i * .1, .3) * (act ? 1.15 : 1), o: i === 3 && !act ? .35 : 1 }); });
      zz.forEach((e, i) => place(e, { x: 590 + i * 22, y: 300 - i * 38 + Math.sin(t * 2 + i) * 6, s: 1, o: .5 + .5 * Math.sin(t * 2 + i) }));
      photo.style.opacity = 1;
    });
  });

  // B: same photos, same title, fourth app
  scene(tS0, tNow, (g, up) => {
    const ck = clockText(g, 96, '#ff8d8d');
    const C = ['vinted', 'marktplaats', 'ebay', 'shop'].map((k, i) => ({ chip: chip(g, k, 130), card: miniCard(g, '#3c4b73'), x: 125 + i * 157 }));
    const tag = badge(g, 'the exact same listing, 4 times', { bg: '#ff4d4d', fg: '#fff', size: 30, pad: '16px 30px' });
    const arrows = C.map(c => node(g, 'font:900 50px Montserrat;color:#ffffff88', '↻'));
    const times = [at('photos'), at('title'), at('Fourth') - .1, at('tonight')];
    up((t, T) => {
      ck.setTime(40 + 3 + Math.min(1, t / (tNow - tS0)) * 52); place(ck, { x: 360, y: 130, s: 1 });
      C.forEach((c, i) => {
        const k = pop(T, times[i] - .3, .35);
        place(c.chip, { x: c.x, y: 340, s: pop(t, .1 + i * .1, .35) });
        place(c.card, { x: c.x, y: 570 + (1 - k) * 60, s: k });
      });
      arrows.forEach((a, i) => place(a, { x: C[i].x, y: 450, s: pop(T, times[i] - .2, .3), r: T * 200 }));
      place(tag, { x: 360, y: 770, s: pop(T, at('title') + .2, .4) });
    });
  });

  // C: same evening, but sunnier: clock runs back
  scene(tNow, tYou, (g, up) => {
    const sn = sun(g), ck = clockText(g, 160, '#fff'), mk = node(g, 'width:420px', '<div style="display:flex;align-items:center;gap:14px;justify-content:center;background:#fff;padding:16px 34px;border-radius:999px;box-shadow:0 14px 40px rgba(0,0,0,.35)"><img src="assets/mark.png" style="width:92px"><span style="font:900 42px Montserrat;color:#0a1936;letter-spacing:-1px">Omnivaleur</span></div>');
    const lbl = badge(g, 'same evening', { bg: '#ffc83d', fg: '#0a1936', size: 34, pad: '14px 30px' });
    up((t, T) => {
      const k = prog(t, .1, 1.6, E.inOut);
      ck.setTime(95 - k * 280); place(ck, { x: 360, y: 330, s: pop(t, 0, .4) });
      place(sn, { x: 360, y: 150, s: pop(t, .9, .5), r: T * 40 });
      place(lbl, { x: 360, y: 520, s: pop(t, .5, .4) });
      place(mk, { x: 360, y: 690, s: pop(T, at('Omnivaleur') - .3, .45) });
    });
  });

  // D: add once, live everywhere
  scene(tYou, tLap, (g, up) => {
    const card = node(g, 'width:540px;padding:18px 26px;border-radius:26px;background:#fff;box-shadow:0 14px 40px rgba(0,0,0,.4);display:flex;align-items:center;gap:22px',
      '<div style="width:80px;height:80px;border-radius:16px;background:linear-gradient(135deg,#ffe3ec,#dbe8ff)"></div><div><div style="font:800 28px Montserrat;color:#0a1936">Nike Tech Fleece, M</div><div style="font:900 34px Montserrat;color:#0649c7">€68</div></div>');
    const cnt = badge(g, 'added once', { bg: '#ffc83d', fg: '#0a1936', size: 30 });
    const hub = node(g, 'width:120px;height:120px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 10px rgba(255,255,255,.3)', '<img src="assets/mark.png" style="width:84px">');
    const D = ['vinted', 'marktplaats', 'ebay', 'shop'].map((k, i) => ({ c: chip(g, k, 130), ok: badge(g, 'Live ✓', { size: 24 }), x: 125 + i * 157, tt: at('live') - .3 + i * .22 }));
    const lines = D.map(d => line(g, 360, 400, d.x, 580));
    up((t, T) => {
      place(card, { x: 360, y: 190, s: pop(t, 0, .4) });
      place(cnt, { x: 560, y: 285, s: pop(t, .5, .3), r: 6 });
      place(hub, { x: 360, y: 400, s: pop(t, .6, .4) });
      D.forEach((d, i) => {
        const k = prog(T, d.tt - .4, d.tt, E.inOut);
        lines[i].set(k, T > d.tt - .4 ? 1 : 0);
        place(d.c, { x: d.x, y: 640, s: pop(t, .7 + i * .08, .35) });
        place(d.ok, { x: d.x, y: 745, s: T > d.tt ? pop(T, d.tt, .3) : 0 });
      });
    });
  });

  // E: laptop closed at nine
  scene(tLap, DURATION + .5, (g, up) => {
    const ck = clockText(g, 150, '#fff'), lp = laptop(g, 520), big = badge(g, 'All 4 live ✓', { size: 40, pad: '16px 34px' });
    const cta = node(g, 'padding:22px 44px;border-radius:999px;background:#85edbc;color:#0a1936;font:900 44px/1 Montserrat;box-shadow:0 14px 40px rgba(0,0,0,.4);white-space:nowrap', '7 days free');
    const mk = node(g, 'width:420px', '<div style="display:flex;align-items:center;gap:14px;justify-content:center"><img src="assets/mark.png" style="width:100px"><span style="font:900 42px Montserrat;color:#fff;letter-spacing:-1px">Omnivaleur</span></div>');
    const dash = node(lp.scr, 'left:30px;top:40px;width:70%;height:20px;border-radius:10px;background:#85edbc');
    up((t, T) => {
      ck.setTime(20 * 60 + 56 + prog(T, tLap, at('nine') + .2, E.lin) * 4); place(ck, { x: 360, y: 150, s: pop(t, 0, .4) });
      const cl_ = prog(T, at('closed') - .15, at('closed') + .35, E.inOut);
      lp.open(1 - cl_); place(lp, { x: 360, y: 450, s: pop(t, .1, .4) });
      place(big, { x: 360, y: 700, s: pop(T, at('closed') + .3, .4) });
      place(cta, { x: 360, y: 800, s: pop(T, tSeven + .1, .4) * (1 + .03 * Math.sin(T * 7)) });
      place(mk, { x: 360, y: 300, s: 0 });
    });
  });
}
