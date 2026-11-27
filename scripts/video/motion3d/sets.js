// Herbruikbare sets en props, alles uit primitieve vormen (geen modellen, geen downloads).
import * as THREE from 'three';
import { matFactory, makeChar } from './rig.js';
const PI = Math.PI;

export function rng(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }

export function labelTex(text, { bg = '#fff', fg = '#111', size = 64, pad = 26, font = 'Montserrat', weight = 900, radius = 26, border = null } = {}) {
  const c = document.createElement('canvas'), x = c.getContext('2d');
  x.font = `${weight} ${size}px ${font}`;
  const lines = String(text).split('\n'), w = Math.max(...lines.map(l => x.measureText(l).width)) + pad * 2, h = size * 1.15 * lines.length + pad * 1.2;
  c.width = Math.ceil(w); c.height = Math.ceil(h);
  x.font = `${weight} ${size}px ${font}`; x.textAlign = 'center'; x.textBaseline = 'middle';
  if (bg) { x.fillStyle = bg; x.beginPath(); x.roundRect(2, 2, c.width - 4, c.height - 4, radius); x.fill(); if (border) { x.lineWidth = 6; x.strokeStyle = border; x.stroke(); } }
  x.fillStyle = fg; lines.forEach((l, i) => x.fillText(l, c.width / 2, pad * .6 + size * .6 + i * size * 1.15));
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  return { t, aspect: c.width / c.height };
}
export function label(text, o = {}) {
  const { t, aspect } = labelTex(text, o); const h = o.h || .5;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthTest: o.depthTest ?? false, fog: false }));
  sp.userData.base = [h * aspect, h]; sp.scale.set(h * aspect, h, 1); sp.renderOrder = 10; return sp;
}
export function sign(text, w, h, o = {}) {
  const { t } = labelTex(text, { size: 90, ...o });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: t, transparent: true })); return m;
}
export function uiTex(w, h, fn) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; fn(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}

export function ctxFor(style) {
  const M = matFactory(style);
  const add = (g, geo, c, p, o = {}) => { const m = new THREE.Mesh(geo, M(c, o)); m.position.set(...(p || [0, 0, 0])); if (o.r) m.rotation.set(...o.r); if (o.s) m.scale.set(...o.s); m.castShadow = o.cast !== false && !o.glow; m.receiveShadow = !o.glow; g.add(m); return m; };
  const box = (g, d, p, c, o) => add(g, new THREE.BoxGeometry(...d), c, p, o);
  const cyl = (g, r, h, p, c, o) => add(g, new THREE.CylinderGeometry(r, o?.r2 ?? r, h, o?.seg || 20), c, p, o);
  const sph = (g, r, p, c, o) => add(g, new THREE.SphereGeometry(r, 20, 14), c, p, o);
  const light = (g, { sun = [4, 9, 6], sunC = '#ffffff', sunI = 2.2, sky = '#ffffff', gnd = '#777788', hemi = 1, shadow = 9 } = {}) => {
    g.add(new THREE.HemisphereLight(sky, gnd, hemi));
    const d = new THREE.DirectionalLight(sunC, sunI); d.position.set(...sun); d.castShadow = true; d.shadow.mapSize.set(2048, 2048);
    Object.assign(d.shadow.camera, { left: -shadow, right: shadow, top: shadow, bottom: -shadow, near: 1, far: 50 }); d.shadow.bias = -.0005; d.shadow.normalBias = .04;
    g.add(d); g.add(d.target);
  };
  return { THREE, style, M, add, box, cyl, sph, light, rounded: style !== 'blocky' };
}

