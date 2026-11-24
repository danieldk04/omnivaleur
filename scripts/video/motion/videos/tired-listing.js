import { chip, badge, textBlock, clockText, check } from '../kit.js';
import { character, SKIN } from '../char.js';

export const mood = t => ({ a: '#0b1026', b: 'rgba(40,60,140,.4)', dots: 0 });

export function build(K) {
  const { cue, capOff, scene, at, place, prog, E, mix, node, DURATION, pop, cl } = K;
  const tTired = at("You're"), tRain = at('raining'), tItems = at('fourteen'), tFour = at('four'), tOr = at('Or') - .1, tOmni = at('Omnivaleur'), tEvery = at('everywhere'), tThen = at('Then') - .1, tSeven = at('Seven') - .1;
  const tTap = tOmni + 1.0;
  cue(tRain - .15, 'hit'); cue(tItems, 'pop'); cue(tFour, 'buzz'); cue(tOmni + .2, 'pop'); cue(tTap, 'tick'); cue(tTap + .25, 'ding'); cue(tEvery, 'ding'); cue(tSeven, 'pop');
  capOff(tSeven - .05, tSeven + .1);

  scene(0, DURATION + .5, (g, up) => {
    // ---------- room ----------
    node(g, 'left:0;top:0;width:720px;height:900px;transform:none;background:linear-gradient(#1c2447,#232b52 60%,#2a2f5a)');
    node(g, 'left:0;top:760px;width:720px;height:200px;transform:none;background:linear-gradient(#4a3426,#3a281d)');
    // window with rain
    const win = node(g, 'left:50px;top:90px;width:250px;height:290px;transform:none;border-radius:14px;border:12px solid #e9edf5;overflow:hidden;background:linear-gradient(#0d1b3d,#223a70);box-shadow:0 10px 30px rgba(0,0,0,.4)');
    [[40, 200, 50, '#ffcf6b'], [120, 230, 36, '#7fb0ff'], [190, 190, 44, '#ff8fb0'], [80, 150, 30, '#ffcf6b'], [200, 110, 28, '#7fb0ff']].forEach(([x, y, r, c]) => node(win, `left:${x}px;top:${y}px;width:${r}px;height:${r}px;border-radius:50%;background:${c};opacity:.45;filter:blur(5px);transform:none`));
    const drops = []; for (let i = 0; i < 34; i++) drops.push(node(win, `left:${(i * 37) % 250}px;top:0;width:2.5px;height:${30 + (i * 13) % 26}px;border-radius:2px;background:rgba(190,215,255,.7);transform:none`));
    node(g, 'left:50px;top:90px;width:250px;height:290px;transform:none;border-radius:14px;border:12px solid #e9edf5;border-width:0;box-shadow:inset 0 0 0 0 transparent');
    node(g, 'left:175px;top:90px;width:12px;height:290px;transform:none;background:#e9edf5');
    node(g, 'left:50px;top:228px;width:250px;height:12px;transform:none;background:#e9edf5');
    // clock on shelf
    const shelf = node(g, 'left:60px;top:455px;width:230px;height:14px;transform:none;border-radius:6px;background:#6b4630');
    const ck = clockText(g, 60, '#ff6b6b'); ck.setTime(23 * 60 + 40);
    // lamp
    node(g, 'left:628px;top:380px;width:14px;height:420px;transform:none;background:#3a3a4a;border-radius:7px');
    node(g, 'left:585px;top:330px;width:100px;height:70px;transform:none;background:#f2c078;clip-path:polygon(20% 0,80% 0,100% 100%,0 100%);opacity:.9');
    // couch back + arms
    node(g, 'left:90px;top:470px;width:540px;height:330px;transform:none;border-radius:60px 60px 0 0;background:#23366f');
    node(g, 'left:50px;top:600px;width:110px;height:260px;transform:none;border-radius:40px;background:#2b4285');
    node(g, 'left:560px;top:600px;width:110px;height:260px;transform:none;border-radius:40px;background:#2b4285');
    // character
    const me = character(g, { skin: SKIN.b, hair: '#2a1d16', hoodie: '#3c4b73', style: 'short', w: 400 });
    // couch front + table
    node(g, 'left:40px;top:700px;width:640px;height:200px;transform:none;border-radius:46px 46px 10px 10px;background:linear-gradient(#2f4a96,#26397a)');
    node(g, 'left:200px;top:735px;width:130px;height:140px;transform:none;border-radius:26px;background:rgba(255,255,255,.07)');
    node(g, 'left:390px;top:735px;width:130px;height:140px;transform:none;border-radius:26px;background:rgba(255,255,255,.07)');
    node(g, 'left:140px;top:830px;width:440px;height:34px;transform:none;border-radius:10px;background:#7a5238;box-shadow:0 12px 24px rgba(0,0,0,.4)');
    // laptop back view
    const lp = node(g, 'left:225px;top:716px;width:270px;height:122px;transform:none;border-radius:12px 12px 4px 4px;background:linear-gradient(#aab3c8,#8e98b0);box-shadow:0 8px 20px rgba(0,0,0,.4)', '<div style="position:absolute;left:50%;top:50%;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;background:rgba(255,255,255,.55)"></div>');
    // mug with steam
    node(g, 'left:520px;top:795px;width:46px;height:38px;transform:none;border-radius:6px 6px 14px 14px;background:#f4efe6');
    const steam = [0, 1, 2].map(i => node(g, `left:${531 + i * 12}px;top:770px;width:4px;height:24px;transform:none;border-radius:3px;background:rgba(255,255,255,.55)`));
    // overlays
    const dark = node(g, 'left:0;top:0;width:720px;height:960px;transform:none;background:rgba(5,10,35,.3);pointer-events:none');
    const glowFace = node(g, 'left:160px;top:380px;width:400px;height:360px;transform:none;background:radial-gradient(ellipse at 50% 50%,rgba(120,170,255,.45),transparent 65%);mix-blend-mode:screen;pointer-events:none');
    const warm = node(g, 'left:0;top:0;width:720px;height:960px;transform:none;background:radial-gradient(ellipse at 88% 38%,rgba(255,190,100,.55),rgba(255,160,80,.18) 55%,transparent 80%);mix-blend-mode:screen;pointer-events:none');
    const flash = node(g, 'left:0;top:0;width:720px;height:960px;transform:none;background:#dfe8ff;pointer-events:none');
    // UI card
    const ui = node(g, 'width:420px;padding:22px 24px 24px;border-radius:30px;background:#fff;box-shadow:0 18px 50px rgba(0,0,0,.5)');
    const uiHead = node(ui, 'position:relative;left:0;top:0;transform:none;font:800 24px Montserrat;color:#485363;margin-bottom:6px', 'To list');
    const uiBig = node(ui, 'position:relative;left:0;top:0;transform:none;font:900 96px/1 Montserrat;color:#ff4d4d', '14');
    const uiSub = node(ui, 'position:relative;left:0;top:0;transform:none;font:800 28px Montserrat;color:#0a1936;margin-bottom:12px', 'items');
    const row = node(ui, 'position:relative;left:0;top:0;transform:none;display:flex;gap:12px;height:76px');
    const logos = ['vinted', 'marktplaats', 'ebay', 'shop'].map(k => { const c = chip(row, k, 76); c.style.position = 'relative'; c.style.left = '0'; c.style.top = '0'; c.style.transform = 'none'; return c; });
    const btn = node(ui, 'position:absolute;top:auto;left:24px;right:24px;bottom:24px;transform:none;padding:20px;border-radius:999px;background:#0649c7;color:#fff;font:900 34px Montserrat;text-align:center;box-shadow:0 10px 24px rgba(6,73,199,.5)', 'Publish to all');
    const cur = node(g, 'width:54px;height:54px;border-radius:50%;background:rgba(255,255,255,.7);border:6px solid #0649c7');
    const cta = node(g, 'padding:22px 44px;border-radius:999px;background:#85edbc;color:#0a1936;font:900 46px/1 Montserrat;box-shadow:0 14px 40px rgba(0,0,0,.4);white-space:nowrap', '7 days free');
    const mk = node(g, 'width:440px', '<div style="display:flex;align-items:center;gap:14px;justify-content:center;background:#fff;padding:14px 30px;border-radius:999px;box-shadow:0 14px 40px rgba(0,0,0,.35)"><img src="assets/mark.png" style="width:92px"><span style="font:900 42px Montserrat;color:#0a1936;letter-spacing:-1px">Omnivaleur</span></div>');

    up((t) => {
      const happy = prog(t, tTap + .2, tTap + .7, E.out), calm = prog(t, tThen, tThen + .8, E.inOut);
      // rain
      const rainK = t < tRain - .3 ? .5 : mix(1, .35, calm);
      drops.forEach((d, i) => { const sp = 380 + (i % 5) * 70; const y = ((t * sp + i * 47) % 360) - 40; d.style.transform = `translateY(${y}px)`; d.style.opacity = rainK; });
      const fl = t < tRain - .3 ? 0 : Math.max(0, Math.exp(-(t - (tRain - .15)) * 7) * (t > tRain - .15 ? 1 : 0)) + (t > tRain + .05 ? Math.exp(-(t - tRain - .05) * 9) * .5 : 0);
      flash.style.opacity = Math.min(.7, fl * (t < tRain + 1 ? 1 : 0));
      dark.style.opacity = mix(1, .0, happy);
      glowFace.style.opacity = 1 - happy;
      warm.style.opacity = mix(.25, 1, happy);
      steam.forEach((s, i) => { s.style.transform = `translateY(${-((t * 20 + i * 9) % 26)}px) scaleY(${.6 + .4 * Math.sin(t * 3 + i)})`; s.style.opacity = .55 * (1 - ((t * 20 + i * 9) % 26) / 26); });
      ck.style.opacity = 1; ck.setTime(23 * 60 + 40 + Math.floor(t / 4));
      // character poses
      const p = { eye: .45, bags: 1, headY: 12, headRot: -5, mouth: 'flat', brow: 6, lSh: 8, lEl: 6, rSh: -8, rEl: -6, lean: 3, bob: 6 };
      if (t > tRain - .3) { p.eye = .35; p.mouth = 'wavy'; p.headY = 18; p.headRot = 6; }
      if (t > tItems - .1) { const k = prog(t, tItems - .1, tItems + .4, E.out); p.eye = mix(.35, 1, k); p.gy = -.6; p.gx = .6; p.brow = -14 * k; p.browY = -6 * k; p.sweat = prog(t, tFour, tFour + .6); p.mouth = 'o'; p.headY = mix(18, 0, k); p.headRot = 0; p.rSh = mix(-8, -160, k); p.rEl = mix(-6, -120, k); p.bob = 0; p.lean = 0; }
      if (t > tOr) { const k = prog(t, tOr, tOr + .4, E.out); p.gx = mix(.6, 0, k); p.gy = mix(-.6, 0, k); p.sweat = 1 - k; p.mouth = k > .5 ? 'smile' : 'o'; p.brow = mix(-14, 0, k); p.rSh = mix(-160, -8, k); p.rEl = mix(-120, -6, k); p.bags = 1 - .5 * k; p.eye = 1; }
      if (t > tTap) { p.happy = happy; p.mouth = 'grin'; p.bags = .3 * (1 - happy); p.lSh = mix(8, 160, happy); p.rSh = mix(-8, -160, happy); p.lEl = mix(6, 20, happy); p.rEl = mix(-6, -20, happy); p.headY = -4 * happy; p.blush = .6 * happy; p.eye = 1; p.gx = 0; p.gy = 0; }
      if (t > tThen) { p.happy = 1; p.mouth = 'smile'; p.lSh = mix(160, 12, calm); p.rSh = mix(-160, -12, calm); p.lEl = mix(20, 6, calm); p.rEl = mix(-20, -6, calm); p.lean = mix(0, -8, calm); p.headRot = mix(0, 4, calm); p.bob = mix(0, 4, calm); p.bags = 0; }
      me.pose(p, t);
      place(me, { x: 360, y: 640, s: 1.2 });
      place(ck, { x: 175, y: 425, s: 1 });
      // UI card
      const showUI = prog(t, tItems - .2, tItems + .3, E.back);
      const afterOr = t > tOmni - .1;
      const done = t > tTap + .5;
      uiHead.textContent = done ? 'Live everywhere' : afterOr ? 'One tap' : 'To list';
      const n = done ? Math.min(14, Math.round(prog(t, tTap + .3, tTap + 1.1, E.out) * 14)) : 14;
      uiBig.textContent = done ? n + ' / 14' : afterOr ? '1×' : '14';
      uiBig.style.color = done ? '#00a368' : afterOr ? '#0649c7' : '#ff4d4d';
      uiSub.textContent = done ? 'live on 4 apps' : afterOr ? 'add once' : 'items';
      logos.forEach((c, i) => { const pc = (t > tFour ? 1 : 0); c.style.opacity = t > tFour + i * .18 ? 1 : .12; c.style.outline = done ? '5px solid #85edbc' : 'none'; });
      btn.style.opacity = afterOr && !done ? 1 : 0; btn.style.transform = (t > tTap - .1 && t < tTap + .1) ? 'scale(.94)' : 'none';
      ui.style.height = '330px';
      const away = prog(t, tThen + .2, tThen + .6, E.lin);
      place(ui, { x: 480, y: 255 + (1 - showUI) * 30, s: showUI * (1 - away), r: 2 });
      const curK = prog(t, tOmni + .3, tTap - .05, E.inOut);
      place(cur, { x: mix(640, 495, curK), y: mix(420, 405, curK), s: afterOr && t < tTap + .45 ? 1 : 0 });
      place(mk, { x: 440, y: 110, s: pop(t, tThen + .5, .45) });
      place(cta, { x: 470, y: 215, s: pop(t, tSeven, .4) * (1 + .03 * Math.sin(t * 7)) });
    });
  });
}
