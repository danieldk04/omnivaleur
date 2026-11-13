import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { makeBlocky } from './blocky.js';
import { kf, lerp, smooth, easeOut, easeInOut, range, clamp, V, cam, place, shake } from './anim.js';

export const DURATION = 18.0;
// [start, text, end?]  (retimed from the voiceover by captions.py)
export const CAPTIONS = [
  [0.00, 'you sell on Vinted'],
  [1.44, 'then Marktplaats'],
  [2.40, 'then eBay'],
  [3.28, 'then Shopify'],
  [4.48, 'same photos'],
  [5.44, 'same text'],
  [6.40, 'typed again and again'],
  [7.76, "it's midnight"],
  [8.48, "and you're still"],
  [9.04, 'listing'],
  [9.80, 'omnivaleur fixes that'],
  [11.20, 'one listing'],
  [12.00, 'every platform'],
  [12.88, 'one click'],
  [13.68, 'your evening is yours'],
  [14.96, 'again', 15.82],
];
export const FADES = [];

const TEAL = 0x1aa6a0, NAVY = 0x14233f;

// ---------- assets (preloaded, so renders never see a half-loaded texture) ----------
const loadImg = src => new Promise(res => { const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = src; });
const IMG = {};
for (const k of ['vinted.png', 'marktplaats.png', 'ebay.webp', 'shopify.webp', '2dehands.png', 'dashboard-overview.webp', 'items-crosslisted.webp', 'analytics-revenue.webp', 'dash.jpg', 'items.jpg', 'analytics.jpg']) IMG[k] = await loadImg('./assets/' + k);
const PLATFORMS = ['vinted.png', 'marktplaats.png', 'ebay.webp', 'shopify.webp', '2dehands.png'];

function canvasTex(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
}
function rr(g, x, y, w, h, r) { g.beginPath(); g.roundRect(x, y, w, h, r); }
const logoTex = k => canvasTex(512, 320, (g, w, h) => {
  g.fillStyle = '#fff'; rr(g, 0, 0, w, h, 44); g.fill();
  const im = IMG[k]; if (im) { const s = Math.min(380 / im.width, 190 / im.height); g.drawImage(im, (w - im.width * s) / 2, (h - im.height * s) / 2, im.width * s, im.height * s); }
});
const listingTex = () => canvasTex(512, 640, (g, w, h) => {
  g.fillStyle = '#fff'; rr(g, 0, 0, w, h, 40); g.fill();
  const gr = g.createLinearGradient(0, 30, 0, 400); gr.addColorStop(0, '#5b7fb5'); gr.addColorStop(1, '#2d4670');
  g.fillStyle = gr; rr(g, 28, 28, w - 56, 380, 26); g.fill();
  // little hoodie icon
  g.fillStyle = '#f2f4f8'; g.beginPath(); g.moveTo(170, 120); g.lineTo(210, 100); g.lineTo(302, 100); g.lineTo(342, 120); g.lineTo(420, 190); g.lineTo(380, 250); g.lineTo(344, 226); g.lineTo(344, 360); g.lineTo(168, 360); g.lineTo(168, 226); g.lineTo(132, 250); g.lineTo(92, 190); g.closePath(); g.fill();
  g.fillStyle = '#1b2a44'; g.font = '700 44px Montserrat, sans-serif'; g.fillText('Nike Tech Fleece', 34, 470);
  g.fillStyle = '#6b778c'; g.font = '500 34px Montserrat, sans-serif'; g.fillText('Maat M · Zo goed als nieuw', 34, 520);
  g.fillStyle = '#1aa6a0'; g.font = '800 54px Montserrat, sans-serif'; g.fillText('€68', 34, 600);
});
const checkTex = () => canvasTex(128, 128, (g) => {
  g.fillStyle = '#19b36b'; g.beginPath(); g.arc(64, 64, 60, 0, 7); g.fill();
  g.strokeStyle = '#fff'; g.lineWidth = 14; g.lineCap = 'round'; g.lineJoin = 'round'; g.beginPath(); g.moveTo(36, 66); g.lineTo(58, 88); g.lineTo(94, 44); g.stroke();
});
const cursorTex = () => canvasTex(128, 128, (g) => {
  g.fillStyle = '#fff'; g.strokeStyle = '#111'; g.lineWidth = 6; g.beginPath(); g.moveTo(24, 12); g.lineTo(24, 100); g.lineTo(46, 80); g.lineTo(62, 114); g.lineTo(78, 106); g.lineTo(62, 74); g.lineTo(92, 72); g.closePath(); g.fill(); g.stroke();
});
const ledTex = txt => canvasTex(256, 128, (g, w, h) => {
  g.fillStyle = '#1a0606'; g.fillRect(0, 0, w, h);
  g.fillStyle = '#ff3b2f'; g.shadowColor = '#ff3b2f'; g.shadowBlur = 18; g.font = '700 92px Menlo, monospace'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(txt, w / 2, h / 2 + 4);
});
const endTex = () => canvasTex(720, 1280, (g, w, h) => {
  const gr = g.createLinearGradient(0, 0, w, h); gr.addColorStop(0, '#14233f'); gr.addColorStop(1, '#0f6f78'); g.fillStyle = gr; g.fillRect(0, 0, w, h);
  g.textAlign = 'center'; g.fillStyle = '#fff'; g.font = '800 92px Montserrat, sans-serif'; g.fillText('Omnivaleur', w / 2, 560);
  g.fillStyle = '#57e0d6'; g.font = 'italic 400 54px Georgia, serif'; g.fillText('list once. sell everywhere.', w / 2, 650);
  g.fillStyle = 'rgba(255,255,255,.85)'; g.font = '600 40px Montserrat, sans-serif'; g.fillText('omnivaleur.com', w / 2, 1010);
});

// ---------- scene helpers ----------
const std = (c, r = 0.8, extra = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: r, ...extra });
const rbox = (w, h, d, r, mat, pos) => { const m = new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 3, r), mat); m.castShadow = m.receiveShadow = true; m.userData.solid = true; if (pos) m.position.set(...pos); return m; };
const lights = s => ({ key: s.userData.key, hemi: s.children.find(o => o.isHemisphereLight), rim: s.children.find(o => o.isDirectionalLight && o !== s.userData.key) });

