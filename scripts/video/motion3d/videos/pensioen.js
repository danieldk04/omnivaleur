// NL, stijl B (zacht cartoon), tijdsprong-grap met droge verteller: Sven en de elf dagen per jaar.
import { attic, street, studio, hoodieProp, phoneProp, laptopProp } from '../sets.js';
export const style = 'toon';
export const hotWords = ['Elf', 'vijf', 'uur', 'Tweeduizend', 'zeshonderd', 'baard', 'Omnivaleur', 'buiten', 'gratis', 'dezelfde', 'tien'];

export async function build(K) {
  const { X, THREE, set, shot, actor, prop, label, W, cue, dolly, orbit, stat, pop, E, prog, lerp, liveTex, omniUI, endCard, cl, image, coverTex } = K;
  const PI = Math.PI;
  const night = { wall: '#3b4170', floor: '#5a4638', sky: '#101c42', skyL: '#8a9ce0', sunC: '#9fb2ff', sunI: .9, hemi: .6, lamp: '#ffd8a0', blanket: '#e07a3d', rug: '#9a4a3a' };
  set('day', (X, g) => { attic(X, g, { wall: '#e9d7b8', floor: '#9a7a54', sky: '#bfe3ff', sunI: 2.2, hemi: 1 }); return { bg: '#bfe3ff' }; });
  set('night', (X, g) => { attic(X, g, night); const pl = new THREE.PointLight('#ffb870', 14, 9, 1.6); pl.position.set(1.6, 1.7, -1.9); g.add(pl); return { bg: '#0b1230', fog: ['#0b1230', 10, 30] }; });
  set('dawn', (X, g) => { street(X, g, { sky: '#ffd29a', sunC: '#ffb060', sunI: 2.8, wall: '#f3d7b5', grass: '#8ccf6a', sun: [-8, 3.2, 6], skyL: '#ffd6b0' }); return { bg: '#ffd9a8', fog: ['#ffd9a8', 14, 50] }; });
  set('calm', (X, g) => { studio(X, g, { wall: '#f6c9a0', floor: '#efe0c8' }); X.box(g, [1.8, .1, 1.1], [0, .82, -.2], '#d9b98a'); [[-.8, -.45], [.8, -.45], [-.8, .45], [.8, .45]].forEach(([a, b]) => X.box(g, [.1, .8, .1], [a, .4, -.2 + b], '#a47c48')); return { bg: '#f6c9a0' }; });
  const sven = actor({ skin: '#e0ac85', shirt: '#1f2a55', pants: '#2a2f45', hairStyle: 'short', sleeves: true });
  const oldS = actor({ skin: '#e0ac85', shirt: '#1f2a55', pants: '#2a2f45', hairStyle: 'short', hair: '#d8d8d8', sleeves: true });
  const beard = prop(new THREE.Mesh(new THREE.BoxGeometry(.34, .36, .2), new THREE.MeshStandardMaterial({ color: '#cfcfcf', roughness: 1 })));
  const lap = prop(laptopProp(X, null, 1)); const ph = prop(phoneProp(X, null, 1.7)); const hd = [0, 1, 2].map(() => prop(hoodieProp(X, '#3c4b73', .8)));
  const type = liveTex(512, 312, (x, w, h, n) => { x.fillStyle = '#fff'; x.fillRect(0, 0, w, h); x.fillStyle = '#09b1ba'; x.fillRect(0, 0, w, h * .16); x.fillStyle = '#fff'; x.font = '900 32px Montserrat'; x.textBaseline = 'middle'; x.fillText('Nieuwe advertentie', 20, h * .08); x.fillStyle = '#0a1936'; x.font = '800 30px Montserrat'; const s = 'Vintage blauwe hoodie, maat M'.slice(0, Math.floor(n) % 31); x.fillText(s + (Math.floor(n * 2) % 2 ? '|' : ''), 20, h * .38); x.fillStyle = '#c8d0de'; x.fillRect(20, h * .55, w - 40, 14); x.fillRect(20, h * .65, w * .7, 14); });
  const dTex = coverTex(await image('assets/items-crosslisted.webp'), .92 / .56);
  const phUI = liveTex(512, 900, (x, w, h, p) => omniUI(x, w, h, p));
  const scr = (o, tex) => { const m = o.userData.screen.material; if (m.map !== tex) { m.map = tex; m.needsUpdate = true; } };
  const L = (t, c, o = {}) => label(t, { h: .6, bg: c, fg: o.fg || '#fff', ...o });
  const l11 = L('11 DAGEN PER JAAR', '#ff4d4d', { h: .7 }), l50 = L('50 ARTIKELEN', '#ffffff', { fg: '#0a1936' }), l6 = L('6 MIN PER STUK', '#ffd23f', { fg: '#0a1936' }), l5 = L('5 UUR PER WEEK', '#ff4d4d', { h: .7 }), l10 = L('JAAR 10', '#0a0a0a', { fg: '#ffd23f', h: .8 }), l26 = L('2.600 UUR', '#ff4d4d', { h: .8 }), lBaard = L('BAARD', '#cfcfcf', { fg: '#222', h: .5 }), l7 = L('7 DAGEN GRATIS', '#85edbc', { fg: '#0a1936', h: .7 }), lJ1 = L('JAAR 1', '#0a0a0a', { fg: '#85edbc', h: .8 });
  const apps = [['Vinted', '#09b1ba'], ['Marktplaats', '#2f6fe0'], ['eBay', '#e53238'], ['Eigen shop', '#6b46c1']].map(([n, c]) => L(n, c, { h: .5 }));
  const ok = ['Vinted ✓', 'Marktplaats ✓', 'eBay ✓', 'Eigen shop ✓'].map(n => L(n, '#1faa6b', { h: .5 }));
  const t = (i, off = 0) => Math.max(0, W(i) + off);
  const sh = (i, s, cam, fn, o = {}, off = -.04) => shot(t(i, off), s, cam, fn, o);
  const desk = (a, who, lt, anim = 'type', o = {}) => { a.put(who, [1.2, 0, -1.7], PI, anim, lt, { sit: 1, ...o }); a.at(lap, 1.6, .87, -2.7); };
  // 1. Elf dagen per jaar
  sh(0, 'day', dolly([2.3, 1.5, -.6], [1.8, 1.4, -1.4], [1.6, 1.15, -2.7], [1.6, 1.15, -2.7], 40, 0, 0), (lt, T, a) => { desk(a, sven, lt); scr(lap, type.tex); type.draw(T * 14); a.at(l11, 1.6, 2.3, -2.5); a.sc(l11, pop(lt, .1, .35)); }, {}, 0);
  cue(W(0), 'pop');
  sh(4, 'day', dolly([4.6, 2.0, 5.2], [3.6, 1.8, 3.4], [1.0, 1.2, -2.2], [1.2, 1.2, -2.2], 50, 0, 0), (lt, T, a) => { desk(a, sven, lt); scr(lap, type.tex); type.draw(T * 14); });
  sh(8, 'day', dolly([2.0, 1.6, -.3], [1.7, 1.4, -1.1], [1.6, 1.1, -2.7], [1.6, 1.1, -2.7], 36, 0, 0), (lt, T, a) => { desk(a, sven, lt); scr(lap, type.tex); type.draw(T * 14); });
  sh(11, 'day', dolly([.2, 1.8, .2], [.8, 1.7, -.3], [1.6, 1.15, -2.7], [1.6, 1.15, -2.7], 34, 6, 0), (lt, T, a) => { desk(a, sven, lt); scr(lap, type.tex); type.draw(T * 22); });
  // 2. de rekensom
  sh(15, 'day', dolly([-1.8, 1.4, 3.0], [-1.0, 1.5, 2.4], [-.4, 1.0, -.2], [0, 1.1, -.2], 46, 0, 0), (lt, T, a) => { hd.forEach((h, i) => { a.at(h, -1.4 + i * 1.2, 1.0 + Math.abs(Math.sin(T * 3 + i)) * .12, -.2, T * 1.3 + i); }); a.at(l50, 0, 2.3, -.2); a.sc(l50, pop(lt, .05, .35)); });
  cue(W(15), 'pop');
  sh(17, 'day', stat([0, 1.7, 4.8], [0, 1.4, -.2], 46, 0), (lt, T, a) => { apps.forEach((l, i) => { a.at(l, -1.5 + i * 1.0, 1.5 + (i % 2) * .5, -.2); a.sc(l, pop(lt, i * .18 + .1, .3)); }); });
  cue(W(17), 'pop'); cue(W(17) + .4, 'pop');
  sh(19, 'day', dolly([0, 1.5, 3.6], [0, 1.6, 2.8], [0, 1.5, -.2], [0, 1.6, -.2], 44, 0, 0), (lt, T, a) => { a.at(l6, 0, 1.6, -.2); a.sc(l6, pop(lt, .05, .35)); });
  sh(23, 'day', dolly([2.9, 1.8, 1.2], [2.0, 1.6, .2], [1.4, 1.2, -1.8], [1.2, 1.2, -1.8], 46, 0, 0), (lt, T, a) => { desk(a, sven, lt, 'sad'); scr(lap, type.tex); type.draw(T * 14); a.at(l5, 1.2, 2.5, -1.9); a.sc(l5, pop(lt, .05, .35)); });
  cue(W(23), 'hit');
  // 3. tijdsprong
  sh(27, 'night', orbit([1.6, 0, -2.2], 3.4, 1.9, .4, -.9, 50, 1.5), (lt, T, a) => { desk(a, oldS, lt); scr(lap, type.tex); type.draw(T * 14); a.at(l10, -.4, 2.7, -1.2); a.sc(l10, pop(lt, .05, .3)); });
  cue(W(27), 'whoosh');
  sh(30, 'night', dolly([-.4, 1.7, 1.0], [.2, 1.6, .2], [1.2, 1.3, -1.7], [1.2, 1.3, -1.7], 46, -4, 3), (lt, T, a) => { desk(a, oldS, lt); scr(lap, type.tex); type.draw(T * 14); a.at(l26, 1.0, 2.9, -1.7); a.sc(l26, pop(lt, .05, .35) * (1 + .03 * Math.sin(T * 8))); });
  cue(W(30), 'hit');
  sh(33, 'night', stat([1.2, 1.7, .9], [1.2, 1.4, -1.6], 28, 0), (lt, T, a) => { a.put(oldS, [1.2, 0, -1.7], 0, 'sad', lt, { sit: 1 }); a.at(beard, 1.2, 1.28, -1.36, 0); a.at(lBaard, 1.2, 2.3, -1.6); a.sc(lBaard, pop(T, t(36, -.15), .3)); });
  sh(37, 'night', dolly([1.0, 1.5, -.6], [1.15, 1.4, -1.2], [1.6, 1.15, -2.7], [1.6, 1.15, -2.7], 34, 0, 0), (lt, T, a) => { desk(a, oldS, lt, 'sad'); a.at(beard, 1.2, 1.28, -2.02, PI); scr(lap, type.tex); type.draw(T * 14); });
  // 4. de oplossing
  sh(42, 'calm', dolly([-2.4, 1.6, 4.2], [-1.0, 1.7, 3.2], [0, 1.2, -.2], [0, 1.3, -.2], 46, 0, 0), (lt, T, a) => { a.put(oldS, [-.6, 0, 1.0], .35, 'point', lt); a.at(beard, -.6, 1.48, 1.22, 0); a.at(ph, .5, 1.5 + Math.sin(T * 1.7) * .05, .2, -.2); scr(ph, phUI.tex); phUI.draw({ sold: 0, rm: [0, 0, 0], title: 'Vintage hoodie', price: '€45' }); });
  cue(W(45), 'ding');
  sh(46, 'calm', dolly([1.4, 1.5, 1.6], [.9, 1.3, 1.0], [0, .95, -.2], [0, .95, -.2], 40, 0, 0), (lt, T, a) => { a.at(lap, 0, .87, -.2); lap.userData.lid.rotation.x = -.25; scr(lap, dTex); a.put(oldS, [-1.2, 0, .5], .6, 'type', lt, {}); a.at(beard, -1.2, 1.48, .72, 0); });
  sh(49, 'calm', dolly([-2.8, 1.4, 4.0], [2.8, 1.4, 4.0], [0, 1.5, 0], [0, 1.5, 0], 46, 0, 0, E.lin), (lt, T, a) => { ok.forEach((l, i) => { a.at(l, -2.1 + i * 1.4, 1.15 + (i % 2) * .4, .3); a.sc(l, pop(T, t(49) + i * .18, .3)); }); a.put(oldS, [0, 0, 1.4], 0, 'cheer', lt, {}); a.at(beard, 0, 1.48, 1.62, 0); }, {}, -.1);
  cue(W(49), 'ding'); cue(W(49) + .25, 'ding'); cue(W(49) + .5, 'ding'); cue(W(50), 'ding');
  // 5. Sven gaat naar buiten
  sh(51, 'calm', dolly([0, 1.5, 3.4], [0, 1.6, 2.6], [0, 1.5, 0], [0, 1.6, 0], 38, 0, 0), (lt, T, a) => { a.put(oldS, [0, 0, 0], 0, 'shrug', lt, {}); a.at(beard, 0, 1.48, .22, 0); });
  sh(53, 'dawn', dolly([-5.4, 1.2, 4.0], [-1.8, 1.4, 3.2], [-2.2, 1.0, 0], [0, 1.1, 0], 48, 0, 0), (lt, T, a) => { a.put(oldS, [-3.4 + lt * 2.6, 0, 0], PI / 2, 'walk', lt * 1.2); a.at(beard, -3.4 + lt * 2.6 + .22, 1.48, 0, PI / 2); });
  sh(56, 'dawn', dolly([2.6, 1.4, 4.4], [1.2, 1.5, 3.4], [0, 1.2, 0], [0, 1.3, 0], 46, 0, 0), (lt, T, a) => { a.put(oldS, [.2, 0, 0], .3, 'cheer', lt, {}); a.at(beard, .2, 1.48, .22, 0); a.at(l7, 0, 2.9, 0); a.sc(l7, pop(T, t(58, -.1), .35)); });
  cue(W(58), 'pop');
  endCard(t(60, .55)); cue(t(60, .55), 'pop');
}
