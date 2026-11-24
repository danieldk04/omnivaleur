// Deterministic 2D motion-graphics engine: everything is a pure function of t, so Playwright can render any frame.
export const E = {
  lin: t => t,
  out: t => 1 - Math.pow(1 - t, 3),
  inOut: t => (t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  back: t => { const c = 2.1, c3 = c + 1; return 1 + c3 * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); },
  slam: t => (t < .6 ? 3.2 - 2.2 * (t / .6) : 1 + Math.sin((t - .6) / .4 * Math.PI * 3) * .06 * (1 - t) ),
};
export const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const prog = (t, a, b, ease = E.out) => ease(cl((t - a) / Math.max(1e-6, b - a)));
export const mix = (a, b, k) => a + (b - a) * k;
export const pop = (t, a, d = .35) => (t < a ? 0 : E.back(cl((t - a) / d)));

const world = document.getElementById('world');
const capEl = document.getElementById('cap');
const bg = document.getElementById('bg');
const params = new URLSearchParams(location.search);
const NAME = params.get('v') || 'sold-twice';

export function node(parent, css = '', html = '', tag = 'div') {
  const e = document.createElement(tag);
  e.className = 'a';
  if (css) e.style.cssText = css;
  if (html) e.innerHTML = html;
  parent.appendChild(e);
  return e;
}
// place by centre x,y (stage px); s scale, r degrees, o opacity
export function place(e, { x = 0, y = 0, s = 1, r = 0, o = 1, sx, sy } = {}) {
  e.style.transform = `translate(${x}px,${y}px) translate(-50%,-50%) rotate(${r}deg) scale(${sx ?? s},${sy ?? s})`;
  e.style.opacity = o;
  e.style.visibility = o <= 0.001 ? 'hidden' : 'visible';
}

// ---------- scenes ----------
const updaters = [];
export const CUES = []; window.CUES = CUES;
export const cue = (t, type = 'hit') => CUES.push([t, type]);
export function scene(t0, t1, build, { enter = .32, exit = .22, push = .035 } = {}) {
  if (t0 > 0.05) CUES.push([t0, 'whoosh']);
  const g = node(world, 'width:720px;height:1280px;left:360px;top:640px');
  g.style.left = '360px'; g.style.top = '640px';
  const ups = [];
  build(g, f => ups.push(f));
  updaters.push(t => {
    if (t < t0 - .001 || t > t1 + .001) { g.style.visibility = 'hidden'; g.style.opacity = 0; return; }
    const lt = t - t0, k = prog(t, t0, t0 + enter), o = k * (1 - prog(t, t1 - exit, t1, E.lin));
    const sc = 1 + push * (lt / (t1 - t0)) + (1 - k) * -0.04;
    g.style.visibility = 'visible';
    g.style.opacity = o;
    g.style.transform = `translate(-50%,-50%) translateY(${(1 - k) * 36}px) scale(${sc})`;
    ups.forEach(f => f(lt, t));
  });
  return g;
}
const CAPOFF = [];
const PUNCH = [];
const CAMS = [];
export const cam = (t0, t1, o = {}) => CAMS.push([t0, t1, o]);
export const punch = (t, a = .045) => PUNCH.push([t, a]);
let HOTX = null;
export const capOff = (a, b) => CAPOFF.push([a, b]);
export const always = f => updaters.push(f);

// ---------- words / captions ----------
const norm = s => s.toLowerCase().replace(/[^a-z0-9àâçéèêëîïôûùüÿñæœ€]/g, '');
let WORDS = [];
export function at(w, n = 0) {
  let c = 0;
  for (const x of WORDS) if (norm(x.w) === norm(w)) { if (c++ === n) return x.s; }
  throw new Error('word not found: ' + w + ' #' + n);
}
export function endOf(w, n = 0) {
  let c = 0;
  for (const x of WORDS) if (norm(x.w) === norm(w)) { if (c++ === n) return x.e; }
  throw new Error('word not found: ' + w);
}
const SMALL = new Set(['a', 'an', 'the', 'at', 'to', 'of', 'in', 'on', 'and', 'or', 'but', 'for', 'with', 'by', 'it', 'is', 'as', 'so', 'op', 'en', 'de', 'het', 'een', 'je', 'dan']);
function chunks(words, maxw = 3, maxc = 17) {
  const out = []; let cur = [];
  words.forEach((w, i) => {
    cur.push(w);
    const text = cur.map(x => x.w).join(' ');
    const stop = /[.,?!;:]$/.test(w.w);
    const dangling = SMALL.has(norm(w.w)) && i + 1 < words.length && cur.length < maxw + 1;
    if (stop || ((cur.length >= maxw || text.length >= maxc) && !dangling)) { out.push(cur); cur = []; }
  });
  if (cur.length) out.push(cur);
  return out;
}
const HOT = /^(omnivaleur|free|gratis|sold|verkocht|everywhere|overal|once|twee|zero|geen|\d+|€.*)$/;
function capHTML(g) {
  return g.map(x => { const t = x.w.replace(/[.,;:]+$/, ''); return HOT.test(norm(t)) || HOT.test(t.toLowerCase()) || (HOTX && HOTX.test(norm(t))) ? `<b>${t}</b>` : t; }).join(' ');
}
let CAPS = [];
function drawCaption(t) {
  let cur = null;
  for (let i = 0; i < CAPS.length; i++) if (t >= CAPS[i].s - 0.02 && (i + 1 >= CAPS.length || t < CAPS[i + 1].s - 0.02)) cur = CAPS[i];
  if (!cur || t > DURATION - 1.55 || CAPOFF.some(([a, b]) => t >= a && t < b)) { capEl.style.opacity = 0; return; }
  if (capEl.dataset.k !== String(cur.s)) { capEl.dataset.k = String(cur.s); capEl.innerHTML = '<span>' + cur.html + '</span>'; }
  const k = E.back(cl((t - cur.s) / .16));
  capEl.style.opacity = 1;
  capEl.style.transform = `scale(${mix(.7, 1, k)}) translateY(${(1 - k) * 14}px)`;
}