function room(makeStage, { wall = 0x1b2750, floor = 0x2a2f55, sky = [0x0a1030, 0x101a45, 0x182559], key = 0.5, keyColor = 0x9fb4ff, hemi = 0.35, hemiColor = 0x6f86d8, rim = 0.4, W = 7 } = {}) {
  const scene = makeStage({ shadowSize: 3, sunDir: [-2, 5, 3], sun: key });
  scene.children.find(o => o.material && o.material.type === 'ShadowMaterial').visible = false;
  const L = lights(scene); L.key.color.set(keyColor); L.hemi.intensity = hemi; L.hemi.color.set(hemiColor); L.hemi.groundColor.set(0x303860); L.rim.intensity = rim; L.rim.color.set(keyColor);
  const u = scene.userData.sky.material.uniforms; u.top.value.set(sky[0]); u.mid.value.set(sky[1]); u.horizon.value.set(sky[2]); u.floorC.value.set(sky[2]);
  scene.environmentIntensity = 0.25;
  const fl = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), std(floor, 0.9)); fl.rotation.x = -Math.PI / 2; fl.receiveShadow = true; scene.add(fl);
  const bw = new THREE.Mesh(new THREE.PlaneGeometry(14, 6), std(wall, 0.95)); bw.position.set(0, 3, -1.6); bw.receiveShadow = true; scene.add(bw);
  const sw = new THREE.Mesh(new THREE.PlaneGeometry(14, 6), std(wall, 0.95)); sw.position.set(-3.4, 3, 0); sw.rotation.y = Math.PI / 2; sw.receiveShadow = true; scene.add(sw);
  const side2 = sw.clone(); side2.position.x = 3.6; side2.rotation.y = -Math.PI / 2; scene.add(side2);
  const front = new THREE.Mesh(new THREE.PlaneGeometry(14, 6), std(wall, 0.95)); front.position.set(0, 3, 4.2); front.rotation.y = Math.PI; scene.add(front);
  const ceil = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), std(wall, 0.95)); ceil.position.y = 3.2; ceil.rotation.x = Math.PI / 2; scene.add(ceil);
  return scene;
}
function windowPane(scene, { x = 0, y = 1.75, z = -1.58, night = true } = {}) {
  const g = new THREE.Group(); g.position.set(x, y, z); scene.add(g);
  const frame = rbox(1.5, 1.2, 0.06, 0.02, std(0x9aa6c8, 0.5)); g.add(frame);
  const tex = canvasTex(256, 256, (c, w, h) => {
    const gr = c.createLinearGradient(0, 0, 0, h);
    if (night) { gr.addColorStop(0, '#060b25'); gr.addColorStop(1, '#16275a'); } else { gr.addColorStop(0, '#ff9a4a'); gr.addColorStop(1, '#ffd7a0'); }
    c.fillStyle = gr; c.fillRect(0, 0, w, h);
    if (night) { c.fillStyle = '#fff'; for (let i = 0; i < 26; i++) c.fillRect((i * 97) % 250, (i * 53) % 130, 2, 2); }
    c.fillStyle = night ? '#0a1130' : '#9b4a2a'; for (let i = 0; i < 8; i++) { const bh = 50 + ((i * 37) % 70); c.fillRect(i * 34, h - bh, 30, bh); }
    c.fillStyle = night ? '#ffd27a' : '#ffe7b8'; for (let i = 0; i < 18; i++) c.fillRect(((i * 61) % 240) + 4, 150 + ((i * 29) % 90), 4, 5);
  });
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(1.36, 1.06), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false })); glass.position.z = 0.04; g.add(glass);
  const bar = rbox(0.04, 1.06, 0.03, 0.01, std(0x9aa6c8), [0, 0, 0.05]); g.add(bar);
  return g;
}
function desk(scene, { z = 0.78 } = {}) {
  const g = new THREE.Group(); g.position.z = z; scene.add(g);
  g.add(rbox(1.7, 0.07, 0.85, 0.03, std(0x6b5037, 0.6), [0, 0.74, 0]));
  for (const sx of [-0.78, 0.78]) for (const sz of [-0.36, 0.36]) g.add(rbox(0.07, 0.72, 0.07, 0.02, std(0x3a2c1f), [sx, 0.36, sz]));
  const chair = new THREE.Group(); chair.position.z = 0.02; scene.add(chair);
  chair.add(rbox(0.62, 0.08, 0.6, 0.03, std(0x2a3a66, 0.7), [0, 0.5, -0.02]));
  chair.add(rbox(0.6, 0.62, 0.08, 0.03, std(0x2a3a66, 0.7), [0, 0.86, -0.34]));
  chair.add(rbox(0.08, 0.5, 0.08, 0.02, std(0x222), [0, 0.25, -0.02]));
  return g;
}
function laptop(scene, { z = 0.74, tex = null, glow = 1.0 } = {}) {
  const g = new THREE.Group(); g.position.set(0, 0.78, z); scene.add(g);
  g.add(rbox(0.62, 0.025, 0.42, 0.01, std(0xb5bccc, 0.4, { metalness: 0.6 }), [0, 0.012, 0]));
  const lid = new THREE.Group(); lid.position.set(0, 0.025, 0.2); lid.rotation.x = 0.22; g.add(lid);           // leans back, screen faces the person (-z... toward +z flipped below)
  lid.add(rbox(0.62, 0.4, 0.02, 0.01, std(0xb5bccc, 0.4, { metalness: 0.6 }), [0, 0.2, 0]));
  const mat = new THREE.MeshBasicMaterial({ map: tex || null, color: tex ? 0xffffff : 0xdfe9ff, toneMapped: false });
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.57, 0.36), mat); screen.position.set(0, 0.2, -0.0115); screen.rotation.y = Math.PI; lid.add(screen); // faces -z (toward the chair)
  const fill = new THREE.PointLight(0xaac4ff, 0.9 * glow, 3, 1.5); fill.position.set(0, 0.5, -0.1); g.add(fill);
  g.userData.screen = screen; g.userData.lid = lid;
  return g;
}
function lamp(scene, { x = -0.7, z = 0.7, color = 0xffb26b, intensity = 1.6 } = {}) {
  const g = new THREE.Group(); g.position.set(x, 0.775, z); scene.add(g);
  g.add(new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.13, 0.03, 24), std(0x222)));
  const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.36, 10), std(0x222)); stem.position.y = 0.19; g.add(stem);
  const shade = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.17, 0.2, 28, 1, true), new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide, toneMapped: false })); shade.position.y = 0.42; g.add(shade);
  const l = new THREE.PointLight(color, intensity, 5, 1.6); l.position.set(0, 0.4, 0.05); l.castShadow = true; l.shadow.mapSize.set(1024, 1024); g.add(l);
  g.userData.light = l; return g;
}
// Numeric arm solver: finds shoulder and elbow angles that put each hand exactly on a world target (the keys), so arms never pass through the laptop.
function solveArms(h, base, tL, tR) {
  const out = {};
  for (const [side, tgt, zs] of [['l', tL, 0.2], ['r', tR, -0.2]]) {
    let best = null;
    for (let a = -2.0; a <= 0.1; a += 0.05) for (let b = -2.2; b <= 0; b += 0.05) {
      h.pose({ ...base, [side + 'Sh']: [a, 0, zs], [side + 'El']: [b, 0, 0] });
      const d = h.points().find(q => q[0] === side.toUpperCase() + 'hand')[1].distanceTo(tgt);
      if (!best || d < best.d) best = { d, a, b };
    }
    const c0 = best; // refine around the best coarse hit
    for (let a = c0.a - 0.05; a <= c0.a + 0.05; a += 0.01) for (let b = c0.b - 0.05; b <= c0.b + 0.05; b += 0.01) {
      h.pose({ ...base, [side + 'Sh']: [a, 0, zs], [side + 'El']: [b, 0, 0] });
      const d = h.points().find(q => q[0] === side.toUpperCase() + 'hand')[1].distanceTo(tgt);
      if (d < best.d) best = { d, a, b };
    }
    out[side + 'Sh'] = [best.a, 0, zs]; out[side + 'El'] = [best.b, 0, 0];
  }
  return out;
}
const KEYS_L = V(-0.15, 0.93, 0.66), KEYS_R = V(0.15, 0.93, 0.66);
function typingPose(h, t, extra = {}) {
  const base = { drop: 0.28, hip: [0, 0, 0], torso: [0.06, 0, 0], neck: [0.05, 0, 0], lHip: [-1.5, 0.05, 0], lKn: [1.5, 0, 0], rHip: [-1.5, -0.05, 0], rKn: [1.5, 0, 0], ...extra };
  const key = JSON.stringify([base.torso, base.neck, base.drop]);
  h.userData = h.userData || {}; h.userData.arms = h.userData.arms || {};
  const arms = h.userData.arms[key] || (h.userData.arms[key] = solveArms(h, base, KEYS_L, KEYS_R));
  const k = Math.sin(t * 15) * 0.025, k2 = Math.sin(t * 15 + 2) * 0.025;
  h.pose({ ...base, lSh: [arms.lSh[0] + k, 0, 0.2], lEl: [arms.lEl[0] + k2, 0, 0], rSh: [arms.rSh[0] + k2, 0, -0.2], rEl: [arms.rEl[0] + k, 0, 0], blink: ((t * 0.7) % 3) > 2.92, ...extra });
}
const seat = h => { h.root.position.set(0, 0, 0.02); h.root.rotation.y = 0; };

