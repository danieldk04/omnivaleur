// Week 46 scenes: courtroom, cooking show, space. Built on the helpers exported by shots.js.
import * as THREE from 'three';
import { makeBlocky } from './blocky.js';
import { kf, lerp, easeOut, easeInOut, range, clamp, V, cam, place, shake } from './anim.js';
import { std, rbox, room, windowPane, desk, laptop, lamp, typingPose, seat, pop, planeCard, lights, logoTex, listingTex, checkTex, bubbleTex, canvasTex, rr, gradTex, walkPose, cheer, IMG, PLATFORMS, rnd, kitchen, ledTex } from './shots.js';

export const labelTex = (txt, { bg = '#fff', fg = '#1b2a44', w = 640, h = 200, size = 72, font = '800' } = {}) => canvasTex(w, h, (g, W, H) => {
  g.fillStyle = bg; rr(g, 0, 0, W, H, 36); g.fill(); g.fillStyle = fg; g.font = `${font} ${size}px Montserrat, sans-serif`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(txt, W / 2, H / 2 + 3);
});
export const stampTex = (txt, col = '#d62b2b') => canvasTex(640, 240, (g, W, H) => {
  g.strokeStyle = col; g.fillStyle = col; g.lineWidth = 16; rr(g, 12, 12, W - 24, H - 24, 24); g.stroke();
  g.font = `900 ${txt.length > 8 ? 70 : 120}px Montserrat, sans-serif`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(txt, W / 2, H / 2 + 6);
});
const kids = (o, f) => { o.children.forEach(c => f(c)); };

// ---------- courtroom ----------
export function courtroom(makeStage) {
  const scene = room(makeStage, { wall: 0x7a5538, floor: 0x9a7650, sky: [0x3a2a1a, 0x5a4028, 0x7a5538], key: 1.1, keyColor: 0xffe2b8, hemi: 0.75, hemiColor: 0xffe8c8, rim: 0.5 });
  scene.add(Object.assign(rbox(2.6, 0.32, 0.9, 0.04, std(0x5a3b25, 0.7), [0, 0.16, -1.15]), {}));                    // platform
  scene.add(rbox(2.3, 0.78, 0.12, 0.03, std(0x4a2f1c, 0.65), [0, 0.7, -0.74]));                                        // bench front
  scene.add(rbox(2.4, 0.06, 0.55, 0.02, std(0x3a2414, 0.6), [0, 1.1, -0.9]));                                          // bench top
  const seal = new THREE.Mesh(new THREE.CircleGeometry(0.33, 40), new THREE.MeshBasicMaterial({ color: 0xd8b04a, toneMapped: false })); seal.position.set(0, 2.85, -1.57); scene.add(seal);
  const bar = new THREE.Mesh(new THREE.PlaneGeometry(0.4, 0.05), new THREE.MeshBasicMaterial({ color: 0x5a3b25, toneMapped: false })); bar.position.set(0, 2.85, -1.56); 
  const scale = new THREE.Mesh(new THREE.PlaneGeometry(0.05, 0.42), new THREE.MeshBasicMaterial({ color: 0x5a3b25, toneMapped: false })); scale.position.set(0, 2.85, -1.56); 
  for (const sx of [-1, 1]) scene.add(rbox(0.18, 2.2, 0.18, 0.03, std(0x4a2f1c, 0.7), [sx * 1.5, 1.1, -1.45]));
  // judge on the platform
  const judge = makeBlocky({ hoodie: 0x15151c, hair: 0xf2f2f4 }); judge.root.position.set(0, 0.32, -1.3); scene.add(judge.root);
  const wig = new THREE.Mesh(new THREE.SphereGeometry(0.3, 28, 18), std(0xf4f4f6, 0.95)); wig.scale.set(1, 0.9, 1); wig.position.set(0, 0.03, -0.04); judge.head.add(wig);
  const gavel = new THREE.Group(); const gh = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.3, 12), std(0x5a3b25)); gavel.add(gh);
  const gb = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.2, 16), std(0x3a2414)); gb.rotation.z = Math.PI / 2; gb.position.y = 0.15; gavel.add(gb);
  judge.R.el.add(gavel); gavel.position.set(0, -0.36, 0.05); gavel.rotation.x = -1.2;
  const block = rbox(0.28, 0.06, 0.2, 0.02, std(0x3a2414), [0.55, 1.16, -0.82]); scene.add(block);
  // defendant at a small desk
  const dk = desk(scene); const lap = laptop(scene); const hd = makeBlocky({ hoodie: 0xb55a3a }); seat(hd); scene.add(hd.root);
  return { scene, judge, gavel, hd, lap, dk };
}
// strike: 0..1 phase of one gavel strike; returns pose for the judge's right arm
export function judgeStrike(judge, k, extra = {}) {
  const up = Math.sin(clamp(k) * Math.PI);            // 0 at rest, 1 at the top of the swing
  judge.pose({ drop: 0.0, torso: [0.05, 0, 0], head: [0, 0, 0], rSh: [-1.0 - up * 1.0, 0, -0.15], rEl: [-1.3 + up * 0.3, 0, 0], lSh: [-0.5, 0, 0.15], lEl: [-0.7, 0, 0], ...extra });
}

