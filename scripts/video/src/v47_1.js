import { shot, cm, put, person, P, SKIN, typer, walker, finale, logoCard, bubble, tag, sign, hoodieFace, buyer, montage, PL, PL5, K, Ll, Mm, Nn, Oo, kinetic, soldPoof, hoodieChar, planeCard, stampTex, pop, lerp, kf, easeOut, easeInOut, range, typingPose, seat, walkPose, cheer, parcel, rbox, std, laptop, THREE, cookingStage, plate, steam, labelTex, listingTex, makeBlocky } from './week47b.js';
export { CAPTIONS, DURATION } from './cap.js';
import { DURATION, LINES } from './cap.js';
export const FADES = [];

const A0 = walker({ hoodie: 0x3c4b73, parcel: true, walkT: 1.0 });
const A1 = typer({ hoodie: 0xe58aa8, hair: 0x5a3a2a, skin: SKIN.b, bun: true, logo: 'vinted.png', logos: ['marktplaats.png', 'ebay.webp', 'shopify.webp'], cam: [[0.6, 1.5, 3.8], [0, 1.45, 3.0], [0, 1.55, 0.3]] });
const B1 = typer({ hoodie: 0x2f6f7a, hair: 0x14141a, skin: SKIN.c, cap: 0xe8872a, logo: 'marktplaats.png', cam: [[-0.7, 1.4, 3.0], [-0.2, 1.5, 2.4], [0, 1.45, 0.3]], fov: 36 });
const B2 = shot('kitchen', S => { S.h = person({ hoodie: 0x5b7f5d, hair: 0x3a2a1a, skin: SKIN.d, glasses: true }); put(S, S.h, 0, -0.35); S.ps = []; for (let i = 0; i < 5; i++) { const p = parcel(0.3, 0.2, 0.24); S.scene.add(p); S.ps.push(p); } S.lg = logoCard(S, 'ebay.webp', 0.55, 1.75, 0.5, 0.2, 0.55, 0.34); },
  (t, S) => { const k1 = Math.sin(t * 15) * 0.18, k2 = Math.sin(t * 15 + 2) * 0.18; S.h.pose({ torso: [0.22, 0, 0], neck: [0.1, 0, 0], head: [0.05, Math.sin(t * 7) * 0.12, 0], lSh: [-0.95 + k1, 0, 0.2], rSh: [-0.95 + k2, 0, -0.2], lEl: [-0.9, 0, 0], rEl: [-0.9, 0, 0] });
    S.ps.forEach((p, i) => { const f = easeOut(range(t, i * 0.14, i * 0.14 + 0.22)); p.position.set(lerp(1.5, -0.6 + (i % 4) * 0.4, f), lerp(1.2, 0.83 + Math.floor(i / 4) * 0.24, f), 0.7); p.scale.setScalar(pop(t, i * 0.14, 0.2, 1.2)); }); S.lg(t); cm(S, t, [0.2, 0.9, 3.2], [-0.1, 1.45, 2.2], [0, 1.1, 0.2], 1.1); }, { fov: 42 });
const B3 = walker({ hoodie: 0x6b4630, hair: 0x14141a, skin: SKIN.e, parcel: true, logo: 'shopify.webp', walkT: 0.8 });
const C = typer({ hoodie: 0x3c4b73, bubble: 'Nike Tech Fleece · M · €68', cards: true, cam: [[0.5, 1.5, 3.8], [-0.1, 1.45, 2.8], [0, 1.55, 0.3]] });
const D = typer({ hoodie: 0x3c4b73, clock: '00:47', slump: 0.3, tag: ['GONE', 0.9, { bg: '#ff6b6b', fg: '#fff' }], cam: [[0.3, 1.45, 3.4], [0.2, 1.3, 2.7], [0.1, 1.4, 0.3]] });
const E = shot('living', S => { S.a = person({ hoodie: 0x3c4b73 }); put(S, S.a, 0, 0.2); S.l = PL.map((k, i) => logoCard(S, k, -0.9 + i * 0.6, 2.35, 0.3, 0.1 + i * 0.12, 0.5, 0.31)); },
  (t, S) => { S.a.pose({ ...cheer(t), drop: -Math.abs(Math.sin(t * 6)) * 0.12 }); S.l.forEach(f => f(t)); cm(S, t, [0.3, 1.2, 4.0], [0, 1.4, 3.2], [0, 1.4, 0.2], 1.4); }, { fov: 44 });
const F = shot('living', S => { S.a = person({ hoodie: 0x3c4b73 }); put(S, S.a, -0.4, -0.15, 0.2); S.b = person({ hoodie: 0xe58aa8, hair: 0x5a3a2a, skin: SKIN.b, bun: true }); put(S, S.b, 0.45, -0.15, -0.2); },
  (t, S) => { P.lean(S.a, t, { lHip: [-1.5, 0.05, 0], drop: 0.3 }); P.lean(S.b, t + 1, { drop: 0.3 }); cm(S, t, [0.5, 1.2, 3.8], [0, 1.2, 3.2], [0, 0.9, -0.2], 2.0); }, { fov: 42 });
const END = finale('golden', [{ x: -0.8, hoodie: 0x3c4b73 }, { x: 0, hoodie: 0xe58aa8, hair: 0x5a3a2a, skin: SKIN.b, bun: true }, { x: 0.8, hoodie: 0x2f6f7a, cap: 0xe8872a, skin: SKIN.c }], { sy: 2.3, logos: PL });
export const SHOTS = montage([[0, A0], [0.5, A1], [1, B1], [1.35, B2], [1.7, B3], [2, C], [3, D], [4, K], [4.35, Mm], [4.7, E], [5, F]], LINES, DURATION, END);
