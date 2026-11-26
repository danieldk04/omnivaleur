// NL, stijl C (realistischer), relatiegrap met twee stemmen: het eten wordt koud. Kruisgesneden tussen keuken en zolder.
import { kitchen, attic, phoneProp, laptopProp } from '../sets.js';
export const style = 'real';
export const hotWords = ['Schat', 'eten', 'uur', 'Omnivaleur', 'Tien', 'vier', 'overal', 'gratis', 'Eten', 'zet'];

export async function build(K) {
  const { X, THREE, set, shot, actor, prop, label, W, cue, dolly, stat, pop, E, prog, lerp, liveTex, omniUI, endCard, cl } = K;
  const PI = Math.PI;
  const warm = (g, x, y, z, i = 14) => { const pl = new THREE.PointLight('#ffb870', i, 10, 1.5); pl.position.set(x, y, z); g.add(pl); };
  const nightP = { wall: '#2c3050', floor: '#3a3030', sky: '#0c1430', skyL: '#6f86c9', lamp: '#ffd9a0', sunC: '#ffcf9a', sunI: 1.7, hemi: .7 };
  set('kit', (X, g) => { kitchen(X, g, { ...nightP, wall: '#d9c9ad', floor: '#7a6a58', sunI: 2, hemi: .9 }); warm(g, 0, 2.3, .6, 18); X.box(g, [1.4, .08, .9], [1.2, .82, .9], '#c89a6a'); return { bg: '#1a1d33', fog: ['#1a1d33', 10, 28] }; });
  set('study', (X, g) => { attic(X, g, nightP); warm(g, 1.6, 1.7, -1.9, 14); return { bg: '#0b1230', fog: ['#0b1230', 9, 26] }; });
  const her = actor({ skin: '#f0cdb0', shirt: '#b84a6a', pants: '#2a2a34', hairStyle: 'bun', hair: '#5a3a2a' });
  const him = actor({ skin: '#d9a07a', shirt: '#8a8f99', pants: '#2f3a55', hairStyle: 'short', hair: '#2a1d16' });
  const lap = prop(laptopProp(X, null, 1)); const ph = prop(phoneProp(X, null, 1.7));
  const type = liveTex(512, 312, (x, w, h, n) => { x.fillStyle = '#fff'; x.fillRect(0, 0, w, h); x.fillStyle = '#09b1ba'; x.fillRect(0, 0, w, h * .16); x.fillStyle = '#fff'; x.font = '900 32px Montserrat'; x.textBaseline = 'middle'; x.fillText('Nieuwe advertentie', 20, h * .08); x.fillStyle = '#0a1936'; x.font = '800 30px Montserrat'; const s = 'Leren jas, maat L, als nieuw'.slice(0, Math.floor(n) % 29); x.fillText(s + (Math.floor(n * 2) % 2 ? '|' : ''), 20, h * .38); x.fillStyle = '#c8d0de'; x.fillRect(20, h * .55, w - 40, 14); x.fillRect(20, h * .65, w * .7, 14); });
  const phUI = liveTex(512, 900, (x, w, h, p) => omniUI(x, w, h, { title: 'Leren jas', price: '€89', ...p }));
  const clk = liveTex(512, 256, (x, w, h, s) => { x.fillStyle = '#12080a'; x.fillRect(0, 0, w, h); x.fillStyle = s.c || '#ff3b30'; x.font = '900 120px Montserrat'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(s.t, w / 2, h / 2 + 6); });
  const clkM = prop(new THREE.Mesh(new THREE.PlaneGeometry(1.4, .7), new THREE.MeshBasicMaterial({ map: clk.tex })));
  const scr = (o, tex) => { const m = o.userData.screen.material; if (m.map !== tex) { m.map = tex; m.needsUpdate = true; } };
  const L = (t, c, o = {}) => label(t, { h: .55, bg: c, fg: o.fg || '#fff', ...o });
  const lPasta = L('PASTA', '#ffd23f', { fg: '#0a1936', h: .7 }), lKoud = L('KOUD', '#6fb7ff', { h: .6 }), lMp = L('Marktplaats', '#2f6fe0'), lE = L('eBay', '#e53238'), lF = L("FOTO'S", '#7a3fa0'), l10 = L('10 SEC', '#1faa6b', { h: .8 }), l4 = L('4 UUR', '#ff4d4d', { h: .8 }), lOm = L('Omnivaleur ✓', '#1faa6b', { h: .7 }), l7 = L('7 DAGEN GRATIS', '#85edbc', { fg: '#0a1936', h: .7 });
  const t = (i, off = 0) => Math.max(0, W(i) + off);
  const sh = (i, s, cam, fn, o = {}, off = -.04) => shot(t(i, off), s, cam, fn, o);
  const tt = (i, off = 0) => { try { return W(i) + off; } catch (e) { return 1e9; } };
  const talk = (T, a, b) => (T >= tt(a) && T < tt(b, -.05) ? { open: .25 + .5 * Math.abs(Math.sin(T * 17)), mouth: .6 } : { open: 0 });
  const H = (a, lt, T, anim, sa, sb, o = {}) => a.put(her, [-.9, 0, .3], .4, anim, lt, { ...o, ...talk(T, sa, sb) });
  const M = (a, lt, T, anim, sa, sb, o = {}) => a.put(him, [1.2, 0, -1.7], PI, anim, lt, { sit: 1, ...o, ...talk(T, sa, sb) });
  const Mface = (a, lt, T, anim, sa, sb, o = {}) => a.put(him, [1.2, 0, -1.7], 0, anim, lt, { sit: 1, ...o, ...talk(T, sa, sb) });
  const dsk = a => { a.at(lap, 1.6, .87, -2.7); };
  // keuken: eten klaar
  sh(0, 'kit', dolly([-3.0, 1.5, 4.4], [-1.8, 1.55, 3.6], [-.9, 1.4, .3], [-.9, 1.4, .3], 46, 0, 0), (lt, T, a) => { H(a, lt, T, 'wave', 0, 5); a.at(lPasta, 1.2, 1.7, .9); a.sc(lPasta, pop(lt, .15, .3)); }, {}, 0);
  cue(W(0), 'pop');
  sh(2, 'kit', stat([.3, 1.6, 3.4], [-.9, 1.45, .3], 34, -3), (lt, T, a) => { H(a, lt, T, 'wave', 0, 5, { brow: -.2 }); });
  // zolder: ja ja
  sh(5, 'study', dolly([3.2, 1.9, .8], [2.8, 1.7, .3], [1.4, 1.3, -2.3], [1.4, 1.3, -2.3], 44, 4, 0), (lt, T, a) => { M(a, lt, T, 'type', 5, 10); dsk(a); scr(lap, type.tex); type.draw(T * 14); }, { shake: .01 });
  sh(7, 'study', dolly([1.5, 1.25, -1.3], [1.6, 1.2, -1.9], [1.6, 1.15, -2.7], [1.6, 1.15, -2.7], 36, 0, 0), (lt, T, a) => { dsk(a); scr(lap, type.tex); type.draw(T * 16); });
  // een uur geleden
  sh(10, 'kit', dolly([.8, 1.6, 3.6], [.4, 1.6, 3.1], [-.9, 1.45, .3], [-.9, 1.45, .3], 36, -3, 0), (lt, T, a) => { H(a, lt, T, 'idle', 10, 16, { brow: .5, mouth: -.4 }); });
  sh(13, 'study', stat([-.1, 2.3, .6], [-.1, 2.3, -3.36], 36, 0), (lt, T, a) => { a.at(clkM, -.1, 2.35, -3.36); clk.draw({ t: T < t(14) ? '19:00' : '20:00' }); });
  cue(W(14), 'tick');
  // ja maar Marktplaats, eBay, foto's
  sh(16, 'study', dolly([.4, 1.5, 1.2], [.7, 1.5, .7], [1.2, 1.35, -1.7], [1.2, 1.35, -1.7], 38, -4, 2), (lt, T, a) => { Mface(a, lt, T, 'panic', 16, 29); });
  sh(22, 'study', stat([2.6, 1.7, -1.2], [1.6, 1.3, -2.2], 42, 0), (lt, T, a) => { M(a, lt, T, 'type', 16, 29); dsk(a); a.at(lMp, 1.6, 2.1, -2.7); a.sc(lMp, pop(T, t(23, -.1), .3)); a.at(lE, 2.5, 2.1, -2.2); a.sc(lE, pop(T, t(25, -.1), .3)); });
  cue(W(23), 'pop'); cue(W(25), 'pop');
  sh(26, 'study', dolly([.5, 1.5, 1.0], [.8, 1.5, .6], [1.2, 1.35, -1.7], [1.2, 1.35, -1.7], 36, 3, -2), (lt, T, a) => { Mface(a, lt, T, 'panic', 16, 29, { sweat: 1 }); a.at(lF, .5, 2.4, -1.3); a.sc(lF, pop(lt, .15, .3)); }, { shake: .015 });
  // ik heb hem net overal gezet
  sh(29, 'kit', dolly([-2.8, 1.5, 3.2], [-1.6, 1.55, 2.4], [-.8, 1.4, .3], [-.8, 1.4, .3], 40, 0, 0), (lt, T, a) => { H(a, lt, T, 'phone', 29, 39, { mouth: .5 }); a.at(ph, -.2, 1.3, .8, .4); scr(ph, phUI.tex); phUI.draw({ sold: 0, rm: [0, 0, 0] }); });
  sh(33, 'kit', dolly([.3, 1.5, 2.4], [-.1, 1.4, 1.5], [-.2, 1.3, .8], [-.2, 1.3, .8], 34, 0, 0), (lt, T, a) => { H(a, lt, T, 'phone', 29, 39); a.at(ph, -.2, 1.3, .8, .4); scr(ph, phUI.tex); phUI.draw({ sold: 1, rm: [prog(T, t(33), t(34), E.out), prog(T, t(34), t(35), E.out), prog(T, t(35), t(36), E.out)] }); });
  cue(W(34), 'tick'); cue(W(35), 'tick'); cue(W(36), 'ding');
  sh(36, 'kit', stat([-.4, 1.9, 3.8], [-.8, 1.6, .3], 38, 2), (lt, T, a) => { H(a, lt, T, 'idle', 29, 39); a.at(lOm, -.2, 2.9, .3); a.sc(lOm, pop(lt, .05, .3)); });
  sh(37, 'kit', dolly([.6, 1.6, 3.6], [.1, 1.6, 3.1], [-.8, 1.6, .3], [-.8, 1.6, .3], 36, 0, 0), (lt, T, a) => { H(a, lt, T, 'idle', 29, 39); a.at(l10, -.2, 2.7, .3); a.sc(l10, pop(lt, .05, .3)); });
  cue(W(37), 'pop');
  // ik zit hier al vier uur
  sh(39, 'study', dolly([.5, 1.5, 1.3], [.7, 1.5, .8], [1.2, 1.35, -1.7], [1.2, 1.35, -1.7], 34, 0, 0), (lt, T, a) => { Mface(a, lt, T, 'shock', 39, 45, { eye: 1.3 }); });
  sh(43, 'study', stat([3.2, 1.7, .5], [1.2, 1.35, -1.7], 40, -3), (lt, T, a) => { Mface(a, lt, T, 'sad', 39, 45); a.at(l4, 1.4, 2.7, -1.6); a.sc(l4, pop(lt, .05, .3)); });
  cue(W(43), 'hit');
  // Eten.
  sh(45, 'kit', dolly([.2, 1.6, 3.2], [-.1, 1.6, 2.7], [-.9, 1.5, .3], [-.9, 1.5, .3], 34, 0, 0), (lt, T, a) => { H(a, lt, T, 'idle', 45, 51, { brow: .2, mouth: .8 }); }, {}, -.05);
  sh(46, 'kit', dolly([.2, 1.8, 5.0], [.1, 1.7, 4.4], [.1, 1.3, .4], [.1, 1.3, .4], 46, 0, 0), (lt, T, a) => { H(a, lt, T, 'idle', 45, 51, { mouth: .9 }); a.put(him, [.9, 0, .5], -.9, 'sad', lt, {}); a.at(l7, -.4, 2.7, .4); a.sc(l7, pop(T, t(48, -.1), .35)); }, {}, .4);
  cue(W(47), 'pop');
  endCard(t(50, .5)); cue(t(50, .5), 'pop');
}