// ---------- cooking show ----------
export function cookingStage(makeStage) {
  const scene = kitchen(makeStage);
  scene.add(rbox(2.6, 0.9, 0.7, 0.03, std(0xe9e4da, 0.5), [0, 0.45, 0.3]));          // counter (solid)
  scene.add(rbox(2.7, 0.05, 0.78, 0.02, std(0x4a4540, 0.4), [0, 0.92, 0.3]));          // worktop
  for (const sx of [-1, 1]) scene.add(rbox(0.5, 1.6, 0.4, 0.03, std(0x8a7258, 0.8), [sx * 1.55, 0.8, -1.3]));
  const host = makeBlocky({ hoodie: 0xf2f2f0, pants: 0x2a2a33 }); host.root.position.set(0, 0, -0.35); scene.add(host.root);
  const hat = new THREE.Group(); const base = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.16, 28), std(0xffffff, 0.8)); const puff = new THREE.Mesh(new THREE.SphereGeometry(0.27, 28, 18), std(0xffffff, 0.8)); puff.position.y = 0.2; puff.scale.set(1, 0.85, 1); hat.add(base, puff); hat.position.set(0, 0.22, -0.02); host.head.add(hat);
  return { scene, host };
}
export const plate = (col = 0xffffff) => { const g = new THREE.Group(); const p = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.17, 0.03, 32), std(col, 0.4)); p.castShadow = true; g.add(p); return g; };
export const pan = () => { const g = new THREE.Group(); const p = new THREE.Mesh(new THREE.CylinderGeometry(0.19, 0.16, 0.06, 32), std(0x22242a, 0.5, { metalness: 0.4 })); p.castShadow = true; g.add(p); const h = rbox(0.28, 0.025, 0.05, 0.01, std(0x22242a), [0.32, 0.01, 0]); g.add(h); return g; };
export const steam = (n = 6) => { const g = new THREE.Group(); const ms = []; for (let i = 0; i < n; i++) { const m = new THREE.Mesh(new THREE.SphereGeometry(0.05, 10, 8), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.35, toneMapped: false })); g.add(m); ms.push(m); } g.userData.tick = (t) => ms.forEach((m, i) => { const p = ((t * 0.7 + i / n) % 1); m.position.set(Math.sin(i * 2 + t) * 0.05, p * 0.5, 0); m.scale.setScalar(0.6 + p); m.material.opacity = 0.35 * (1 - p); }); return g; };

