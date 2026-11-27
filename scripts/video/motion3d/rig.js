// 3D poppetje (blocky | toon | real). pose(name, t, extra) is een pure functie van t.
import * as THREE from 'three';
const PI = Math.PI, S = Math.sin, C = Math.cos;

export function matFactory(style) {
  const d = new Uint8Array([95, 175, 255]);
  const grad = new THREE.DataTexture(d, 3, 1, THREE.RedFormat); grad.minFilter = grad.magFilter = THREE.NearestFilter; grad.needsUpdate = true;
  return (c, o = {}) => {
    if (o.glow) return new THREE.MeshBasicMaterial({ color: c });
    if (style === 'blocky') return new THREE.MeshLambertMaterial({ color: c, flatShading: true });
    if (style === 'toon') return new THREE.MeshToonMaterial({ color: c, gradientMap: grad });
    return new THREE.MeshStandardMaterial({ color: c, roughness: .82, metalness: 0 });
  };
}

const BASE = { y: 0, bob: 0, lean: 0, tw: 0, hx: 0, hy: 0, hz: 0, lx: 0, lz: .1, le: -.1, rx: 0, rz: .1, re: -.1, ll: 0, lk: 0, rl: 0, rk: 0, eye: 1, brow: 0, mouth: .3, open: 0, lie: 0, sit: 0 };
export const ANIM = {
  idle: t => ({ bob: S(t * 2) * .012, lz: .1 + S(t * 1.7) * .03, rz: .1 + S(t * 1.9) * .03 }),
  walk: (t, sp = 1) => { const p = t * 6.5 * sp, a = S(p) * .7; return { y: Math.abs(S(p)) * .05, ll: a, rl: -a, lk: Math.max(0, -S(p)) * .9, rk: Math.max(0, S(p)) * .9, lx: -a * .8, rx: a * .8, le: -.3, re: -.3 }; },
  run: t => { const p = t * 11, a = S(p) * 1.05; return { y: Math.abs(S(p)) * .12, lean: .3, ll: a, rl: -a, lk: Math.max(0, -S(p)) * 1.5, rk: Math.max(0, S(p)) * 1.5, lx: -a, rx: a, le: -1.3, re: -1.3, mouth: -.2, open: .5 }; },
  wave: t => ({ rx: -PI + .5 + S(t * 3) * .1, rz: .5, re: -.2 + S(t * 11) * .7, mouth: .9, lz: .1, brow: -.1 }),
  panic: t => ({ lx: -2.7 + S(t * 20) * .25, rx: -2.7 + S(t * 21) * .25, lz: .55, rz: .55, le: -.4, re: -.4, eye: 1.3, brow: -.7, mouth: -.3, open: .9 + S(t * 18) * .1, hy: S(t * 19) * .12, y: Math.abs(S(t * 16)) * .04 }),
  type: t => ({ lx: -.95 + S(t * 22) * .08, rx: -.95 + S(t * 19) * .08, le: -1.2, re: -1.2, lz: .05, rz: .05, hx: .28, mouth: 0 }),
  angry: t => ({ lx: -1.1, rx: -1.1, le: -1.9, re: -1.9, lz: .1, rz: .1, brow: .6, mouth: -.8, open: .35 + S(t * 14) * .2, lean: .12, y: Math.abs(S(t * 13)) * .03, hy: S(t * 9) * .1 }),
  cheer: t => ({ lx: -2.8, rx: -2.8, lz: .6, rz: .6, le: -.2, re: -.2, y: Math.abs(S(t * 8)) * .28, mouth: 1, open: .7, brow: -.2, hz: S(t * 8) * .05 }),
  point: t => ({ rx: -1.55, re: -.05, rz: .05, lz: .55, le: -2.1, lx: .1, mouth: .2, lean: .05 }),
  shock: t => ({ lx: -.5, rx: -.5, lz: .4, rz: .4, le: -.9, re: -.9, eye: 1.45, brow: -.7, mouth: -.2, open: .8, hx: -.08, y: S(t * 30) * .006 }),
  think: t => ({ rx: -1.0, re: -2.3, rz: .1, hx: .1, hy: S(t * 1.2) * .2, mouth: 0, brow: .15 }),
  shrug: t => ({ lz: .8, rz: .8, le: -1.2, re: -1.2, lx: -.4, rx: -.4, brow: -.4, mouth: -.4, hz: .12 }),
  carry: t => ({ lx: -1.2, rx: -1.2, le: -.6, re: -.6, lz: .12, rz: .12 }),
  phone: t => ({ rx: -1.15, re: -1.6, rz: .0, lx: .05, hx: .22, mouth: 0, eye: .95 }),
  fight: t => ({ lx: -1.5 + S(t * 12) * .6, rx: -1.5 - S(t * 12) * .6, le: -1.6, re: -1.6, brow: .7, mouth: -.8, open: .5, lean: .25, ll: S(t * 6) * .3, rl: -S(t * 6) * .3, y: Math.abs(S(t * 6)) * .06 }),
  sad: t => ({ hx: .45, lean: .15, lx: .1, rx: .1, mouth: -.8, brow: -.5, eye: .8 }),
  laugh: t => ({ hx: -.2, mouth: 1, open: .9, y: Math.abs(S(t * 12)) * .05, lz: .3, rz: .3, brow: -.15 }),
  sleep: t => ({ hx: .5, eye: .08, mouth: 0, bob: S(t * 1.5) * .01 }),
  clap: t => ({ lx: -1.3, rx: -1.3, le: -1.4 + S(t * 14) * .3, re: -1.4 + S(t * 14) * .3, lz: .12 - S(t * 14) * .1, rz: .12 - S(t * 14) * .1, mouth: 1, open: .4 }),
  lie: t => ({ lie: 1, eye: .15, mouth: 0, lz: .2, rz: .2 }),
  sneak: t => { const p = t * 4, a = S(p) * .5; return { y: -.08, ll: a, rl: -a, lk: .6, rk: .6, lx: -a, rx: a, hx: .1, lean: .15, eye: 1.1, brow: .2 }; },
};

