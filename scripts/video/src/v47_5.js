import { shot, cm, put, person, P, SKIN, typer, walker, finale, logoCard, bubble, tag, sign, hoodieFace, buyer, montage, PL, PL5, K, Ll, Mm, Nn, Oo, kinetic, soldPoof, hoodieChar, planeCard, stampTex, pop, lerp, kf, easeOut, easeInOut, range, typingPose, seat, walkPose, cheer, parcel, rbox, std, laptop, THREE, cookingStage, plate, steam, labelTex, listingTex, makeBlocky } from './week47b.js';
export { CAPTIONS, DURATION } from './cap.js';
import { DURATION, LINES } from './cap.js';
export const FADES = [];

const BL = 0x3c4b73, PK = 0xe58aa8, OR = 0xe8872a;
const A0 = typer({ hoodie: BL, clock: '00:12', slump: 0.6, cam: [[0.4, 1.45, 3.6], [0, 1.4, 2.9], [0, 1.45, 0.3]] });
const A1 = shot('living', S => { S.a = person({ hoodie: BL }); put(S, S.a, -0.4, -0.15, 0.2); S.b = person({ hoodie: PK, hair: 0x5a3a2a, skin: SKIN.b, bun: true }); put(S, S.b, 0.45, -0.15, -0.2); },
  (t, S) => { P.lean(S.a, t, { drop: 0.3 }); P.lean(S.b, t + 1, { drop: 0.3 }); cm(S, t, [0.5, 1.2, 3.8], [0, 1.2, 3.2], [0, 0.9, -0.2], 2.0); }, { fov: 42 });
const B1 = typer({ hoodie: BL, cards: true, clock: '00:00', logos: PL, gap: 0.3, cam: [[0.5, 1.5, 3.8], [-0.1, 1.45, 2.8], [0, 1.55, 0.3]] });
const B2 = typer({ hoodie: BL, clock: '00:00', slump: 0.1, tag: ['still listing', 0.3, { bg: '#ff6b6b', fg: '#fff' }], cam: [[0.3, 1.45, 3.4], [0.2, 1.3, 2.7], [0.1, 1.4, 0.3]] });
const C1 = shot('night', S => { S.lap = laptop(S.scene, { glow: 0.9 }); S.me = person({ hoodie: BL }); seat(S.me); S.scene.add(S.me.root); S.l = PL.map((k, i) => logoCard(S, k, -0.9 + i * 0.6, 2.2, 0.5, 0.1 + i * 0.1, 0.5, 0.31)); S.tg = tag(S, 'Added once', 0.0, 2.5, 0.6, 0.6, { bg: '#7dffc4', fg: '#0b1530' }); },
  (t, S) => { const k = Math.min(1, Math.max(0, (t - 1.2) / 0.4)); S.lap.userData.lid.rotation.x = lerp(0.22, -1.45, k); if (t < 1.2) typingPose(S.me, t * 1.6, { head: [0.1, 0, 0] }); else P.lean(S.me, t, { torso: [-0.25, 0, 0] }); S.l.forEach(f => f(t)); S.tg(t); cm(S, t, [0.5, 1.5, 3.8], [0, 1.5, 3.2], [0, 1.5, 0.3], 2.2); }, { fov: 40 });
const C2 = shot('living', S => { S.a = person({ hoodie: BL }); put(S, S.a, 0, 0.2); },
  (t, S) => { S.a.pose({ ...cheer(t), drop: -Math.abs(Math.sin(t * 6)) * 0.12 }); cm(S, t, [0.3, 1.2, 4.0], [0, 1.4, 3.2], [0, 1.4, 0.2], 1.4); }, { fov: 44 });
const D1 = A1;
const D2 = typer({ hoodie: BL, clock: '00:47', slump: 0.1, cam: [[0.3, 1.45, 3.4], [0.2, 1.3, 2.7], [0.1, 1.4, 0.3]] });
const D3 = walker({ hoodie: BL, golden: true, walkT: 1.2, end: (h, t) => P.idle(h, t, { ...cheer(t) }), zEnd: 0.3 });
const E = shot('living', S => { S.a = person({ hoodie: BL }); put(S, S.a, -0.5, 0.3, 0.3); S.b = person({ hoodie: PK, hair: 0x5a3a2a, skin: SKIN.b, bun: true }); put(S, S.b, 0.5, 0.3, -0.3); S.l = PL.map((k, i) => logoCard(S, k, -0.9 + i * 0.6, 2.35, 0.3, 0.1 + i * 0.12, 0.5, 0.31)); },
  (t, S) => { S.a.pose({ ...cheer(t), drop: -Math.abs(Math.sin(t * 6)) * 0.12 }); S.b.pose({ ...cheer(t + 1), drop: -Math.abs(Math.sin(t * 6 + 1)) * 0.12 }); S.l.forEach(f => f(t)); cm(S, t, [0.3, 1.2, 4.2], [0, 1.4, 3.4], [0, 1.4, 0.2], 2.0); }, { fov: 44 });
const END = shot('living', S => { S.a = person({ hoodie: BL }); put(S, S.a, -0.4, -0.15, 0.2); S.b = person({ hoodie: PK, hair: 0x5a3a2a, skin: SKIN.b, bun: true }); put(S, S.b, 0.45, -0.15, -0.2); S.sg = sign(S, 0, 2.1, 0.3, 0.3); },
  (t, S) => { P.lean(S.a, t, { drop: 0.3 }); P.lean(S.b, t + 1, { drop: 0.3 }); S.sg(t); cm(S, t, [0.4, 1.3, 4.0], [0, 1.3, 3.3], [0, 1.2, -0.2], 2.6, easeOut); }, { fov: 42, bloom: 0.7 });
export const SHOTS = montage([[0, A0], [0.5, A1], [1, B1], [1.6, B2], [2, C1], [2.55, Mm], [3, A1], [3.35, D2], [3.7, C2], [4, E]], LINES, DURATION, END);
