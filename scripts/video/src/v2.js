// Video 2: cooking show. Hypothesis: a "recipe" format (instruction, not complaint) with a step-by-step structure keeps people to the end.
import * as THREE from 'three';
import { kf, lerp, easeOut, easeInOut, range, clamp, V, cam, place } from './anim.js';
import { pop, planeCard, wrap, logoTex, listingTex, bubbleTex, checkTex, K, Ll, Mm, Nn, s8, PLATFORMS, rnd } from './shots.js';
import { cookingStage, plate, pan, steam, labelTex } from './week46.js';
export { CAPTIONS, DURATION } from './cap.js';
import { DURATION } from './cap.js';
export const FADES = [];

const TOP = 0.96;
function cook(update, { fov = 40 } = {}) {
  return ({ makeStage }) => {
    const C = cookingStage(makeStage), c = cam(fov);
    return { scene: C.scene, camera: c, update: (t, T) => update(t, T, C, c) };
  };
}
const hostPose = (h, t, extra = {}) => h.pose({ torso: [0.08, 0, 0], head: [0, Math.sin(t * 2) * 0.05, 0], lSh: [-0.9, 0, 0.25], lEl: [-1.0, 0, 0], rSh: [-0.9, 0, -0.25], rEl: [-1.0, 0, 0], blink: ((t * 0.7) % 3) > 2.9, smile: 1, ...extra });
const wave = (t) => ({ rSh: [-2.7 + Math.sin(t * 9) * 0.15, 0, -0.5], rEl: [-0.3 + Math.sin(t * 9) * 0.25, 0, 0] });
const plates = (C, n, xs) => { if (!C.pl) { C.pl = xs.map(x => { const p = plate(); p.position.set(x, TOP + 0.01, 0.3); C.scene.add(p); return p; }); } return C.pl; };
const X5 = [-0.9, -0.45, 0, 0.45, 0.9];

