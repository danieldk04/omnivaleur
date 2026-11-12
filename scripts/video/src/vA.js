// Voorbeeld A: storytime. Een mens met een inzet (middernacht, een gesprek met zijn vriendin), een draai en een einde dat telt (samen eten).
import * as THREE from 'three';
import { makeBlocky } from './blocky.js';
import { kf, lerp, easeOut, easeInOut, range, clamp, V, cam, place } from './anim.js';
import { std, rbox, room, windowPane, desk, laptop, lamp, typingPose, seat, pop, planeCard, wrap, logoTex, listingTex, bubbleTex, gradTex, ledTex, K, Ll, Mm, Nn, s8, PLATFORMS } from './shots.js';
import { stampTex } from './week46.js';
export { CAPTIONS, DURATION } from './cap.js';
import { DURATION, LINES } from './cap.js';
export const FADES = [];
const OLD_STARTS = [0, 5.356, 10.627, 13.295, 17.115, 19.228], OLD_END = 21.68;
const T = x => { const o = [...OLD_STARTS, OLD_END], n = [...LINES.map(l => l[0]), LINES[LINES.length - 1][1]]; for (let i = 0; i < o.length - 1; i++) if (x < o[i + 1] || i === o.length - 2) return n[i] + (x - o[i]) * (n[i + 1] - n[i]) / (o[i + 1] - o[i]); return x; };

function night(update, { fov = 40, clock = '00:47' } = {}) {
  return ({ makeStage }) => {
    const scene = room(makeStage, { key: 0.9, hemi: 0.6, hemiColor: 0x8fa4ff, rim: 0.6 }); windowPane(scene, { x: -0.9 }); desk(scene); const lap = laptop(scene, { glow: 0.9 }); lamp(scene, { intensity: 1.1 });
    const me = makeBlocky(); seat(me); scene.add(me.root);
    scene.add(rbox(0.3, 0.14, 0.12, 0.03, std(0x222), [0.62, 0.86, 1.1]));
    const face = new THREE.Mesh(new THREE.PlaneGeometry(0.25, 0.1), new THREE.MeshBasicMaterial({ map: ledTex(clock), toneMapped: false })); face.position.set(0.62, 0.86, 1.165); scene.add(face);
    const gf = makeBlocky({ hoodie: 0xe58aa8, hair: 0x5a3a2a, skin: 0xe0a98a, pants: 0x3a3f5c }); gf.root.position.set(1.25, 0, 0.45); gf.root.rotation.y = -1.5; scene.add(gf.root);
    const c = cam(fov); const S = { scene, me, gf, lap, c, face };
    return { scene, camera: c, update: (t, T2) => update(t, T2, S) };
  };
}
const gfPose = (gf, t, extra = {}) => gf.pose({ torso: [0, 0.1, 0], head: [0, 0.2 * Math.sin(t * 1.5), 0], lSh: [-0.1, 0, 0.75], lEl: [-2.0, 0, 0], rSh: [-0.1, 0, -0.75], rEl: [-2.0, 0, 0], blink: ((t * 0.7) % 3) > 2.9, ...extra });
const bub = (S, txt, t, t0, x, y, z) => { if (!S.bb) { S.bb = planeCard(bubbleTex(txt), 0.62, 0.19); S.scene.add(S.bb); } S.bb.position.set(x, y, z); S.bb.scale.setScalar(pop(t, t0, 0.22, 1.5) * (t < t0 ? 0 : 1)); };

// A1: the clock, then we pull back to the typing person (hook: the stake)
const A1 = night((t, T2, S) => { typingPose(S.me, t * 1.2, { head: [0.1, 0, 0] }); gfPose(S.gf, t);
  place(S.c, [kf(t, [[0, 0.7], [1.3, 1.6]], easeInOut), kf(t, [[0, 0.95], [1.3, 1.45]], easeInOut), kf(t, [[0, 1.75], [1.3, 3.4]], easeInOut)], [kf(t, [[0, 0.62], [1.3, 0.2]], easeInOut), kf(t, [[0, 0.9], [1.3, 1.3]], easeInOut), 0.9]);
  return { dof: { focus: 1.6, aperture: 0.005, maxblur: 0.012 }, bloom: 0.7, exposure: 0.95 }; }, { fov: 38 });
