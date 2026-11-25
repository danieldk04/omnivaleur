// Stijl A: lowpoly blokpoppetjes, absurde escalatie, ca. 1 shot per seconde.
import { attic, bedroom, street, space, studio, crowd, hoodieProp, phoneProp, laptopProp, parcelProp } from '../sets.js';
export const style = 'blocky';
export const hotColor = '#ffd23f';
export const hotWords = ['hoodie', 'buyer', 'paid', 'fight', 'planet', 'once', 'town', 'cousin', 'genius', 'Easy'];

export async function build(K) {
  const { X, set, shot, actor, prop, label, W, cue, dolly, orbit, stat, pop, E, prog, lerp, liveTex, omniUI, endCard, DURATION, coverTex, image } = K;
  const PI = Math.PI;
  set('attic', (X, g) => { attic(X, g); return { bg: '#d8c7a8' }; });
  set('bed', (X, g) => { bedroom(X, g, { blanket: '#ff7a59' }); return { bg: '#bfe0f5' }; });
  set('door', (X, g) => { street(X, g); return { bg: '#9fd4ff' }; });
  let cr; set('town', (X, g) => { street(X, g, { sky: '#ffb36b' }); cr = crowd(X, g, { n: 260, x0: -9, x1: 9, z0: -1, z1: 9, seed: 7, clear: [-3.2, 3.2, -1.6, 4.8] }); return { bg: '#ffb27a', upd: T => cr.upd(T, 1.6) }; });
  set('space', (X, g) => space(X, g));
  set('calm', (X, g) => { studio(X, g, { wall: '#8fd0ff', floor: '#f1e7d4' }); X.box(g, [1.8, .1, 1.1], [0, .82, -.2], '#d9b98a'); [[-.8, -.45], [.8, -.45], [-.8, .45], [.8, .45]].forEach(([a, b]) => X.box(g, [.1, .8, .1], [a, .4, -.2 + b], '#a47c48')); return { bg: '#8fd0ff' }; });

  const seller = actor({ skin: '#d9a07a', shirt: '#3c4b73', pants: '#2a2f45', hairStyle: 'short', sleeves: true });
  const bA = actor({ skin: '#a8734f', shirt: '#2f6f7a', hairStyle: 'cap', cap: '#e8872a' });
  const bB = actor({ skin: '#f6d7c0', shirt: '#e58aa8', hairStyle: 'bun', hair: '#5a3a2a' });
  const bC = actor({ skin: '#7a4e32', shirt: '#e8872a', hairStyle: 'beanie' });
  const nb = actor({ skin: '#d9a07a', shirt: '#7a3fa0', hairStyle: 'long', hair: '#14141a' });
  const hd = prop(hoodieProp(X, '#3c4b73', 1)), hd2 = prop(hoodieProp(X, '#3c4b73', 1));
  const lap = prop(laptopProp(X, null, 1)); lap.userData.screen.material.dispose();
  const vint = liveTex(512, 312, (x, w, h, mode) => { x.fillStyle = '#fff'; x.fillRect(0, 0, w, h); x.fillStyle = mode === 'mp' ? '#2f6fe0' : '#09b1ba'; x.fillRect(0, 0, w, h * .2); x.fillStyle = '#fff'; x.font = '900 40px Montserrat'; x.textBaseline = 'middle'; x.fillText(mode === 'mp' ? 'Marktplaats' : 'Vinted', 24, h * .1); x.fillStyle = '#0a1936'; x.font = '900 50px Montserrat'; x.fillText('Blue hoodie', 24, h * .42); x.fillStyle = '#e53935'; x.font = '900 70px Montserrat'; x.fillText('EUR 45', 24, h * .68); x.fillStyle = '#85edbc'; x.beginPath(); x.roundRect(24, h * .8, w - 48, h * .14, 16); x.fill(); x.fillStyle = '#0a1936'; x.font = '900 34px Montserrat'; x.textAlign = 'center'; x.fillText('PUBLISH', w / 2, h * .87); x.textAlign = 'left'; });
  lap.userData.screen.material = new K.THREE.MeshBasicMaterial({ map: vint.tex });
  const dash = coverTex(await image('assets/dashboard-overview.webp'), .92 / .56), lap2 = prop(laptopProp(X, dash, 1));
  const phUI = liveTex(512, 900, (x, w, h, p) => omniUI(x, w, h, p));
  const ph = prop(phoneProp(X, phUI.tex, 1.7));
  const L = (t, c, o = {}) => label(t, { h: .5, ...o, bg: c, fg: o.fg || '#fff' });
  const lEuro = L('EUR 45', '#ffd23f', { fg: '#0a1936', h: .7 }), lGen = L('GENIUS', '#ff4d4d', { h: .55 }), lKnock = L('KNOCK KNOCK', '#ffffff', { fg: '#0a1936', h: .5 });
  const lPaidA = L('PAID', '#1faa6b', { h: .45 }), lPaidB = L('PAID', '#1faa6b', { h: .45 }), lCousin = L('COUSIN', '#7aa2ff', { h: .45 }), lNb = L('NEIGHBOR', '#a06cd5', { h: .45 });
  const lMp = L('Marktplaats', '#2f6fe0', { h: .6 }), lVin = L('Vinted', '#09b1ba', { h: .6 }), lMad = L('8 BILLION BUYERS', '#ff4d4d', { h: .8 });
  const t = (i, off = 0) => Math.max(0, W(i) + off);
  const sh = (i, s, cam, fn, o, off = -.05) => shot(t(i, off), s, cam, fn, o);

  // 1. Je verkoopt een hoodie
  sh(0, 'attic', dolly([5.2, 2.6, 5], [3.2, 1.7, 1.2], [1.6, 1.0, -2], [1.4, 1.1, -2.2], 50), (lt, T, a) => { a.put(seller, [1.2, .0, -1.7], PI, 'type', lt, { sit: 1 }); a.at(lap, 1.6, .87, -2.7); lap.userData.lid.rotation.x = -.25; vint.draw('v'); }, {}, 0);
  sh(3, 'attic', dolly([0, 1.7, 3.8], [1.0, 1.6, 2.6], [2.3, 1.4, -.6], [2.4, 1.5, -.5], 46, -6, 4), (lt, T, a) => { a.at(hd, 2.5, 1.5 + Math.sin(T * 3) * .05, -.4, T * 1.6); a.put(seller, [1.2, 0, -1.7], PI, 'type', lt, { sit: 1 }); a.at(lap, 1.6, .87, -2.7); });
  sh(5, 'attic', dolly([1.5, 1.2, -.2], [1.6, 1.15, -1.0], [1.6, 1.1, -2.7], [1.6, 1.1, -2.7], 40), (lt, T, a) => { a.at(lap, 1.6, .87, -2.7); vint.draw('v'); a.at(lVin, 2.6, 1.9, -2.6); a.sc(lVin, pop(lt, .05, .3)); });
  sh(6, 'attic', stat([.2, .5, 1.6], [1.3, 1.5, -1.2], 56, 10), (lt, T, a) => { a.at(hd, 1.3, 1.2, -1.2, T * 1.2 + .5); a.at(lEuro, 1.3, 2.3, -1.1); a.sc(lEuro, pop(lt, .05, .35)); }, { shake: .03 });
  cue(W(6), 'ding');
  sh(8, 'attic', dolly([1.2, 1.3, 2.8], [1.2, 1.5, 1.9], [1.2, 1.35, -.5], [1.2, 1.7, -.5], 42), (lt, T, a) => { a.put(seller, [1.2, 0, -.5], 0, 'cheer', lt); a.at(hd, 1.2, 3.0, -.5, T * 2); a.sc(hd, .8); }, {});
  // 2. Je denkt: ik ben een genie
  sh(9, 'bed', dolly([3.5, 1.5, 3.2], [1.5, 1.45, 2.0], [-2.5, 1.2, -1.2], [-2.5, 1.3, -1.2], 48, -5, 5), (lt, T, a) => { a.put(seller, [-1.2, 0, -.6], PI / 2 + .8, 'think', lt); });
  sh(12, 'bed', dolly([-.6, .5, 1.2], [-1.0, .9, .9], [-1.3, 1.5, -.6], [-1.3, 1.7, -.6], 52, 8, 0), (lt, T, a) => { a.put(seller, [-1.3, 0, -.6], .2, 'cheer', lt); a.at(lGen, -1.3, 2.7, -.6); a.sc(lGen, pop(lt, .05, .3)); }, { shake: .02 });
  cue(W(14), 'pop');
  sh(16, 'attic', dolly([1.6, 1.15, -1.0], [1.6, 1.15, -1.8], [1.6, 1.1, -2.7], [1.6, 1.1, -2.7], 40, 0, 0), (lt, T, a) => { a.at(lap, 1.6, .87, -2.7); vint.draw('mp'); a.at(lMp, 2.5, 1.9, -2.6); a.sc(lMp, pop(lt, .15, .3)); });
  sh(19, 'attic', orbit([1.6, 0, -2], 3.2, 1.8, .6, -.4, 48, 1.2), (lt, T, a) => { a.put(seller, [1.2, 0, -1.7], PI, 'laugh', lt, { sit: 1 }); a.at(lap, 1.6, .87, -2.7); a.at(lMp, 1.6, 2.6, -2.2); a.sc(lMp, 1 + Math.sin(T * 8) * .05); a.at(lVin, .4, 2.3, -2.2); a.sc(lVin, 1); });
  // 3. Een koper staat aan de deur
  sh(21, 'door', dolly([-7, 1.2, 8], [-2, 1.4, 5], [0, 1.4, -3], [0, 1.4, -3], 50), (lt, T, a) => {}, {});
  sh(23, 'door', dolly([-5.2, .45, 2.4], [-.8, .5, 1.2], [-1, 1.0, -2], [-.3, 1.1, -2.2], 56, 0, -4), (lt, T, a) => { a.put(bA, [-4 + lt * 2.6, 0, 0 + lt * -.5], PI / 2 - .25, 'run', lt * 1.0); a.put(seller, [-8, 0, 8]); }, { shake: .04 });
  sh(26, 'door', dolly([1.3, 1.5, -.8], [.8, 1.55, -1.5], [0, 1.5, -2.7], [0, 1.5, -2.7], 40, 4, 0), (lt, T, a) => { a.put(bA, [-.1, 0, -2.2], PI, 'angry', lt); a.at(lKnock, 1.2, 2.5, -2.6); a.sc(lKnock, pop(lt, .1, .3) * (1 + .1 * Math.sin(lt * 20))); }, { shake: .05 });
  cue(W(26), 'hit'); cue(W(26) + .25, 'hit'); cue(W(26) + .5, 'hit');
  sh(29, 'door', dolly([3, 1.5, 3.5], [1.6, 1.6, 1.4], [-.3, 1.0, -2.2], [0, 1.0, -2.2], 52, -6, 0), (lt, T, a) => { a.put(bA, [-.6, 0, -2.2], PI, 'angry', lt); a.put(bB, [6 - lt * 6.3, 0, 0 - lt * 2.2], -PI / 2 - .2 + .2, lt < 1 ? 'run' : 'angry', lt * 1.0); if (lt > 1) a.put(bB, [-.3 + .8, 0, -2.2], PI, 'angry', lt); }, { shake: .03 });
  sh(32, 'door', dolly([0, 1.1, 2.2], [0, 1.4, 1.0], [0, 1.1, -2.2], [0, 1.4, -2.2], 58, 5, -5), (lt, T, a) => { a.put(bA, [-1.0, 0, -2.2], PI, 'angry', lt); a.put(bB, [-.1, 0, -2.2], PI, 'angry', lt + .3); a.put(bC, [.9, 0, -2.2 + (1 - pop(lt, 0, .3)) * 1.4], PI, 'angry', lt + .6); a.at(lCousin, .9, 2.55, -2.2); a.sc(lCousin, pop(lt, .3, .3)); }, { shake: .03 });
  sh(35, 'door', dolly([.9, 1.7, -.2], [.9, 1.7, -1.1], [.9, 1.6, -2.2], [.9, 1.6, -2.2], 30), (lt, T, a) => { a.put(bC, [.9, 0, -2.2], 0, 'angry', lt); }, { shake: .02 });
  // 4. Beiden hebben betaald
  sh(36, 'door', dolly([-2.4, 1.0, 1.0], [-1.8, 1.2, .2], [-.4, 1.4, -2.2], [-.4, 1.4, -2.2], 46), (lt, T, a) => { a.put(bA, [-.5, 0, -2.2], 0, 'angry', lt); a.at(lPaidA, 0.6, 2.4, -2.2); a.sc(lPaidA, pop(lt, .1, .3)); a.put(bB, [1.1, 0, -2.2], 0, 'angry', lt); a.at(lPaidB, 1.9, 2.4, -2.2); a.sc(lPaidB, pop(lt, .35, .3)); }, {});
  cue(W(36), 'ding'); cue(W(37) + .1, 'ding');
  sh(38, 'door', dolly([0, .5, 2.4], [0, 1.1, 1.6], [0, 1.4, -2.2], [0, 1.5, -2.2], 54, 0, 5), (lt, T, a) => { a.put(bA, [-1.05, 0, -2.2], PI / 2, 'carry', lt, { brow: .6, mouth: -.8, open: .4 }); a.put(bB, [1.05, 0, -2.2], -PI / 2, 'carry', lt, { brow: .6, mouth: -.8, open: .4 }); a.at(hd, 0, 1.1 + Math.sin(T * 5) * .03, -2.2, T * 2); a.sc(hd, .9); }, { shake: .03 });
  sh(42, 'door', stat([0, 1.9, 1.0], [0, 1.4, -2.2], 38, -8), (lt, T, a) => { const s = Math.sin(lt * 18); a.put(bA, [-1.05 + s * .08, 0, -2.2], PI / 2, 'carry', lt, { brow: .7, mouth: -.8, open: .5, y: Math.abs(s) * .05 }); a.put(bB, [1.05 - s * .08, 0, -2.2], -PI / 2, 'carry', lt, { brow: .7, mouth: -.8, open: .5, y: Math.abs(s) * .05 }); a.at(hd, s * .08, 1.1, -2.2, T * 6); a.sc(hd, .9); }, { shake: .08 });
  // 5. Ze vechten, de buren doen mee, de hele stad
  sh(43, 'town', orbit([0, 0, 1.5], 3.6, 1.4, 0, 1.6, 60, 1.0, 6), (lt, T, a) => { a.put(bA, [-.85, 0, 1.5], PI / 2, 'fight', lt); a.put(bB, [.85, 0, 1.5], -PI / 2, 'fight', lt + .3); a.put(bC, [1.8, 0, 2.2], -PI / 2, 'run', lt); a.put(nb, [-1.9, 0, 2.2], PI / 2, 'run', lt); }, { shake: .06 });
  cue(W(44), 'hit');
  sh(45, 'door', dolly([4, 1.4, 3.2], [2, 1.5, 1.4], [0, 1.2, -1.5], [0, 1.2, -1.5], 52, 6, -3), (lt, T, a) => { a.put(bA, [-.4, 0, -1.4], PI / 2, 'fight', lt); a.put(bB, [.4, 0, -1.4], -PI / 2, 'fight', lt + .3); a.put(nb, [-5 + lt * 3.4, 0, 0 - lt * 1.4], PI / 2 - .2, 'run', lt); a.at(lNb, -3 + lt * 3, 2.4, -1.0 - lt * .4); a.sc(lNb, pop(lt, .1, .3)); }, { shake: .04 });
  sh(48, 'town', dolly([-8, 7, 12], [4, 3, 8], [0, 0, 2], [0, 1, 2], 54, 0, 4), (lt, T, a) => { a.put(bA, [-.85, 0, 1.5], PI / 2, 'fight', lt); a.put(bB, [.85, 0, 1.5], -PI / 2, 'fight', lt + .3); }, { shake: .02 });
  sh(50, 'town', orbit([0, 0, 1.5], 8, 2.5, -.7, .4, 62, 1.0), (lt, T, a) => { a.put(bA, [-.85, 0, 1.5], PI / 2, 'fight', lt); a.put(bB, [.85, 0, 1.5], -PI / 2, 'fight', lt + .3); a.at(hd, 0, 3.0 + Math.abs(Math.sin(T * 4)) * .4, 1.5, T * 3); }, { shake: .05 });
  // 6. De hele planeet
  sh(52, 'space', dolly([0, .2, 3], [0, .2, 0], [0, 0, -14], [0, 0, -14], 50, 0, 0), (lt, T, a) => {}, {}, -.05);
  cue(W(52), 'whoosh');
  sh(55, 'space', dolly([0, 3.2, 1], [0, 1.5, -3], [0, 0, -14], [0, 0, -14], 54, 8, -5), (lt, T, a) => { a.at(lMad, 0, 2.2, -8); a.sc(lMad, pop(lt, .1, .4) * 1.0); }, { shake: .02 });
  sh(59, 'space', dolly([0, .3, 3], [0, .1, -3.2], [0, 0, -8], [0, 0, -8], 46, 0, 0), (lt, T, a) => { a.at(hd, 0, Math.sin(T * 2) * .1, -6.5, T * 1.4 + 2); a.sc(hd, 1); }, {});
  // 7. Of: Omnivaleur
  sh(62, 'calm', dolly([-3, 1.2, 4], [-1.2, 1.5, 3.2], [0, 1.1, 0], [0, 1.2, 0], 50, 0, 0), (lt, T, a) => { a.put(seller, [0, .2, 0], .1, 'phone', lt, {}); }, {});
  sh(65, 'calm', dolly([1.4, 1.7, 2.4], [.5, 1.35, 1.2], [0, .95, -.2], [0, .95, -.2], 40), (lt, T, a) => { a.at(lap2, 0, .87, -.2); lap2.userData.lid.rotation.x = -.25; a.put(seller, [-1.3, .2, .5], .6, 'point', lt); });
  const rmAt = (T, t0, d = .5) => K.cl((T - t0) / d);
  sh(66, 'calm', dolly([1.7, 1.45, 2.8], [1.2, 1.4, 2.3], [.8, 1.4, .6], [.8, 1.4, .6], 36, 0, 0), (lt, T, a) => { a.put(seller, [0, .2, 0], .05, 'phone', lt); a.at(ph, .9, 1.35, .6, -.35); phUI.draw({ sold: rmAt(T, W(67)), rm: [0, 0, 0] }); });
  cue(W(67), 'ding');
  sh(69, 'calm', dolly([1.5, 1.5, 2.6], [1.1, 1.4, 2.2], [.9, 1.4, .6], [.9, 1.4, .6], 36, 0, 0), (lt, T, a) => { a.at(ph, .9, 1.35, .6, -.35); phUI.draw({ sold: 1, rm: [rmAt(T, W(70) + .1), rmAt(T, W(73) - .2), rmAt(T, W(74) + .3)] }); });
  cue(W(70), 'tick'); cue(W(73) - .1, 'tick'); cue(W(74) + .4, 'tick');
  sh(73, 'calm', dolly([-1.2, 1.5, 2.6], [-.6, 1.5, 2.0], [.9, 1.4, .6], [.9, 1.4, .6], 40, 3, 0), (lt, T, a) => { a.at(ph, .9, 1.35, .6, -.35); a.put(seller, [0, .2, 0], .05, 'phone', lt); phUI.draw({ sold: 1, rm: [1, rmAt(T, W(73) - .2), rmAt(T, W(74) + .3)] }); });
  sh(77, 'calm', dolly([0, 1.3, 3.4], [0, 1.6, 2.2], [0, 1.4, 0], [0, 1.5, 0], 48, -4, 0), (lt, T, a) => { a.put(seller, [0, .2, 0], 0, 'cheer', lt); a.at(hd, -1.2, 1.2 + Math.abs(Math.sin(T * 5)) * .3, 0, T * 2); }, {});
  cue(W(77), 'pop');
  sh(80, 'calm', dolly([-.4, 1.2, 5.2], [0, 1.7, 4.2], [0, 2.4, 0], [0, 2.5, 0], 52, 0, 0), (lt, T, a) => { a.put(seller, [0, .2, 0], 0, 'cheer', lt); }, {}, -.08);
  endCard(t(80, -.1)); cue(t(80, -.1), 'pop');
}