function pop(t, t0, dur = 0.35, over = 1.7) { // scale 0 -> 1 with overshoot
  const k = clamp((t - t0) / dur); if (k <= 0) return 0.0001; const c1 = over; return 1 + (c1 + 1) * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2);
}
const planeCard = (tex, w, h) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false })); return m; };


// ============ S7: your evening is yours ============
function s7({ makeStage }) {
  const scene = room(makeStage, { wall: 0xe9b27d, floor: 0xb98a63, sky: [0xff9a4a, 0xffb36b, 0xffd9a0], key: 1.6, keyColor: 0xffd2a0, hemi: 0.75, hemiColor: 0xffe2c0, rim: 0.7 });
  windowPane(scene, { x: 0.9, night: false });
  // couch, facing the camera side
  const couchM = std(0x2f6f7a, 0.85);
  const couch = new THREE.Group(); couch.position.set(0, 0, -0.5); scene.add(couch);
  couch.add(rbox(1.7, 0.42, 0.8, 0.1, couchM, [0, 0.21, 0]));
  couch.add(rbox(1.7, 0.6, 0.22, 0.1, couchM, [0, 0.62, -0.36]));
  couch.add(rbox(0.2, 0.55, 0.8, 0.1, couchM, [-0.85, 0.35, 0])); couch.add(rbox(0.2, 0.55, 0.8, 0.1, couchM, [0.85, 0.35, 0]));
  const table = rbox(0.9, 0.04, 0.5, 0.02, std(0x6b5037, 0.6), [0, 0.38, 0.85]); scene.add(table);
  for (const sx of [-0.4, 0.4]) for (const sz of [0.65, 1.05]) scene.add(rbox(0.05, 0.36, 0.05, 0.01, std(0x3a2c1f), [sx, 0.18, sz]));
  const mug = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.045, 0.1, 20), std(0xffffff, 0.4)); mug.position.set(0.2, 0.45, 0.85); mug.castShadow = true; scene.add(mug);
  const lampL = new THREE.PointLight(0xffb36b, 1.4, 6, 1.5); lampL.position.set(-1.1, 1.8, 0.4); scene.add(lampL);
  for (let i = 0; i < 14; i++) { const b = new THREE.Mesh(new THREE.SphereGeometry(0.03, 10, 8), new THREE.MeshBasicMaterial({ color: 0xfff0c0, toneMapped: false })); b.position.set(-1.6 + i * 0.25, 2.5 + Math.sin(i * 0.9) * 0.08, -1.55); scene.add(b); }
  const h = makeBlocky({ hoodie: 0x3c4b73 }); h.root.position.set(0, 0.0, -0.45); scene.add(h.root);
  const c = cam(36);
  return { scene, camera: c, update(t) {
    const br = Math.sin(t * 1.4) * 0.01;
    h.pose({ drop: 0.4, hip: [-0.25, 0, 0], torso: [-0.2 + br, 0, 0], neck: [0.2, 0, 0], head: [0, -0.15, 0],
      lHip: [-1.2, 0.05, 0], lKn: [1.2, 0, 0], rHip: [-1.45, -0.05, 0], rKn: [0.9, 0, 0],
      lSh: [-0.5, 0, 0.35], lEl: [-0.5, 0, 0], rSh: [-1.0, 0, -0.1], rEl: [-1.4, 0, 0.1], smile: 1, blink: ((t * 0.6) % 3) > 2.9 });
    const a = kf(t, [[0, -0.5], [3.2, 0.25]], easeInOut);
    place(c, [Math.sin(a) * 2.7, 1.15, 0.9 + Math.cos(a) * 2.5], [0, 0.85, 0.1]);
    return { dof: { focus: 2.7, aperture: 0.004, maxblur: 0.01 }, bloom: 0.55, exposure: 1.05 };
  } };
}

