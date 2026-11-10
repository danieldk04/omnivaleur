// Video 3: space emergency. Hypothesis: drama and speed (alarm, short sentences, fastest cuts of the week) beats a calm explainer on retention.
import * as THREE from 'three';
import { kf, lerp, easeOut, easeInOut, range, clamp, V, cam, place } from './anim.js';
import { pop, planeCard, wrap, logoTex, listingTex, checkTex, K, Ll, Mm, s8, PLATFORMS, rnd } from './shots.js';
import { spaceScene, astronaut, satellite, labelTex, stampTex } from './week46.js';
export { CAPTIONS, DURATION } from './cap.js';
import { DURATION } from './cap.js';
export const FADES = [];

function space(update, { fov = 40, red = false } = {}) {
  return ({ makeStage }) => {
    const S = spaceScene(), a = astronaut(), c = cam(fov); S.scene.add(a.root); S.a = a; S.red = red;
    const alarm = new THREE.PointLight(0xff2a2a, 0, 8); alarm.position.set(0, 0.6, 1.5); S.scene.add(alarm); S.alarm = alarm;
    return { scene: S.scene, camera: c, update: (t, T) => { const r = update(t, T, S, c) || {}; alarm.intensity = red ? (Math.sin(t * 14) > 0 ? 14 : 2) : 0; return r; } };
  };
}
const float = (a, t, o = {}) => a.pose({ drop: -0.2, hip: [0.3 * Math.sin(t * 1.3), 0, 0.15 * Math.sin(t * 1.1)], torso: [0.1, 0, 0], lSh: [-0.6 + Math.sin(t * 2) * 0.2, 0, 0.9], rSh: [-0.6 - Math.sin(t * 2) * 0.2, 0, -0.9], lEl: [-0.3, 0, 0], rEl: [-0.3, 0, 0], lHip: [-0.5, 0, 0.2], rHip: [-0.3, 0, -0.2], lKn: [0.5, 0, 0], rKn: [0.7, 0, 0], blink: ((t * 0.7) % 3) > 2.9, ...o });
const panic = (t) => ({ lSh: [-2.6 + Math.sin(t * 20) * 0.25, 0, 0.5], rSh: [-2.6 - Math.sin(t * 20) * 0.25, 0, -0.5], lEl: [-0.4, 0, 0], rEl: [-0.4, 0, 0], mouth: 0.8, smile: 0 });