// A2: she is in the doorway, hands on hips: "Again?"
const A2 = night((t, T2, S) => { typingPose(S.me, t * 1.2 + 3, { head: [0.15, 0, 0] }); gfPose(S.gf, t); bub(S, 'Again?', t, 0.25, 0.95, 2.4, 0.5);
  place(S.c, [kf(t, [[0, 0.2], [1.5, 0.7]], easeInOut), 1.5, 3.6], [0.65, 1.3, 0.4]);
  return { dof: { focus: 3.6, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.0 }; });
// A3: he slumps, listing cards drift
const A3 = night((t, T2, S) => { typingPose(S.me, 1, { neck: [0.5, 0, 0], head: [0.2, 0, 0.12], blink: t > 0.8 }); gfPose(S.gf, t, { head: [0, 0.4, 0] });
  if (!S.cards) { const tx = listingTex(); S.cards = Array.from({ length: 8 }, () => { const m = planeCard(tx, 0.26, 0.325); S.scene.add(m); return m; }); }
  S.cards.forEach((m, i) => { const a = t * 1.5 + i * 0.8; m.position.set(Math.sin(a) * 0.9, 1.9 + (i % 3) * 0.25, 0.3 + Math.cos(a) * 0.5); m.scale.setScalar(pop(t, i * 0.1, 0.25, 1.3)); m.quaternion.copy(S.c.quaternion); });
  place(S.c, [kf(t, [[0, 0.6], [2.0, 0.2]], easeInOut), 1.5, kf(t, [[0, 3.6], [2.0, 2.8]], easeInOut)], [0, 1.4, 0.3]);
  return { dof: { focus: 2.9, aperture: 0.005, maxblur: 0.012 }, bloom: 0.5, exposure: 0.95 }; });
// A4/A5/A6: three platforms, same text, three times
const typeShot = (k, off) => night((t, T2, S) => { typingPose(S.me, t * 1.6 + off, { head: [0.1, Math.sin(t * 11) * 0.09, 0] }); gfPose(S.gf, t);
  if (!S.lg) { S.lg = planeCard(logoTex(k), 0.55, 0.34); S.scene.add(S.lg); S.tx = planeCard(bubbleTex('Nike Tech Fleece · M · €68'), 0.74, 0.23); S.scene.add(S.tx); }
  S.lg.position.set(-0.55, 2.2, 0.6); S.lg.scale.setScalar(pop(t, 0.05, 0.25, 1.7)); S.lg.rotation.z = -0.05;
  S.tx.position.set(0.45, 2.0, 0.6); S.tx.scale.setScalar(pop(t, 0.35, 0.25, 1.5) * (t < 0.35 ? 0 : 1));
  place(S.c, [kf(t, [[0, 0.5 - off * 0.2], [1.3, -0.1]], easeOut), 1.5, kf(t, [[0, 3.8], [1.3, 2.8]], easeOut)], [0, 1.55, 0.3]);
  return { dof: { focus: 2.8, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.0 }; });
// A7: she, close: "there has to be a better way"
const A7 = night((t, T2, S) => { typingPose(S.me, 1, { neck: [0.4, 0, 0] }); gfPose(S.gf, t, { mouth: 0.5 + 0.5 * Math.sin(t * 14) * 0.5, smile: 0 }); bub(S, 'There has to be a better way', t, 0.2, 0.95, 2.4, 0.5);
  place(S.c, [kf(t, [[0, 0.3], [1.4, 0.7]], easeInOut), 1.45, kf(t, [[0, 2.6], [1.4, 2.0]], easeOut)], [1.25, 1.4, 0.45]);
  return { dof: { focus: 1.5, aperture: 0.006, maxblur: 0.012 }, bloom: 0.5, exposure: 1.0 }; }, { fov: 36 });
// A8: lightbulb moment, the screen brightens
const A8 = night((t, T2, S) => { typingPose(S.me, t * 1.2, { head: [-0.05, 0, 0], smile: 1 }); gfPose(S.gf, t);
  if (!S.bulb) { S.bulb = new THREE.Mesh(new THREE.SphereGeometry(0.13, 20, 14), new THREE.MeshBasicMaterial({ color: 0xfff1a0, toneMapped: false })); S.scene.add(S.bulb); S.bl = new THREE.PointLight(0xfff1a0, 0, 4); S.scene.add(S.bl); }
  S.bulb.position.set(0, 2.45, 0.3); S.bulb.scale.setScalar(pop(t, 0.3, 0.25, 2)); S.bl.position.copy(S.bulb.position); S.bl.intensity = 3 * range(t, 0.3, 0.5);
  place(S.c, [kf(t, [[0, 0.3], [1.2, 0.0]], easeOut), 1.7, kf(t, [[0, 3.6], [1.2, 2.9]], easeOut)], [0, 1.7, 0.3]);
  return { dof: { focus: 2.9, aperture: 0.004, maxblur: 0.01 }, bloom: 0.8, exposure: 1.0 }; });
// dinner: warm, two people at a candlelit table
function dinner(update, { fov = 38 } = {}) {
  return ({ makeStage }) => {
    const scene = room(makeStage, { wall: 0xb5774a, floor: 0x8a6240, sky: [0xff9a4a, 0xffb36b, 0xffd9a0], key: 0.5, keyColor: 0xffc890, hemi: 0.55, hemiColor: 0xffd9b0, rim: 0.4 });
    scene.add(rbox(1.1, 0.05, 0.8, 0.02, std(0xf2e8d8, 0.7), [0, 0.76, 0]));
    for (const sx of [-0.45, 0.45]) for (const sz of [-0.32, 0.32]) scene.add(rbox(0.05, 0.74, 0.05, 0.01, std(0x4a3524), [sx, 0.37, sz]));
    const mk = (hx, hair, sk, px) => { const h = makeBlocky({ hoodie: hx, hair, skin: sk }); h.root.position.set(px, 0, 0); h.root.rotation.y = px < 0 ? Math.PI / 2 : -Math.PI / 2; scene.add(h.root); const d = px < 0 ? -1 : 1; scene.add(rbox(0.6, 0.08, 0.6, 0.03, std(0x5a3b25, 0.7), [px + d * 0.18, 0.5, 0])); scene.add(rbox(0.08, 0.6, 0.6, 0.03, std(0x5a3b25, 0.7), [px + d * 0.5, 0.86, 0])); return h; };
    const a = mk(0x3c4b73, 0x14141a, 0xc98a64, -0.78), b = mk(0xe58aa8, 0x5a3a2a, 0xe0a98a, 0.78);
    for (const sx of [-0.25, 0.25]) { const p = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.13, 0.02, 28), std(0xffffff, 0.4)); p.position.set(sx * 1.3, 0.8, 0); scene.add(p); }
    const candle = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.16, 12), std(0xfff4e0)); candle.position.set(0, 0.87, 0); scene.add(candle);
    const fl = new THREE.Mesh(new THREE.SphereGeometry(0.03, 10, 8), new THREE.MeshBasicMaterial({ color: 0xffd27a, toneMapped: false })); fl.position.set(0, 0.99, 0); fl.scale.y = 1.6; scene.add(fl);
    const cl = new THREE.PointLight(0xffb870, 2.2, 5, 1.5); cl.position.set(0, 1.1, 0); scene.add(cl);
    const c = cam(fov); const S = { scene, a, b, c, fl, cl };
    return { scene, camera: c, update: (t, T2) => { S.fl.scale.set(1, 1.6 + Math.sin(t * 17) * 0.15, 1); S.cl.intensity = 2.2 + Math.sin(t * 13) * 0.2; return update(t, T2, S); } };
  };
}
const seatedPose = (h, t, extra = {}) => h.pose({ drop: 0.28, torso: [0.05, 0, 0], head: [0, Math.sin(t * 2) * 0.12, 0], lHip: [-1.5, 0.05, 0], lKn: [1.5, 0, 0], rHip: [-1.5, -0.05, 0], rKn: [1.5, 0, 0], lSh: [-0.8, 0, 0.3], lEl: [-1.2, 0, 0], rSh: [-0.8, 0, -0.3], rEl: [-1.2, 0, 0], blink: ((t * 0.7) % 3) > 2.9, smile: 1, ...extra });
const D1 = dinner((t, T2, S) => { seatedPose(S.a, t); seatedPose(S.b, t + 1);
  place(S.c, [kf(t, [[0, -0.6], [1.6, 0.4]], easeInOut), 1.5, 3.8], [0, 1.0, 0]);
  return { dof: { focus: 3.8, aperture: 0.003, maxblur: 0.01 }, bloom: 0.7, exposure: 1.05 }; });
