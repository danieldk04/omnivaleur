// NL, stijl A (blokpoppetjes), sketch met twee stemmen: sollicitatiegesprek. Snel: een shot per ~1 s, snijden op het woord.
import { studio, hoodieProp, phoneProp } from '../sets.js';
export const style = 'blocky';
export const hotColor = '#ffd23f';
export const hotWords = ['vijf', 'titel', 'vier', 'apps', 'half', 'vijfenveertig', 'Omnivaleur', 'overal', 'Slapen', 'avonden', 'geen'];

export async function build(K) {
  const { X, set, shot, actor, prop, label, W, cue, dolly, stat, pop, E, prog, lerp, liveTex, omniUI, endCard, cl } = K;
  const PI = Math.PI;
  set('office', (X, g) => { studio(X, g, { wall: '#9fc3e8', floor: '#e6dcc8' }); X.box(g, [1.8, .1, 1.1], [0, .82, -.2], '#b98a5a'); [[-.8, -.45], [.8, -.45], [-.8, .45], [.8, .45]].forEach(([a, b]) => X.box(g, [.1, .8, .1], [a, .4, -.2 + b], '#8a6a46')); X.box(g, [2.2, 1.3, .1], [0, 2.6, -2.4], '#f4f1ea'); return { bg: '#9fc3e8' }; });
  const boss = actor({ skin: '#a8734f', shirt: '#2a2f45', pants: '#1c2030', hairStyle: 'short', hair: '#14141a', sleeves: true });
  const cand = actor({ skin: '#d9a07a', shirt: '#3c4b73', pants: '#2a2f45', hairStyle: 'beanie', sleeves: true });
  const ph = prop(phoneProp(X, null, 1.7)); const phUI = liveTex(512, 900, (x, w, h, p) => omniUI(x, w, h, p));
  ph.userData.screen.material.map = phUI.tex; ph.userData.screen.material.needsUpdate = true;
  const hd = prop(hoodieProp(X, '#3c4b73', .9));
  const L = (t, c, o = {}) => label(t, { h: .5, bg: c, fg: o.fg || '#fff', ...o });
  const lTitle = L('SOLLICITATIE', '#ffd23f', { fg: '#0a1936', h: .6 }), lTit = L('DEZELFDE TITEL', '#ff4d4d', { h: .5 }), lClock = L('01:30', '#0a0a0a', { fg: '#ff6b6b', h: .8 }), lEuro = L('€45', '#ffd23f', { fg: '#0a1936', h: .7 });
  const apps = [['Vinted', '#09b1ba'], ['Marktplaats', '#2f6fe0'], ['eBay', '#e53238'], ['Eigen shop', '#6b46c1']].map(([n, c]) => L(n, c, { h: .5 }));
  const ok = ['Vinted ✓', 'Marktplaats ✓', 'eBay ✓', 'Eigen shop ✓'].map(n => L(n, '#1faa6b', { h: .5 }));
  const l7 = L('7 DAGEN GRATIS', '#85edbc', { fg: '#0a1936', h: .6 }), lZzz = L('Z z z', '#cfd8ff', { fg: '#3a4a80', h: .6 }), lSol = L('"TOT HALF TWEE"', '#ffffff', { fg: '#0a1936', h: .5 });
  const t = (i, off = 0) => Math.max(0, W(i) + off);
  const sh = (i, s, cam, fn, o = {}, off = -.04) => shot(t(i, off), s, cam, fn, o);
  const tt = (i, off = 0) => { try { return W(i) + off; } catch (e) { return 1e9; } };
  const mouth = (T, a, b) => (T >= tt(a) && T < tt(b, -.05) ? { open: .25 + .5 * Math.abs(Math.sin(T * 17)), mouth: .6 } : { open: 0 });
  const B = (a, lt, anim, T, sa, sb, o = {}) => a.put(boss, [-1.5, 0, 0], PI / 2, anim, lt, { ...o, ...mouth(T, sa, sb) });
  const C = (a, lt, anim, T, sa, sb, o = {}) => a.put(cand, [1.5, 0, 0], -PI / 2, anim, lt, { ...o, ...mouth(T, sa, sb) });
  const both = (a, lt, T, ba, ca, sp, o = {}) => { B(a, lt, ba, T, sp[0], sp[1], o.b); C(a, lt, ca, T, sp[2], sp[3], o.c); };
  // middenshots (hoofd en schouders) met kleine push-in; z = afstand, k = rol, z2 = push-in
  const BC = (roll = 0, push = .3) => dolly([.8, 1.85, 4.4], [.8 - push, 1.8, 4.4 - push * 1.8], [-1.5, 1.65, 0], [-1.5, 1.65, 0], 36, roll, 0);
  const CC = (roll = 0, push = .3) => dolly([2.6, 1.85, 4.4], [2.6 - push, 1.8, 4.4 - push * 1.8], [1.5, 1.65, 0], [1.5, 1.65, 0], 36, roll, 0);
  const wide = (k = 0) => stat([k, 1.9, 5.6], [0, 1.3, 0], 46, 0);
  // 1. vraag
  sh(0, 'office', wide(), (lt, T, a) => { both(a, lt, T, 'idle', 'idle', [0, 8, 99, 99]); a.at(lTitle, 0, 2.7, -.2); a.sc(lTitle, pop(lt, .1, .3)); }, {}, 0);
  sh(1, 'office', BC(3), (lt, T, a) => { B(a, lt, 'think', T, 0, 8); C(a, lt, 'idle', T, 99, 99); });
  sh(5, 'office', BC(-3, .6), (lt, T, a) => { B(a, lt, 'think', T, 0, 8); C(a, lt, 'idle', T, 99, 99); });
  // 2. Eh... nog steeds dezelfde titel
  sh(8, 'office', CC(-3), (lt, T, a) => { C(a, lt, 'shrug', T, 8, 19); B(a, lt, 'idle', T, 99, 99); });
  sh(11, 'office', CC(4, .5), (lt, T, a) => { C(a, lt, 'sad', T, 8, 19); B(a, lt, 'idle', T, 99, 99); a.at(lTit, 1.5, 2.55, 0); a.sc(lTit, pop(lt, .05, .3)); });
  cue(W(11), 'pop');
  sh(16, 'office', dolly([0, 2.4, 6.4], [0, 2.0, 5.2], [0, 1.9, -.2], [0, 1.9, -.2], 52, 0, 0), (lt, T, a) => { both(a, lt, T, 'idle', 'idle', [99, 99, 8, 19]); apps.forEach((l, i) => { a.at(l, -1.2 + i * .85, 2.6 + (i % 2) * .5, -.2); a.sc(l, pop(T, t(17) + (i - 1) * .22 + .15, .3)); }); }, {}, -.1);
  cue(W(17), 'pop'); cue(W(17) + .45, 'pop'); cue(W(18) + .1, 'pop');
  // 3. Dat is... geen antwoord
  sh(19, 'office', BC(2), (lt, T, a) => { B(a, lt, 'idle', T, 19, 23, { brow: .3, mouth: -.2 }); C(a, lt, 'idle', T, 99, 99); });
  sh(21, 'office', BC(-2, .9), (lt, T, a) => { B(a, lt, 'idle', T, 19, 23, { brow: .5, mouth: -.5, eye: .7 }); C(a, lt, 'idle', T, 99, 99); });
  // 4. mijn hele avond
  sh(23, 'office', CC(4), (lt, T, a) => { C(a, lt, 'sad', T, 23, 40); B(a, lt, 'idle', T, 99, 99); });
  sh(27, 'office', CC(0, .6), (lt, T, a) => { C(a, lt, 'laugh', T, 23, 40, { mouth: -.8, brow: -.4 }); B(a, lt, 'idle', T, 99, 99); });
  sh(30, 'office', stat([0, 1.6, 3.4], [0, 2.3, -.2], 44, 0), (lt, T, a) => { a.at(lClock, 0, 2.3, -.2); a.sc(lClock, pop(lt, .05, .3) * (1 + .04 * Math.sin(T * 9))); both(a, lt, T, 'idle', 'idle', [99, 99, 99, 99]); });
  cue(W(30), 'tick');
  sh(34, 'office', dolly([.2, 1.3, 2.8], [.6, 1.5, 2.2], [0, 1.3, 0], [0, 1.4, 0], 46, 0, 0), (lt, T, a) => { a.at(hd, 0, 1.25 + Math.sin(T * 3) * .05, 0, T * 2.2); a.at(lEuro, 0, 2.3, 0); a.sc(lEuro, pop(T, t(38, -.1), .3)); C(a, lt, 'sad', T, 23, 40); B(a, lt, 'idle', T, 99, 99); });
  // 5. Ken je Omnivaleur
  sh(40, 'office', BC(-2), (lt, T, a) => { B(a, lt, 'point', T, 40, 54, { mouth: .8 }); C(a, lt, 'idle', T, 99, 99); });
  sh(43, 'office', dolly([.9, 1.5, 2.4], [.7, 1.45, 1.4], [.8, 1.4, .5], [.8, 1.4, .5], 38, 0, 0), (lt, T, a) => { a.at(ph, .8, 1.35, .5, -.3); phUI.draw({ sold: 0, rm: [0, 0, 0] }); });
  sh(46, 'office', dolly([.9, 1.5, 2.2], [.7, 1.45, 1.4], [.8, 1.4, .5], [.8, 1.4, .5], 38, 0, 0), (lt, T, a) => { a.at(ph, .8, 1.35, .5, -.3); phUI.draw({ sold: 1, rm: [prog(T, t(46), t(47), E.out), prog(T, t(48), t(49), E.out), prog(T, t(49), t(50), E.out)] }); });
  cue(W(46), 'ding'); cue(W(49), 'tick'); cue(W(50) - .2, 'tick');
  sh(49, 'office', dolly([0, 2.2, 6.0], [0, 2.0, 5.0], [0, 1.8, -.2], [0, 1.8, -.2], 52, 0, 0), (lt, T, a) => { both(a, lt, T, 'idle', 'idle', [40, 54, 99, 99]); ok.forEach((l, i) => { a.at(l, -1.3 + i * .9, 2.6 + (i % 2) * .5, -.2); a.sc(l, pop(T, t(49) + i * .2, .3)); }); }, {}, -.1);
  cue(W(49), 'ding'); cue(W(49) + .2, 'ding'); cue(W(49) + .4, 'ding');
  sh(51, 'office', BC(2), (lt, T, a) => { B(a, lt, 'cheer', T, 40, 54); C(a, lt, 'idle', T, 99, 99); a.at(l7, -1.3, 2.8, 0); a.sc(l7, pop(lt, .05, .3)); });
  cue(W(51), 'pop');
  // 6. wat ga ik dan doen
  sh(54, 'office', CC(3), (lt, T, a) => { C(a, lt, 'shock', T, 54, 64); B(a, lt, 'idle', T, 99, 99); });
  sh(59, 'office', CC(-2, .7), (lt, T, a) => { C(a, lt, 'think', T, 54, 64); B(a, lt, 'idle', T, 99, 99); });
  sh(63, 'office', CC(0, .8), (lt, T, a) => { C(a, lt, 'shrug', T, 54, 64); B(a, lt, 'idle', T, 99, 99); });
  // 7. Slapen, joh
  sh(64, 'office', BC(0, .8), (lt, T, a) => { B(a, lt, 'idle', T, 64, 66, { brow: .25, mouth: -.1 }); C(a, lt, 'idle', T, 99, 99); }, {}, -.05);
  sh(65, 'office', stat([0, 1.9, 5.6], [0, 1.3, 0], 46, 0), (lt, T, a) => { B(a, lt, 'idle', T, 99, 99); C(a, lt, 'sleep', T, 99, 99); a.at(lZzz, 1.5, 2.6 + Math.sin(T * 2) * .08, 0); a.sc(lZzz, pop(lt, .3, .3)); }, {}, .55);
  endCard(t(65, 1.3)); cue(t(65, 1.3), 'pop');
}