// ============ S8: end card ============
function s8() {
  const scene = new THREE.Scene(); scene.userData.sky = new THREE.Object3D();
  const m = new THREE.Mesh(new THREE.PlaneGeometry(2.25, 4), new THREE.MeshBasicMaterial({ map: endTex(), toneMapped: false })); scene.add(m);
  const c = cam(35);
  return { scene, camera: c, update(t) { const z = kf(t, [[0, 6.9], [2.5, 6.4]], easeOut); place(c, [0, 0, z], [0, 0, 0]); m.scale.setScalar(1.14); return { bloom: 0.2 }; } };
}


// ================= v2: fast cuts, varied places, a moving character, real dashboard =================
const rnd = (i) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const gradTex = (a, b) => canvasTex(64, 256, (g, w, h) => { const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, a); gr.addColorStop(1, b); g.fillStyle = gr; g.fillRect(0, 0, w, h); });
const bubbleTex = (txt) => canvasTex(640, 200, (g, w, h) => {
  g.fillStyle = '#fff'; rr(g, 0, 0, w, h - 30, 36); g.fill(); g.beginPath(); g.moveTo(80, h - 32); g.lineTo(110, h); g.lineTo(130, h - 32); g.fill();
  g.fillStyle = '#1b2a44'; g.font = '700 46px Montserrat, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(txt, w / 2, (h - 30) / 2 + 2);
});
const windowsTex = (col) => canvasTex(128, 256, (g, w, h) => { g.fillStyle = col; g.fillRect(0, 0, w, h); g.fillStyle = 'rgba(255,255,255,.55)'; for (let y = 14; y < h - 10; y += 34) for (let x = 10; x < w - 10; x += 30) g.fillRect(x, y, 16, 20); });

// --- character motion ---
function walkPose(h, t, sp = 1, extra = {}) {
  const ph = t * 7.5 * sp, s = Math.sin(ph);
  h.pose({ drop: 0.035 * Math.abs(s), torso: [0.07, Math.sin(ph) * 0.06, Math.sin(ph) * 0.03], head: [-0.04, -Math.sin(ph) * 0.05, 0],
    lHip: [s * 0.8, 0, 0], rHip: [-s * 0.8, 0, 0], lKn: [0.12 + Math.max(0, Math.sin(ph + 1.7)) * 0.95, 0, 0], rKn: [0.12 + Math.max(0, Math.sin(ph + 1.7 + Math.PI)) * 0.95, 0, 0],
    lSh: [-s * 0.75, 0, 0.08], rSh: [s * 0.75, 0, -0.08], lEl: [-0.35, 0, 0], rEl: [-0.35, 0, 0], blink: ((t * 0.7) % 3) > 2.9, ...extra });
}
const cheer = (t) => ({ lSh: [-2.9 + Math.sin(t * 9) * 0.15, 0, 0.45], rSh: [-2.9 - Math.sin(t * 9) * 0.15, 0, -0.45], lEl: [-0.2, 0, 0], rEl: [-0.2, 0, 0], smile: 1 });

// --- scenes ---
function street(makeStage, { golden = false } = {}) {
  const scene = makeStage({ shadowSize: 7, sunDir: golden ? [-5, 2.2, 3] : [-3, 6, 4], sun: golden ? 2.8 : 2.3 });
  scene.children.find(o => o.material && o.material.type === 'ShadowMaterial').visible = false;
  const L = lights(scene);
  if (golden) {
    const u = scene.userData.sky.material.uniforms; u.top.value.set(0x5a6fd0); u.mid.value.set(0xff9a6a); u.horizon.value.set(0xffd09a); u.floorC.value.set(0xffd09a);
    L.key.color.set(0xffc08a); L.hemi.color.set(0xffc9a0); L.hemi.intensity = 0.7; L.rim.intensity = 0.6;
  }
  const road = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), std(0x5a606c, 0.95)); road.rotation.x = -Math.PI / 2; road.receiveShadow = true; scene.add(road);
  for (const sx of [-1, 1]) { const walk = rbox(1.6, 0.12, 40, 0.02, std(0xb9bcc6, 0.9), [sx * 2.0, 0.0, 0]); walk.receiveShadow = true; scene.add(walk); }
  for (let i = 0; i < 12; i++) { const d = rbox(0.12, 0.01, 0.8, 0.0, std(0xf2f2f2), [0, 0.006, -9 + i * 1.8]); scene.add(d); }
  const pal = [0xd9a07a, 0xc9d3e6, 0xe8c9a0, 0xa9c4b8, 0xd6b3c4, 0xb7a9d1];
  for (const sx of [-1, 1]) for (let i = 0; i < 12; i++) {
    const hgt = 2.4 + rnd(i + sx * 5) * 2.4, c = pal[(i + (sx > 0 ? 3 : 0)) % pal.length];
    const b = new THREE.Mesh(new THREE.BoxGeometry(1.7, hgt, 1.7), new THREE.MeshStandardMaterial({ map: windowsTex('#' + new THREE.Color(c).getHexString()), roughness: 0.9 })); b.position.set(sx * 3.5, hgt / 2, -10 + i * 1.8); b.castShadow = b.receiveShadow = true; scene.add(b);
  }
  for (const sx of [-1, 1]) for (let i = 0; i < 6; i++) {
    const tr = new THREE.Group(); tr.position.set(sx * 1.35, 0, -8 + i * 3.1 + sx); scene.add(tr);
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.07, 0.7, 8), std(0x5a3d26)); trunk.position.y = 0.35; trunk.castShadow = true; tr.add(trunk);
    const fol = new THREE.Mesh(new THREE.SphereGeometry(0.42, 16, 12), std(golden ? 0xd98a3a : 0x3f9e5a, 0.9)); fol.position.y = 1.0; fol.castShadow = true; tr.add(fol);
  }
  return scene;
}
function bedroom(makeStage) {
  const scene = room(makeStage, { wall: 0x23305c, floor: 0x2c335a });
  windowPane(scene, { x: 0.8 });
  const bed = new THREE.Group(); bed.position.set(0, 0, -0.2); scene.add(bed);
  bed.add(rbox(1.5, 0.3, 2.3, 0.05, std(0x3a2c1f), [0, 0.15, 0]));
  bed.add(rbox(1.4, 0.2, 2.2, 0.08, std(0xdfe6f5, 0.9), [0, 0.4, 0]));
  bed.add(rbox(1.42, 0.06, 1.2, 0.03, std(0x1aa6a0, 0.9), [0, 0.52, 0.45]));
  bed.add(rbox(0.9, 0.14, 0.4, 0.06, std(0xf2f4f8, 0.9), [0, 0.58, -0.9]));
  return scene;
}
function kitchen(makeStage) {
  const scene = room(makeStage, { wall: 0xcbb99a, floor: 0x8a7258, sky: [0x7fa8d8, 0x9fc2e8, 0xc9def2], key: 0.9, keyColor: 0xffe2c0, hemi: 0.7, hemiColor: 0xfff0dc, rim: 0.4 });
  windowPane(scene, { x: -1.0, night: false });
  scene.add(rbox(1.9, 0.07, 0.95, 0.03, std(0xe9e4da, 0.5), [0, 0.76, 0.55]));
  for (const sx of [-0.85, 0.85]) for (const sz of [0.2, 0.9]) scene.add(rbox(0.07, 0.74, 0.07, 0.02, std(0x777), [sx, 0.37, sz]));
  return scene;
}
const parcel = (w = 0.34, h = 0.22, d = 0.26) => { const g = new THREE.Group(); g.add(rbox(w, h, d, 0.015, std(0xb98a5a, 0.85))); const tape = rbox(0.05, h + 0.004, d + 0.004, 0.005, std(0xe9d9b0)); g.add(tape); return g; };