// ---------- rooms ----------
export function room(X, g, P = {}) {
  const { box, cyl, sph, light } = X;
  const o = { wall: '#9fc7b0', floor: '#8a5a36', sky: '#cfe8ff', trim: '#ffffff', lamp: '#ffe9b0', sun: [3, 8, 6], sunC: '#fff2dd', sunI: 2.1, hemi: .9, w: 8, d: 7, ...P };
  light(g, { sun: o.sun, sunC: o.sunC, sunI: o.sunI, hemi: o.hemi, sky: o.skyL || '#ffffff', gnd: o.gnd || '#8a7a70' });
  box(g, [o.w, .2, o.d], [0, -.1, 0], o.floor);
  box(g, [o.w, 3.2, .2], [0, 1.6, -o.d / 2], o.wall);
  box(g, [.2, 3.2, o.d], [-o.w / 2, 1.6, 0], o.wall);
  box(g, [.2, 3.2, o.d], [o.w / 2, 1.6, 0], o.wall);
  box(g, [o.w, .12, .12], [0, .06, -o.d / 2 + .1], o.trim);
  if (o.window !== false) { box(g, [1.7, 1.5, .1], [1.8, 1.9, -o.d / 2 + .08], o.trim); box(g, [1.5, 1.3, .12], [1.8, 1.9, -o.d / 2 + .1], o.sky, { glow: true }); box(g, [.06, 1.3, .14], [1.8, 1.9, -o.d / 2 + .12], o.trim); }
  cyl(g, .02, .6, [0, 2.9, 0], '#333'); sph(g, .22, [0, 2.55, 0], o.lamp, { glow: true });
  return o;
}
export function bedroom(X, g, P = {}) {
  const { box, cyl, sph } = X; const o = room(X, g, P);
  box(g, [2.3, .45, 3.1], [-2.5, .25, -1.7], '#6b3f22'); box(g, [2.1, .3, 2.9], [-2.5, .62, -1.7], P.sheet || '#f4f1ea');
  box(g, [2.12, .14, 1.7], [-2.5, .8, -1.1], P.blanket || '#2f8f5b'); box(g, [1.4, .22, .6], [-2.5, .85, -2.85], '#ffffff');
  box(g, [2.3, 1.1, .2], [-2.5, .75, -3.3], '#6b3f22');
  box(g, [.8, .75, .8], [-.7, .38, -3.0], '#7a4a2a'); box(g, [.5, .3, .1], [-.7, .92, -2.95], '#111', {}); box(g, [.44, .24, .06], [-.7, .92, -2.9], '#ff3b30', { glow: true });
  cyl(g, 1.3, .04, [1.2, .02, .5], P.rug || '#c9714a', { seg: 32 }); box(g, [1.2, .8, .06], [-1.0, 1.9, -o.d / 2 + .12], '#222'); box(g, [1.1, .7, .06], [-1.0, 1.9, -o.d / 2 + .15], '#e6b94d');
  return o;
}
export function parcels(X, g, n, base, seed = 3) {
  const r = rng(seed); const cols = ['#c9a06a', '#b98e57', '#d4b27a', '#a47c48'];
  for (let i = 0; i < n; i++) {
    const w = .5 + r() * .5, h = .35 + r() * .4, d = .5 + r() * .4, x = base[0] + (r() - .5) * 1.4, z = base[2] + (r() - .5) * 1.0, lvl = Math.floor(i / 5);
    X.box(g, [w, h, d], [x, base[1] + lvl * .55 + h / 2, z], cols[i % 4], { r: [0, r() * .5, 0] }); X.box(g, [w * .2, h + .01, d + .01], [x, base[1] + lvl * .55 + h / 2, z], '#e8e0cc');
  }
}
export function attic(X, g, P = {}) {
  const { box, cyl, sph } = X; const o = room(X, g, { wall: '#b9a58d', floor: '#7a5a3c', sky: '#9ec6ff', ...P });
  box(g, [2.8, .1, 1.3], [1.6, .82, -2.7], '#d9c9a5'); [[-1.3, -.55], [1.3, -.55], [-1.3, .55], [1.3, .55]].forEach(([a, b]) => box(g, [.1, .8, .1], [1.6 + a, .4, -2.7 + b], '#8a6a46'));
  box(g, [.7, .12, .7], [1.2, .5, -1.6], '#2a2f45'); box(g, [.7, .7, .1], [1.2, .9, -1.9], '#2a2f45'); [[-.3, -.3], [.3, -.3], [-.3, .3], [.3, .3]].forEach(([a, b]) => box(g, [.06, .5, .06], [1.2 + a, .25, -1.6 + b], '#222'));
  parcels(X, g, 14, [-2.5, 0, -2.2], 5); parcels(X, g, 6, [-.4, 0, -3], 9);
  box(g, [2.2, .08, .6], [-1.5, 2.0, -o.d / 2 + .4], '#8a6a46'); box(g, [.5, .4, .5], [-2.2, 2.25, -o.d / 2 + .4], '#c9a06a'); box(g, [.5, .5, .5], [-1.4, 2.3, -o.d / 2 + .4], '#b98e57');
  return o;
}
export function kitchen(X, g, P = {}) {
  const { box, cyl, sph } = X; const o = room(X, g, { wall: '#d9d2c2', floor: '#6b6258', sky: '#2a3a66', lamp: '#fff3c9', sunI: 1.4, hemi: .7, ...P });
  box(g, [4.2, .95, .75], [-1.6, .48, -o.d / 2 + .5], '#e9e4d8'); box(g, [4.3, .08, .8], [-1.6, .98, -o.d / 2 + .5], '#555a60');
  box(g, [2.4, .9, .35], [-2.5, 2.2, -o.d / 2 + .3], '#cdbfa5'); box(g, [.9, 1.9, .9], [2.7, .95, -o.d / 2 + .6], '#f2f2f2'); box(g, [.05, .6, .05], [2.2, 1.1, -o.d / 2 + 1.1], '#999');
  box(g, [1.4, .08, 1.4], [.6, .78, 0], '#b08a5a'); [[-.6, -.6], [.6, -.6], [-.6, .6], [.6, .6]].forEach(([a, b]) => box(g, [.08, .76, .08], [.6 + a, .38, b], '#7a5a3a'));
  return o;
}
export function pantry(X, g, P = {}) {
  const { box, cyl, sph, light } = X; light(g, { sun: [2, 6, 5], sunI: 1.4, hemi: .9, sunC: '#ffd9a8', sky: '#ffd9a8', gnd: '#554433' });
  box(g, [2.6, .2, 2.4], [0, -.1, 0], '#4a3a2c'); box(g, [2.6, 3, .2], [0, 1.5, -1.2], '#6a5645'); box(g, [.2, 3, 2.4], [-1.3, 1.5, 0], '#6a5645'); box(g, [.2, 3, 2.4], [1.3, 1.5, 0], '#6a5645');
  [0.6, 1.2, 1.8, 2.4].forEach(y => { box(g, [2.4, .06, .6], [0, y, -.9], '#8a6a46'); for (let i = 0; i < 5; i++) cyl(g, .12, .3, [-.95 + i * .47, y + .18, -.9], ['#c0392b', '#e8c14a', '#3a7d44', '#d9d9d9', '#6b8cb8'][i], { seg: 14 }); });
  sph(g, .16, [0, 2.7, 0], '#ffd28a', { glow: true });
  return { w: 2.6 };
}
export function street(X, g, P = {}) {
  const { box, cyl, sph, light } = X; const o = { grass: '#6fbf5a', road: '#4a4d57', wall: '#f0d9b5', roof: '#a54b3a', sky: '#9fd4ff', sun: [6, 10, 8], sunC: '#fff4d6', sunI: 2.4, hemi: 1, ...P };
  light(g, { sun: o.sun, sunC: o.sunC, sunI: o.sunI, hemi: o.hemi, sky: o.skyL || '#cfe6ff', gnd: '#667755', shadow: 14 });
  box(g, [40, .2, 30], [0, -.1, 0], o.grass); box(g, [40, .05, 6], [0, .03, 5], o.road); box(g, [40, .1, 1.4], [0, .06, 1.2], '#c9c9c9'); for (let i = -5; i < 6; i++) box(g, [1.2, .02, .15], [i * 3.2, .07, 5], '#ffe28a');
  box(g, [6, 3.6, .4], [0, 1.8, -3.5], o.wall); box(g, [6.6, .3, 1.2], [0, 3.75, -3.5], o.roof); box(g, [5, .8, 1.0], [0, 4.15, -3.6], o.roof, { r: [0, 0, 0] });
  box(g, [1.2, 2.2, .14], [0, 1.1, -3.25], '#7a4a2c'); sph(g, .07, [.4, 1.1, -3.14], '#e8c36a'); box(g, [1.8, .2, 1.2], [0, .1, -2.7], '#cfcfcf');
  box(g, [1.1, 1.1, .1], [-2.1, 1.9, -3.3], '#ffffff'); box(g, [.95, .95, .12], [-2.1, 1.9, -3.28], '#8fc5ff', { glow: true });
  box(g, [1.1, 1.1, .1], [2.1, 1.9, -3.3], '#ffffff'); box(g, [.95, .95, .12], [2.1, 1.9, -3.28], '#8fc5ff', { glow: true });
  [[-4.6, -3], [5, -4.2], [-8, -2]].forEach(([x, z], i) => { cyl(g, .22, 1.8, [x, .9, z], '#6b4a2b'); sph(g, 1.2 + i * .1, [x, 2.5, z], '#3fa04a'); });
  for (let i = -7; i <= 7; i++) if (Math.abs(i) >= 3) box(g, [.12, .9, .06], [i * .8, .45, -1.6], '#ffffff'); [-1, 1].forEach(sx => box(g, [3.6, .1, .06], [sx * 3.6, .7, -1.6], '#ffffff'));
  box(g, [.5, .5, .5], [1.6, .25, -2.4], '#d94b3a');
  [[-3.2, 2], [4.2, 3]].forEach(([x, z]) => { box(g, [.6, 1.7, .4], [x, .85, z - 5.5], '#cf5a5a'); });
  return o;
}
export function stage(X, g, P = {}) { // ruimte met veel mensen (instanced)
  const { box, cyl, sph, light } = X; const o = { floor: '#c9a06a', wall: '#2a3a6a', ...P };
  light(g, { sun: [3, 10, 7], sunI: 2.0, hemi: .9, shadow: 14 });
  box(g, [30, .2, 24], [0, -.1, 0], o.floor); box(g, [30, 8, .4], [0, 4, -12], o.wall); box(g, [.4, 8, 24], [-15, 4, 0], o.wall); box(g, [.4, 8, 24], [15, 4, 0], o.wall);
  return o;
}
export function space(X, g, P = {}) {
  const { box, cyl, sph, light } = X; light(g, { sun: [8, 4, 10], sunI: 2.6, hemi: .35, sky: '#aabbff', gnd: '#111133', shadow: 12 });
  const r = rng(11), pts = new Float32Array(900 * 3); for (let i = 0; i < 900; i++) { const a = r() * PI * 2, b = Math.acos(2 * r() - 1), R = 40 + r() * 30; pts[i * 3] = R * Math.sin(b) * Math.cos(a); pts[i * 3 + 1] = R * Math.cos(b); pts[i * 3 + 2] = -Math.abs(R * Math.sin(b) * Math.sin(a)); }
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pts, 3));
  g.add(new THREE.Points(geo, new THREE.PointsMaterial({ color: '#ffffff', size: .35, sizeAttenuation: true, fog: false })));
  const planet = new THREE.Group(); planet.position.set(0, 0, -14); g.add(planet);
  const p = sph(planet, 6, [0, 0, 0], '#2f7fd0'); [[2, 3, 4.8, 1.8], [-3, 1, 5, 1.4], [1, -3, 5, 1.6], [-2, -3, 4.8, 1.2], [4, -1, 4.3, 1.5]].forEach(([x, y, z, s]) => { const m = sph(planet, s, [x, y, z], '#4caf50'); m.scale.z = .35; m.lookAt(planet.position.clone().add(new THREE.Vector3(x, y, z)).multiplyScalar(2)); });
  const n = 520, geoM = new THREE.BoxGeometry(.12, .3, .12), mat = X.M('#ffffff'), im = new THREE.InstancedMesh(geoM, mat, n); const cols = ['#ff5a5a', '#ffd23f', '#6ee7b7', '#7aa2ff', '#ff9ad5'];
  const ph = Math.PI * (3 - Math.sqrt(5)); const d = new THREE.Object3D();
  for (let i = 0; i < n; i++) { const y = 1 - i / (n - 1) * 2, rr = Math.sqrt(1 - y * y), th = ph * i; const v = new THREE.Vector3(Math.cos(th) * rr, y, Math.sin(th) * rr); d.position.copy(v.clone().multiplyScalar(6.1)); d.lookAt(v.clone().multiplyScalar(10)); d.updateMatrix(); im.setMatrixAt(i, d.matrix); im.setColorAt(i, new THREE.Color(cols[i % 5])); }
  im.instanceMatrix.needsUpdate = true; planet.add(im);
  return { bg: '#04061a', upd: t => { planet.rotation.y = t * .12; } };
}
export function yard(X, g, P = {}) { // nacht
  const { box, cyl, sph, light } = X; const o = { grass: '#2d4a35', wall: '#cfc7b8', sky: '#0a1226', ...P };
  light(g, { sun: [-5, 10, 6], sunC: '#b4c6ff', sunI: 3.0, hemi: 1.1, sky: '#8aa0e0', gnd: '#2a3548', shadow: 14 });
  box(g, [40, .2, 30], [0, -.1, 0], o.grass); box(g, [6, 3.4, .4], [0, 1.7, -4.5], o.wall); box(g, [6.6, .3, 1.2], [0, 3.55, -4.5], '#3a3040'); box(g, [1.2, 2.2, .14], [0, 1.1, -4.25], '#5a3a2a');
  box(g, [1, 1, .1], [-2.1, 1.8, -4.3], '#ffd27a', { glow: true }); box(g, [1, 1, .1], [2.1, 1.8, -4.3], '#ffd27a', { glow: true });
  for (let i = -8; i <= 8; i++) box(g, [.12, 1, .06], [i * .8, .5, 3.4], '#e8e8e8'); box(g, [14, .1, .06], [0, .8, 3.4], '#e8e8e8');
  for (let i = -3; i <= 3; i++) box(g, [.12, 1, .06], [i * .8 - 3.2, .5, 1.6 - i * .0 + 0], '#e8e8e8');
  cyl(g, .22, 1.8, [-5.5, .9, -3], '#4a3320'); sph(g, 1.3, [-5.5, 2.6, -3], '#1f5a35'); cyl(g, .22, 1.8, [6, .9, -2], '#4a3320'); sph(g, 1.4, [6, 2.6, -2], '#1f5a35');
  cyl(g, .06, 2.2, [3.2, 1.1, -1.8], '#444'); sph(g, .2, [3.2, 2.3, -1.8], '#ffe9a8', { glow: true });
  return { bg: '#070d1c', fog: ['#0b1428', 8, 38] };
}
export function studio(X, g, P = {}) { // rustige afsluiter
  const { box, cyl, sph, light } = X; const o = { floor: '#e9dcc9', wall: '#f6c9a0', ...P };
  light(g, { sun: [4, 8, 6], sunC: '#fff0d8', sunI: 2, hemi: 1, sky: '#fff4e6', gnd: '#b99a7a' });
  box(g, [40, .2, 40], [0, -.1, 0], o.floor); box(g, [40, 20, .4], [0, 10, -8], o.wall); cyl(g, 2.2, .2, [0, .1, 0], '#ffffff', { seg: 40 });
  return { bg: o.wall };
}

