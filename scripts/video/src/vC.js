// Voorbeeld C: komedie. Een hoodie met een gezicht is het hoofdpersonage en de pijn is dubbel verkocht (echt, en iedereen herkent het).
import * as THREE from 'three';
import { makeBlocky } from './blocky.js';
import { kf, lerp, easeOut, easeInOut, range, clamp, cam, place } from './anim.js';
import { std, rbox, room, windowPane, desk, laptop, lamp, typingPose, seat, pop, planeCard, wrap, logoTex, listingTex, bubbleTex, K, Ll, Mm, Nn, s8 } from './shots.js';
import { hoodieChar, soldPoof, stampTex, labelTex } from './week46.js';
export { CAPTIONS, DURATION } from './cap.js';
import { DURATION, LINES } from './cap.js';
export const FADES = [];
const OLD_STARTS = [0, 2.903, 5.955, 8.239, 11.376, 14.62], OLD_END = 15.69;
const T = x => { const o = [...OLD_STARTS, OLD_END], n = [...LINES.map(l => l[0]), LINES[LINES.length - 1][1]]; for (let i = 0; i < o.length - 1; i++) if (x < o[i + 1] || i === o.length - 2) return n[i] + (x - o[i]) * (n[i + 1] - n[i]) / (o[i + 1] - o[i]); return x; };

function studio(update, { fov = 40, calm = false } = {}) {
  return ({ makeStage }) => {
    const scene = room(makeStage, { wall: calm ? 0x3a6f6a : 0x4a3f8a, floor: calm ? 0x6a9a8a : 0x6a5fb0, sky: [0x2a2060, 0x3a3080, 0x5a4fb0], key: 1.0, keyColor: 0xfff0e0, hemi: 0.8, hemiColor: 0xe8e0ff, rim: 0.6 });
    scene.add(rbox(1.7, 0.06, 0.8, 0.02, std(0xe9e1d3, 0.6), [0, 0.76, 0]));
    for (const sx of [-0.78, 0.78]) for (const sz of [-0.3, 0.3]) scene.add(rbox(0.06, 0.74, 0.06, 0.01, std(0x6a5a48), [sx, 0.37, sz]));
    const H = hoodieChar(); H.g.position.set(0, 1.18, 0); scene.add(H.g);
    const pk = makeBlocky({ hoodie: 0xe58aa8, hair: 0x5a3a2a, skin: 0xe0a98a }); pk.root.position.set(-1.15, 0, 0); pk.root.rotation.y = Math.PI / 2; scene.add(pk.root);
    const og = makeBlocky({ hoodie: 0xe8872a, hair: 0x14141a }); og.root.position.set(1.15, 0, 0); og.root.rotation.y = -Math.PI / 2; scene.add(og.root);
    const c = cam(fov); const S = { scene, H, pk, og, c };
    return { scene, camera: c, update: (t, T2) => update(t, T2, S) };
  };
}
const face = (S, t, { mouthOpen = 0, panic = 0, look = 0, calm = false } = {}) => {
  S.H.mouth.scale.set(1 + mouthOpen * 0.5, 1 + mouthOpen * 12, 1); S.H.mouth.position.y = 0.03 - mouthOpen * 0.02;
  S.H.eyes.forEach(e => { e.p.position.x = look * 0.03; e.p.position.y = Math.sin(t * 20) * 0.02 * panic; e.w.scale.y = calm ? 0.12 : 1; });
  S.H.g.rotation.z = Math.sin(t * 24) * 0.05 * panic; S.H.g.position.y = 1.18 + Math.abs(Math.sin(t * 18)) * 0.03 * panic;
};
const buyer = (h, t, { pull = 0, side = 1, smile = 0 } = {}) => h.pose({ torso: [0.15 * pull, 0, 0], head: [0, 0, 0], lSh: [-1.5, 0, 0.12], lEl: [-0.1 - pull * 0.1, 0, 0], rSh: [-1.5, 0, -0.12], rEl: [-0.1 - pull * 0.1, 0, 0], lHip: [0.1 * pull, 0, 0], rHip: [0.1 * pull, 0, 0], blink: ((t * 0.7) % 3) > 2.9, smile });

