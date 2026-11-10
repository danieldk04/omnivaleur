import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

// Blocky little person in the style of the renno.app reels: round head, boxy hoodie body, big calm eyes.
const std = (color, rough = 0.78) => new THREE.MeshStandardMaterial({ color, roughness: rough });
const rbox = (w, h, d, r, mat) => { const m = new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 4, r), mat); m.castShadow = true; m.receiveShadow = true; return m; };

export function makeBlocky({ hoodie = 0x3c4b73, pants = 0x20232e, hair = 0x14141a, skin = 0xc98a64, shoes = 0xe9eaf0 } = {}) {
  const root = new THREE.Group();
  const hip = new THREE.Group(); hip.position.y = 0.82; root.add(hip);          // pelvis pivot
  const M = { hoodie: std(hoodie), pants: std(pants), skin: std(skin, 0.6), hair: std(hair, 0.9), shoe: std(shoes, 0.5) };

  const torso = new THREE.Group(); hip.add(torso);
  const body = rbox(0.56, 0.66, 0.34, 0.1, M.hoodie); body.position.y = 0.33; torso.add(body);
  const pocket = rbox(0.34, 0.14, 0.03, 0.02, std(new THREE.Color(hoodie).multiplyScalar(0.8).getHex())); pocket.position.set(0, 0.16, 0.18); torso.add(pocket);

  const neck = new THREE.Group(); neck.position.y = 0.68; torso.add(neck);
  const head = new THREE.Group(); head.position.y = 0.2; neck.add(head);
  const skull = new THREE.Mesh(new THREE.SphereGeometry(0.255, 40, 28), M.skin); skull.scale.set(1, 1.02, 0.96); skull.castShadow = true; head.add(skull);
  const cap = new THREE.Mesh(new THREE.SphereGeometry(0.268, 40, 20, 0, Math.PI * 2, 0, Math.PI * 0.36), M.hair); cap.position.set(0, 0.015, -0.03); cap.castShadow = true; head.add(cap);
  const fringe = rbox(0.4, 0.07, 0.1, 0.03, M.hair); fringe.position.set(0, 0.165, 0.15); head.add(fringe);
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x0b0b10, roughness: 0.25 });
  const eyes = [];
  for (const s of [-1, 1]) {
    const e = new THREE.Mesh(new THREE.SphereGeometry(0.03, 16, 12), eyeMat); e.scale.set(0.9, 1.3, 0.5); e.position.set(s * 0.09, 0.0, 0.235); head.add(e); eyes.push(e);
  }
  const mouth = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.013, 0.01), new THREE.MeshStandardMaterial({ color: 0x3a1a14 })); mouth.position.set(0, -0.085, 0.245); head.add(mouth);
  const ear = s => { const m = new THREE.Mesh(new THREE.SphereGeometry(0.05, 12, 10), M.skin); m.scale.set(0.5, 1, 0.8); m.position.set(s * 0.255, -0.01, 0); head.add(m); };
  ear(-1); ear(1);

  const arm = s => {
    const sh = new THREE.Group(); sh.position.set(s * 0.37, 0.58, 0); torso.add(sh);
    const up = rbox(0.17, 0.42, 0.18, 0.07, M.hoodie); up.position.y = -0.18; sh.add(up);
    const el = new THREE.Group(); el.position.y = -0.38; sh.add(el);
    const lo = rbox(0.16, 0.38, 0.17, 0.07, M.hoodie); lo.position.y = -0.14; el.add(lo);
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 12), M.skin); hand.position.y = -0.36; hand.castShadow = true; el.add(hand);
    return { sh, el, hand };
  };
  const leg = s => {
    const hp = new THREE.Group(); hp.position.set(s * 0.15, 0, 0); hip.add(hp);
    const up = rbox(0.22, 0.45, 0.24, 0.08, M.pants); up.position.y = -0.2; hp.add(up);
    const kn = new THREE.Group(); kn.position.y = -0.4; hp.add(kn);
    const lo = rbox(0.21, 0.42, 0.23, 0.08, M.pants); lo.position.y = -0.18; kn.add(lo);
    const foot = rbox(0.24, 0.13, 0.36, 0.06, M.shoe); foot.position.set(0, -0.4, 0.06); kn.add(foot);
    return { hp, kn };
  };
  const L = arm(-1), R = arm(1), LL = leg(-1), RL = leg(1);

  const set = (o, v) => { if (v) o.rotation.set(v[0] || 0, v[1] || 0, v[2] || 0); };
  // pose({ hip:[x,y,z], drop, torso, neck, head, lSh, lEl, rSh, rEl, lHip, lKn, rHip, rKn, blink, mouth })
  function pose(p = {}) {
    hip.position.y = 0.82 - (p.drop || 0);
    set(hip, p.hip || [0, 0, 0]); set(torso, p.torso || [0, 0, 0]); set(neck, p.neck || [0, 0, 0]); set(head, p.head || [0, 0, 0]);
    set(L.sh, p.lSh || [0, 0, 0.06]); set(L.el, p.lEl || [-0.1, 0, 0]); set(R.sh, p.rSh || [0, 0, -0.06]); set(R.el, p.rEl || [-0.1, 0, 0]);
    set(LL.hp, p.lHip || [0, 0, 0]); set(LL.kn, p.lKn || [0, 0, 0]); set(RL.hp, p.rHip || [0, 0, 0]); set(RL.kn, p.rKn || [0, 0, 0]);
    const b = p.blink ? 0.12 : 1; eyes.forEach(e => (e.scale.y = 1.3 * b));
    mouth.scale.set(1 + (p.smile || 0) * 0.6, 1 + (p.mouth || 0) * 14, 1);
    mouth.position.y = -0.085 + (p.smile || 0) * 0.01;
  }
  pose();
  const wp = o => o.getWorldPosition(new THREE.Vector3());
  function points() { // body samples for the clipping test: [name, world point, radius]
    root.updateMatrixWorld(true); const out = [];
    for (const [n, a] of [['L', L], ['R', R]]) {
      const hp = wp(a.hand), ep = wp(a.el), sp = wp(a.sh);
      out.push([n + 'hand', hp, 0.09], [n + 'elbow', ep, 0.08], [n + 'forearm', ep.clone().lerp(hp, 0.5), 0.08], [n + 'upper', sp.clone().lerp(ep, 0.5), 0.08]);
    }
    out.push(['head', wp(head), 0.25], ['chest', wp(torso).add(new THREE.Vector3(0, 0.33, 0).applyQuaternion(torso.getWorldQuaternion(new THREE.Quaternion()))), 0.2]);
    return out;
  }
  root.userData.points = points;
  return { points, root, hip, torso, head, L, R, LL, RL, pose, M };
}