// ---------- props ----------
export function hoodieProp(X, color = '#3c4b73', s = 1) {
  const g = new THREE.Group(), { box, sph, add } = X;
  if (X.rounded) { const b = add(g, new THREE.CapsuleGeometry(.4, .5, 6, 14), color, [0, 0, 0]); b.scale.z = .6; } else box(g, [.9, 1.0, .5], [0, 0, 0], color);
  [1, -1].forEach(sx => { const a = box(g, [.28, .8, .3], [sx * .6, -.1, 0], color); a.rotation.z = sx * .35; });
  sph(g, .26, [0, .6, -.1], color); box(g, [.46, .3, .05], [0, -.15, .3], '#00000033'.slice(0, 7) === '#000000' ? color : color);
  g.scale.setScalar(s); g.traverse(m => { if (m.isMesh) m.castShadow = true; }); return g;
}
export function jacketProp(X, color = '#6b3f22', s = 1) {
  const g = hoodieProp(X, color, 1); X.box(g, [.14, .5, .05], [-.2, .15, .27], '#3d2414', { r: [0, 0, .3] }); X.box(g, [.14, .5, .05], [.2, .15, .27], '#3d2414', { r: [0, 0, -.3] }); X.sph(g, .05, [0, -.1, .3], '#d4b25a'); g.scale.setScalar(s); return g;
}
export function parcelProp(X, s = 1) { const g = new THREE.Group(); X.box(g, [.6, .45, .5], [0, 0, 0], '#c9a06a'); X.box(g, [.12, .46, .52], [0, 0, 0], '#e8e0cc'); X.box(g, [.22, .16, .02], [.15, .05, .26], '#ffffff', { glow: true }); g.scale.setScalar(s); return g; }
export function phoneProp(X, tex, s = 1) {
  const g = new THREE.Group(); X.box(g, [.36, .62, .05], [0, 0, 0], '#111'); const sc = new THREE.Mesh(new THREE.PlaneGeometry(.32, .56), new THREE.MeshBasicMaterial({ map: tex })); sc.position.z = .028; g.add(sc); g.scale.setScalar(s); g.userData.screen = sc; return g;
}
export function laptopProp(X, tex, s = 1) {
  const g = new THREE.Group(); X.box(g, [1.0, .05, .7], [0, 0, 0], '#8a8f99'); const lid = new THREE.Group(); lid.position.set(0, .03, -.35); lid.rotation.x = -.25; g.add(lid);
  X.box(lid, [1.0, .65, .04], [0, .33, 0], '#8a8f99'); const sc = new THREE.Mesh(new THREE.PlaneGeometry(.92, .56), new THREE.MeshBasicMaterial({ map: tex })); sc.position.set(0, .33, .025); lid.add(sc);
  g.scale.setScalar(s); g.userData.lid = lid; g.userData.screen = sc; return g;
}
export function crowd(X, g, { n = 200, x0 = -10, x1 = 10, z0 = -4, z1 = 8, seed = 4, hi = .8, clear = null } = {}) {
  const r = rng(seed), rounded = X.rounded;
  const body = new THREE.InstancedMesh(new THREE.BoxGeometry(.5, .8, .32), X.M('#ffffff'), n), head = new THREE.InstancedMesh(rounded ? new THREE.SphereGeometry(.22, 10, 8) : new THREE.BoxGeometry(.4, .4, .4), X.M('#ffffff'), n);
  const cols = ['#ff5a5a', '#ffd23f', '#6ee7b7', '#7aa2ff', '#ff9ad5', '#ffffff', '#ff9f43', '#a06cd5'], skins = ['#f1c3a0', '#d9a07a', '#a8734f', '#7a4e32', '#f6d7c0'];
  const P = []; for (let i = 0; i < n; i++) { let px, pz; do { px = x0 + r() * (x1 - x0); pz = z0 + r() * (z1 - z0); } while (clear && px > clear[0] && px < clear[1] && pz > clear[2] && pz < clear[3]); P.push({ x: px, z: pz, ph: r() * 6.28, sp: 4 + r() * 5, s: .85 + r() * .3 }); body.setColorAt(i, new THREE.Color(cols[Math.floor(r() * cols.length)])); head.setColorAt(i, new THREE.Color(skins[Math.floor(r() * skins.length)])); }
  body.castShadow = head.castShadow = true; g.add(body); g.add(head); const d = new THREE.Object3D();
  const upd = (T, frenzy = 1) => { P.forEach((p, i) => { const y = Math.abs(Math.sin(T * p.sp + p.ph)) * .25 * hi * frenzy; d.position.set(p.x, .4 * p.s + y, p.z); d.rotation.set(0, Math.sin(T * 3 + p.ph) * .5, Math.sin(T * p.sp * .5 + p.ph) * .1 * frenzy); d.scale.setScalar(p.s); d.updateMatrix(); body.setMatrixAt(i, d.matrix); d.position.y += .6 * p.s; d.updateMatrix(); head.setMatrixAt(i, d.matrix); }); body.instanceMatrix.needsUpdate = head.instanceMatrix.needsUpdate = true; };
  upd(0); return { upd, body, head };
}

