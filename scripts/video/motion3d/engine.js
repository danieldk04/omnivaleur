// 3D-motor: alles is een pure functie van t. Shots wisselen op woordtimings, de camera beweegt per shot.
import * as THREE from 'three';
import { makeChar } from './rig.js';
import { ctxFor, label as mkLabel, sign as mkSign, uiTex, labelTex, liveTex, omniUI, coverTex } from './sets.js';

export const E = {
  lin: t => t, out: t => 1 - Math.pow(1 - t, 3), inOut: t => (t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  back: t => { const c = 2.1, c3 = c + 1; return 1 + c3 * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); },
};
const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const prog = (t, a, b, e = E.out) => e(cl((t - a) / Math.max(1e-6, b - a)));
const pop = (t, a, d = .3) => (t < a ? 0 : E.back(cl((t - a) / d)));
const lerp = (a, b, k) => a + (b - a) * k, l3 = (a, b, k) => a.map((v, i) => lerp(v, b[i], k));

const params = new URLSearchParams(location.search);
const NAME = params.get('v');
export const CUES = []; window.CUES = CUES;

// ---------- cameras ----------
export const stat = (p, l, fov = 48, roll = 0) => () => ({ p, l, fov, roll });
export const dolly = (p0, p1, l0, l1 = l0, fov = 48, roll0 = 0, roll1 = roll0, ease = E.inOut) => k => { const e = ease(k); return { p: l3(p0, p1, e), l: l3(l0, l1, e), fov, roll: lerp(roll0, roll1, e) }; };
export const orbit = (c, r, h, a0, a1, fov = 48, ly = 1.2, roll = 0, h1 = h) => k => { const e = E.inOut(k), a = lerp(a0, a1, e); return { p: [c[0] + Math.sin(a) * r, lerp(h, h1, e), c[2] + Math.cos(a) * r], l: [c[0], ly, c[2]], fov, roll }; };

// ---------- woorden en captions ----------
let WORDS = [];
const norm = s => s.toLowerCase().replace(/[^a-z0-9€]/g, '');
const SMALL = new Set(['a', 'an', 'the', 'at', 'to', 'of', 'in', 'on', 'and', 'or', 'but', 'for', 'with', 'by', 'it', 'is', 'as', 'so', 'your', 'you', 'his', 'one', 'that']);
function chunks(words, maxw = 3, maxc = 17) {
  const out = []; let cur = [];
  words.forEach((w, i) => {
    cur.push(w); const text = cur.map(x => x.w).join(' '), stop = /[.,?!;:]$/.test(w.w);
    const dangling = SMALL.has(norm(w.w)) && i + 1 < words.length && cur.length < maxw + 1;
    if (stop || ((cur.length >= maxw || text.length >= maxc) && !dangling)) { out.push(cur); cur = []; }
  });
  if (cur.length) out.push(cur); return out;
}
let HOT = null, CAPS = [], DURATION = 20;
const capEl = document.getElementById('cap');
const capHTML = g => g.map(x => { const t = x.w.replace(/[.,;:!?]+$/, ''); return (/^(omnivaleur|free|gratis|nul|\d+|zero|€.*)$/.test(norm(t)) || (HOT && HOT.test(norm(t)))) ? `<b>${t}</b>` : t; }).join(' ');
function drawCaption(t, hide) {
  let cur = null; for (let i = 0; i < CAPS.length; i++) if (t >= CAPS[i].s - .02 && (i + 1 >= CAPS.length || t < CAPS[i + 1].s - .02)) cur = CAPS[i];
  if (!cur || hide || t > DURATION - 1.45) { capEl.style.opacity = 0; return; }
  if (capEl.dataset.k !== String(cur.s)) { capEl.dataset.k = String(cur.s); capEl.innerHTML = '<span>' + cur.html + '</span>'; }
  const k = E.back(cl((t - cur.s) / .14)); capEl.style.opacity = 1; capEl.style.transform = `scale(${lerp(.75, 1, k)})`;
}

