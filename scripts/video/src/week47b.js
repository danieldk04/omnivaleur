// Week 47 B: poppetjes in situaties. Kamers, cast en poses; elke shot is een kamer, een setup en een update.
import * as THREE from 'three';
import { makeBlocky } from './blocky.js';
import { kf, lerp, easeOut, easeInOut, range, clamp, cam, place } from './anim.js';
import { std, rbox, room, windowPane, desk, laptop, lamp, typingPose, seat, pop, planeCard, wrap, logoTex, listingTex, bubbleTex, gradTex, ledTex, walkPose, cheer, parcel, street, bedroom, kitchen, rnd, s8 } from './shots.js';
import { cookingStage, hoodieChar, soldPoof, stampTex, bigTex, labelTex, kinetic, plate, steam } from './week46.js';
export { wrap, pop, planeCard, logoTex, listingTex, bubbleTex, stampTex, bigTex, labelTex, kinetic, soldPoof, hoodieChar, typingPose, seat, walkPose, cheer, parcel, rbox, std, laptop, lamp, desk, windowPane, ledTex, lerp, kf, easeOut, easeInOut, range, makeBlocky, plate, steam, THREE, cookingStage };
export { K, Ll, Mm, Nn, Oo } from './shots.js';
export { montage, PL, PL5 } from './week47.js';

// ---- cast ----
export const SKIN = { a: 0xc98a64, b: 0xe0a98a, c: 0x8a5a3c, d: 0xf1c9a5, e: 0x6b4630 };
export function person(o = {}) {
  const h = makeBlocky(o), mat = c => std(c, 0.8);
  if (o.beanie) { const b = new THREE.Mesh(new THREE.SphereGeometry(0.285, 28, 14, 0, Math.PI * 2, 0, Math.PI * 0.5), mat(o.beanie)); b.position.set(0, 0.04, -0.01); b.castShadow = true; h.head.add(b); const p = new THREE.Mesh(new THREE.SphereGeometry(0.06, 12, 10), mat(0xffffff)); p.position.set(0, 0.3, 0); h.head.add(p); }
  if (o.cap) { const b = new THREE.Mesh(new THREE.SphereGeometry(0.275, 28, 14, 0, Math.PI * 2, 0, Math.PI * 0.45), mat(o.cap)); b.position.set(0, 0.03, -0.01); h.head.add(b); const br = rbox(0.32, 0.03, 0.2, 0.01, mat(o.cap)); br.position.set(0, 0.07, 0.28); h.head.add(br); }
  if (o.glasses) for (const s of [-1, 1]) { const r = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.012, 8, 20), mat(0x111111)); r.position.set(s * 0.09, 0.0, 0.25); h.head.add(r); }
  if (o.bun) { const b = new THREE.Mesh(new THREE.SphereGeometry(0.1, 14, 10), mat(o.hair || 0x5a3a2a)); b.position.set(0, 0.28, -0.12); h.head.add(b); }
  return h;
}
const bl = t => ((t * 0.7) % 3) > 2.9;
export const P = {
  idle: (h, t, x = {}) => h.pose({ torso: [0.02, Math.sin(t * 1.3) * 0.03, 0], head: [0, Math.sin(t * 1.1) * 0.12, 0], lSh: [0, 0, 0.08], rSh: [0, 0, -0.08], blink: bl(t), ...x }),
  talk: (h, t, x = {}) => P.idle(h, t, { mouth: Math.max(0, Math.sin(t * 13)) * 0.4, rSh: [-0.8 + Math.sin(t * 5) * 0.3, 0, -0.25], rEl: [-1.0, 0, 0], ...x }),
  shock: (h, t, x = {}) => h.pose({ torso: [-0.1, 0, 0], head: [-0.15, Math.sin(t * 30) * 0.03, 0], lSh: [-1.3, 0, 0.35], lEl: [-2.1, 0, 0], rSh: [-1.3, 0, -0.35], rEl: [-2.1, 0, 0], mouth: 0.55, ...x }),
  stop: (h, t, x = {}) => P.idle(h, t, { rSh: [-1.55, 0, -0.08], rEl: [-0.05, 0, 0], torso: [-0.04, 0, 0], mouth: 0.15, ...x }),
  slump: (h, t, x = {}) => h.pose({ torso: [0.35, 0, 0], neck: [0.3, 0, 0], head: [0.25, 0, 0.1], lSh: [0.1, 0, 0.1], rSh: [0.1, 0, -0.1], blink: t > 0.4, ...x }),
  sit: (h, t, x = {}) => h.pose({ drop: 0.28, torso: [0.05, 0, 0], head: [0, Math.sin(t * 2) * 0.12, 0], lHip: [-1.5, 0.05, 0], lKn: [1.5, 0, 0], rHip: [-1.5, -0.05, 0], rKn: [1.5, 0, 0], lSh: [-0.8, 0, 0.3], lEl: [-1.2, 0, 0], rSh: [-0.8, 0, -0.3], rEl: [-1.2, 0, 0], blink: bl(t), ...x }),
  shake: (h, t, x = {}) => P.idle(h, t, { head: [0, Math.sin(t * 12) * 0.5, 0], torso: [0, 0, 0], lSh: [-0.9, 0, 0.3], lEl: [-1.4, 0, 0], rSh: [-0.9, 0, -0.3], rEl: [-1.4, 0, 0], ...x }),
  hold: (h, t, x = {}) => P.idle(h, t, { lSh: [-1.15, 0, 0.3], rSh: [-1.15, 0, -0.3], lEl: [-0.6, 0, 0], rEl: [-0.6, 0, 0], torso: [0.1, 0, 0], ...x }),
  point: (h, t, x = {}) => P.idle(h, t, { rSh: [-1.5, 0.2, -0.15], rEl: [-0.05, 0, 0], mouth: 0.2, ...x }),
  lean: (h, t, x = {}) => h.pose({ drop: 0.28, torso: [-0.35, 0, 0], neck: [-0.1, 0, 0], head: [0, 0, 0], lHip: [-1.5, 0.05, 0], lKn: [1.4, 0, 0], rHip: [-1.5, -0.05, 0], rKn: [1.4, 0, 0], lSh: [-0.3, 0, 0.4], lEl: [-1.0, 0, 0], rSh: [-0.3, 0, -0.4], rEl: [-1.0, 0, 0], smile: 1, blink: bl(t), ...x }),
};