// ---------- space ----------
export function spaceScene() {
  const scene = new THREE.Scene(); scene.userData.sky = new THREE.Object3D(); scene.background = new THREE.Color(0x03040c);
  const pts = []; for (let i = 0; i < 700; i++) { const a = rnd(i) * 6.283, b = (rnd(i + 900) - 0.5) * 3.0, r = 30; pts.push(Math.cos(a) * r * Math.cos(b), Math.sin(b) * r, Math.sin(a) * r * Math.cos(b)); }
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  scene.add(new THREE.Points(sg, new THREE.PointsMaterial({ color: 0xffffff, size: 0.09, sizeAttenuation: true })));
  const key = new THREE.DirectionalLight(0xfff0dd, 2.6); key.position.set(-4, 3, 5); scene.add(key); scene.userData.key = key;
  scene.add(new THREE.AmbientLight(0x6070a0, 0.8));
  const tex = canvasTex(512, 256, (g, w, h) => { g.fillStyle = '#1b5fa8'; g.fillRect(0, 0, w, h); g.fillStyle = '#3f9e5a'; for (let i = 0; i < 18; i++) { g.beginPath(); g.ellipse((i * 97) % w, 40 + (i * 53) % 180, 30 + (i * 13) % 40, 14 + (i * 7) % 22, i, 0, 7); g.fill(); } g.fillStyle = 'rgba(255,255,255,.5)'; for (let i = 0; i < 14; i++) { g.beginPath(); g.ellipse((i * 71) % w, (i * 37) % h, 40, 8, 0, 0, 7); g.fill(); } });
  const earth = new THREE.Mesh(new THREE.SphereGeometry(2.4, 48, 32), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.9 })); earth.position.set(0, -3.1, -4); scene.add(earth);
  const atm = new THREE.Mesh(new THREE.SphereGeometry(2.5, 48, 32), new THREE.MeshBasicMaterial({ color: 0x6fb6ff, transparent: true, opacity: 0.16, side: THREE.BackSide, toneMapped: false })); atm.position.copy(earth.position); atm.scale.setScalar(1.06); scene.add(atm);
  return { scene, earth };
}
export function astronaut() {
  const h = makeBlocky({ hoodie: 0xf0f2f6, pants: 0xe4e7ee, hair: 0xe4e7ee, shoes: 0xb8bfcc });
  const helmet = new THREE.Mesh(new THREE.SphereGeometry(0.36, 32, 20), new THREE.MeshStandardMaterial({ color: 0xaecbff, transparent: true, opacity: 0.22, roughness: 0.05, metalness: 0.2 })); helmet.position.y = 0.0; h.head.add(helmet);
  const pack = rbox(0.42, 0.5, 0.2, 0.06, std(0xcfd4de, 0.6), [0, 0.35, -0.27]); h.torso.add(pack);
  return h;
}
export const satellite = (logoKey) => { const g = new THREE.Group(); g.add(rbox(0.2, 0.2, 0.2, 0.03, std(0xc9ced9, 0.4, { metalness: 0.5 }))); for (const sx of [-1, 1]) g.add(rbox(0.3, 0.012, 0.17, 0.004, std(0x2a4fa0, 0.3), [sx * 0.27, 0, 0])); const l = planeCard(logoTex(logoKey), 0.42, 0.26); l.position.set(0, 0.3, 0); g.add(l); g.userData.logo = l; return g; };

