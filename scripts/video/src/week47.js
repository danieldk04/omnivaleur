// Week 47: tekstgedreven video's met echt dashboard; tijden volgen de voice-over (LINES uit cap.js)
import * as THREE from 'three';
import { kf, lerp, easeOut, easeInOut, range, clamp, cam, place } from './anim.js';
import { pop, planeCard, wrap, listingTex, gradTex, K, Ll, Mm, Nn, Oo, s8 } from './shots.js';
import { labelTex, kinetic, soldPoof } from './week46.js';
export { kinetic, soldPoof, K, Ll, Mm, Nn, Oo };
export const PL = ['vinted.png', 'marktplaats.png', 'ebay.webp', 'shopify.webp'];
export const PL5 = [...PL, '2dehands.png'];
export const addItem = ({ makeStage }) => {
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
// spec: [[pos, builder], ...]; pos = regelnummer plus fractie. Laatste kinetic eindigt waar de stem eindigt, dan de eindkaart.
export function montage(spec, LINES, DURATION, endBuild) {
  const at = p => { const i = Math.min(Math.floor(p), LINES.length - 1), f = p - i; return LINES[i][0] + f * (LINES[i][1] - LINES[i][0]); };
  const times = spec.map(([p], k) => k === 0 ? 0 : at(p)), endV = LINES[LINES.length - 1][1];
  const shots = spec.map(([, b], i) => { const a = times[i], z = i + 1 < spec.length ? times[i + 1] : endV; return { start: a, end: z, build: i % 3 === 2 ? b : wrap(b, z - a, i % 2 ? 1 : -1) }; });
  return shots.concat([{ start: endV, end: DURATION + 1, build: endBuild || s8 }]);
}