// ---- kamers ----
const night = makeStage => { const s = room(makeStage, { key: 0.9, hemi: 0.6, hemiColor: 0x8fa4ff, rim: 0.6 }); windowPane(s, { x: -0.9 }); desk(s); lamp(s, { intensity: 1.1 }); return s; };
const living = makeStage => { const s = room(makeStage, { wall: 0x8a5a4a, floor: 0x5a4636, sky: [0xffb070, 0xffc890, 0xffe0b8], key: 0.8, keyColor: 0xffd7a8, hemi: 0.7, hemiColor: 0xffe8d0, rim: 0.4 }); windowPane(s, { x: 1.2, night: false });
  s.add(rbox(1.9, 0.42, 0.85, 0.08, std(0x3f6f8a, 0.9), [0, 0.21, -0.4])); s.add(rbox(1.9, 0.5, 0.2, 0.08, std(0x356079, 0.9), [0, 0.6, -0.78]));
  for (const sx of [-1, 1]) s.add(rbox(0.2, 0.55, 0.85, 0.08, std(0x356079, 0.9), [sx * 1.0, 0.3, -0.4])); s.add(rbox(1.0, 0.04, 0.6, 0.02, std(0x7a5a3a, 0.7), [0, 0.3, 0.6])); return s; };
const studio = (col = 0x4a3f8a, flo = 0x6a5fb0) => makeStage => { const s = room(makeStage, { wall: col, floor: flo, sky: [0x2a2060, 0x3a3080, 0x5a4fb0], key: 1.0, keyColor: 0xfff0e0, hemi: 0.8, hemiColor: 0xe8e0ff, rim: 0.6 });
  s.add(rbox(1.7, 0.06, 0.8, 0.02, std(0xe9e1d3, 0.6), [0, 0.76, 0])); for (const sx of [-0.78, 0.78]) for (const sz of [-0.3, 0.3]) s.add(rbox(0.06, 0.74, 0.06, 0.01, std(0x6a5a48), [sx, 0.37, sz])); return s; };