// --- shot wrapper: whip-pan in and out, so cuts feel like swipes ---
function wrap(build, dur, dir = 1) {
  return (a) => {
    const sh = build(a), u = sh.update;
    sh.update = (t, T) => {
      const r = u(t, T) || {};
      const w = Math.max(1 - range(t, 0, 0.13), range(t, dur - 0.11, dur)), sgn = t < dur / 2 ? -dir : dir;
      if (w > 0.01) { sh.camera.translateX(sgn * w * w * 0.5); sh.camera.rotateZ(sgn * w * 0.12); r.dof = { focus: 1.6, aperture: 0.045 * w, maxblur: 0.035 * w }; }
      return r;
    };
    return sh;
  };
}

// ---------------- 3D character shots ----------------
function A({ makeStage }) { // you sell on Vinted: walks toward camera with a parcel
  const scene = street(makeStage), h = makeBlocky({ hoodie: 0x3c4b73 }); scene.add(h.root);
  const bx = parcel(); h.torso.add(bx); bx.position.set(0, 0.32, 0.36);
  const logo = planeCard(logoTex('vinted.png'), 0.46, 0.29); scene.add(logo); const c = cam(46);
  return { scene, camera: c, update(t) {
    const z = lerp(-2.6, 0.5, easeOut(t / 0.9));
    h.root.position.set(0, 0, z); walkPose(h, t, 1.25, { lSh: [-1.15, 0, 0.3], rSh: [-1.15, 0, -0.3], lEl: [-0.6, 0, 0], rEl: [-0.6, 0, 0], torso: [0.12, 0, 0] });
    logo.position.set(0.55, 1.55 + Math.sin(t * 5) * 0.02, z); logo.scale.setScalar(pop(t, 0.2, 0.3)); logo.rotation.set(0, -0.3, 0.05);
    const p = kf(t, [[0, [0.9, 0.5, 2.6]], [0.9, [0.4, 0.75, 2.1]]], easeOut); place(c, p, [0, 0.95, z * 0.4]);
    return { dof: { focus: 2.5, aperture: 0.003, maxblur: 0.01 }, bloom: 0.4, exposure: 1.0 };
  } };
}
function B({ makeStage }) { // desk, punch in
  const scene = room(makeStage); windowPane(scene, { x: -0.9 }); desk(scene); laptop(scene); lamp(scene);
  const h = makeBlocky(); seat(h); scene.add(h.root); const c = cam(40);
  return { scene, camera: c, update(t) {
    typingPose(h, t + 3, { smile: 0 });
    const p = kf(t, [[0, [1.6, 1.5, 3.6]], [0.7, [0.5, 1.4, 2.2]]], easeOut); place(c, p, [0, 1.3, 0.3], (1 - range(t, 0, 0.6)) * 0.08);
    return { dof: { focus: 2.4, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
  } };
}
function C({ makeStage }) { // marktplaats card slams in
  const scene = room(makeStage); windowPane(scene, { x: -0.9 }); desk(scene); laptop(scene); lamp(scene);
  const h = makeBlocky(); seat(h); scene.add(h.root); const m = planeCard(logoTex('marktplaats.png'), 0.55, 0.34); scene.add(m); const c = cam(40);
  return { scene, camera: c, update(t) {
    typingPose(h, t + 7, { head: [0, Math.sin(t * 9) * 0.05, 0] });
    const k = easeOut(range(t, 0.1, 0.35)); m.position.set(lerp(-1.3, 0.05, k), 1.35, lerp(2.0, 1.4, k)); m.scale.setScalar(1 + (1 - k) * 0.3); m.rotation.set(0, 0, lerp(-0.4, 0.04, k));
    const sh = Math.exp(-Math.pow((t - 0.35) * 14, 2)) * 0.03;
    const p = kf(t, [[0, [-0.9, 1.45, 3.3]], [1.0, [0.2, 1.4, 2.6]]], easeInOut); place(c, [p[0] + sh, p[1] - sh, p[2]], [0, 1.3, 0.3]);
    return { dof: { focus: 2.6, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
  } };
}
function D({ makeStage }) { // eBay: on the bed with a laptop
  let arms = null;
  const scene = bedroom(makeStage), h = makeBlocky({ hoodie: 0x4a3c73 }); scene.add(h.root); h.root.position.set(0, 0, -0.35);
  const lap = laptop(scene, { z: 0 }); h.root.add(lap); lap.position.set(0, 0.8, 0.52);
  const m = planeCard(logoTex('ebay.webp'), 0.55, 0.34); scene.add(m); const c = cam(42);
  return { scene, camera: c, update(t) {
    const bBase = { drop: 0.2, hip: [0, 0, 0], torso: [0, 0, 0], neck: [0.12, 0, 0], head: [0.1, Math.sin(t * 6) * 0.06, 0], lHip: [-1.5, 0.1, 0], rHip: [-1.5, -0.1, 0], lKn: [0.05, 0, 0], rKn: [0.05, 0, 0], blink: false };
    arms = arms || solveArms(h, bBase, V(-0.15, 0.95, 0.12), V(0.15, 0.95, 0.12));
    h.pose({ ...bBase, lSh: [arms.lSh[0] + Math.sin(t * 16) * 0.04, 0, 0.2], rSh: [arms.rSh[0] + Math.sin(t * 16 + 2) * 0.04, 0, -0.2], lEl: arms.lEl, rEl: arms.rEl });
    const k = easeOut(range(t, 0.1, 0.4)); m.position.set(lerp(1.4, 0.35, k), 1.55, 1.0); m.scale.setScalar(pop(t, 0.1, 0.35)); m.rotation.set(0, -0.35, -0.05);
    const a = lerp(0.9, -0.4, easeInOut(t / 0.95)); place(c, [Math.sin(a) * 2.6, 1.5, 1.2 + Math.cos(a) * 2.6], [0, 0.95, 0.2]);
    return { dof: { focus: 2.7, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
  } };
}
function E({ makeStage }) { // Shopify: wrapping parcels, they pile up
  const scene = kitchen(makeStage), h = makeBlocky({ hoodie: 0x5b7f5d }); h.root.position.set(0, 0, -0.35); scene.add(h.root);
  const ps = []; for (let i = 0; i < 7; i++) { const p = parcel(0.3 + rnd(i) * 0.12, 0.18 + rnd(i + 3) * 0.1, 0.24); scene.add(p); ps.push(p); }
  const m = planeCard(logoTex('shopify.webp'), 0.4, 0.4); scene.add(m); const c = cam(42);
  return { scene, camera: c, update(t) {
    const k1 = Math.sin(t * 15) * 0.18, k2 = Math.sin(t * 15 + 2) * 0.18;
    h.pose({ torso: [0.22, 0, 0], neck: [0.1, 0, 0], head: [0.05, Math.sin(t * 7) * 0.12, 0], lSh: [-0.95 + k1, 0, 0.2], rSh: [-0.95 + k2, 0, -0.2], lEl: [-0.9, 0, 0], rEl: [-0.9, 0, 0], blink: false });
    ps.forEach((p, i) => { const t0 = i * 0.14, f = easeOut(range(t, t0, t0 + 0.22)); const col = i % 4, row = Math.floor(i / 4);
      p.position.set(lerp(1.5, -0.6 + col * 0.4, f), lerp(1.2, 0.83 + row * 0.24, f), 0.7 + (row ? 0.08 : -0.05)); p.rotation.y = rnd(i) * 0.6 - 0.3; p.scale.setScalar(pop(t, t0, 0.2, 1.2)); });
    const sk = pop(t, 0.35, 0.3); m.position.set(0.55, 1.75, 0.5); m.scale.setScalar(sk); m.rotation.set(0, -0.2, 0.05);
    const p = kf(t, [[0, [0.2, 0.9, 3.2]], [1.1, [-0.1, 1.45, 2.2]]], easeInOut); place(c, p, [0, 1.1, 0.2]);
    return { dof: { focus: 2.5, aperture: 0.004, maxblur: 0.01 }, bloom: 0.4, exposure: 1.0 };
  } };
}
function F({ makeStage }) { // same photos: the listing multiplies in a grid
  const scene = new THREE.Scene(); scene.userData.sky = new THREE.Object3D();
  const bg = new THREE.Mesh(new THREE.PlaneGeometry(8, 12), new THREE.MeshBasicMaterial({ map: gradTex('#14233f', '#0c4a5a'), toneMapped: false })); bg.position.z = -0.5; scene.add(bg);
  const tex = listingTex(), cards = []; for (let i = 0; i < 15; i++) { const m = planeCard(tex, 0.3, 0.375); scene.add(m); cards.push(m); }
  const c = cam(40);
  return { scene, camera: c, update(t) {
    cards.forEach((m, i) => { const col = i % 3, row = Math.floor(i / 3); m.position.set((col - 1) * 0.34, (2 - row) * 0.42 - 0.35, 0 + rnd(i) * 0.02); m.scale.setScalar(pop(t, i * 0.055, 0.2, 1.4)); m.visible = t > i * 0.055; m.rotation.set(0, (col - 1) * -0.12, (rnd(i) - 0.5) * 0.06); });
    const p = kf(t, [[0, [0.3, 0.3, 2.9]], [1.0, [-0.1, -0.1, 1.9]]], easeInOut); place(c, p, [0, -0.1, 0], Math.sin(t * 4) * 0.03);
    return { bloom: 0.3 };
  } };
}
function G({ makeStage }) { // same text: frantic typing, text bubbles pop
  const scene = room(makeStage); windowPane(scene, { x: -0.9 }); desk(scene); laptop(scene); lamp(scene);
  const h = makeBlocky(); seat(h); scene.add(h.root);
  const txt = ['Nike Tech Fleece', 'Maat M, zo goed als nieuw', 'Merk: Nike', 'Prijs: €68'], bs = txt.map(s => { const m = planeCard(bubbleTex(s), 0.56, 0.175); scene.add(m); return m; }); const c = cam(40);
  return { scene, camera: c, update(t) {
    const q = Math.sin(t * 22) * 0.09; typingPose(h, t * 1.4, { head: [0.1, Math.sin(t * 11) * 0.08, Math.sin(t * 7) * 0.05] });
    bs.forEach((m, i) => { m.position.set(i % 2 ? 0.3 : -0.3, 1.95 + (i % 2) * 0.22 - 0.0, 0.5); m.scale.setScalar(pop(t, 0.05 + i * 0.22, 0.2) * (t < 0.05 + i * 0.22 ? 0 : 1)); m.rotation.set(0, 0, i % 2 ? 0.05 : -0.05); });
    const p = kf(t, [[0, [0.4, 1.4, 3.8]], [1.0, [-0.1, 1.5, 2.7]]], easeOut); place(c, p, [0, 1.55, 0.3]);
    return { dof: { focus: 2.7, aperture: 0.004, maxblur: 0.01 }, bloom: 0.5, exposure: 1.05 };
  } };
}
function Hh({ makeStage }) { // again and again: a swirl of listing cards around the desk
  const scene = room(makeStage); windowPane(scene, { x: -0.9 }); desk(scene); laptop(scene); lamp(scene);
  const h = makeBlocky(); seat(h); scene.add(h.root); const tex = listingTex(), cards = []; for (let i = 0; i < 26; i++) { const m = planeCard(tex, 0.28, 0.35); scene.add(m); cards.push(m); }
  const c = cam(44);
  return { scene, camera: c, update(t) {
    typingPose(h, t + 11, { head: [0.05, Math.sin(t * 8) * 0.1, 0] });
    cards.forEach((m, i) => { const r = 0.9 + (i % 3) * 0.25, a = t * 2.2 + i * 0.52, k = pop(t, i * 0.035, 0.2); m.position.set(Math.sin(a) * r, 0.9 + (i / 26) * 1.3 + Math.sin(t * 3 + i) * 0.05, 0.3 + Math.cos(a) * r); m.scale.setScalar(k); });
    const a = lerp(0.3, -0.6, easeInOut(t / 1.35)); place(c, [Math.sin(a) * 3.0, 1.9, 0.3 + Math.cos(a) * 3.0], [0, 1.3, 0.3]);
    cards.forEach((m, i) => m.quaternion.copy(c.quaternion).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, Math.sin(t * 3 + i) * 0.12))));
    return { dof: { focus: 3.0, aperture: 0.005, maxblur: 0.012 }, bloom: 0.5, exposure: 1.05 };
  } };
}
function I({ makeStage }) { // midnight: LED clock close-up, pulls back to the slumped person
  const scene = room(makeStage, { key: 0.3, hemi: 0.22 }); windowPane(scene, { x: -0.9 }); desk(scene); laptop(scene, { glow: 0.6 }); lamp(scene, { intensity: 1.0 });
  const h = makeBlocky(); seat(h); scene.add(h.root);
  scene.add(rbox(0.3, 0.14, 0.12, 0.03, std(0x222), [0.62, 0.86, 1.1]));
  const face = new THREE.Mesh(new THREE.PlaneGeometry(0.25, 0.1), new THREE.MeshBasicMaterial({ map: ledTex('00:47'), toneMapped: false })); face.position.set(0.62, 0.86, 1.165); scene.add(face);
  const gl = new THREE.PointLight(0xff3b2f, 0.5, 1.6); gl.position.set(0.62, 0.95, 1.5); scene.add(gl); const c = cam(38);
  return { scene, camera: c, update(t) {
    typingPose(h, 1, { neck: [0.55, 0, 0], head: [0.25, 0, 0.14], blink: true });
    const p = kf(t, [[0, [0.7, 0.95, 1.75]], [0.95, [1.8, 1.4, 3.3]]], easeInOut); place(c, p, [kf(t, [[0, 0.62], [0.95, 0.15]], easeInOut), kf(t, [[0, 0.9], [0.95, 1.1]], easeInOut), 0.9]);
    return { dof: { focus: 1.2, aperture: 0.006, maxblur: 0.012 }, bloom: 0.7, exposure: 0.95 };
  } };
}
function Jj({ makeStage }) { // still listing, eyes closing
  const scene = room(makeStage, { key: 0.3, hemi: 0.22 }); windowPane(scene, { x: -0.9 }); desk(scene); laptop(scene, { glow: 1.2 }); lamp(scene, { intensity: 1.0 });
  const h = makeBlocky(); seat(h); scene.add(h.root); const c = cam(36);
  return { scene, camera: c, update(t) {
    const nod = Math.max(0, Math.sin(t * 3.2)) * 0.25; typingPose(h, t * 0.3, { torso: [0.1 + nod * 0.1, 0, 0], neck: [0.2 + nod, 0, 0], head: [0.1, 0, 0.1], blink: Math.sin(t * 3.2) > 0.3 });
    const p = kf(t, [[0, [0.5, 1.5, 3.0]], [0.9, [0.1, 1.55, 2.3]]], easeInOut); place(c, p, [0, 1.5, 0.3], 0.05 * (1 - t));
    return { dof: { focus: 2.2, aperture: 0.005, maxblur: 0.012 }, bloom: 0.5, exposure: 0.95 };
  } };
}

// ---------------- real dashboard shots (flat, fast zoom and pan) ----------------
function dashShot(key, keys, { cursor = null, tilt = 0.12 } = {}) {
  return ({ makeStage }) => {
    const im = IMG[key], ratio = im.height / im.width, PW = 1.6, PH = PW * ratio;
    const X = px => (px / im.width - 0.5) * PW, Y = py => (0.5 - py / im.height) * PH;
    const scene = new THREE.Scene(); scene.userData.sky = new THREE.Object3D();
    const bg = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), new THREE.MeshBasicMaterial({ map: gradTex('#14233f', '#0f6f78'), toneMapped: false })); bg.position.z = -0.4; scene.add(bg);
    const sh = new THREE.Mesh(new THREE.PlaneGeometry(PW * 1.03, PH * 1.03), new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.35 })); sh.position.set(0.03, -0.03, -0.02); scene.add(sh);
    const tex = new THREE.Texture(im); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8; tex.needsUpdate = true;
    const m = new THREE.Mesh(new THREE.PlaneGeometry(PW, PH), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false })); scene.add(m);
    let cur = null, ring = null;
    if (cursor) { cur = planeCard(cursorTex(), 0.09, 0.09); scene.add(cur); ring = new THREE.Mesh(new THREE.RingGeometry(0.03, 0.036, 40), new THREE.MeshBasicMaterial({ color: 0x1aa6a0, transparent: true, toneMapped: false })); scene.add(ring); }
    const c = cam(40);
    return { scene, camera: c, update(t) {
      const k = kf(t, keys, easeInOut), vw = k[2], wW = vw / im.width * PW, d = wW / 0.4094;
      const cx = X(k[0]), cy = Y(k[1]); place(c, [cx + d * tilt * Math.sin(t * 2.2 + 0.5), cy + d * 0.04 * Math.cos(t * 1.7), d], [cx, cy, 0]);
      if (cursor) {
        const [x0, y0, x1, y1, tc] = cursor, f = easeOut(range(t, 0, tc)); cur.position.set(X(lerp(x0, x1, f)) + 0.03, Y(lerp(y0, y1, f)) - 0.03, 0.05); cur.scale.setScalar(1 - 0.18 * Math.exp(-Math.pow((t - tc) * 12, 2)));
        const rk = range(t, tc, tc + 0.3); ring.position.set(X(x1), Y(y1), 0.04); ring.scale.setScalar(0.3 + rk * 3.2); ring.material.opacity = (1 - rk) * (t >= tc ? 1 : 0);
      }
      return { bloom: 0.15, exposure: 1.0 };
    } };
  };
}
const K = dashShot('dash.jpg', [[0, [620, 300, 1300]], [0.3, [430, 120, 700]], [0.8, [440, 120, 620]]], { tilt: 0.07 });                  // whip onto the dashboard, push to the stats
const Ll = dashShot('items.jpg', [[0, [930, 200, 520]], [0.8, [930, 560, 520]]], { tilt: 0.06 });                                           // down the platform badges
const Mm = dashShot('items.jpg', [[0, [900, 300, 900]], [0.4, [1040, 205, 480]], [0.8, [1050, 205, 440]]], { cursor: [880, 330, 1121, 189, 0.4], tilt: 0.05 }); // the one click
function Nn() { // every platform: logos burst out
  const scene = new THREE.Scene(); scene.userData.sky = new THREE.Object3D();
  const bg = new THREE.Mesh(new THREE.PlaneGeometry(8, 12), new THREE.MeshBasicMaterial({ map: gradTex('#14233f', '#0c6a73'), toneMapped: false })); bg.position.z = -1; scene.add(bg);
  const listing = planeCard(listingTex(), 0.5, 0.625); scene.add(listing);
  const logos = PLATFORMS.map(k => { const m = planeCard(logoTex(k), 0.5, 0.31); scene.add(m); return m; }), checks = PLATFORMS.map(() => { const m = planeCard(checkTex(), 0.15, 0.15); scene.add(m); return m; });
  const ang = [-90, -18, 54, 126, 198].map(a => a * Math.PI / 180), c = cam(40);
  return { scene, camera: c, update(t) {
    listing.scale.setScalar(pop(t, 0, 0.2) * (1 - 0.4 * easeInOut(range(t, 0.15, 0.4)))); listing.position.set(0, 0, 0.05);
    logos.forEach((m, i) => { const t0 = 0.15 + i * 0.07, f = easeOut(range(t, t0, t0 + 0.3)), r = 0.78 * f; m.position.set(Math.cos(ang[i] + Math.PI / 2) * r * 0.62, Math.sin(ang[i] + Math.PI / 2) * r, 0.02 + i * 0.01); m.scale.setScalar(pop(t, t0, 0.3, 1.8)); const ck = checks[i]; ck.position.set(m.position.x + 0.22, m.position.y + 0.12, 0.2); ck.scale.setScalar(pop(t, t0 + 0.3, 0.2, 2.2)); });
    place(c, [0, 0, kf(t, [[0, 3.2], [0.9, 2.6]], easeOut)], [0, 0, 0], Math.sin(t * 6) * 0.02);
    return { bloom: 0.3 };
  } };
}
const Oo = dashShot('analytics.jpg', [[0, [700, 350, 1200]], [0.75, [420, 215, 640]]], { tilt: -0.07 });