async function boot() {
  const mod = await import(`./videos/${NAME}.js`);
  const style = mod.style || 'blocky';
  document.getElementById('stage').className = style;
  WORDS = await (await fetch(`vo/${NAME}.words.json`)).json();
  DURATION = WORDS[WORDS.length - 1].e + 1.6; window.DURATION = DURATION;
  CAPS = chunks(WORDS).map(g => ({ s: g[0].s, html: capHTML(g) }));
  if (mod.hotWords) HOT = new RegExp('^(' + mod.hotWords.map(norm).join('|') + ')$');
  await document.fonts.load('900 64px Montserrat'); await document.fonts.ready;

  const canvas = document.getElementById('gl');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Number(params.get('pr') || 1)); renderer.setSize(720, 1280, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  if (style === 'real') { renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.35; }
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(48, 720 / 1280, .05, 200);
  const X = ctxFor(style);
  const sets = {}, setList = [], dyn = [], shots = []; let endT = null, cctvOn = false;
  const loader = new THREE.TextureLoader();
  const K = {
    THREE, X, style, words: WORDS, DURATION, E, pop, prog, cl, lerp,
    W: i => { if (!WORDS[i]) throw new Error('woord ' + i); return WORDS[i].s; },
    cue: (t, type = 'hit') => CUES.push([t, type]),
    set(name, fn) {
      const g = new THREE.Group(); g.position.set(setList.length * 300, 0, 0); scene.add(g);
      const ex = fn(X, g) || {}; const s = { g, ox: g.position.x, ex, name }; sets[name] = s; setList.push(s); return s;
    },
    actor(o) { const c = makeChar(style, o); scene.add(c); dyn.push(c); return c; },
    prop(obj) { scene.add(obj); dyn.push(obj); return obj; },
    label(text, o = {}) { const s = mkLabel(text, { ...o, h: (o.h || .5) * .62 }); scene.add(s); dyn.push(s); return s; },
    sign: mkSign, uiTex, labelTex, liveTex, omniUI, coverTex,
    image: url => new Promise(r => loader.load(url, t => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; r(t); })),
    stat, dolly, orbit,
    shot(t, setName, cam, fn, opts = {}) { shots.push({ t, set: setName, cam, fn, opts }); },
    endCard(t) { endT = t; },
  };
  await mod.build(K);
  shots.sort((a, b) => a.t - b.t);
  const SET = n => { if (!sets[n]) throw new Error('set ' + n); return sets[n]; };
  const endEl = document.getElementById('end'), cctvEl = document.getElementById('cctv'), stage = document.getElementById('stage');
  const nz = t => Math.sin(t * 13.1 + 1) * .6 + Math.sin(t * 7.7 + 3) * .4;

  const render = T => {
    let idx = 0; for (let i = 0; i < shots.length; i++) if (T >= shots[i].t - 1e-6) idx = i;
    const sh = shots[idx], nxt = shots[idx + 1], S = SET(sh.set);
    dyn.forEach(o => { o.visible = false; });
    setList.forEach(s => { s.g.visible = s === S; });
    scene.background = new THREE.Color(S.ex.bg || '#9fd4ff'); scene.fog = S.ex.fog ? new THREE.Fog(S.ex.fog[0], S.ex.fog[1], S.ex.fog[2]) : null;
    const lt = Math.max(0, T - sh.t), dur = (nxt ? nxt.t : DURATION + .5) - sh.t, k = cl(lt / dur), ox = S.ox;
    const api = {
      lt, T, k, w: (x, y, z) => new THREE.Vector3(ox + x, y, z),
      at(o, x, y, z, ry = 0) { o.visible = true; o.position.set(ox + x, y, z); o.rotation.y = ry; return o; },
      put(o, p, ry = 0, anim = 'idle', t = lt, extra) { o.visible = true; o.position.set(ox + p[0], p[1], p[2]); o.rotation.y = ry; if (o.pose) o.pose(anim, t, extra); return o; },
      sc(o, s) { if (o.userData.base) o.scale.set(o.userData.base[0] * s, o.userData.base[1] * s, 1); else o.scale.setScalar(s); },
    };
    sh.fn && sh.fn(lt, T, api, k);
    S.ex.upd && S.ex.upd(T, lt);
    const c = sh.cam(k, lt), sk = sh.opts.shake || 0;
    camera.position.set(ox + c.p[0] + nz(T * 1.3) * sk, c.p[1] + nz(T * 1.7 + 2) * sk * .7, c.p[2] + nz(T * 1.1 + 5) * sk);
    camera.up.set(0, 1, 0); camera.lookAt(ox + c.l[0] + nz(T * 2.1) * sk * .5, c.l[1] + nz(T * 1.9) * sk * .4, c.l[2]);
    if (c.roll) camera.rotateZ(c.roll * Math.PI / 180);
    camera.fov = c.fov * (1 - .05 * Math.exp(-lt * 9)); camera.updateProjectionMatrix();
    renderer.render(scene, camera);
    const cc = !!sh.opts.cctv; if (cc !== cctvOn) { cctvOn = cc; cctvEl.style.display = cc ? 'block' : 'none'; }
    canvas.style.filter = sh.opts.filter || ''; stage.style.filter = '';
    drawCaption(T, !!sh.opts.nocap || (endT != null && T >= endT));
    if (endT != null && T >= endT - .05) { endEl.style.display = 'block'; [...endEl.children].forEach((e, i) => { const s = pop(T, endT + i * .22, .4); e.style.opacity = s > 0 ? 1 : 0; e.style.transform = (i > 0 ? 'translateX(-50%) ' : '') + `scale(${Math.max(.001, s)})`; if (i === 0) e.style.transform = `scale(${Math.max(.001, s)})`; }); } else endEl.style.display = 'none';
    stage.style.opacity = cl((DURATION - T) / .25);
  };
  window.renderAt = t => { render(t); return true; };
  window.ready = Promise.resolve(true);
  if (!params.get('render')) { const t0 = performance.now(); (function loop() { render(((performance.now() - t0) / 1000) % DURATION); requestAnimationFrame(loop); })(); }
}
boot();