const C1 = studio((t, T2, S) => { face(S, t, { mouthOpen: Math.max(0, Math.sin(t * 17)) * 0.6, panic: 0.2 }); buyer(S.pk, t); buyer(S.og, t);
  place(S.c, [kf(t, [[0, 0.3], [1.3, 0.0]], easeOut), 1.25, kf(t, [[0, 2.0], [1.3, 1.5]], easeOut)], [0, 1.2, 0]);
  return { dof: { focus: 1.6, aperture: 0.006, maxblur: 0.012 }, bloom: 0.5, exposure: 1.05 }; }, { fov: 36 });
const C2 = studio((t, T2, S) => { face(S, t, { mouthOpen: Math.max(0, Math.sin(t * 15)) * 0.5, panic: 1, look: Math.sin(t * 8) });
  buyer(S.pk, t); buyer(S.og, t);
  if (!S.st) { S.st = [['vinted.png', -0.85], ['marktplaats.png', 0.85]].map(([k, x]) => { const a = planeCard(stampTex('SOLD', '#19b36b'), 0.62, 0.23), l = planeCard(logoTex(k), 0.46, 0.29); S.scene.add(a, l); return { a, l, x }; }); }
  S.st.forEach((o, i) => { const t0 = 0.15 + i * 0.5; o.a.position.set(o.x, 1.45, 0.4); o.a.scale.setScalar(pop(t, t0, 0.2, 2.2) * (t < t0 ? 0 : 1)); o.a.rotation.z = -o.x * 0.12; o.l.position.set(o.x, 1.8, 0.4); o.l.scale.setScalar(pop(t, t0 - 0.1, 0.25, 1.4) * (t < t0 - 0.1 ? 0 : 1)); });
  place(S.c, [0, 1.5, kf(t, [[0, 4.0], [1.5, 3.4]], easeOut)], [0, 1.3, 0]);
  return { dof: { focus: 3.4, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 }; }, { fov: 50 });
const claim = (who, line, mirror) => studio((t, T2, S) => { face(S, t, { panic: 0.5, look: mirror ? 1 : -1 }); const p = who === 'pk' ? S.pk : S.og; buyer(S.pk, t, { smile: who === 'pk' ? 1 : 0 }); buyer(S.og, t, { smile: who === 'og' ? 1 : 0 });
  p.pose({ lSh: [-1.5, 0, 0.12], rSh: [-1.5, 0, -0.12], lEl: [-0.1, 0, 0], rEl: [-0.1, 0, 0], head: [0, 0, 0.05 * Math.sin(t * 6)], smile: 1, blink: false });
  if (!S.l) { S.l = planeCard(logoTex(line), 0.5, 0.31); S.scene.add(S.l); S.bb = planeCard(bubbleTex(who === 'pk' ? 'Mine!' : 'Mine!'), 0.5, 0.155); S.scene.add(S.bb); }
  const x = who === 'pk' ? -1.15 : 1.15; S.l.position.set(x, 2.25, 0.1); S.l.scale.setScalar(pop(t, 0.1, 0.25, 1.5)); S.bb.position.set(x * 0.5, 2.0, 0.3); S.bb.scale.setScalar(pop(t, 0.5, 0.2, 1.8) * (t < 0.5 ? 0 : 1));
  place(S.c, [x * 0.8 + kf(t, [[0, mirror ? -0.1 : 0.1], [1.5, mirror ? 0.1 : -0.1]], easeInOut), 1.5, 3.2], [x * 0.8, 1.3, 0]);
  return { dof: { focus: 3.0, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 }; }, { fov: 50 });
const C5 = studio((t, T2, S) => { const sw = Math.sin(t * 13); face(S, t, { mouthOpen: 0.6, panic: 1.5, look: sw });
  buyer(S.pk, t, { pull: 1 }); buyer(S.og, t, { pull: 1 }); S.pk.root.position.x = -1.15 - 0.1 * (1 + sw) * 0.5; S.og.root.position.x = 1.15 + 0.1 * (1 - sw) * 0.5;
  S.H.slv.forEach((m, i) => { m.scale.y = 1 + 0.25 * (i ? (1 - sw) / 2 : (1 + sw) / 2); });
  place(S.c, [Math.sin(t * 2) * 0.3, 1.6, kf(t, [[0, 4.6], [2, 3.8]], easeOut)], [0, 1.3, 0], Math.sin(t * 7) * 0.02);
  return { dof: { focus: 4.0, aperture: 0.003, maxblur: 0.01 }, bloom: 0.55, exposure: 1.05 }; }, { fov: 55 });
const hand = ({ makeStage }) => { // the person who listed it by hand: frantic typing, cards swirl
  const scene = room(makeStage, { key: 0.35, hemi: 0.25 }); windowPane(scene, { x: -0.9 }); desk(scene); laptop(scene, { glow: 0.9 }); lamp(scene, { intensity: 1.1 });
  const me = makeBlocky(); seat(me); scene.add(me.root); const tx = listingTex(), cards = Array.from({ length: 22 }, () => { const m = planeCard(tx, 0.28, 0.35); scene.add(m); return m; }); const c = cam(44);
  return { scene, camera: c, update(t) {
    typingPose(me, t * 1.8 + 5, { head: [0.1, Math.sin(t * 11) * 0.1, 0] });
    cards.forEach((m, i) => { const r = 0.9 + (i % 3) * 0.25, a = t * 2.4 + i * 0.52, k = pop(t, i * 0.03, 0.2); m.position.set(Math.sin(a) * r, 0.9 + (i / 22) * 1.3, 0.3 + Math.cos(a) * r); m.scale.setScalar(k); m.quaternion.copy(c.quaternion); });
    const a = lerp(0.3, -0.6, easeInOut(t / 1.7)); place(c, [Math.sin(a) * 3.0, 1.9, 0.3 + Math.cos(a) * 3.0], [0, 1.3, 0.3]);
    return { dof: { focus: 3.0, aperture: 0.005, maxblur: 0.012 }, bloom: 0.5, exposure: 1.0 };
  } };
};
const C7 = studio((t, T2, S) => { face(S, t, { mouthOpen: 0.7, panic: 2, look: Math.sin(t * 10) }); buyer(S.pk, t, { pull: 1 }); buyer(S.og, t, { pull: 1 });
  place(S.c, [0.1, 1.3, kf(t, [[0, 2.8], [1.4, 1.6]], easeIn)], [0, 1.2, 0]);
  return { dof: { focus: 1.9, aperture: 0.007, maxblur: 0.013 }, bloom: 0.5, exposure: 1.0 }; }, { fov: 38 });
function easeIn(x) { return Math.pow(clamp(x), 3); }
const C10 = studio((t, T2, S) => { face(S, t, { calm: true, mouthOpen: 0 }); S.H.g.position.y = 1.18 + Math.sin(t * 2) * 0.02; S.pk.root.visible = false; S.og.root.visible = false;
  if (!S.sp) { S.sp = Array.from({ length: 10 }, () => { const m = new THREE.Mesh(new THREE.SphereGeometry(0.025, 8, 6), new THREE.MeshBasicMaterial({ color: 0xfff2b0, toneMapped: false })); S.scene.add(m); return m; }); }
  S.sp.forEach((m, i) => { const a = i * 0.9 + t * 0.8; m.position.set(Math.sin(a) * (0.5 + 0.05 * i), 1.1 + ((t * 0.3 + i * 0.13) % 1) * 0.9, 0.3 + Math.cos(a) * 0.2); m.scale.setScalar(0.6 + 0.4 * Math.sin(t * 5 + i)); });
  place(S.c, [kf(t, [[0, 0.5], [1.4, 0]], easeInOut), 1.3, kf(t, [[0, 2.8], [1.4, 2.2]], easeOut)], [0, 1.2, 0]);
  return { dof: { focus: 2.4, aperture: 0.005, maxblur: 0.012 }, bloom: 0.9, exposure: 1.1 }; }, { fov: 38, calm: true });

export const SHOTS = [
  [0.0, 1.4, C1], [1.4, 2.9, C2], [2.9, 4.3, claim('pk', 'vinted.png', false)], [4.3, 5.95, claim('og', 'marktplaats.png', true)],
  [5.95, 7.95, C5], [7.95, 9.8, hand], [9.8, 11.4, C7],
  [11.4, 12.4, Mm], [12.4, 14.3, soldPoof(0.2)],
  [14.3, 15.7, C10],
].map(([start, end, b], i) => { const a = T(start), z = T(end); return { start: a, end: z, build: i % 3 === 2 ? b : wrap(b, z - a, i % 2 ? 1 : -1) }; }).concat([{ start: T(15.7), end: DURATION + 1, build: s8 }]);