// R1 wave hello
const R1 = cook((t, T, C, c) => {
  hostPose(C.host, t, wave(t));
  place(c, [kf(t, [[0, 0.7], [1.1, 0.2]], easeOut), 1.45, 3.1], [0, 1.45, -0.3]);
  return { dof: { focus: 3.2, aperture: 0.003, maxblur: 0.01 }, bloom: 0.45, exposure: 1.05 };
});
// R2 "one listing": the listing card pops above the host's hat
const R2 = cook((t, T, C, c) => {
  hostPose(C.host, t, { rSh: [-1.7, 0, -0.35], rEl: [-0.6, 0, 0] });
  if (!C.card) { C.card = planeCard(listingTex(), 0.5, 0.625); C.scene.add(C.card); }
  C.card.position.set(0.45, 2.15, -0.1); C.card.scale.setScalar(pop(t, 0.1, 0.3, 1.8)); C.card.rotation.z = -0.08;
  place(c, [kf(t, [[0, -0.3], [1.1, 0.1]], easeInOut), 1.75, kf(t, [[0, 3.4], [1.1, 2.7]], easeOut)], [0.1, 1.85, -0.3]);
  return { dof: { focus: 2.9, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
}, { fov: 42 });
// R3 "five platforms": five empty plates pop onto the counter
const R3 = cook((t, T, C, c) => {
  hostPose(C.host, t, { lSh: [-1.0, 0, 0.5], rSh: [-1.0, 0, -0.5], lEl: [-0.6, 0, 0], rEl: [-0.6, 0, 0] });
  plates(C, 5, X5).forEach((p, i) => { const t0 = 0.05 + i * 0.16; p.scale.setScalar(pop(t, t0, 0.2, 1.4) * (t < t0 ? 0 : 1)); });
  place(c, [kf(t, [[0, 0.0], [1.2, 0.3]], easeInOut), kf(t, [[0, 2.6], [1.2, 1.9]], easeInOut), 2.8], [0, 0.95, 0.3]);
  return { dof: { focus: 2.9, aperture: 0.004, maxblur: 0.01 }, bloom: 0.4, exposure: 1.05 };
}, { fov: 44 });
// R4 "take one hoodie": the card lands on a board
const R4 = cook((t, T, C, c) => {
  hostPose(C.host, t, { torso: [0.2, 0, 0], head: [0.15, 0, 0], lSh: [-1.0, 0, 0.35], rSh: [-1.0, 0, -0.35] });
  if (!C.card) { C.card = planeCard(listingTex(), 0.5, 0.625); C.scene.add(C.card); }
  const k = easeOut(range(t, 0, 0.35)); C.card.position.set(0, lerp(2.2, 1.28, k), 0.5); C.card.rotation.x = -0.35; C.card.rotation.z = (1 - k) * 0.4; C.card.scale.setScalar(1.1);
  place(c, [kf(t, [[0, 0.5], [1.2, -0.1]], easeInOut), 1.6, kf(t, [[0, 2.8], [1.2, 2.2]], easeOut)], [0, 1.2, 0.4]);
  return { dof: { focus: 2.4, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
}, { fov: 40 });
// R5/R6 "photos, text, price": ingredient chips fly into the pan
const chips = (labels, off) => cook((t, T, C, c) => {
  hostPose(C.host, t, { torso: [0.15, 0, 0], head: [0.1, Math.sin(t * 8) * 0.1, 0], lSh: [-1.0 + Math.sin(t * 14) * 0.15, 0, 0.3], rSh: [-1.0 - Math.sin(t * 14) * 0.15, 0, -0.3] });
  if (!C.p) { C.p = pan(); C.p.position.set(0, TOP + 0.03, 0.3); C.scene.add(C.p); C.ch = labels.map(s => { const m = planeCard(labelTex(s, { size: 80 }), 0.44, 0.14); C.scene.add(m); return m; }); C.stm = steam(); C.stm.position.set(0, TOP + 0.1, 0.3); C.scene.add(C.stm); }
  C.stm.userData.tick(t);
  C.ch.forEach((m, i) => { const t0 = 0.05 + i * 0.4, k = easeOut(range(t, t0, t0 + 0.3)), j = range(t, t0 + 0.3, t0 + 0.55); m.position.set(lerp(-0.9 + i * 0.9, (i - 1) * 0.25, k), lerp(2.0, 1.7 + i * 0.2, k) - j * 0.6, 0.3); m.scale.setScalar(pop(t, t0, 0.25, 1.4) * (t < t0 ? 0 : 1) * (1 - 0.5 * j)); m.rotation.z = (i - 1) * 0.1; });
  place(c, [kf(t, [[0, -0.5 + off], [1.0, 0.1 + off]], easeInOut), 1.6, 2.9], [0, 1.3, 0.1]);
  return { dof: { focus: 2.9, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
});
// R7/R8 "five times": five pans on the boil, host in a panic
const pans = (rush) => cook((t, T, C, c) => {
  hostPose(C.host, t, { head: [0.05, Math.sin(t * 12) * 0.35, 0], lSh: [-1.1 + Math.sin(t * 16) * 0.3, 0, 0.3], rSh: [-1.1 - Math.sin(t * 16) * 0.3, 0, -0.3], smile: 0, mouth: 0.6 });
  if (!C.ps) { C.ps = X5.map((x, i) => { const p = pan(); p.position.set(x, TOP + 0.03, 0.3); p.rotation.y = Math.PI; C.scene.add(p); const s = steam(); s.position.set(x, TOP + 0.08, 0.3); C.scene.add(s); const l = planeCard(logoTex(PLATFORMS[i]), 0.36, 0.22); l.position.set(x, 1.55 + (i % 2) * 0.1, 0.3); C.scene.add(l); return { p, s, l }; }); }
  C.ps.forEach((o, i) => { o.s.userData.tick(t * (1 + rush) + i); const t0 = 0.05 + i * 0.12; o.l.scale.setScalar(pop(t, t0, 0.2, 1.4) * (t < t0 ? 0 : 1)); o.l.rotation.z = Math.sin(t * 8 + i) * 0.12; });
  place(c, [kf(t, [[0, rush ? 0.9 : -0.6], [1.4, rush ? 0.1 : 0.2]], easeInOut), 1.5, kf(t, [[0, 3.2], [1.4, 2.6]], easeOut)], [0, 1.2, 0.2], Math.sin(t * 10) * 0.015 * rush);
  return { dof: { focus: 3.0, aperture: 0.004, maxblur: 0.01 }, bloom: 0.55, exposure: 1.0 };
});
// R9/R10/R11 "served on ...": logos land on the plates, checks follow
const served = (ids, from, last) => cook((t, T, C, c) => {
  hostPose(C.host, t, { lSh: [-1.0, 0, 0.5], rSh: [-1.8, 0, -0.45], rEl: [-0.5, 0, 0], head: [0, Math.sin(t * 3) * 0.1, 0] });
  const pl = plates(C, 5, X5);
  if (!C.lg) { C.lg = PLATFORMS.map((k, i) => { const m = planeCard(logoTex(k), 0.4, 0.25); C.scene.add(m); const ck = planeCard(checkTex(), 0.12, 0.12); C.scene.add(ck); return [m, ck]; }); }
  C.lg.forEach(([m, ck], i) => { const on = ids.includes(i), before = i < from; const t0 = 0.05 + (ids.indexOf(i)) * 0.35; const vis = before || (on && t >= t0); m.visible = vis; ck.visible = vis; const s = before ? 1 : pop(t, t0, 0.25, 1.6); m.position.set(X5[i], TOP + 0.34 + (before ? 0 : (1 - easeOut(range(t, t0, t0 + 0.2))) * 0.5), 0.3); m.scale.setScalar(s); ck.position.set(X5[i] + 0.19, TOP + 0.5, 0.35); ck.scale.setScalar(before ? 1 : pop(t, t0 + 0.2, 0.2, 2.2)); });
  place(c, [kf(t, [[0, last ? -0.9 : -0.3], [1.3, last ? 0.0 : 0.4]], easeInOut), kf(t, [[0, 1.7], [1.3, 1.5]], easeInOut), kf(t, [[0, 2.6], [1.3, last ? 3.4 : 2.2]], easeInOut)], [0, 1.15, 0.3]);
  return { dof: { focus: 2.6, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
}, { fov: 44 });
// R12 cheer: the hat flies off
const R12 = cook((t, T, C, c) => {
  hostPose(C.host, t, { ...{ lSh: [-2.9 + Math.sin(t * 9) * 0.15, 0, 0.45], rSh: [-2.9 - Math.sin(t * 9) * 0.15, 0, -0.45], lEl: [-0.2, 0, 0], rEl: [-0.2, 0, 0] }, drop: -0.05 * Math.abs(Math.sin(t * 7)) });
  plates(C, 5, X5);
  place(c, [kf(t, [[0, -0.4], [1.0, 0.3]], easeInOut), 1.6, 3.0], [0, 1.5, 0]);
  return { dof: { focus: 3.0, aperture: 0.003, maxblur: 0.01 }, bloom: 0.6, exposure: 1.08 };
});

export const SHOTS = [
  [0.0, 1.1, R1], [1.1, 2.2, R2], [2.2, 3.4, R3], [3.4, 4.6, R4], [4.6, 5.6, chips(['Photos', 'Text', 'Price'], 0)], [5.6, 6.6, chips(['Photos', 'Text', 'Price'], 0.4)],
  [6.6, 7.8, pans(0)], [7.8, 9.2, pans(1)],
  [9.2, 10.2, Mm], [10.2, 10.9, Ll],
  [10.9, 12.0, served([0, 1], 0, false)], [12.0, 13.1, served([2, 3], 2, false)], [13.1, 14.3, served([4], 4, true)],
  [14.3, 15.2, K], [15.2, 16.2, Nn], [16.2, 17.2, R12],
].map(([start, end, b], i) => ({ start, end, build: wrap(b, end - start, i % 2 ? 1 : -1) })).concat([{ start: 17.2, end: DURATION + 1, build: s8 }]);
