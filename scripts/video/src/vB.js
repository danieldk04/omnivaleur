// Voorbeeld B: demo eerst, geen poppetje. Resultaat in de eerste seconde, het echte dashboard, één functie, duidelijke belofte en een gratis proef.
import * as THREE from 'three';
import { kf, lerp, easeOut, easeInOut, range, clamp, cam, place } from './anim.js';
import { pop, planeCard, wrap, logoTex, listingTex, gradTex, K, Ll, Mm, Nn, Oo, s8 } from './shots.js';
import { labelTex, kinetic, soldPoof } from './week46.js';
export { CAPTIONS, DURATION } from './cap.js';
import { DURATION, LINES } from './cap.js';
export const FADES = [];
const OLD_STARTS = [0, 2.732, 5.976, 10.799, 14.576], OLD_END = 17.93;
const T = x => { const o = [...OLD_STARTS, OLD_END], n = [...LINES.map(l => l[0]), LINES[LINES.length - 1][1]]; for (let i = 0; i < o.length - 1; i++) if (x < o[i + 1] || i === o.length - 2) return n[i] + (x - o[i]) * (n[i + 1] - n[i]) / (o[i + 1] - o[i]); return x; };
const addItem = ({ makeStage }) => { // one listing card, three chips fly in
  const scene = new THREE.Scene(); scene.userData.sky = new THREE.Object3D();
  const bg = new THREE.Mesh(new THREE.PlaneGeometry(8, 12), new THREE.MeshBasicMaterial({ map: gradTex('#14233f', '#0f6f78'), toneMapped: false })); bg.position.z = -0.5; scene.add(bg);
  const card = planeCard(listingTex(), 0.62, 0.78); scene.add(card);
  const chips = ['Photos', 'Price', 'Details'].map(s => { const m = planeCard(labelTex(s, { size: 84, bg: '#57e0d6', fg: '#0b1530' }), 0.46, 0.145); scene.add(m); return m; });
  const c = cam(40);
  return { scene, camera: c, update(t) {
    card.scale.setScalar(pop(t, 0, 0.25, 1.4)); card.position.set(0, -0.05, 0.02);
    chips.forEach((m, i) => { const t0 = 0.3 + i * 0.35, k = easeOut(range(t, t0, t0 + 0.3)); m.position.set(lerp(i % 2 ? 1.2 : -1.2, i % 2 ? 0.5 : -0.5, k), 0.45 - i * 0.28, 0.1); m.scale.setScalar(pop(t, t0, 0.25, 1.5) * (t < t0 ? 0 : 1)); m.rotation.z = (i % 2 ? -1 : 1) * 0.06; });
    place(c, [0, 0, kf(t, [[0, 3.0], [1.5, 2.4]], easeOut)], [0, 0, 0], Math.sin(t * 4) * 0.012);
    return { bloom: 0.3 };
  } };
};
export const SHOTS = [
  [0.0, 0.8, kinetic([['1 LISTING', 0.0, '#fff', 150]])],
  [0.8, 1.6, kinetic([['4 PLATFORMS', 0.0, '#57e0d6', 120]], { logos: ['vinted.png', 'marktplaats.png', 'ebay.webp', 'shopify.webp'] })],
  [1.6, 2.7, Mm],
  [2.7, 4.2, addItem], [4.2, 6.0, K],
  [6.0, 7.5, Mm], [7.5, 9.2, Nn], [9.2, 10.8, Ll],
  [10.8, 12.6, soldPoof(0.2)],
  [12.6, 14.6, kinetic([['SOLD ONCE', 0.1, '#7dffc4', 130], ['GONE ELSEWHERE', 0.55, '#fff', 100]], { shake: 0.004 })],
  [14.6, 16.0, Oo],
  [16.0, 17.9, kinetic([['7 DAYS FREE', 0.1, '#57e0d6', 130], ['omnivaleur.com', 0.6, '#fff', 90]], { logos: ['vinted.png', 'marktplaats.png', 'ebay.webp', 'shopify.webp', '2dehands.png'] })],
].map(([start, end, b], i) => { const a = T(start), z = T(end); return { start: a, end: z, build: i % 3 === 2 ? b : wrap(b, z - a, i % 2 ? 1 : -1) }; }).concat([{ start: T(17.93), end: DURATION + 1, build: s8 }]);