export function makeChar(style, o = {}) {
  const { skin = '#f1c3a0', shirt = '#3c4b73', pants = '#2a2f45', hair = '#2a1d16', hairStyle = 'short', shoe = '#1b1b1f', sleeves = true, scale = 1, cap = '#e8872a', tall = 1 } = o;
  const M = matFactory(style), rounded = style !== 'blocky';
  const root = new THREE.Group(), body = new THREE.Group(); root.add(body);
  const mesh = (g, geo, c, x = 0, y = 0, z = 0) => { const m = new THREE.Mesh(geo, M(c)); m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = false; g.add(m); return m; };
  const limb = (g, w, l, c) => mesh(g, rounded ? new THREE.CapsuleGeometry(w / 2, Math.max(.01, l - w), 4, 12) : new THREE.BoxGeometry(w, l, w * (style === 'blocky' ? 1 : 1)), c, 0, -l / 2, 0);
  const hips = new THREE.Group(); hips.position.y = .92 * tall; body.add(hips);
  const torso = new THREE.Group(); hips.add(torso);
  if (rounded) { const t = mesh(torso, new THREE.CapsuleGeometry(.25, .44, 6, 16), shirt, 0, .31, 0); t.scale.z = .72; } else mesh(torso, new THREE.BoxGeometry(.58, .66, .36), shirt, 0, .32, 0);
  mesh(hips, new THREE.BoxGeometry(.5, .2, .32), pants, 0, -.02, 0);
  const legs = [1, -1].map(sx => {
    const lg = new THREE.Group(); lg.position.set(sx * .14, 0, 0); hips.add(lg);
    limb(lg, .21, .46, pants); const kn = new THREE.Group(); kn.position.y = -.46; lg.add(kn);
    limb(kn, .2, .46 * tall, pants); mesh(kn, new THREE.BoxGeometry(.2, .1, .32), shoe, 0, -.46 * tall + .02, .06);
    return { lg, kn };
  });
  const arms = [1, -1].map(sx => {
    const ar = new THREE.Group(); ar.position.set(sx * (rounded ? .34 : .39), .56, 0); torso.add(ar);
    limb(ar, .17, .38, shirt); const el = new THREE.Group(); el.position.y = -.38; ar.add(el);
    limb(el, .15, .34, sleeves ? shirt : skin); mesh(el, rounded ? new THREE.SphereGeometry(.085, 12, 10) : new THREE.BoxGeometry(.15, .15, .15), skin, 0, -.36, 0);
    return { ar, el, sx };
  });
  const head = new THREE.Group(); head.position.y = .72; torso.add(head);
  const hr = rounded ? .29 : .27;
  mesh(head, rounded ? new THREE.SphereGeometry(hr, 28, 20) : new THREE.BoxGeometry(.52, .52, .5), skin, 0, .28, 0);
  const hairMat = c => c;
  if (hairStyle === 'short') mesh(head, rounded ? new THREE.SphereGeometry(hr + .02, 24, 12, 0, PI * 2, 0, PI * .5) : new THREE.BoxGeometry(.54, .16, .52), hair, 0, rounded ? .29 : .52, rounded ? -.02 : 0);
  if (hairStyle === 'bun') { mesh(head, rounded ? new THREE.SphereGeometry(hr + .02, 24, 12, 0, PI * 2, 0, PI * .5) : new THREE.BoxGeometry(.54, .16, .52), hair, 0, rounded ? .29 : .52, rounded ? -.02 : 0); mesh(head, new THREE.SphereGeometry(.12, 12, 10), hair, 0, .62, -.04); }
  if (hairStyle === 'cap') { mesh(head, rounded ? new THREE.SphereGeometry(hr + .03, 24, 12, 0, PI * 2, 0, PI * .5) : new THREE.BoxGeometry(.55, .16, .53), cap, 0, rounded ? .29 : .52, 0); mesh(head, new THREE.BoxGeometry(.4, .03, .26), cap, 0, rounded ? .33 : .5, .34); }
  if (hairStyle === 'beanie') { mesh(head, rounded ? new THREE.SphereGeometry(hr + .03, 24, 12, 0, PI * 2, 0, PI * .55) : new THREE.BoxGeometry(.56, .22, .54), '#c43c4a', 0, rounded ? .29 : .52, 0); mesh(head, new THREE.SphereGeometry(.06, 10, 8), '#f4d9dc', 0, .62, 0); }
  if (hairStyle === 'long') { mesh(head, rounded ? new THREE.SphereGeometry(hr + .02, 24, 12, 0, PI * 2, 0, PI * .5) : new THREE.BoxGeometry(.54, .16, .52), hair, 0, rounded ? .29 : .52, 0); mesh(head, new THREE.BoxGeometry(.5, .5, .1), hair, 0, .1, -.22); }
  if (hairStyle === 'curly') { for (let i = 0; i < 7; i++) { const a = i / 7 * PI * 2; mesh(head, new THREE.SphereGeometry(.12, 10, 8), hair, Math.cos(a) * .2, .5 + Math.sin(i * 2) * .04, Math.sin(a) * .2 - .02); } mesh(head, new THREE.SphereGeometry(.18, 12, 10), hair, 0, .56, 0); }
  const eyes = [1, -1].map(sx => {
    const e = new THREE.Group(); e.position.set(sx * .1, .31, hr - .02 + (rounded ? 0 : .0)); head.add(e);
    if (rounded) { const w = mesh(e, new THREE.SphereGeometry(.058, 12, 10), '#ffffff'); w.scale.set(1, 1.25, .55); w.castShadow = false; const p = mesh(e, new THREE.SphereGeometry(.032, 10, 8), '#14141a', 0, 0, .026); p.castShadow = false; }
    else { const p = mesh(e, new THREE.BoxGeometry(.075, .11, .03), '#14141a', 0, 0, .13); p.castShadow = false; e.position.z = .12; }
    return e;
  });
  const brows = [1, -1].map(sx => { const b = new THREE.Group(); b.position.set(sx * .1, .42, hr + (rounded ? 0 : .13)); head.add(b); const m = mesh(b, new THREE.BoxGeometry(.1, .025, .02), hair === '#ffffff' ? '#333' : (hairStyle === 'none' ? '#3a2a22' : hair)); m.castShadow = false; return { b, sx }; });
  const mouthG = new THREE.Group(); mouthG.position.set(0, .1, hr + (rounded ? 0 : .13)); head.add(mouthG);
  const arc = mesh(mouthG, new THREE.TorusGeometry(.07, .014, 6, 18, PI), '#4a1f1f'); arc.castShadow = false;
  const openM = mesh(mouthG, new THREE.SphereGeometry(.07, 12, 8), '#5a1520', 0, -.01, -.01); openM.castShadow = false;
  const mk = (g, x, y, z) => { const o = new THREE.Object3D(); o.position.set(x, y, z); g.add(o); return o; };
  root.userData.pts = { head: mk(head, 0, .28, 0), torso: mk(torso, 0, .32, 0), hips: mk(hips, 0, 0, 0), handL: mk(arms[0].el, 0, -.36, 0), handR: mk(arms[1].el, 0, -.36, 0) };
  root.scale.setScalar(scale);

  root.pose = (name, t = 0, extra = {}) => {
    const f = ANIM[name]; const q = { ...BASE, ...(f ? f(t) : {}), ...extra };
    const sit = q.sit;
    body.position.y = q.y + q.bob + (q.lie ? .18 : 0); body.rotation.set(-PI / 2 * q.lie, 0, 0);
    hips.position.y = (.92 * tall) - sit * .4 * tall;
    torso.rotation.set(q.lean, q.tw, 0);
    head.rotation.set(q.hx, q.hy, q.hz);
    arms.forEach(a => {
      const L = a.sx > 0, x = L ? q.lx : q.rx, z = L ? q.lz : q.rz, e = L ? q.le : q.re;
      a.ar.rotation.set(x, 0, a.sx * z); a.el.rotation.set(e, 0, 0);
    });
    const ll = q.ll * (1 - sit) + (-PI / 2 + .1) * sit, rl = q.rl * (1 - sit) + (-PI / 2 + .1) * sit, lk = q.lk * (1 - sit) + (PI / 2 - .1) * sit, rk = q.rk * (1 - sit) + (PI / 2 - .1) * sit;
    legs[0].lg.rotation.x = ll; legs[0].kn.rotation.x = lk; legs[1].lg.rotation.x = rl; legs[1].kn.rotation.x = rk;
    const blink = (t % 3.3) > 3.2 ? .1 : 1;
    eyes.forEach(e => e.scale.set(1, Math.max(.06, q.eye * blink), 1));
    brows.forEach(({ b, sx }) => { b.rotation.z = -sx * q.brow * .55; b.position.y = .42 + (q.brow < 0 ? -q.brow * .04 : 0); });
    arc.rotation.z = q.mouth >= 0 ? PI : 0; arc.scale.set(1, Math.abs(q.mouth) * 1 + .02, 1); arc.visible = q.open < .25;
    openM.visible = q.open >= .25; openM.scale.set(rounded ? 1 : 1.7, .15 + q.open * .75, .4);
  };
  root.pose('idle', 0);
  return root;
}