const D2 = dinner((t, T2, S) => { seatedPose(S.a, t * 1.5, { mouth: Math.max(0, Math.sin(t * 9)) * 0.4 }); seatedPose(S.b, t * 1.5 + 2);
  place(S.c, [kf(t, [[0, 0.2], [1.6, -0.1]], easeInOut), 1.4, kf(t, [[0, 2.4], [1.6, 1.9]], easeOut)], [0, 1.25, 0]);
  return { dof: { focus: 2.1, aperture: 0.006, maxblur: 0.012 }, bloom: 0.8, exposure: 1.05 }; }, { fov: 36 });

export const SHOTS = [
  [0.0, 1.3, A1], [1.3, 3.0, A2], [3.0, 5.3, A3],
  [5.3, 6.8, typeShot('vinted.png', 0)], [6.8, 8.3, typeShot('marktplaats.png', 4)], [8.3, 10.6, typeShot('ebay.webp', 8)],
  [10.6, 12.1, A7], [12.1, 13.3, A8],
  [13.3, 14.5, K], [14.5, 15.7, Mm], [15.7, 17.1, Nn], [17.1, 19.2, Ll],
  [19.2, 20.6, D1], [20.6, 21.7, D2],
].map(([start, end, b], i) => { const a = T(start), z = T(end); return { start: a, end: z, build: i % 3 === 2 ? b : wrap(b, z - a, i % 2 ? 1 : -1) }; }).concat([{ start: T(21.7), end: DURATION + 1, build: s8 }]);