export function liveTex(w, h, fn) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d');
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  return { tex: t, draw: (...a) => { fn(x, w, h, ...a); t.needsUpdate = true; } };
}
// Omnivaleur-achtig scherm: een item, vier kanalen. p = { sold:0..1, rm:[0..1 x3], title, price }
export function omniUI(x, w, h, p = {}) {
  const rows = [['Vinted', '#09b1ba'], ['Marktplaats', '#2f6fe0'], ['eBay', '#e53238'], ['Your shop', '#6b46c1']];
  x.fillStyle = '#f4f7fb'; x.fillRect(0, 0, w, h); x.fillStyle = '#0a1936'; x.fillRect(0, 0, w, h * .13);
  x.fillStyle = '#85edbc'; x.beginPath(); x.arc(w * .1, h * .065, h * .035, 0, 7); x.fill(); x.fillStyle = '#fff'; x.font = `900 ${h * .05}px Montserrat`; x.textBaseline = 'middle'; x.textAlign = 'left'; x.fillText('Omnivaleur', w * .2, h * .068);
  x.fillStyle = '#0a1936'; x.font = `900 ${h * .055}px Montserrat`; x.fillText(p.title || 'Blue hoodie', w * .07, h * .2); x.fillStyle = '#5b6b86'; x.font = `800 ${h * .04}px Montserrat`; x.fillText(p.price || 'EUR 45', w * .07, h * .26);
  rows.forEach(([n, c], i) => {
    const y = h * (.31 + i * .16), rm = i === 0 ? 0 : (p.rm ? p.rm[i - 1] : 0), sold = i === 0 ? (p.sold || 0) : 0;
    x.globalAlpha = 1 - rm * .6; x.fillStyle = '#fff'; x.beginPath(); x.roundRect(w * .05, y, w * .9, h * .13, 14); x.fill(); x.fillStyle = c; x.beginPath(); x.arc(w * .13, y + h * .065, h * .035, 0, 7); x.fill();
    x.fillStyle = '#0a1936'; x.font = `900 ${h * .037}px Montserrat`; x.fillText(n, w * .21, y + h * .065);
    const st = i === 0 ? (sold > .5 ? 'SOLD' : 'LIVE') : (rm > .5 ? 'REMOVED' : 'LIVE'), col = (st === 'LIVE') ? '#1faa6b' : (st === 'SOLD' ? '#ff4d4d' : '#8a94a8');
    x.fillStyle = col; x.beginPath(); x.roundRect(w * .66, y + h * .033, w * .27, h * .065, 12); x.fill(); x.fillStyle = '#fff'; x.font = `900 ${h * .03}px Montserrat`; x.textAlign = 'center'; x.fillText(st, w * .795, y + h * .066); x.textAlign = 'left';
    if (rm > .1) { x.strokeStyle = '#0a1936'; x.lineWidth = 4; x.beginPath(); x.moveTo(w * .2, y + h * .065); x.lineTo(w * .2 + (w * .36) * Math.min(1, rm * 1.4), y + h * .065); x.stroke(); }
    x.globalAlpha = 1;
  });
}