// ---------------- the evening ----------------
function P({ makeStage }) { // golden hour, happy walk and a jump
  const scene = street(makeStage, { golden: true }), h = makeBlocky({ hoodie: 0x3c4b73 }); scene.add(h.root); const c = cam(40);
  return { scene, camera: c, update(t) {
    const x = lerp(-0.9, 0.7, t / 0.95); h.root.position.set(x, 0, 0.2); h.root.rotation.y = Math.PI / 2 - 0.2;
    const jump = Math.max(0, Math.sin(range(t, 0.6, 0.95) * Math.PI)) * 0.35; h.root.position.y = jump;
    walkPose(h, t, 0.9, { ...(t > 0.6 ? cheer(t) : { lSh: [Math.sin(t * 6.5) * 0.7, 0, 0.15], rSh: [-Math.sin(t * 6.5) * 0.7, 0, -0.15] }), smile: 1 });
    place(c, [x - 0.2, 0.9, 3.0], [x + 0.1, 0.95, 0.2]);
    return { dof: { focus: 3.0, aperture: 0.003, maxblur: 0.01 }, bloom: 0.55, exposure: 1.05 };
  } };
}
function Q(a) { const sh = s7(a); const u = sh.update; sh.update = t => u(t + 1.2); return sh; }

const D0 = (a, b) => b - a;
export const SHOTS = [
  [0.0, 0.8, A], [0.8, 1.4, B], [1.4, 2.4, C], [2.4, 3.3, D], [3.3, 4.4, E], [4.4, 5.4, F], [5.4, 6.4, G], [6.4, 7.75, Hh], [7.75, 8.7, I], [8.7, 9.6, Jj],
  [9.6, 10.4, K], [10.4, 11.2, Ll], [11.2, 12.0, Mm], [12.0, 12.9, Nn], [12.9, 13.65, Oo], [13.65, 14.6, P], [14.6, 16.0, Q],
].map(([start, end, b], i) => ({ start, end, build: wrap(b, end - start, i % 2 ? 1 : -1) })).concat([{ start: 16.0, end: DURATION + 1, build: s8 }]);

// exported for the week videos (shots_*.js)
export { street, bedroom, ledTex, std, rbox, room, windowPane, desk, laptop, lamp, typingPose, seat, pop, planeCard, wrap, lights, logoTex, listingTex, checkTex, bubbleTex, canvasTex, rr, gradTex, endTex, dashShot, K, Ll, Mm, Nn, Oo, F, parcel, walkPose, cheer, IMG, PLATFORMS, rnd, kitchen, s8, solveArms };
