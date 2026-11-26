// Stijl B: zacht cartoon-3D, rustige cinematische camera, warm licht, serif captions (renno-gevoel).
import { attic, bedroom, street, studio, hoodieProp, phoneProp, laptopProp } from '../sets.js';
export const style = 'toon';
export const hotWords = ['zonsopkomst', 'twaalf', 'veertig', 'Vierde', 'Dezelfde', 'keer', 'slaapt', 'negen'];

export async function build(K) {
  const { X, THREE, set, shot, actor, prop, label, cue, dolly, orbit, stat, pop, E, prog, lerp, liveTex, omniUI, endCard, sign, cl, coverTex, image } = K;
  const PI = Math.PI;
  const MAP = [0, 1, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 32, 33, 34, 35, 36, 37, 38, 40, 41, 43, 44, 45, 47, 48, 49, 50, 51, 52, 53, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 66, 67, 68, 69]; const W = i => K.W(MAP[Math.min(i, MAP.length - 1)]);
  const night = { wall: '#3b4170', floor: '#5a4638', sky: '#101c42', skyL: '#8a9ce0', sunC: '#9fb2ff', sunI: .9, hemi: .6, lamp: '#ffd8a0', blanket: '#e07a3d', rug: '#9a4a3a' };
  set('dawn', (X, g) => { street(X, g, { sky: '#ffb88a', sunC: '#ffb060', sunI: 2.8, wall: '#f3d7b5', grass: '#8ccf6a', sun: [-8, 3.2, 6], skyL: '#ffd6b0' }); return { bg: '#ffb98c', fog: ['#ffc79c', 14, 50] }; });
  set('night', (X, g) => { attic(X, g, night); const pl = new THREE.PointLight('#ffb870', 14, 9, 1.6); pl.position.set(1.6, 1.7, -1.9); g.add(pl); return { bg: '#0b1230', fog: ['#0b1230', 10, 30] }; });
  set('bednight', (X, g) => { bedroom(X, g, night); const pl = new THREE.PointLight('#8aa0ff', 10, 9, 1.6); pl.position.set(1.8, 2.2, -2.2); g.add(pl); return { bg: '#0b1230' }; });
  set('calm', (X, g) => { studio(X, g, { wall: '#f6c9a0', floor: '#efe0c8' }); X.box(g, [1.8, .1, 1.1], [0, .82, -.2], '#d9b98a'); [[-.8, -.45], [.8, -.45], [-.8, .45], [.8, .45]].forEach(([a, b]) => X.box(g, [.1, .8, .1], [a, .4, -.2 + b], '#a47c48')); return { bg: '#f6c9a0' }; });

  const hero = actor({ skin: '#e0ac85', shirt: '#1f2a55', pants: '#2a2f45', hairStyle: 'short', sleeves: true });
  const hood = prop(hoodieProp(X, '#3c4b73', 1.05)); hood.rotation.order = 'YXZ';
  const dTex = coverTex(await image('assets/items-crosslisted.webp'), .92 / .56), pTex = await image('assets/platforms-connected.webp');
  const panel = prop(new THREE.Mesh(new THREE.PlaneGeometry(2.7, 2.7 * 633 / 1200), new THREE.MeshBasicMaterial({ map: pTex })));
  const lap = prop(laptopProp(X, null, 1)); const ph = prop(phoneProp(X, null, 1.7));
  const type = liveTex(512, 312, (x, w, h, n) => { x.fillStyle = '#fff'; x.fillRect(0, 0, w, h); x.fillStyle = '#09b1ba'; x.fillRect(0, 0, w, h * .16); x.fillStyle = '#fff'; x.font = '900 34px Montserrat'; x.textBaseline = 'middle'; x.fillText('Nieuwe advertentie', 20, h * .08); x.fillStyle = '#0a1936'; x.font = '800 30px Montserrat'; const s = 'Vintage blauwe hoodie, maat M, als nieuw'.slice(0, Math.floor(n)); x.fillText(s + (Math.floor(n * 2) % 2 ? '|' : ''), 20, h * .38); x.fillStyle = '#c8d0de'; x.fillRect(20, h * .55, w - 40, 14); x.fillRect(20, h * .65, w * .7, 14); x.fillRect(20, h * .75, w * .5, 14); });
  const photos = liveTex(512, 900, (x, w, h) => { x.fillStyle = '#f4f7fb'; x.fillRect(0, 0, w, h); x.fillStyle = '#0a1936'; x.font = '900 46px Montserrat'; x.fillText("Foto's", 30, 60); [0, 1, 2, 3, 4, 5].forEach(i => { const cx = 30 + (i % 2) * 235, cy = 110 + Math.floor(i / 2) * 250; x.fillStyle = '#dfe6f2'; x.beginPath(); x.roundRect(cx, cy, 217, 230, 18); x.fill(); x.fillStyle = '#3c4b73'; x.beginPath(); x.roundRect(cx + 50, cy + 60, 117, 130, 18); x.fill(); x.fillRect(cx + 20, cy + 70, 40, 90); x.fillRect(cx + 157, cy + 70, 40, 90); x.beginPath(); x.arc(cx + 108, cy + 55, 26, 0, 7); x.fill(); }); });
  const clock = liveTex(512, 256, (x, w, h, s) => { x.fillStyle = '#12080a'; x.fillRect(0, 0, w, h); x.fillStyle = s.c || '#ff3b30'; x.font = '900 150px Montserrat'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(s.t, w / 2, h / 2 + 6); });
  const clockMesh = prop(new THREE.Mesh(new THREE.PlaneGeometry(1.4, .7), new THREE.MeshBasicMaterial({ map: clock.tex })));
  const phUI = liveTex(512, 900, (x, w, h, p) => omniUI(x, w, h, p));
  const lbl = ['Vinted', 'Marktplaats', 'eBay', 'Eigen shop'].map((n, i) => label(n, { h: .5, bg: ['#09b1ba', '#2f6fe0', '#e53238', '#6b46c1'][i], fg: '#fff' }));
  const lblOk = ['Vinted  ✓', 'Marktplaats  ✓', 'eBay  ✓', 'Eigen shop  ✓'].map((n, i) => label(n, { h: .5, bg: '#1faa6b', fg: '#fff' }));
  const zzz = label('Z z z', { h: .5, bg: null, fg: '#cfd8ff' });
  const scr = (o, tex) => { const m = o.userData.screen.material; if (m.map !== tex) { m.map = tex; m.needsUpdate = true; } };
  const t = (i, off = 0) => Math.max(0, W(i) + off);
  const sh = (i, s, cam, fn, o, off = -.05) => shot(t(i, off), s, cam, fn, o);
  const dim = (T, t0, d) => cl((T - t0) / d);

  // 1 Nooit een zonsopkomst overgeslagen (rennen in ochtendlicht)
  sh(0, 'dawn', dolly([-1.5, .45, 6], [1.5, .55, 5.6], [0, 1.3, 0], [0, 1.3, 0], 46, 0, 0), (lt, T, a) => { a.put(hero, [-3.4 + lt * 3.0, 0, 0], PI / 2, 'run', lt); }, {}, 0);
  // 2 Maar vannacht: het is twaalf uur veertig
  sh(5, 'night', dolly([4.6, 2.0, 6.2], [3.2, 1.7, 3.6], [1.0, 1.2, -2.2], [1.2, 1.2, -2.2], 50, 0, 0), (lt, T, a) => { a.put(hero, [1.2, 0, -1.7], PI, 'type', lt, { sit: 1 }); a.at(lap, 1.6, .87, -2.7); scr(lap, type.tex); type.draw(lt * 14); a.at(clockMesh, -.1, 2.35, -3.36); clock.draw({ t: '12:40' }); }, {});
  sh(8, 'night', dolly([-.2, 2.1, 1.6], [-.6, 2.2, .2], [-.1, 2.35, -3.36], [-.1, 2.35, -3.36], 36, -3, 2), (lt, T, a) => { a.at(clockMesh, -.1, 2.35, -3.36); clock.draw({ t: '12:40' }); }, {});
  cue(W(8), 'tick');
  sh(11, 'night', dolly([2.9, 1.85, -.3], [2.5, 1.7, -.8], [1.6, 1.2, -2.7], [1.6, 1.2, -2.7], 44, 4, 0), (lt, T, a) => { a.put(hero, [1.2, 0, -1.7], PI, 'type', lt, { sit: 1 }); a.at(lap, 1.6, .87, -2.7); type.draw(lt * 14); scr(lap, type.tex); }, { shake: .01 });
  sh(14, 'night', dolly([1.5, 1.25, -1.4], [1.6, 1.2, -1.9], [1.6, 1.15, -2.7], [1.6, 1.15, -2.7], 38, 0, 0), (lt, T, a) => { a.at(lap, 1.6, .87, -2.7); type.draw(14 + lt * 14); scr(lap, type.tex); }, {});
  // 3 Vierde app, dezelfde foto's, dezelfde beschrijving
  sh(17, 'night', orbit([1.6, 0, -2.2], 3.4, 1.9, .4, -.3, 46, 1.6), (lt, T, a) => { a.put(hero, [1.2, 0, -1.7], PI, 'type', lt, { sit: 1 }); a.at(lap, 1.6, .87, -2.7); lbl.forEach((l, i) => { a.at(l, 1.6, 1.9 + i * .38, -2.7); a.sc(l, pop(lt, i * .32, .3)); }); }, {});
  sh(19, 'night', dolly([-.6, 1.5, 1.2], [.2, 1.5, .4], [1.0, 1.35, -1.3], [1.0, 1.35, -1.3], 40, -4, 0), (lt, T, a) => { a.at(ph, 1.0, 1.35 + Math.sin(T * 1.5) * .04, -1.3, -.3); scr(ph, photos.tex); photos.draw(); }, {});
  sh(21, 'night', dolly([1.1, 1.6, .4], [1.2, 1.55, -.3], [1.2, 1.45, -1.7], [1.2, 1.4, -1.7], 34, 0, 3), (lt, T, a) => { a.put(hero, [1.2, 0, -1.7], 0, 'sad', lt, { sit: 1, eye: .55 }); }, {});
  // 4 Elk uur kopiëren is een uur niet verkopen
  const hrs = ['1:40', '2:40', '3:40'];
  sh(23, 'night', dolly([-.4, 2.1, 1.2], [-.9, 2.2, -.6], [-.1, 2.35, -3.36], [-.1, 2.35, -3.36], 40, 0, 0), (lt, T, a) => { a.at(clockMesh, -.1, 2.35, -3.36); clock.draw({ t: hrs[Math.min(2, Math.floor(lt / 1.3))] }); }, {});
  sh(28, 'night', orbit([-2.3, .2, -.7], 3, 1.6, -.6, .5, 46, .5), (lt, T, a) => { hood.rotation.x = -PI / 2; a.at(hood, -2.3, .3, -.7, .6); }, {});
  sh(33, 'night', dolly([1.2, 3.6, -.4], [1.5, 2.2, -.9], [1.4, .8, -2.2], [1.5, .9, -2.4], 50, 0, 0), (lt, T, a) => { a.put(hero, [1.2, 0, -1.7], PI, 'sleep', lt, { sit: 1, lean: .5 }); a.at(lap, 1.6, .87, -2.7); scr(lap, type.tex); type.draw(36); a.at(zzz, 1.2, 2.0 + Math.sin(T * 2) * .1, -1.7); }, {});
  // 5 Omnivaleur lost het op
  sh(34, 'calm', dolly([-2.4, 1.6, 4.2], [-1.0, 1.7, 3.2], [0, 1.2, -.2], [0, 1.3, -.2], 46, 0, 0), (lt, T, a) => { a.put(hero, [-.6, 0, 1.0], .35, 'point', lt); a.at(ph, .5, 1.5 + Math.sin(T * 1.7) * .05, .2, -.2); scr(ph, phUI.tex); phUI.draw({ sold: 0, rm: [0, 0, 0] }); }, {});
  cue(W(34), 'pop');
  sh(37, 'calm', dolly([1.4, 1.5, 1.6], [.9, 1.3, 1.0], [0, .95, -.2], [0, .95, -.2], 40, 0, 0), (lt, T, a) => { a.put(hero, [-1.2, 0, .5], .6, 'type', lt, {}); a.at(lap, 0, .87, -.2); lap.userData.lid.rotation.x = -.25; scr(lap, dTex); }, {});
  // 6 Live op vier kanalen, terwijl je slaapt
  sh(41, 'calm', dolly([-2.8, 1.4, 4.0], [2.8, 1.4, 4.0], [0, 1.5, 0], [0, 1.5, 0], 46, 0, 0, E.lin), (lt, T, a) => { [[45, -2.1], [46, -.7], [47, .7], [51, 2.1]].forEach(([wi, x], i) => { a.at(lblOk[i], x, 1.15 + (i % 2) * .4, .3); a.sc(lblOk[i], pop(T, t(wi, -.1), .3)); }); a.at(panel, 0, 2.55, -.6); a.put(hero, [0, 0, 1.4], 0, 'cheer', lt, {}); }, {});
  cue(W(45), 'ding'); cue(W(46), 'ding'); cue(W(47), 'ding'); cue(W(51), 'ding');
  sh(52, 'bednight', dolly([-.2, 2.0, 2.2], [-1.2, 1.7, 1.2], [-2.5, 1.0, -1.7], [-2.5, 1.0, -1.7], 46, 0, -4), (lt, T, a) => { a.put(hero, [-2.5, .95, -.4], 0, 'lie', lt, {}); a.at(zzz, -2.2, 2.0 + Math.sin(T * 2) * .1, -1.2); }, {});
  // 7 Laptop dicht om negen
  sh(55, 'calm', dolly([1.5, 1.5, 2.4], [.8, 1.2, 1.5], [0, .9, -.2], [0, .9, -.2], 40, 0, 0), (lt, T, a) => { a.at(lap, 0, .87, -.2); lap.userData.lid.rotation.x = lerp(-.25, 1.45, E.inOut(dim(lt, .5, .9))); scr(lap, type.tex); type.draw(36); a.put(hero, [-1.1, 0, .6], .5, 'idle', lt, {}); a.at(clockMesh, 0, 2.6, -2.4); clock.draw({ t: '9:00', c: '#6ee7b7' }); }, {});
  sh(59, 'calm', dolly([0, 1.2, 5.0], [0, 1.6, 4.0], [0, 2.4, 0], [0, 2.5, 0], 50, 0, 0), (lt, T, a) => { a.put(hero, [0, 0, 0], 0, 'wave', lt, {}); }, {}, -.1);
  endCard(t(59, -.1)); cue(t(59, -.1), 'pop');
}