// cover-crop een geladen afbeelding naar een vaste verhouding (geen uitrekken)
export function coverTex(tex, aspect, w = 1024) {
  const im = tex.image, h = Math.round(w / aspect), c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d');
  const ia = im.width / im.height; let sw = im.width, sh = im.height, sx = 0, sy = 0;
  if (ia > aspect) { sw = im.height * aspect; sx = 0; } else { sh = im.width / aspect; sy = 0; }
  x.drawImage(im, sx, sy, sw, sh, 0, 0, w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
}

export function stampSprite(text, color = '#e53935', o = {}) {
  const size = o.size || 84, lines = String(text).split('\n'), c = document.createElement('canvas'), x = c.getContext('2d');
  x.font = `900 ${size}px Montserrat`; const w = Math.ceil(Math.max(...lines.map(l => x.measureText(l).width))) + 90, h = size * lines.length * 1.02 + 70; c.width = w; c.height = Math.ceil(h);
  x.font = `900 ${size}px Montserrat`; x.textAlign = 'center'; x.textBaseline = 'middle'; x.strokeStyle = color; x.fillStyle = color; x.lineWidth = 9; x.beginPath(); x.roundRect(8, 8, w - 16, h - 16, 14); x.stroke(); x.lineWidth = 3; x.beginPath(); x.roundRect(24, 24, w - 48, h - 48, 8); x.stroke();
  lines.forEach((l, i) => x.fillText(l, w / 2, 35 + size * (i + .5) * 1.02 + 4));
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthTest: false, fog: false, rotation: o.rot ?? -.16 }));
  const hh = o.h || .5; sp.userData.base = [hh * w / h, hh]; sp.scale.set(hh * w / h, hh, 1); sp.renderOrder = 12; return sp;
}
export function ticketProp(X, text = 'ADMIT ONE\nSEAT 12', s = 1) {
  const g = new THREE.Group(); const { t } = labelTex(text, { bg: '#f2c14e', fg: '#3a2a10', size: 70, radius: 10, pad: 22 });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(.62, .34), new THREE.MeshBasicMaterial({ map: t })); g.add(m);
  const back = new THREE.Mesh(new THREE.PlaneGeometry(.62, .34), new THREE.MeshBasicMaterial({ color: '#c9962f', side: THREE.BackSide })); back.position.z = -.002; g.add(back);
  g.scale.setScalar(s); g.userData.noAudit = true; return g;
}
export function scannerProp(X, s = 1) {
  const g = new THREE.Group(); X.box(g, [.22, .34, .1], [0, 0, 0], '#1a1d26'); const scr = X.box(g, [.16, .12, .02], [0, .08, .06], '#35e08a', { glow: true }); X.box(g, [.1, .04, .02], [0, -.08, .06], '#6b7a99'); g.userData.screen = scr; g.scale.setScalar(s); return g;
}
export function gate(X, g, P = {}) {
  const { box, cyl, sph, light } = X; const o = { ground: '#262a3a', wall: '#3a3052', ...P };
  light(g, { sun: [-4, 9, 7], sunC: '#aebdff', sunI: 2.4, hemi: .9, sky: '#7d8fe0', gnd: '#2a3050', shadow: 14 });
  box(g, [40, .2, 30], [0, -.1, 0], o.ground); box(g, [20, .08, 4], [0, .04, -2.2], '#3a4054');
  box(g, [13, 5.5, .7], [0, 2.75, -5], o.wall); box(g, [2.6, 3.1, .2], [0, 1.55, -4.62], '#ffd89a', { glow: true }); box(g, [3.0, .25, .5], [0, 3.25, -4.5], '#1a1626');
  [-4.5, -3.2, 3.2, 4.5].forEach((x, i) => box(g, [.9, 1.3, .06], [x, 2.2, -4.6], ['#e85d75', '#4aa3df', '#f2c14e', '#7bd88f'][i]));
  for (let i = 0; i < 16; i++) { const x = -7 + i * .93; sph(g, .09, [x, 3.7 + Math.sin(i * .9) * .1, -4.2], i % 2 ? '#ffe9a8' : '#ff9ad5', { glow: true }); }
  [-1.9, 1.9].forEach(x => { cyl(g, .06, 1.0, [x, .5, -2.9], '#c9a14a'); sph(g, .1, [x, 1.02, -2.9], '#c9a14a'); }); box(g, [3.8, .06, .06], [0, .9, -2.9], '#b02a3a');
  const pl = new THREE.PointLight('#ffb870', 16, 11, 1.5); pl.position.set(0, 3.6, -3.9); g.add(pl);
  return { bg: '#0a1030', fog: ['#0a1030', 12, 38] };
}
export function colliders(g) {
  const out = []; g.updateMatrixWorld(true);
  g.traverse(m => { if (m.isMesh && m.geometry.type === 'BoxGeometry') { const b = new THREE.Box3().setFromObject(m); out.push(b); } });
  return out;
}
