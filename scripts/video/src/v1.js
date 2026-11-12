// Video 1: courtroom. Hypothesis: an accusation as the hook ("this reseller is accused...") holds viewers better than a statement.
import * as THREE from 'three';
import { makeBlocky } from './blocky.js';
import { kf, lerp, easeOut, easeInOut, range, clamp, V, cam, place, shake } from './anim.js';
import { std, rbox, pop, planeCard, wrap, logoTex, listingTex, bubbleTex, gradTex, typingPose, walkPose, cheer, K, Ll, Mm, Nn, s8, IMG } from './shots.js';
import { courtroom, judgeStrike, labelTex, stampTex } from './week46.js';
export { CAPTIONS, DURATION } from './cap.js';
import { DURATION, LINES } from './cap.js';
// shot times were written against the first voice-over; map them onto the new line timings
const OLD_STARTS = [0, 1.585, 5.517, 8.297, 10.629, 12.428, 14.333], OLD_END = 15.49;
const T = x => { const o = [...OLD_STARTS, OLD_END], n = [...LINES.map(l => l[0]), LINES[LINES.length - 1][1]]; for (let i = 0; i < o.length - 1; i++) if (x < o[i + 1] || i === o.length - 2) return n[i] + (x - o[i]) * (n[i + 1] - n[i]) / (o[i + 1] - o[i]); return x; };
export const FADES = [];