// ---------- week 46 b: shared builders for the three example concepts ----------
export const bigTex = (txt, { fg = '#fff', bg = null, size = 150, w = 900, h = 360, stroke = '#0b1530', sw = 22 } = {}) => canvasTex(w, h, (g, W, H) => {
  if (bg) { g.fillStyle = bg; rr(g, 0, 0, W, H, 60); g.fill(); }
  g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineJoin = 'round'; let sz = size; g.font = `900 ${sz}px Montserrat, sans-serif`; while (g.measureText(txt).width > W - 70 && sz > 30) { sz -= 4; g.font = `900 ${sz}px Montserrat, sans-serif`; }
  g.strokeStyle = stroke; g.lineWidth = sw; g.strokeText(txt, W / 2, H / 2 + 6); g.fillStyle = fg; g.fillText(txt, W / 2, H / 2 + 6);
});
export function hoodieChar() {
  const g = new THREE.Group(), col = std(0x2f6f7a, 0.8), dark = std(0x24565f, 0.85);
  const solidOff = m => { m.userData.solid = false; return m; };
  const body = solidOff(rbox(0.62, 0.72, 0.34, 0.12, col, [0, 0, 0])); g.add(body);
  const hood = new THREE.Mesh(new THREE.SphereGeometry(0.22, 24, 16), dark); hood.scale.set(1.25, 0.8, 0.7); hood.position.set(0, 0.4, -0.08); hood.castShadow = true; g.add(hood);
  const pocket = solidOff(rbox(0.38, 0.16, 0.03, 0.02, dark, [0, -0.2, 0.18])); g.add(pocket);
  const slv = [-1, 1].map(s => { const m = solidOff(rbox(0.2, 0.52, 0.2, 0.08, col, [s * 0.4, -0.02, 0])); m.rotation.z = -s * 0.18; g.add(m); return m; });
  const eyes = [-1, 1].map(s => { const w = new THREE.Mesh(new THREE.SphereGeometry(0.075, 18, 14), std(0xffffff, 0.3)); w.position.set(s * 0.12, 0.17, 0.17); w.scale.z = 0.6; g.add(w); const p = new THREE.Mesh(new THREE.SphereGeometry(0.036, 14, 10), std(0x0b0b10, 0.2)); p.position.set(0, 0, 0.05); w.add(p); return { w, p }; });
  const mouth = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.02, 0.01), new THREE.MeshStandardMaterial({ color: 0x3a1a14 })); mouth.position.set(0, 0.03, 0.18); g.add(mouth);
  for (const s of [-1, 1]) { const c = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.14, 8), std(0xe9eef5)); c.position.set(s * 0.07, -0.02, 0.18); g.add(c); }
  return { g, body, slv, eyes, mouth };
}
// the 'sold once, gone everywhere' beat: four logo cards, the first gets a SOLD stamp, the rest pop away one by one
export const soldPoof = (a0 = 0.2) => ({ makeStage }) => {
  const scene = new THREE.Scene(); scene.userData.sky = new THREE.Object3D();
  const bg = new THREE.Mesh(new THREE.PlaneGeometry(8, 12), new THREE.MeshBasicMaterial({ map: gradTex('#14233f', '#0c6a73'), toneMapped: false })); bg.position.z = -0.5; scene.add(bg);
  const ks = ['vinted.png', 'marktplaats.png', 'ebay.webp', 'shopify.webp'], cs = ks.map((k, i) => { const m = planeCard(logoTex(k), 0.62, 0.39); m.position.set(0, 0.62 - i * 0.5, 0); scene.add(m); return m; });
  const st = planeCard(stampTex('SOLD', '#19b36b'), 0.5, 0.19); st.position.set(0.1, 0.44, 0.05); st.rotation.z = -0.1; scene.add(st);
  const gone = ks.map(() => { const m = new THREE.Mesh(new THREE.RingGeometry(0.05, 0.06, 32), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, toneMapped: false })); scene.add(m); return m; });
  const c = cam(40);
  return { scene, camera: c, update(t) {
    cs.forEach((m, i) => { const tg = a0 + 0.55 + (i - 1) * 0.28, k = i ? clamp((t - tg) / 0.25) : 0; m.scale.setScalar(pop(t, i * 0.06, 0.2, 1.4) * (1 - easeOut(k)) + 0.0001); m.rotation.z = i ? k * 0.8 : 0; gone[i].visible = i > 0 && k > 0 && k < 1; gone[i].position.copy(m.position); gone[i].scale.setScalar(0.5 + k * 5); gone[i].material.opacity = 1 - k; });
    st.scale.setScalar(pop(t, a0, 0.2, 2.2) * (t < a0 ? 0 : 1));
    place(c, [0, 0.0, kf(t, [[0, 3.0], [1.6, 2.5]], easeInOut)], [0, 0.0, 0], Math.sin(t * 5) * 0.015);
    return { bloom: 0.3 };
  } };
};
// flat kinetic text card: lines = [[text, t0, colour, size]]; optional logo row
export const kinetic = (lines, { bg = ['#14233f', '#0f6f78'], logos = [], shake = 0 } = {}) => ({ makeStage }) => {
  const scene = new THREE.Scene(); scene.userData.sky = new THREE.Object3D();
  const b = new THREE.Mesh(new THREE.PlaneGeometry(8, 12), new THREE.MeshBasicMaterial({ map: gradTex(bg[0], bg[1]), toneMapped: false })); b.position.z = -0.5; scene.add(b);
  const ms = lines.map(([txt, t0, col, size], i) => { const m = planeCard(bigTex(txt, { fg: col || '#fff', size: (size || 150) * 1.9 }), 1.0, 0.4); m.position.set(0, 0.3 - i * 0.42, 0); scene.add(m); return m; });
  const ls = logos.map((k, i) => { const m = planeCard(logoTex(k), 0.42, 0.26); m.position.set((i - (logos.length - 1) / 2) * 0.46, -0.62, 0.02); scene.add(m); return m; });
  const c = cam(40);
  return { scene, camera: c, update(t) {
    ms.forEach((m, i) => { const t0 = lines[i][1]; m.scale.setScalar(pop(t, t0, 0.22, 1.9) * (t < t0 ? 0 : 1)); m.rotation.z = (i % 2 ? 1 : -1) * 0.03; });
    ls.forEach((m, i) => { const t0 = 0.3 + i * 0.12; m.scale.setScalar(pop(t, t0, 0.2, 1.5) * (t < t0 ? 0 : 1)); });
    place(c, [Math.sin(t * 20) * shake, Math.cos(t * 17) * shake, kf(t, [[0, 2.7], [1.5, 2.45]], easeOut)], [0, 0, 0]);
    return { bloom: 0.35 };
  } };
};
