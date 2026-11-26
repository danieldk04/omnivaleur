// Stijl C: donkerder, realistischer licht, thriller-tempo met bewakingscamera (Dale-gevoel).
import { kitchen, bedroom, yard, pantry, studio, jacketProp, phoneProp, laptopProp } from '../sets.js';
export const style = 'real';
export const hotWords = ['Kevin', 'drie', 'buiten', 'Allebei', 'bonnetjes', 'voorraadkast', 'Omnivaleur', 'verdwijnt', 'slaapt', 'jas', 'boze'];

export async function build(K) {
  const { X, THREE, set, shot, actor, prop, label, cue, dolly, orbit, stat, pop, E, prog, lerp, liveTex, omniUI, endCard, sign, cl, image, coverTex } = K;
  const PI = Math.PI;
  const MAP = [0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 42, 43, 44, 45, 46, 46, 46, 47, 49, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 69, 70, 71, 72, 73, 74, 76, 77, 78, 79, 80, 81, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 92, 93, 94, 95, 96, 97, 98, 98, 99, 100, 101, 102, 103, 104, 105]; const W = i => K.W(MAP[Math.min(i, MAP.length - 1)]);
  const nightP = { wall: '#2c3050', floor: '#3a3030', sky: '#0c1430', skyL: '#6f86c9', lamp: '#ffd9a0', sunC: '#ffcf9a', sunI: 1.7, hemi: .7 };
  const warm = (g, x, y, z, i = 14) => { const pl = new THREE.PointLight('#ffb870', i, 10, 1.5); pl.position.set(x, y, z); g.add(pl); };
  set('kitchenD', (X, g) => { kitchen(X, g, { sky: '#d6ebff', sunC: '#fff0d8', sunI: 2.4, hemi: .8, wall: '#d9d2c2', floor: '#7a6a58' }); return { bg: '#cfe3f5' }; });
  set('kitchenN', (X, g) => { kitchen(X, g, nightP); warm(g, 0, 2.3, .3, 16); return { bg: '#080e22', fog: ['#080e22', 9, 26] }; });
  set('bedN', (X, g) => { bedroom(X, g, { ...nightP, blanket: '#5a6aa0', sheet: '#c9cfe6' }); warm(g, -.7, 1.6, -2.4, 6); return { bg: '#080e22', fog: ['#080e22', 9, 26] }; });
  set('yardN', (X, g) => yard(X, g));
  set('pantryS', (X, g) => { pantry(X, g); return { bg: '#120c08' }; });
  set('calm', (X, g) => { studio(X, g, { wall: '#9ad0f2', floor: '#efe3cf' }); X.box(g, [1.8, .1, 1.1], [0, .82, -.2], '#d9b98a'); [[-.8, -.45], [.8, -.45], [-.8, .45], [.8, .45]].forEach(([a, b]) => X.box(g, [.1, .8, .1], [a, .4, -.2 + b], '#a47c48')); return { bg: '#9ad0f2' }; });

  const kev = actor({ skin: '#d9a07a', shirt: '#8a8f99', pants: '#2f3a55', hairStyle: 'short', sleeves: false, hair: '#2a1d16' });
  const b1 = actor({ skin: '#a8734f', shirt: '#2f6f7a', pants: '#222831', hairStyle: 'cap', cap: '#e8872a' });
  const b2 = actor({ skin: '#f6d7c0', shirt: '#b84a6a', pants: '#2a2a34', hairStyle: 'bun', hair: '#5a3a2a' });
  const jk = prop(jacketProp(X, '#6b3f22', 1.1)); const rc1 = prop(sign('BON\n€89', .55, .75, { bg: '#fff', fg: '#222', size: 70, radius: 6 })); const rc2 = prop(sign('BON\n€89', .55, .75, { bg: '#fff', fg: '#222', size: 70, radius: 6 }));
  const msg = liveTex(400, 700, (x, w, h, m) => { x.fillStyle = '#10151f'; x.fillRect(0, 0, w, h); x.fillStyle = '#7d8aa8'; x.font = '800 30px Montserrat'; x.textBaseline = 'top'; x.fillText(m.from, 30, 40); x.fillStyle = '#fff'; x.beginPath(); x.roundRect(30, 120, w - 60, 200, 28); x.fill(); x.fillStyle = '#0a1936'; x.font = '900 40px Montserrat'; m.text.split('\n').forEach((l, i) => x.fillText(l, 55, 150 + i * 56)); x.fillStyle = '#ff3b30'; x.beginPath(); x.arc(w - 60, 90, 18, 0, 7); x.fill(); });
  const listing = liveTex(400, 700, (x, w, h, ch) => { x.fillStyle = '#fff'; x.fillRect(0, 0, w, h); x.fillStyle = ch.c; x.fillRect(0, 0, w, 90); x.fillStyle = '#fff'; x.font = '900 44px Montserrat'; x.textBaseline = 'middle'; x.fillText(ch.n, 30, 46); x.fillStyle = '#6b3f22'; x.beginPath(); x.roundRect(100, 140, 200, 230, 20); x.fill(); x.fillStyle = '#0a1936'; x.font = '900 40px Montserrat'; x.fillText('Leren jas', 40, 440); x.fillStyle = '#e53935'; x.font = '900 60px Montserrat'; x.fillText('€89', 40, 510); x.fillStyle = '#85edbc'; x.beginPath(); x.roundRect(40, 570, w - 80, 80, 20); x.fill(); x.fillStyle = '#0a1936'; x.font = '900 36px Montserrat'; x.fillText('LIVE', w / 2 - 40, 612); });
  const phUI = liveTex(512, 900, (x, w, h, p) => omniUI(x, w, h, { title: 'Leren jas', price: '€89', ...p }));
  const clk = liveTex(512, 256, (x, w, h, s) => { x.fillStyle = '#12080a'; x.fillRect(0, 0, w, h); x.fillStyle = s.c || '#ff3b30'; x.font = '900 120px Montserrat'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(s.t, w / 2, h / 2 + 6); });
  const clkM = prop(new THREE.Mesh(new THREE.PlaneGeometry(1.4, .7), new THREE.MeshBasicMaterial({ map: clk.tex })));
  const dTex = coverTex(await image('assets/dashboard-overview.webp'), .92 / .56);
  const ph = prop(phoneProp(X, null, 1.7)), lap = prop(laptopProp(X, null, 1));
  const markTex = await image('assets/mark.png'); const mark = prop(new THREE.Mesh(new THREE.PlaneGeometry(1.1, 1.1 * 96 / 176), new THREE.MeshBasicMaterial({ map: markTex, transparent: true })));
  const L = (t, c, o = {}) => label(t, { h: .5, bg: c, fg: o.fg || '#fff', ...o });
  const lV = L('Vinted', '#09b1ba'), lE = L('eBay', '#e53238'), lStar = L('★★★★★', '#0a0a0a', { fg: '#ffd23f', h: .6 }), lDown = L('★★★☆☆', '#0a0a0a', { fg: '#ff6b6b', h: .6 });
  const scr = (o, tex) => { const m = o.userData.screen.material; if (m.map !== tex) { m.map = tex; m.needsUpdate = true; } };
  const t = (i, off = 0) => Math.max(0, W(i) + off);
  const sh = (i, s, cam, fn, o, off = -.05) => shot(t(i, off), s, cam, fn, o);
  const D = (T, a, d) => cl((T - a) / d);
  const chA = { c: '#09b1ba', n: 'Vinted' }, chB = { c: '#e53238', n: 'eBay' };
  const phoneAt = (a, tex, x, y, z, ry, s = 1) => { a.at(ph, x, y, z, ry); a.sc(ph, s); scr(ph, tex); };

  // Meet Kevin
  sh(0, 'kitchenD', dolly([-3.2, 1.5, 4.5], [-1.4, 1.5, 3.4], [0, 1.2, 0], [0, 1.3, 0], 48, 0, 0), (lt, T, a) => { a.put(kev, [0, 0, 0], .1, 'cheer', lt * .7, { lx: -1.0, rx: -1.0, lz: .3, rz: .3, le: -.8, re: -.8 }); a.at(jk, 0, 1.4, .8, T * .6); }, {}, 0);
  sh(1, 'kitchenD', dolly([.5, 1.0, 3.2], [.2, 1.2, 2.5], [0, 1.6, 0], [0, 1.65, 0], 34, 5, 0), (lt, T, a) => { a.put(kev, [0, 0, 0], 0, 'laugh', lt); }, { shake: .01 });
  // sold a vintage leather jacket
  sh(2, 'kitchenD', orbit([0, 0, 0], 2.2, 1.6, .5, -.5, 42, 1.3), (lt, T, a) => { a.at(jk, 0, 1.3, 0, T * .9); }, {});
  sh(5, 'kitchenD', dolly([.9, 1.5, 1.4], [.3, 1.35, .9], [0, 1.3, 0], [0, 1.3, 0], 34, -4, 0), (lt, T, a) => { a.at(jk, 0, 1.3, 0, T * .9 + 1); }, {});
  // Vinted, eBay
  sh(9, 'kitchenD', dolly([-1.0, 1.5, 2.0], [-.3, 1.5, 1.6], [.6, 1.4, 0], [.6, 1.4, 0], 40, 0, 0), (lt, T, a) => { phoneAt(a, listing.tex, .6, 1.4, 0, -.25, 1.9); listing.draw(chA); a.put(kev, [-1.6, 0, 0], .8, 'point', lt); a.at(lV, .6, 2.3, 0); a.sc(lV, pop(lt, .1, .3)); }, {});
  sh(11, 'kitchenD', dolly([1.8, .9, 1.8], [1.1, 1.2, 1.4], [.6, 1.4, 0], [.6, 1.4, 0], 40, 8, 4), (lt, T, a) => { phoneAt(a, listing.tex, .6, 1.4, 0, -.25, 1.9); listing.draw(chB); a.at(lE, .6, 2.3, 0); a.sc(lE, pop(lt, .1, .3)); }, { shake: .02 });
  cue(W(9), 'pop'); cue(W(11), 'pop');
  sh(13, 'kitchenD', dolly([-.6, 1.8, 2.5], [-.2, 1.8, 2.0], [0, 1.65, 0], [0, 1.65, 0], 30, -6, 4), (lt, T, a) => { a.put(kev, [0, 0, 0], 0, 'laugh', lt * .5, { eye: .7, brow: .35, open: 0, mouth: .9 }); }, {});
  // 3 a.m.
  sh(18, 'bedN', dolly([2.8, 1.8, 3.6], [1.4, 1.5, 2.2], [-2.2, 1.0, -2], [-2.2, 1.0, -2], 48, 0, 0), (lt, T, a) => { a.put(kev, [-2.5, .95, -.4], 0, 'lie', lt); a.at(clkM, -.1, 2.35, -3.36); clk.draw({ t: '03:00' }); }, {}, 0);
  cue(W(18), 'tick');
  sh(21, 'bedN', dolly([-.2, 1.5, -.6], [-.6, 1.25, -1.6], [-.7, 1.0, -2.95], [-.7, 1.0, -2.95], 36, 6, 0), (lt, T, a) => { const s = Math.sin(lt * 70) * .04; phoneAt(a, msg.tex, -.7 + s, .95, -2.7, 0, 1.2); msg.draw({ from: 'eBay', text: 'Nieuw bericht' }); }, { shake: .01 });
  cue(W(23), 'buzz'); cue(W(23) + .5, 'buzz');
  sh(24, 'bedN', dolly([-.4, 1.4, -1.4], [-.6, 1.3, -2.0], [-.7, 1.0, -2.95], [-.7, 1.0, -2.95], 30, 0, 0), (lt, T, a) => { phoneAt(a, msg.tex, -.7, .95, -2.7, 0, 1.5); msg.draw({ from: 'Koper 1', text: 'Kan hij er\nmorgen zijn?' }); }, {});
  sh(26, 'bedN', dolly([-2.5, 1.9, 2.6], [-2.5, 1.6, 1.6], [-2.5, 1.4, -1.0], [-2.5, 1.45, -1.2], 50, 0, -3), (lt, T, a) => { a.put(kev, [-2.5, .62, -1.0], 0, 'shock', lt, { sit: 1 }); }, { shake: .01 });
  sh(29, 'bedN', dolly([-.2, 1.5, -.9], [-.6, 1.3, -1.8], [-.7, 1.0, -2.95], [-.7, 1.0, -2.95], 30, -4, 0), (lt, T, a) => { phoneAt(a, msg.tex, -.7, .95, -2.7, 0, 1.5); msg.draw({ from: 'Koper 2', text: 'Ik sta al\nbuiten.' }); }, {});
  cue(W(29), 'buzz');
  sh(31, 'yardN', dolly([-4, 1.0, 9], [-1, 1.4, 6], [0, 1.5, -3.6], [0, 1.5, -3.6], 46, 0, 0), (lt, T, a) => { a.put(b1, [-.8, 0, -3.4], PI + .2, 'angry', lt); a.put(b2, [.9, 0, -3.3], PI - .2, 'angry', lt + .4); }, { shake: .02 });
  // Kevin checks camera
  sh(34, 'kitchenN', dolly([2.2, 1.7, 3.0], [1.0, 1.6, 2.0], [-.4, 1.3, 0], [-.4, 1.4, 0], 44, 0, 0), (lt, T, a) => { a.put(kev, [-.4, 0, 0], .3, 'phone', lt, { eye: .9, sweat: 1 }); }, {});
  sh(37, 'yardN', dolly([-6.5, 4.6, 6.5], [-6, 4.4, 6.2], [0, 1, -2.8], [0, 1, -2.8], 52, 0, 0), (lt, T, a) => { a.put(b1, [-.8 + Math.sin(lt * 1.5) * .3, 0, -3.1], PI + .2, 'angry', lt); a.put(b2, [.9, 0, -3.0], PI - .2, 'angry', lt + .4); }, { cctv: true, filter: 'grayscale(1) contrast(1.15) brightness(1.9)', shake: .015 });
  sh(38, 'yardN', dolly([-4.5, 3.8, 5.2], [-3.2, 3.0, 4.0], [0, 1.2, -3], [0, 1.2, -3], 40, 0, 0), (lt, T, a) => { a.put(b1, [-.8, 0, -3.0], PI + .2, 'angry', lt); a.put(b2, [.9, 0, -3.0], PI - .2, 'angry', lt + .4); }, { cctv: true, filter: 'grayscale(1) contrast(1.15) brightness(1.9)' });
  sh(41, 'yardN', dolly([-2.2, 2.2, 3.0], [-1.0, 1.9, 1.8], [0, 1.4, -3], [0, 1.4, -3], 34, 0, 0), (lt, T, a) => { a.put(b1, [-.7, 0, -3.0], PI - .1, 'angry', lt); a.put(b2, [.8, 0, -3.0], PI + .1, 'angry', lt + .4); }, { cctv: true, filter: 'grayscale(1) contrast(1.15) brightness(1.9)' });
  sh(44, 'yardN', dolly([0, .5, 1.2], [0, 1.2, .2], [0, 1.6, -3], [0, 1.7, -3], 54, -5, 4), (lt, T, a) => { a.put(b1, [-.8, 0, -2.6], PI, 'angry', lt, { rx: -2.4, rz: .2, re: -.3 }); a.at(rc1, -.8, 2.05, -2.45, PI); a.put(b2, [.8, 0, -2.6], PI, 'angry', lt + .3, { rx: -2.4, rz: .2, re: -.3 }); a.at(rc2, .8, 2.05, -2.45, PI); }, { shake: .03 });
  cue(W(44), 'hit');
  sh(46, 'kitchenN', dolly([1.0, 1.6, 1.4], [.4, 1.4, 1.0], [0, 1.3, 0], [0, 1.3, 0], 36, 0, 0), (lt, T, a) => { a.at(jk, 0, 1.3, 0, T * .5); }, {});
  sh(48, 'yardN', dolly([0, 1.0, 1.3], [0, 1.4, .4], [0, 1.6, -3], [0, 1.6, -3], 40, 7, -4), (lt, T, a) => { a.put(b1, [-.95, 0, -2.7], PI + .5, 'fight', lt); a.put(b2, [.95, 0, -2.7], PI - .5, 'fight', lt + .2); }, { shake: .05 });
  // Kevin hides in the pantry
  sh(51, 'kitchenN', dolly([.8, 1.7, 1.0], [.3, 1.65, .6], [-.4, 1.65, 0], [-.4, 1.65, 0], 28, -3, 3), (lt, T, a) => { a.put(kev, [-.4, 0, 0], 0, 'shock', lt, { sweat: 1 }); }, { shake: .012 });
  sh(55, 'kitchenN', dolly([-4.2, 1.1, 2.6], [-1.0, 1.1, 2.6], [-1.5, 1.0, -.5], [-1.5, 1.0, -.5], 46, 0, 0, E.lin), (lt, T, a) => { a.put(kev, [-2.8 + lt * 3.2, 0, -.5], PI / 2, 'run', lt); }, { shake: .02 });
  sh(59, 'pantryS', dolly([0, 1.0, 2.3], [0, 1.1, 1.3], [0, .9, -.3], [0, .9, -.3], 46, 0, 0), (lt, T, a) => { a.put(kev, [0, 0, 0], 0, 'shock', lt, { y: -.25, lean: .35, hx: .2, lz: .9, rz: .9, sweat: 1, sit: .6 }); }, { shake: .01 });
  cue(W(60), 'hit');
  // Refund, apologize, rating
  sh(64, 'kitchenN', dolly([.9, 1.8, 1.4], [.5, 1.6, 1.0], [0, 1.3, .1], [0, 1.3, .1], 38, 0, 0), (lt, T, a) => { a.put(kev, [-.2, 0, 0], .5, 'phone', lt, { sweat: .6 }); a.at(lE, .8, 2.3, .5); a.sc(lE, pop(lt, .1, .3)); }, {});
  sh(67, 'yardN', orbit([0, 0, -3.2], 3.4, 1.5, -.5, .5, 44, 1.4), (lt, T, a) => { a.put(kev, [0, 0, -3.7], 0, 'sad', lt); a.put(b1, [-.9, 0, -2.5], PI - .3, 'angry', lt); a.put(b2, [.9, 0, -2.5], PI + .3, 'angry', lt); }, {});
  sh(72, 'kitchenN', dolly([.4, 1.7, 2.2], [.2, 1.6, 1.8], [0, 1.6, 0], [0, 1.7, 0], 40, 0, 0), (lt, T, a) => { a.put(kev, [-.2, 0, 0], 0, 'sad', lt); const k = D(lt, .6, .35); a.at(lStar, .3, 2.5, .3); a.sc(lStar, (1 - k) * pop(lt, 0, .3)); a.at(lDown, .3, 2.5 - k * .25, .3); a.sc(lDown, k * 1.05); }, {});
  cue(W(74) + .2, 'buzz');
  // Omnivaleur
  sh(77, 'kitchenN', dolly([1.3, 1.6, 2.6], [.7, 1.4, 1.8], [.6, 1.05, 0], [.6, 1.05, 0], 36, 0, 0), (lt, T, a) => { a.put(kev, [-.6, 0, .9], .5, 'think', lt); a.at(lap, .6, .87, 0); lap.userData.lid.rotation.x = -.25; scr(lap, dTex); }, {});
  sh(80, 'calm', dolly([0, 1.4, 4.0], [0, 1.5, 3.0], [0, 1.4, 0], [0, 1.4, 0], 40, 0, 0), (lt, T, a) => { a.at(mark, 0, 1.4 + Math.sin(T * 2) * .05, 0, 0); a.sc(mark, pop(lt, 0, .5)); }, {}, -.1);
  cue(W(80), 'whoosh');
  sh(81, 'calm', dolly([1.0, 1.5, 3.2], [.6, 1.4, 2.4], [0, 1.35, .2], [0, 1.35, .2], 38, 0, 0), (lt, T, a) => { phoneAt(a, phUI.tex, 0, 1.35, .2, 0, 1.9); phUI.draw({ sold: D(T, W(84), .3), rm: [0, 0, 0] }); a.put(kev, [-1.3, 0, .2], .7, 'point', lt); }, {});
  cue(W(84), 'ding');
  sh(85, 'calm', dolly([-.6, 1.5, 2.8], [-.2, 1.4, 2.0], [0, 1.35, .2], [0, 1.35, .2], 34, 3, 0), (lt, T, a) => { phoneAt(a, phUI.tex, 0, 1.35, .2, 0, 1.9); phUI.draw({ sold: 1, rm: [D(T, W(85) + .1, .5), D(T, W(88) - .2, .5), D(T, W(89) + .1, .5)] }); }, {});
  cue(W(86), 'tick'); cue(W(88), 'tick'); cue(W(89) + .2, 'tick');
  sh(91, 'calm', dolly([.9, 1.5, 3.2], [.4, 1.4, 2.4], [0, 1.0, -.2], [0, 1.0, -.2], 36, 0, 0), (lt, T, a) => { a.at(lap, 0, .87, -.2); lap.userData.lid.rotation.x = -.25; scr(lap, dTex); a.put(kev, [-1.4, .2, .4], .6, 'cheer', lt); }, {});
  // Now Kevin sleeps
  sh(93, 'bedN', dolly([1.4, 2.3, 3.0], [-.4, 1.8, 1.4], [-2.5, 1.0, -1.7], [-2.5, 1.0, -1.7], 46, 0, -3), (lt, T, a) => { a.put(kev, [-2.5, .95, -.4], 0, 'lie', lt); }, {});
  sh(96, 'calm', dolly([-.5, 1.2, 4.6], [0, 1.7, 3.6], [0, 2.3, 0], [0, 2.4, 0], 50, 0, 0), (lt, T, a) => { a.put(kev, [0, 0, 0], 0, 'wave', lt); }, {}, -.1);
  endCard(t(96, -.1)); cue(t(96, -.1), 'pop');
}