const dinnerRoom = makeStage => { const s = room(makeStage, { wall: 0xb5774a, floor: 0x8a6240, sky: [0xff9a4a, 0xffb36b, 0xffd9a0], key: 0.5, keyColor: 0xffc890, hemi: 0.55, hemiColor: 0xffd9b0, rim: 0.4 });
  s.add(rbox(1.1, 0.05, 0.8, 0.02, std(0xf2e8d8, 0.7), [0, 0.76, 0])); for (const sx of [-0.45, 0.45]) for (const sz of [-0.32, 0.32]) s.add(rbox(0.05, 0.74, 0.05, 0.01, std(0x4a3524), [sx, 0.37, sz]));
  const candle = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.16, 12), std(0xfff4e0)); candle.position.set(0, 0.87, 0); s.add(candle);
  const fl = new THREE.Mesh(new THREE.SphereGeometry(0.03, 10, 8), new THREE.MeshBasicMaterial({ color: 0xffd27a, toneMapped: false })); fl.position.set(0, 0.99, 0); s.add(fl);
  const cl = new THREE.PointLight(0xffb870, 2.2, 5, 1.5); cl.position.set(0, 1.1, 0); s.add(cl); return s; };
const ROOMS = { night, living, studio: studio(), studio2: studio(0x3a6f6a, 0x6a9a8a), street: m => street(m), golden: m => street(m, { golden: true }), bed: bedroom, kitchen, cook: m => { const C = cookingStage(m); C.scene.userData.host = C.host; return C.scene; }, dinner: dinnerRoom };

// shot(kamer, setup(S), update(t,S), {fov}): S.scene, S.c (camera)
export const shot = (kind, setup, update, { fov = 40, bloom = 0.5, exposure = 1.0 } = {}) => ({ makeStage }) => {
  const scene = ROOMS[kind](makeStage), c = cam(fov), S = { scene, c };
  setup && setup(S);
  return { scene, camera: c, update: (t, T2) => { update(t, S); return { bloom, exposure }; } };
};
export const cm = (S, t, a, b, look, dur = 1.5, ease = easeInOut) => place(S.c, [0, 1, 2].map(i => kf(t, [[0, a[i]], [dur, b[i]]], ease)), look);
export const put = (S, h, x, z, ry = 0) => { h.root.position.set(x, 0, z); h.root.rotation.y = ry; S.scene.add(h.root); return h; };
export const logoCard = (S, key, x, y, z, t0 = 0.1, w = 0.5, h = 0.31) => { const m = planeCard(logoTex(key), w, h); m.position.set(x, y, z); S.scene.add(m); return t => { m.scale.setScalar(pop(t, t0, 0.25, 1.6)); m.quaternion.copy(S.c.quaternion); }; };
export const bubble = (S, txt, x, y, z, t0 = 0.2, w = 0.66) => { const m = planeCard(bubbleTex(txt), w, w * 0.31); m.position.set(x, y, z); S.scene.add(m); return t => { m.scale.setScalar(pop(t, t0, 0.22, 1.5) * (t < t0 ? 0 : 1)); }; };
export const tag = (S, txt, x, y, z, t0 = 0.2, o = {}) => { const m = planeCard(labelTex(txt, { size: 70, ...o }), 0.62, 0.19); m.position.set(x, y, z); S.scene.add(m); return t => { m.scale.setScalar(pop(t, t0, 0.22, 1.6) * (t < t0 ? 0 : 1)); m.quaternion.copy(S.c.quaternion); }; };
// slot aan het einde: levend einde in plaats van de vaste eindkaart. Het bord noemt Omnivaleur en de gratis week.
export const sign = (S, x, y, z, t0 = 0.25) => { const g = new THREE.Group(); const a = planeCard(bigTex('omnivaleur.com', { fg: '#fff', size: 120, w: 900, h: 260 }), 0.9, 0.26), b = planeCard(labelTex('7 days free', { size: 84, bg: '#57e0d6', fg: '#0b1530' }), 0.5, 0.15); b.position.y = -0.2; g.add(a, b); g.position.set(x, y, z); S.scene.add(g); return t => { g.scale.setScalar(pop(t, t0, 0.3, 1.5) * (t < t0 ? 0 : 1)); g.quaternion.copy(S.c.quaternion); g.position.y = y + Math.sin(t * 3) * 0.02; }; };

