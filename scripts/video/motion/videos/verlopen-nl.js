import { chip, stamp, bubble, badge, hoodie } from '../kit.js';
import { character, SKIN } from '../char.js';
import { envBeach, envStreet, wall, mkPill, ctaPill, urlTag, card, rel, finger } from '../common.js';

export const hotColor = '#ffd23f';
export const hotWords = ['twaalf', 'niet', 'niks', 'verlopen', 'klik', 'gratis', 'verwijderd'];
export const mood = t => ({ a: '#161b3a', b: 'rgba(120,160,255,.2)', dots: 0 });

export function build(K) {
  const { cam, punch, cue, capOff, scene, at, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tWist = at('wist') - .2, tMp = at('Marktplaats'), tStil = at('stilletjes'), tGeen = at('Geen') - .1, tNiks = at('niks.'), tTot = at('Tot') - .1, tZag = at('zag.'), tOmni = at('Omnivaleur') - .1, tKlik = at('klik'), tZeven = at('Zeven') - .1;
  [tStil, tNiks, tZag, tKlik, tZeven, at('Twaalf', 1)].forEach(t => punch(t, .045));
  cue(.2, 'tick'); cue(tStil, 'hit'); cue(tNiks, 'hit'); cue(tTot, 'buzz'); cue(tZag, 'pop'); cue(tKlik, 'tick'); cue(tKlik + .25, 'ding'); cue(tZeven, 'pop');
  capOff(at('Zeven') + .5, DURATION);
  cam(.0, 1.3, { s: 1 }); cam(1.3, 3.2, { s: 1.5, fx: 360, fy: 560 }); cam(3.2, 5.2, { s: 1.15, fx: 450, fy: 400 }); cam(5.2, 7.2, { s: 1.6, fx: 520, fy: 330 }); cam(7.2, 9.0, { s: 1.0 }); cam(9.0, 11.9, { s: 1.45, fx: 360, fy: 560 }); cam(12.0, 13.6, { s: 1.35, fx: 360, fy: 720 }); cam(13.6, 17.9, { s: 1.0 }); cam(17.9, 19.3, { s: 1.35, fx: 360, fy: 380 });

  // S1: twelve days tick by
  scene(0, tWist, (g, up) => {
    envBeach(g);
    const me = character(g, { skin: SKIN.d, hair: '#14141a', hoodie: '#e8872a', style: 'curly', glasses: true, w: 400 });
    const cal = card(g, 250, 'text-align:center;padding:14px 10px'); cal.innerHTML = '<div style="background:#ff4d4d;color:#fff;border-radius:14px 14px 0 0;font:900 28px Montserrat;padding:6px">DAG</div><div class="n" style="font:900 120px/1.1 Montserrat;color:#0a1936">1</div>';
    const mp = chip(g, 'marktplaats', 150), st = badge(g, 'Online', { size: 28 });
    const jas = hoodie(g, '#3c4b73', 190);
    up((t) => {
      const d = 1 + Math.floor(prog(t, .2, 2.7, E.lin) * 11);
      cal.querySelector('.n').textContent = d;
      me.pose({ happy: 1, mouth: 'smile', lSh: 8, rSh: -8, eye: 1 }, t); place(me, { x: 360, y: 700, s: 1.1 });
      place(cal, { x: 160, y: 250, s: pop(t, 0, .4) });
      place(jas, { x: 540, y: 270, s: pop(t, .2, .4) });
      place(mp, { x: 560, y: 420, s: pop(t, .4, .35) }); const late = d > 6;
      st.textContent = late ? 'Verlopen' : 'Online'; st.style.background = late ? '#c5c9d6' : '#85edbc';
      place(st, { x: 560, y: 520, s: pop(t, .6, .3) });
    });
  });

  // S2: nobody told him
  scene(tWist, tGeen, (g, up) => {
    envBeach(g);
    const me = character(g, { skin: SKIN.d, hair: '#14141a', hoodie: '#e8872a', style: 'curly', glasses: true, w: 400 });
    const mp = chip(g, 'marktplaats', 190), clock = node(g, 'font:900 80px Montserrat;color:#c5c9d6', '⏰'), sv = stamp(g, 'VERLOPEN', '#7a8199', 40);
    const th = bubble(g, 'Alles loopt toch?', { w: 330, size: 30 });
    up((t, T) => {
      me.pose({ happy: 1, mouth: 'smile', lSh: 8, rSh: -8, headRot: Math.sin(t * 2) * 3 }, t); place(me, { x: 360, y: 700, s: 1.2 });
      place(th, { x: 250, y: 330, s: pop(t, .3, .35) * (1 - prog(T, tStil - .3, tStil, E.lin)) });
      place(mp, { x: 520, y: 300, s: pop(T, tMp - .1, .4) });
      mp.style.filter = `grayscale(${prog(T, tStil, tStil + .4, E.lin)})`;
      place(sv, { x: 520, y: 380, s: T < tStil ? 0 : E.slam(cl((T - tStil) / .5)), r: -10 });
      place(clock, { x: 640, y: 220, s: pop(T, tStil, .4), r: Math.sin(T * 12) * 10 });
    });
  });

  // S3: zero views
  scene(tGeen, tTot, (g, up) => {
    envStreet(g);
    const me = character(g, { skin: SKIN.d, hair: '#14141a', hoodie: '#e8872a', style: 'curly', glasses: true, w: 400 });
    const big = node(g, 'font:900 260px/1 Montserrat;color:#ff4d4d;text-shadow:0 10px 40px rgba(255,77,77,.4)', '0'); const lb = badge(g, 'views', { bg: '#fff', size: 40 });
    const ppl = [0, 1, 2].map(i => node(g, 'width:90px;height:90px;border-radius:50%;background:#59607d;display:flex;align-items:center;justify-content:center;font:900 50px Montserrat;color:#c5c9d6', '?'));
    up((t, T) => {
      me.pose({ eye: .8, brow: -10, mouth: 'flat', sweat: prog(t, 2, 3), lSh: 8, rSh: -8, gx: Math.sin(t * 2) * .8 }, t); place(me, { x: 360, y: 740, s: 1.15 });
      place(big, { x: 360, y: 250, s: T < tNiks - .3 ? .6 + .2 * Math.sin(t * 4) : E.slam(cl((T - tNiks + .3) / .5)) });
      place(lb, { x: 360, y: 400, s: pop(t, .3, .3) });
      ppl.forEach((p, i) => place(p, { x: ((t * 120 + i * 260) % 900) - 90, y: 520 + (i % 2) * 20, s: 1 }));
    });
  });

  // S4 + S5: discovery, then one click
  scene(tTot, tZeven, (g, up) => {
    wall(g, '#18326e', '#25488f', '#2a3f78');
    const me = character(g, { skin: SKIN.d, hair: '#14141a', hoodie: '#e8872a', style: 'curly', glasses: true, w: 400 });
    const ui = card(g, 560, 'height:360px;padding:22px 26px');
    rel(ui, 'display:flex;gap:14px;margin-bottom:16px', '<div style="padding:8px 18px;border-radius:999px;background:#eaf1f6;font:800 24px Montserrat;color:#485363">Live</div><div class="tab" style="padding:8px 18px;border-radius:999px;background:#0649c7;color:#fff;font:800 24px Montserrat">Verlopen 1</div>');
    const row = rel(ui, 'display:flex;align-items:center;gap:18px;padding:16px;border-radius:20px;background:#f4f7fb', '<div style="width:80px;height:80px;border-radius:16px;background:linear-gradient(135deg,#ffe3ec,#dbe8ff)"></div><div style="flex:1"><div style="font:800 28px Montserrat;color:#0a1936">Beste jas</div><div class="s" style="font:800 24px Montserrat;color:#7a8199">⏰ Verlopen op Marktplaats</div></div>');
    const btn = rel(ui, 'margin-top:24px;padding:20px;border-radius:999px;background:#0649c7;color:#fff;font:900 34px Montserrat;text-align:center;box-shadow:0 10px 24px rgba(6,73,199,.5)', 'Weer online zetten');
    const f = finger(g); const bang = node(g, 'font:900 150px Montserrat;color:#ffd23f;text-shadow:0 8px 24px rgba(0,0,0,.5)', '!');
    up((t, T) => {
      const shock = T < tOmni; const done = T > tKlik + .3;
      me.pose(shock ? { eye: 1, mouth: 'o', brow: -14, sweat: .8, lSh: 8, rSh: -8 } : done ? { happy: 1, mouth: 'grin', lSh: 150, rSh: -150, lEl: 20, rEl: -20, blush: .5 } : { eye: 1, mouth: 'smile', lSh: 8, rSh: -8 }, t);
      place(me, { x: 360, y: 790, s: 1.0 });
      place(bang, { x: 600, y: 540, s: shock ? pop(T, tZag - .3, .4) : 0 });
      place(ui, { x: 360, y: 280, s: pop(T, tZag - .1, .45), r: 0 });
      row.querySelector('.s').textContent = done ? '✓ Online op Marktplaats' : '⏰ Verlopen op Marktplaats'; row.querySelector('.s').style.color = done ? '#00a368' : '#7a8199';
      btn.style.background = done ? '#00a368' : '#0649c7'; btn.textContent = done ? 'Online ✓' : 'Weer online zetten';
      const k = prog(T, tKlik - .9, tKlik - .05, E.inOut);
      place(f, { x: mix(560, 360, k), y: mix(520, 392, k), s: T > tOmni && !done ? 1 : 0 });
    });
  });

  // S6: CTA
  scene(tZeven, DURATION + .5, (g, up) => {
    wall(g, '#2f4a8a', '#4a6fb5', '#3a4f80');
    const me = character(g, { skin: SKIN.d, hair: '#14141a', hoodie: '#e8872a', style: 'curly', glasses: true, w: 400 });
    const mk = mkPill(g), cta = ctaPill(g, '7 dagen gratis'), url = urlTag(g), share = badge(g, 'Stuur dit naar een verkoper', { bg: '#ffd23f', fg: '#0a1936', size: 28, pad: '12px 26px' });
    up((t) => {
      me.pose({ happy: 1, mouth: 'grin', blush: .6, lSh: 150, rSh: -150, lEl: 20, rEl: -20, bob: -Math.abs(Math.sin(t * 5)) * 5 }, t); place(me, { x: 360, y: 700, s: 1.2 });
      place(mk, { x: 360, y: 105, s: pop(t, .1, .4) }); place(cta, { x: 360, y: 200, s: pop(t, .15, .4) * (1 + .03 * Math.sin(t * 7)) });
      place(url, { x: 360, y: 275, s: pop(t, .3, .4) }); place(share, { x: 360, y: 340, s: pop(t, .45, .4) });
    });
  });
}