// S1 tumble in, alarm flashing
const S1 = space((t, T, S, c) => {
  S.a.root.position.set(0, 0, 0); S.a.root.rotation.set(0.5 * Math.sin(t * 1.2), t * 0.9, 0.3 * Math.sin(t)); float(S.a, t, { ...panic(t) });
  place(c, [Math.sin(t * 0.8) * 1.2 + 1.2, 0.5, kf(t, [[0, 4.4], [1.0, 3.2]], easeOut)], [0, 0.2, 0]);
  return { bloom: 0.6, exposure: 1.1 };
}, { red: true, fov: 42 });
// S2 face in the helmet, ALERT stamp
const S2 = space((t, T, S, c) => {
  S.a.root.position.set(0, 0, 0); S.a.root.rotation.set(0, 0, 0); float(S.a, t * 2, { ...panic(t), head: [0, Math.sin(t * 12) * 0.3, 0] });
  if (!S.st) { S.st = planeCard(stampTex('ALERT'), 0.8, 0.3); S.scene.add(S.st); }
  S.st.position.set(0.0, 1.55, 0.6); S.st.scale.setScalar(pop(t, 0.2, 0.2, 2) * (t < 0.2 ? 0 : 1)); S.st.rotation.z = -0.1;
  place(c, [0.0, 1.4, kf(t, [[0, 2.8], [1.1, 2.0]], easeOut)], [0, 1.35, 0]);
  return { bloom: 0.7, exposure: 1.05, dof: { focus: 2.2, aperture: 0.005, maxblur: 0.012 } };
}, { red: true, fov: 38 });
// S3/S4 satellites with logos arrive (four platforms)
const sats = (ids, off) => space((t, T, S, c) => {
  S.a.root.position.set(0, 0, 0); S.a.root.rotation.set(0, 0.3, 0); float(S.a, t, panic(t));
  if (!S.sat) { S.sat = ids.map(i => { const g = satellite(PLATFORMS[i]); S.scene.add(g); return g; }); }
  S.sat.forEach((g, i) => { const t0 = i * 0.3, k = easeOut(range(t, t0, t0 + 0.5)); const x = (i - (ids.length - 1) / 2) * 1.5; g.position.set(lerp(x * 3, x, k), 0.9 + 0.35 * (i % 2) + Math.sin(t * 3 + i) * 0.05, lerp(-6, 0.5 - off, k)); g.rotation.set(0, Math.sin(t + i) * 0.3, 0); g.userData.logo.quaternion.copy(c.quaternion); g.scale.setScalar(pop(t, t0, 0.3, 1.3) * (t < t0 ? 0 : 1)); });
  place(c, [0.0, 0.6, 4.2], [0, 0.35, 0]);
  return { bloom: 0.5, exposure: 1.1 };
}, { fov: 46 });
// S5 one astronaut, zero evenings: drifts away, Earth behind
const S5 = space((t, T, S, c) => {
  S.a.root.position.set(lerp(-0.3, 0.8, t / 1.1), lerp(0.2, 0.6, t / 1.1), lerp(0, -1.5, t / 1.1)); S.a.root.rotation.set(0.6 * t, 1 + t * 0.7, 0.4 * t); float(S.a, t * 0.6, { blink: true, head: [0.3, 0, 0.2] });
  place(c, [0.0, 0.2, 3.8], [0, 0.0, -0.5]);
  return { bloom: 0.5, exposure: 1.0 };
}, { fov: 42 });
// S6/S7 every listing typed again: swirl of listing cards around the astronaut
const swirl = (rush) => space((t, T, S, c) => {
  S.a.root.position.set(0, 0, 0); S.a.root.rotation.set(0.2, 0.3, 0); float(S.a, t * 2, { torso: [0.35, 0, 0], head: [0.3, 0, 0], lSh: [-1.0 + Math.sin(t * 18) * 0.12, 0, 0.3], rSh: [-1.0 - Math.sin(t * 18) * 0.12, 0, -0.3] });
  if (!S.cards) { const tex = listingTex(); S.cards = Array.from({ length: 22 }, () => { const m = planeCard(tex, 0.3, 0.375); S.scene.add(m); return m; }); }
  S.cards.forEach((m, i) => { const r = 1.1 + (i % 3) * 0.3, a = t * (2.0 + rush) + i * 0.6, k = pop(t, i * 0.04, 0.2); m.position.set(Math.sin(a) * r, 0.2 + (i / 22) * 1.6 - 0.5 + Math.sin(t * 3 + i) * 0.05, Math.cos(a) * r - 0.2); m.scale.setScalar(k * (t < i * 0.04 ? 0 : 1)); m.quaternion.copy(c.quaternion); });
  place(c, [Math.sin(0.3 - t * 0.4) * 3.5, 1.0, Math.cos(0.3 - t * 0.4) * 3.5], [0, 0.4, 0]);
  return { bloom: 0.5, exposure: 1.05 };
}, { fov: 44, red: rush > 0 });
// S8 five satellites orbit, checks, camera pulls back
const S8 = space((t, T, S, c) => {
  S.a.root.visible = false;
  if (!S.sat) { S.sat = PLATFORMS.map(k => { const g = satellite(k); S.scene.add(g); const ck = planeCard(checkTex(), 0.16, 0.16); S.scene.add(ck); return [g, ck]; }); }
  S.sat.forEach(([g, ck], i) => { const a = t * 1.3 + i * 1.256, t0 = i * 0.14; g.position.set(Math.cos(a) * 1.7, 0.3 + Math.sin(a * 2) * 0.1, Math.sin(a) * 1.0); g.userData.logo.quaternion.copy(c.quaternion); g.scale.setScalar(pop(t, t0, 0.25, 1.4) * (t < t0 ? 0 : 1)); ck.position.set(g.position.x + 0.3, g.position.y + 0.55, g.position.z + 0.1); ck.quaternion.copy(c.quaternion); ck.scale.setScalar(pop(t, t0 + 0.25, 0.2, 2.2) * (t < t0 + 0.25 ? 0 : 1)); });
  S.earth.position.set(0, -2.2, -2.5);
  place(c, [0.0, 1.0, kf(t, [[0, 3.6], [1.6, 5.2]], easeInOut)], [0, -0.2, 0]);
  return { bloom: 0.6, exposure: 1.1 };
}, { fov: 44 });
// S9 mission accomplished: happy float, thumbs up, Earth glows
const S9 = space((t, T, S, c) => {
  S.a.root.position.set(0, 0.1 + Math.sin(t * 2) * 0.05, 0); S.a.root.rotation.set(0, 0.2 * Math.sin(t), 0); float(S.a, t, { lSh: [-2.9 + Math.sin(t * 9) * 0.15, 0, 0.45], rSh: [-2.9 - Math.sin(t * 9) * 0.15, 0, -0.45], lEl: [-0.2, 0, 0], rEl: [-0.2, 0, 0], smile: 1 });
  place(c, [kf(t, [[0, -0.8], [1.5, 0.6]], easeInOut), 0.6, 3.6], [0, 0.4, 0]);
  return { bloom: 0.7, exposure: 1.1 };
}, { fov: 42 });

export const SHOTS = [
  [0.0, 1.0, S1], [1.0, 2.1, S2], [2.1, 3.3, sats([0, 1], 0)], [3.3, 4.4, sats([2, 3], 0)], [4.4, 5.5, S5],
  [5.5, 7.0, swirl(0)], [7.0, 8.3, swirl(1.5)],
  [8.3, 9.4, K], [9.4, 10.5, Ll], [10.5, 11.5, Mm], [11.5, 13.4, S8], [13.4, 15.0, S9],
].map(([start, end, b], i) => ({ start, end, build: wrap(b, end - start, i % 2 ? 1 : -1) })).concat([{ start: 15.0, end: DURATION + 1, build: s8 }]);