// ---- vaste bouwstenen ----
export const hoodieFace = (H, t, { mouthOpen = 0, panic = 0, look = 0, calm = false } = {}) => {
  H.mouth.scale.set(1 + mouthOpen * 0.5, 1 + mouthOpen * 12, 1); H.mouth.position.y = 0.03 - mouthOpen * 0.02;
  H.eyes.forEach(e => { e.p.position.x = look * 0.03; e.p.position.y = Math.sin(t * 20) * 0.02 * panic; e.w.scale.y = calm ? 0.12 : 1; });
  H.g.rotation.z = Math.sin(t * 24) * 0.05 * panic; H.g.position.y = 1.18 + Math.abs(Math.sin(t * 18)) * 0.03 * panic;
};
export const buyer = (h, t, { pull = 0, smile = 0, mouth = 0 } = {}) => h.pose({ torso: [0.15 * pull, 0, 0], lSh: [-1.5, 0, 0.12], lEl: [-0.1 - pull * 0.1, 0, 0], rSh: [-1.5, 0, -0.12], rEl: [-0.1 - pull * 0.1, 0, 0], smile, mouth, blink: bl(t) });
const mk = o => person({ hoodie: o.hoodie, hair: o.hair, skin: o.skin, pants: o.pants, beanie: o.beanie, cap: o.cap, glasses: o.glasses, bun: o.bun });
export const typer = (o = {}) => shot('night', S => {
  S.lap = laptop(S.scene, { glow: 0.9 }); S.me = mk(o); seat(S.me); S.scene.add(S.me.root); S.fx = [];
  if (o.logo) S.fx.push(logoCard(S, o.logo, -0.55, 2.15, 0.6, 0.05, 0.55, 0.34));
  if (o.bubble) S.fx.push(bubble(S, o.bubble, 0.45, 1.95, 0.6, 0.35, 0.74));
  (o.logos || []).forEach((k, i) => S.fx.push(logoCard(S, k, -0.9 + i * 0.6, 2.2, 0.5, 0.1 + i * 0.35, 0.5, 0.31)));
  if (o.tag) S.fx.push(tag(S, o.tag[0], 0.4, 2.2, 0.6, o.tag[1] || 0.3, o.tag[2] || {}));
  if (o.clock) { S.scene.add(rbox(0.3, 0.14, 0.12, 0.03, std(0x222), [0.62, 0.86, 1.1])); const f = new THREE.Mesh(new THREE.PlaneGeometry(0.25, 0.1), new THREE.MeshBasicMaterial({ map: ledTex(o.clock), toneMapped: false })); f.position.set(0.62, 0.86, 1.165); S.scene.add(f); }
  if (o.cards) { const tx = listingTex(); S.cards = Array.from({ length: 8 }, () => { const m = planeCard(tx, 0.26, 0.325); S.scene.add(m); return m; }); }
}, (t, S) => {
  if (o.slump && t > (o.slump === true ? 0 : o.slump)) typingPose(S.me, 1, { neck: [0.5, 0, 0], head: [0.2, 0, 0.12], blink: t > 0.8 }); else typingPose(S.me, t * 1.6, { head: [0.1, Math.sin(t * 11) * 0.09, 0] });
  if (o.cardsOn !== false && S.cards) S.cards.forEach((m, i) => { const a = t * 1.5 + i * 0.8; m.position.set(Math.sin(a) * 0.9, 1.9 + (i % 3) * 0.25, 0.3 + Math.cos(a) * 0.5); m.scale.setScalar(pop(t, i * 0.1, 0.25, 1.3)); m.quaternion.copy(S.c.quaternion); });
  S.fx.forEach(f => f(t)); const c = o.cam || [[0.5, 1.5, 3.8], [-0.1, 1.45, 2.8], [0, 1.55, 0.3]]; cm(S, t, c[0], c[1], c[2], o.dur || 1.5);
}, { fov: o.fov || 40 });
export const walker = (o = {}) => shot(o.golden ? 'golden' : 'street', S => {
  S.h = mk(o); S.scene.add(S.h.root); if (o.parcel) { const bx = parcel(); S.h.torso.add(bx); bx.position.set(0, 0.32, 0.36); }
  if (o.logo) { S.lg = planeCard(logoTex(o.logo), 0.46, 0.29); S.scene.add(S.lg); }
}, (t, S) => {
  const z = lerp(-2.6, o.zEnd ?? 0.5, easeOut(t / (o.walkT || 1.0)));
  S.h.root.position.set(o.x || 0, 0, z);
  if (t < (o.walkT || 1.0)) walkPose(S.h, t, 1.25, o.parcel ? { lSh: [-1.15, 0, 0.3], rSh: [-1.15, 0, -0.3], lEl: [-0.6, 0, 0], rEl: [-0.6, 0, 0], torso: [0.12, 0, 0] } : {});
  else (o.end || P.stop)(S.h, t, o.parcel ? { lSh: [-1.15, 0, 0.3], rSh: [-1.15, 0, -0.3], lEl: [-0.6, 0, 0], rEl: [-0.6, 0, 0] } : {});
  if (S.lg) { S.lg.position.set(0.55 + (o.x || 0), 1.55 + Math.sin(t * 5) * 0.02, z); S.lg.scale.setScalar(pop(t, 0.2, 0.3)); S.lg.rotation.set(0, -0.3, 0.05); }
  const p = [lerp(1.2, 0.6, easeOut(t / 1.2)), lerp(0.9, 1.1, easeOut(t / 1.2)), lerp(4.6, 3.8, easeOut(t / 1.2))]; place(S.c, p, [o.x || 0, 0.95, 0.2]);
}, { fov: 46, bloom: 0.4 });
// levend einde: groep poppetjes die springen onder het Omnivaleur-bord
export const finale = (room, cast, o = {}) => shot(room, S => { S.hs = cast.map(c => { const h = mk(c); put(S, h, c.x, c.z || 0, c.ry || 0); return h; }); S.sg = sign(S, o.sx || 0, o.sy || 2.15, o.sz || 0.3, 0.3); S.logos = (o.logos || []).map((k, i, a) => logoCard(S, k, (i - (a.length - 1) / 2) * 0.55, 2.7, 0.2, 0.15 + i * 0.12, 0.46, 0.29)); },
  (t, S) => { S.hs.forEach((h, i) => { const j = Math.abs(Math.sin(t * 6 + i * 1.3)) * (o.jump ?? 0.14); cheer(t + i).smile = 1; h.pose({ ...cheer(t + i * 0.7), drop: -j }); }); S.sg(t); S.logos.forEach(f => f(t)); const c = o.cam || [[0, 1.5, 6.2], [0, 1.4, 5.4], [0, 1.2, 0]]; cm(S, t, c[0], c[1], c[2], 2.6, easeOut); },
  { fov: o.fov || 42, bloom: 0.6 });