const bang = (t, t0) => Math.exp(-Math.pow((t - t0) * 14, 2));      // short pulse at the strike
function court(update, { fov = 40 } = {}) {
  return ({ makeStage }) => {
    const C = courtroom(makeStage), c = cam(fov);
    return { scene: C.scene, camera: c, update: (t, T) => update(t, T, C, c) };
  };
}
// A: low angle on the judge, gavel strikes
const A = court((t, T, C, c) => {
  judgeStrike(C.judge, range(t, 0.25, 0.75)); typingPose(C.hd, t + 3, { smile: 0 });
  const s = bang(t, 0.7) * 0.05; place(c, [1.0 + s, 1.6 - s, kf(t, [[0, 3.3], [1.3, 2.6]], easeOut)], [0, 1.85, -1.3]);
  return { dof: { focus: 2.6, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
}, { fov: 42 });
// B: judge points at the defendant (wide)
const B = court((t, T, C, c) => {
  C.judge.pose({ torso: [0.05, 0, 0], rSh: [-1.7, 0, -0.1], rEl: [-0.15, 0, 0], lSh: [-0.5, 0, 0.15], lEl: [-0.7, 0, 0], head: [0, Math.sin(t * 3) * 0.05, 0] });
  typingPose(C.hd, t + 5, { smile: 0 });
  place(c, [kf(t, [[0, -1.6], [1.6, -0.6]], easeInOut), 1.6, 3.6], [0, 1.2, -0.3]);
  return { dof: { focus: 3.4, aperture: 0.003, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
});
// C: defendant close-up, four listing cards pop out one by one
const Cc = court((t, T, C, c) => {
  typingPose(C.hd, t * 1.3 + 7, { head: [0.1, Math.sin(t * 9) * 0.08, 0] });
  if (!C.cards) { const tex = listingTex(); C.cards = [0, 1, 2, 3].map(() => { const m = planeCard(tex, 0.36, 0.45); C.scene.add(m); return m; }); }
  C.cards.forEach((m, i) => { const t0 = 0.05 + i * 0.28; m.position.set(-0.62 + i * 0.42, 2.35 + (i % 2) * 0.12, 0.6); m.scale.setScalar(pop(t, t0, 0.22, 1.5) * (t < t0 ? 0 : 1)); m.rotation.set(0, 0, (i - 1.5) * 0.06); });
  const p = kf(t, [[0, [0.3, 1.5, 3.7]], [1.2, [-0.1, 1.6, 2.8]]], easeOut); place(c, p, [0, 1.75, 0.3]);
  return { dof: { focus: 2.8, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
}, { fov: 44 });
// D: frantic typing, speech bubbles
const D = court((t, T, C, c) => {
  typingPose(C.hd, t * 1.6 + 1, { head: [0.1, Math.sin(t * 11) * 0.09, Math.sin(t * 7) * 0.05] });
  if (!C.bs) { C.bs = ['Nike Tech Fleece', 'Size M, like new', 'Brand: Nike', 'Price: €68'].map(s => { const m = planeCard(bubbleTex(s), 0.56, 0.175); C.scene.add(m); return m; }); }
  C.bs.forEach((m, i) => { const t0 = 0.05 + i * 0.22; m.position.set(i % 2 ? 0.3 : -0.3, 2.0 + (i % 2) * 0.22, 0.5); m.scale.setScalar(pop(t, t0, 0.2) * (t < t0 ? 0 : 1)); m.rotation.set(0, 0, i % 2 ? 0.05 : -0.05); });
  const p = kf(t, [[0, [0.5, 1.4, 3.8]], [1.1, [-0.1, 1.5, 2.8]]], easeOut); place(c, p, [0, 1.55, 0.3]);
  return { dof: { focus: 2.8, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
});
// E: exhibit boards, two platform logos slam in with a stamp
const exhibit = (ids, labels, a0) => ({ makeStage }) => {
  const scene = new THREE.Scene(); scene.userData.sky = new THREE.Object3D();
  const bg = new THREE.Mesh(new THREE.PlaneGeometry(8, 12), new THREE.MeshBasicMaterial({ map: gradTex('#3a2a1a', '#7a5538'), toneMapped: false })); bg.position.z = -0.5; scene.add(bg);
  const cards = ids.map((k, i) => { const m = planeCard(logoTex(k), 0.62, 0.39); scene.add(m); const st = planeCard(stampTex(labels[i]), 0.5, 0.19); scene.add(st); return [m, st]; });
  const c = cam(40);
  return { scene, camera: c, update(t) {
    cards.forEach(([m, st], i) => { const t0 = a0[i]; m.position.set(0, 0.28 - i * 0.62, 0); m.scale.setScalar(pop(t, t0, 0.22, 1.6) * (t < t0 ? 0 : 1)); m.rotation.z = (i ? 1 : -1) * 0.05; st.position.set(0.0, 0.28 - i * 0.62 - 0.27, 0.05); st.scale.setScalar(pop(t, t0 + 0.2, 0.18, 2.2) * (t < t0 + 0.2 ? 0 : 1)); st.rotation.z = -0.08; });
    const p = kf(t, [[0, [0.15, 0.0, 2.9]], [1.4, [-0.05, -0.1, 2.3]]], easeInOut); place(c, p, [0, -0.1, 0], Math.sin(t * 4) * 0.02);
    return { bloom: 0.3 };
  } };
};
// G: GUILTY, judge close-up, stamp pops
const G = court((t, T, C, c) => {
  judgeStrike(C.judge, range(t, 0.05, 0.5), { rSh: [-1.0 - Math.sin(clamp(range(t, 0.05, 0.5)) * Math.PI) * 1.0, 0, -0.15] }); typingPose(C.hd, 1, { neck: [0.5, 0, 0], head: [0.2, 0, 0.1], blink: true });
  if (!C.st) { C.st = planeCard(stampTex('GUILTY'), 0.95, 0.36); C.scene.add(C.st); }
  C.st.position.set(-0.05, 2.45, -0.6); C.st.scale.setScalar(pop(t, 0.35, 0.18, 2.4) * (t < 0.35 ? 0 : 1)); C.st.rotation.z = -0.12;
  const s = bang(t, 0.3) * 0.05; place(c, [0.3 + s, 2.3 - s, kf(t, [[0, 3.2], [1.1, 2.7]], easeOut)], [0, 1.95, -1.3]);
  return { dof: { focus: 3.2, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
});
// H: defendant slumped, camera pushes in
const H = court((t, T, C, c) => {
  typingPose(C.hd, 1, { neck: [0.55, 0, 0], head: [0.25, 0, 0.14], blink: t > 0.4 });
  const p = kf(t, [[0, [0.9, 1.4, 3.3]], [1.2, [0.2, 1.5, 2.2]]], easeInOut); place(c, p, [0, 1.45, 0.3]);
  return { dof: { focus: 2.4, aperture: 0.005, maxblur: 0.012 }, bloom: 0.4, exposure: 0.9 };
}, { fov: 38 });
// P: case dismissed: gavel, defendant cheers
const P = court((t, T, C, c) => {
  judgeStrike(C.judge, range(t, 0.15, 0.6), { smile: 1 });
  typingPose(C.hd, t, { smile: 1, ...cheer(t), neck: [0, 0, 0], head: [0, 0, 0] });
  const s = bang(t, 0.55) * 0.05; place(c, [kf(t, [[0, -0.9], [1.3, 0.5]], easeInOut) + s, 1.5 - s, 3.6], [0, 1.4, -0.4]);
  return { dof: { focus: 3.6, aperture: 0.003, maxblur: 0.01 }, bloom: 0.55, exposure: 1.08 };
});

export const SHOTS = [
  [0.0, 1.3, A], [1.3, 3.0, B], [3.0, 4.2, Cc], [4.2, 5.4, D],
  [5.4, 6.8, exhibit(['vinted.png', 'marktplaats.png'], ['EXHIBIT A', 'EXHIBIT B'], [0.15, 0.85])],
  [6.8, 8.2, exhibit(['ebay.webp', 'shopify.webp'], ['EXHIBIT C', 'EXHIBIT D'], [0.0, 0.55])],
  [8.2, 9.3, G], [9.3, 10.5, H],
  [10.5, 11.5, K], [11.5, 12.4, Ll], [12.4, 13.3, Mm], [13.3, 14.3, Nn], [14.3, 15.7, P],
].map(([start, end, b], i) => { const a = T(start), z = T(end); return { start: a, end: z, build: i % 3 === 2 ? b : wrap(b, z - a, i % 2 ? 1 : -1) }; }).concat([{ start: T(15.7), end: DURATION + 1, build: s8 }]);   // every third cut is a hard cut, the rest whip