// ---------- background ----------
function drawBg(t, mood) {
  const m = mood(t);
  const a = m.a, b = m.b;
  bg.style.cssText = `left:0;top:0;width:720px;height:1280px;transform:none;background:
    radial-gradient(circle at ${50 + Math.sin(t * .4) * 12}% ${30 + Math.cos(t * .33) * 8}%, ${b} 0%, transparent 62%),
    linear-gradient(170deg, ${a}, #0a1936 120%)`;
  const dots = bg.querySelector('.dots') || node(bg, 'inset:0;left:0;top:0;width:720px;height:1280px');
  dots.className = 'a dots';
  dots.style.transform = `translate(${-(t * 14) % 48}px,${-(t * 9) % 48}px)`;
  dots.style.cssText += `;background-image:radial-gradient(rgba(255,255,255,.10) 1.6px, transparent 1.7px);background-size:48px 48px;width:820px;height:1380px;opacity:${m.dots ?? 1}`;
}

// ---------- grain ----------
const gctx = document.getElementById('grain').getContext('2d');
function drawGrain(t) {
  const d = gctx.createImageData(400, 700), seed = Math.floor(t * 24);
  let s = seed * 9301 + 49297;
  for (let i = 0; i < d.data.length; i += 4) { s = (s * 9301 + 49297) % 233280; const v = (s / 233280) * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
  gctx.putImageData(d, 0, 0);
}

export let DURATION = 20;
let mood = () => ({ a: '#12306b', b: 'rgba(6,73,199,.55)' });

async function boot() {
  const mod = await import(`./videos/${NAME}.js`);
  WORDS = await (await fetch(`vo/${NAME}.words.json`)).json();
  DURATION = WORDS[WORDS.length - 1].e + 1.6;
  window.DURATION = DURATION;
  CAPS = chunks(WORDS).map(g => ({ s: g[0].s, html: capHTML(g) }));
  if (mod.mood) mood = mod.mood;
  if (mod.hotWords) HOTX = new RegExp('^(' + mod.hotWords.map(w => w.toLowerCase().replace(/[^a-z0-9]/g, '')).join('|') + ')$');
  if (mod.hotColor) document.documentElement.style.setProperty('--hot', mod.hotColor);
  mod.build({ cam, punch, capOff, cue, node, place, scene, always, at, endOf, DURATION, E, prog, mix, cl, pop });
  const imgs = [...document.images];
  await Promise.all(imgs.map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; })));
  await document.fonts.ready;
  const render = t => {
    drawBg(t, mood);
    updaters.forEach(f => f(t));
    const z = PUNCH.reduce((s, [ti, a]) => s + (t >= ti ? a * Math.exp(-(t - ti) * 7) : 0), 0);
    let cs = 1, fx = 360, fy = 640, st = 0;
    for (const c of CAMS) if (t >= c[0] && t < c[1]) { cs = c[2].s || 1; fx = c[2].fx ?? 360; fy = c[2].fy ?? 640; st = Math.exp(-(t - c[0]) * 9) * .04; }
    world.style.transformOrigin = `${fx}px ${fy}px`; world.style.transform = `scale(${cs * (1 + st) + z})`;
    drawCaption(t);
    if (params.get('grain') !== '0') drawGrain(t);
    document.getElementById('stage').style.opacity = cl((DURATION - t) / .25) ;
  };
  window.renderAt = t => { render(t); return true; };
  window.ready = Promise.resolve(true);
  if (!params.get('render')) { let t0 = performance.now(); (function loop() { render(((performance.now() - t0) / 1000) % DURATION); requestAnimationFrame(loop); })(); }
}
boot();
