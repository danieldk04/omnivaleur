// Renno-ontleding toegepast: analogie (concertticket + portier), spiegel (hoodie), product als echte geanimeerde UI,
// kleurboog koud (nacht) naar warm (zonsopkomst), rekwisieten die het verhaal dragen, terugkoppeling in het slot.
import { bedroom, street, studio, hoodieProp, phoneProp, laptopProp } from '../sets.js';
export const style = 'toon';
export const hotWords = ['twice', 'doorman', 'hoodie', 'once', 'Omnivaleur', 'refunds'];

export async function build(K) {
  const { X, THREE, set, shot, actor, prop, label, stamp, ticketProp, scannerProp, gate, W, cue, dolly, orbit, stat, pop, E, prog, lerp, liveTex, endCard, title, frames, cl } = K;
  const PI = Math.PI;
  const night = { wall: '#3b4170', floor: '#5a4638', sky: '#101c42', skyL: '#8a9ce0', sunC: '#9fb2ff', sunI: 1.0, hemi: .7, lamp: '#ffd8a0', blanket: '#e07a3d', rug: '#9a4a3a' };
  set('gate', (X, g) => gate(X, g));
  set('bed', (X, g) => { bedroom(X, g, night); const pl = new THREE.PointLight('#ffb870', 12, 9, 1.6); pl.position.set(-.7, 1.7, -2.2); g.add(pl); return { bg: '#0b1230', fog: ['#0b1230', 10, 30] }; });
  set('lab', (X, g) => {
    X.light(g, { sun: [3, 7, 6], sunC: '#cfeaff', sunI: 1.9, hemi: .9, sky: '#9fd8ff', gnd: '#1a3a50' });
    X.box(g, [40, .2, 40], [0, -.1, 0], '#17303f'); X.box(g, [40, 20, .4], [0, 10, -6], '#0f4a5e'); X.cyl(g, 2.6, .12, [0, .06, -.6], '#1f5a70', { seg: 48 });
    X.box(g, [2.0, .1, 1.1], [0, .82, -.9], '#d9b98a'); [[-.9, -.45], [.9, -.45], [-.9, .45], [.9, .45]].forEach(([a, b]) => X.box(g, [.1, .8, .1], [a, .4, -.9 + b], '#a47c48'));
    return { bg: '#0f4a5e', fog: ['#0f4a5e', 14, 40] };
  });
  set('dawn', (X, g) => { street(X, g, { sky: '#ffb88a', sunC: '#ffb060', sunI: 2.8, wall: '#f3d7b5', grass: '#8ccf6a', sun: [-8, 3.2, 6], skyL: '#ffd6b0' }); return { bg: '#ffb98c', fog: ['#ffc79c', 14, 50] }; });
  set('warm', (X, g) => { studio(X, g, { wall: '#f6c9a0', floor: '#efe0c8' }); return { bg: '#f6c9a0' }; });

  const hero = actor({ name: 'hero', skin: '#e0ac85', shirt: '#4a63c0', pants: '#2a2f45', hairStyle: 'short' });
  const door = actor({ name: 'doorman', skin: '#7a4e32', shirt: '#1d2230', pants: '#15161d', hairStyle: 'none', scale: 1.1, sleeves: true });
  const b1 = actor({ name: 'buyer1', skin: '#a8734f', shirt: '#2f6f7a', hairStyle: 'cap', cap: '#e8872a' });
  const b2 = actor({ name: 'buyer2', skin: '#f6d7c0', shirt: '#d9658a', hairStyle: 'bun', hair: '#5a3a2a' });
  const hood = prop(hoodieProp(X, '#3d6df0', 1.0), 'hoodie'); hood.rotation.order = 'YXZ';
  const tA = prop(ticketProp(X, 'ADMIT ONE\nSEAT 12'), 'ticketA'), tB = prop(ticketProp(X, 'ADMIT ONE\nSEAT 12'), 'ticketB');
  const scan = prop(scannerProp(X, 1.0), 'scanner');
  const mark = prop((() => { const m = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 1.5 * 96 / 176), new THREE.MeshBasicMaterial({ transparent: true })); return m; })(), 'mark');
  const markTex = await K.image('assets/mark.png'); mark.material.map = markTex; mark.material.needsUpdate = true;
  const wide = await frames('assets/dash/wide', 124, 20, 1440 / 878), close = await frames('assets/dash/close', 124, 20, 752 / 800);
  const lap = prop(laptopProp(X, null, 1.25), 'laptop'); const card = prop(new THREE.Mesh(new THREE.PlaneGeometry(2.2, 2.2 / (752 / 800)), new THREE.MeshBasicMaterial({ map: close.tex })), 'card');
  const scr = (o, tex) => { const m = o.userData.screen.material; if (m.map !== tex) { m.map = tex; m.needsUpdate = true; } };
  const phone = prop(phoneProp(X, null, 1.7), 'phone');
  const ph = liveTex(320, 560, (x, w, h, m) => {
    x.fillStyle = '#fff'; x.fillRect(0, 0, w, h);
    if (m.mode === 'sold') {
      x.fillStyle = '#0a1936'; x.fillRect(0, 0, w, h * .12); x.fillStyle = '#fff'; x.font = '900 28px Montserrat'; x.textBaseline = 'middle'; x.fillText('Notifications', 20, h * .06); if (m.a < .02) { x.fillStyle = '#b3bdd0'; x.font = '800 26px Montserrat'; x.textAlign = 'center'; x.fillText('No new sales', w / 2, h * .5); x.textAlign = 'left'; }
      [['Vinted', '#09b1ba', m.a], ['Marktplaats', '#2f6fe0', m.b]].forEach(([n, c, k], i) => { const y = h * (.2 + i * .25), off = (1 - k) * -w; x.save(); x.translate(off, 0); x.fillStyle = '#f4f7fb'; x.beginPath(); x.roundRect(14, y, w - 28, h * .2, 18); x.fill(); x.fillStyle = c; x.beginPath(); x.arc(52, y + h * .1, 22, 0, 7); x.fill(); x.fillStyle = '#0a1936'; x.font = '900 26px Montserrat'; x.fillText(n, 90, y + h * .065); x.fillStyle = '#e53935'; x.font = '900 40px Montserrat'; x.fillText('SOLD  45', 90, y + h * .135); x.restore(); });
      return;
    }
    x.fillStyle = m.mode === 'mp' ? '#2f6fe0' : '#09b1ba'; x.fillRect(0, 0, w, h * .13); x.fillStyle = '#fff'; x.font = '900 32px Montserrat'; x.textBaseline = 'middle'; x.fillText(m.mode === 'mp' ? 'Marktplaats' : 'Vinted', 20, h * .065);
    x.fillStyle = '#dbeafe'; x.beginPath(); x.roundRect(w * .18, h * .17, w * .64, h * .34, 18); x.fill(); x.fillStyle = '#3d6df0'; x.beginPath(); x.roundRect(w * .36, h * .27, w * .28, h * .2, 14); x.fill(); x.fillRect(w * .24, h * .3, w * .16, h * .13); x.fillRect(w * .6, h * .3, w * .16, h * .13); x.beginPath(); x.arc(w * .5, h * .26, w * .07, 0, 7); x.fill(); x.fillStyle = '#0a1936'; x.font = '900 25px Montserrat'; x.fillText('Blue hoodie, size M', 20, h * .6); x.fillStyle = '#e53935'; x.font = '900 40px Montserrat'; x.fillText('EUR 45', 20, h * .7);
    x.fillStyle = '#85edbc'; x.beginPath(); x.roundRect(20, h * .8, w - 40, h * .1, 16); x.fill(); x.fillStyle = '#0a1936'; x.font = '900 28px Montserrat'; x.textAlign = 'center'; x.fillText(m.pub ? 'LIVE ✓' : 'PUBLISH', w / 2, h * .85); x.textAlign = 'left';
  });
  const stScan = stamp('SCANNED', '#10b981', { h: .5 }), stDeny = stamp('ALREADY\nSCANNED', '#e53935', { h: .6 }), stNo = stamp('NOT\nSCANNED', '#f59e0b', { h: .6 });
  const stS1 = stamp('SOLD', '#e53935', { h: .55 }), stS2 = stamp('SOLD', '#e53935', { h: .55 }), stTw = stamp('SOLD\nTWICE', '#e53935', { h: .55 });
  const stRef = stamp('NO\nREFUNDS', '#10b981', { h: .75 }), stOnce = stamp('SCANNED\nONCE', '#10b981', { h: .7 });
  const eq = label('=', { h: .9, bg: null, fg: '#fff' });
  const chan = ['Vinted', 'Marktplaats', 'eBay', 'Shopify'].map((n, i) => label(n, { h: .5, bg: ['#09b1ba', '#2f6fe0', '#e53238', '#6b46c1'][i], fg: '#fff' }));
  const t = (i, off = 0) => Math.max(0, W(i) + off);
  const sh = (i, s, cam, fn, o, off = -.04) => shot(t(i, off), s, cam, (lt, T, a, k) => { hood.rotation.x = 0; fn(lt, T, a, k); }, o);
  const D0 = t(51) - 1.0; // dashboard-tijd 0 (verkoop op Vinted valt op "sells")
  const dt = T => cl(T - D0, 0, 6.15);
  const pose = (a, p, ry, anim, lt, ex) => a.put ? 0 : 0;

  // ===== Haak: de poortwachter en het ticket =====
  title(.15, t(8, -.1), "You'd never sell the same concert ticket <em>twice.</em>");
  sh(0, 'gate', dolly([0, 5.4, 10], [0, 2.1, 6.2], [0, 1.2, -3], [0, 1.4, -2.8], 48), (lt, T, a) => {
    a.put(door, [1.2, 0, -3.6], 0, 'idle', lt); a.put(hero, [-1.1, 0, -1.3], .35, 'idle', lt); a.put(b1, [-2.6, 0, -2.4], .7, 'idle', lt + .4); a.put(b2, [2.8, 0, -2.2], -.6, 'idle', lt + .8);
  }, { nocap: true }, 0);
  sh(3, 'gate', dolly([0, 1.0, 3.0], [0, 1.1, 2.3], [0, 2.1, -.5], [0, 2.1, -.5], 40), (lt, T, a) => {
    a.put(hero, [0, 0, -1.0], 0, 'carry', lt, { mouth: .7, brow: -.1 }); a.at(tA, 0, 1.38, -.2, 0);
  }, { nocap: true });
  sh(5, 'gate', orbit([0, 0, -1.0], 3.8, 1.1, .25, -.3, 40, 2.0), (lt, T, a) => {
    a.put(hero, [0, 0, -1.0], 0, 'carry', lt, { mouth: .7 }); a.at(tA, 0, 1.38, -.2, 0);
  }, { nocap: true });
  sh(7, 'gate', dolly([0, 1.6, 5.6], [0, 1.5, 4.2], [0, 1.9, -1.2], [0, 1.9, -1.2], 46), (lt, T, a) => {
    a.put(hero, [0, 0, -1.2], 0, 'laugh', lt, { lz: .5, rz: .5 }); a.put(b1, [-1.5, 0, -1.2], PI / 2, 'carry', lt); a.put(b2, [1.5, 0, -1.2], -PI / 2, 'carry', lt + .3);
    a.at(tA, -.72, 1.42, -1.2, PI / 2); a.at(tB, .72, 1.42, -1.2, -PI / 2);
  }, { nocap: true });
  cue(W(7), 'pop');
  // ===== Twee mensen, een stoel =====
  sh(8, 'gate', dolly([0, 2.2, 3.8], [0, 1.9, 2.8], [0, 1.4, -3.1], [0, 1.4, -3.1], 50), (lt, T, a) => {
    a.put(door, [0, 0, -3.7], 0, 'idle', lt); a.put(b1, [-.9, 0, -2.0], PI, 'carry', lt); a.put(b2, [.9, 0, -2.0], PI, 'carry', lt + .3);
    a.at(tA, -.9 + .0, 1.42, -2.8, PI); a.at(tB, .9, 1.42, -2.8, PI);
  }, { allow: ['actors'] });
  sh(10, 'gate', stat([0, 1.45, 1.4], [0, 1.42, -2.8], 36), (lt, T, a) => {
    a.at(tA, -.4, 1.42, -2.8, 0); a.at(tB, .4, 1.42, -2.8, 0); a.at(eq, 0, 1.42, -2.7); a.sc(eq, pop(lt, .25, .3) * .6);
  });
  cue(W(10) + .25, 'pop');
  sh(12, 'gate', dolly([1.4, 1.7, -.7], [1.1, 1.75, -1.5], [1.2, 1.75, -3.6], [1.2, 1.75, -3.6], 32), (lt, T, a) => {
    a.put(door, [1.2, 0, -3.7], 0, 'idle', lt, { brow: .35, mouth: -.2, eye: .85 });
  });
  sh(14, 'gate', dolly([3.2, 1.8, -1.0], [2.5, 1.7, -1.4], [0, 1.5, -2.9], [0, 1.5, -2.9], 42), (lt, T, a) => {
    a.put(door, [0, 0, -3.7], 0, 'carry', lt); a.put(b1, [0, 0, -2.1], PI, 'carry', lt); a.at(tA, 0, 1.42, -2.9, PI); a.at(scan, 0, 1.42, -2.82, 0);
    const k = pop(lt, .4, .3); a.at(stScan, 0, 2.15, -2.9); a.sc(stScan, k * .45);
  });
  cue(W(14) + .5, 'ding');
  sh(17, 'gate', dolly([.6, 1.7, 1.3], [.2, 1.65, .7], [0, 1.8, -2.6], [0, 1.8, -2.6], 48, 3, -3), (lt, T, a) => {
    a.put(door, [0, 0, -3.7], 0, 'point', lt, { brow: .5 }); a.put(b2, [0, 0, -2.0], 0, 'sad', lt); a.at(stDeny, .1, 2.45, -2.0); a.sc(stDeny, pop(lt, .4, .3) * .5);
  }, { nocap: false });
  cue(W(19), 'buzz');
  sh(21, 'gate', dolly([1.9, 1.4, 2.6], [-.7, 1.4, 2.6], [.3, 1.2, -.9], [-.4, 1.2, .1], 46), (lt, T, a) => {
    a.put(b2, [.6 - lt * 1.1, 0, -1.2 + lt * 1.3], -.6, 'walk', lt * .8, { hx: .45, mouth: -.8, brow: -.5, lx: .1, rx: .1 });
  });

  // ===== Spiegel: jouw hoodie =====
  sh(22, 'bed', dolly([-1.9, 1.5, 3.4], [-2.3, 1.45, 2.8], [-2.4, 1.1, -.5], [-2.4, 1.15, -.5], 46), (lt, T, a) => {
    a.put(hero, [-2.0, .33, -.35], 0, 'sad', lt, { sit: 1, hx: .35, mouth: .1 }); hood.rotation.x = -PI / 2; a.at(hood, -2.95, .98, -.7, .5); a.sc(hood, .8);
  }, { allow: ['set'] });
  sh(25, 'bed', dolly([-2.2, 1.75, 2.8], [-2.45, 1.75, 2.3], [-2.5, 1.75, .1], [-2.5, 1.75, .1], 34), (lt, T, a) => {
    ph.draw({ mode: 'v', pub: lt > .8 }); a.at(phone, -2.5, 1.75, .1, 0); if (phone.userData.screen.material.map !== ph.tex) { phone.userData.screen.material.map = ph.tex; phone.userData.screen.material.needsUpdate = true; }
  });
  cue(W(25), 'pop');
  sh(30, 'bed', dolly([-2.2, 1.75, 2.8], [-2.45, 1.75, 2.3], [-2.5, 1.75, .1], [-2.5, 1.75, .1], 34, 0, 3), (lt, T, a) => {
    ph.draw({ mode: 'mp', pub: lt > .7 }); a.at(phone, -2.5, 1.75, .1, 0); phone.userData.screen.material.map = ph.tex;
  });
  sh(33, 'bed', dolly([-2.2, 1.8, 3.2], [-2.45, 1.78, 2.6], [-2.5, 1.9, .1], [-2.5, 1.9, .1], 38, -3, 0), (lt, T, a) => {
    ph.draw({ mode: 'sold', a: prog(lt, .25, .6), b: prog(lt, .6, .95) }); a.at(phone, -2.5, 1.75, .1, 0); phone.userData.screen.material.map = ph.tex;
    if (lt > 1.05) { a.at(stTw, -2.5, 2.7, .3); a.sc(stTw, pop(lt, 1.05, .35) * .8); }
  }, { shake: .012 });
  cue(W(33) + .2, 'buzz'); cue(W(33) + .6, 'buzz'); cue(W(33) + 1.05, 'hit');
  sh(36, 'gate', dolly([-.6, 1.8, 4.2], [.2, 1.7, 3.3], [.4, 1.3, -3.0], [.4, 1.4, -3.2], 52), (lt, T, a) => {
    a.put(door, [1.5, 0, -3.5], -.2, 'sleep', lt); a.put(b1, [-1.0, 0, -1.0 - lt * 1.0], PI, 'walk', lt * .9); a.put(b2, [-.1, 0, -1.2 - lt * 1.0], PI, 'walk', lt * .9 + .3);
    a.at(scan, 2.3, .15, -3.0, .8); scan.rotation.x = -PI / 2;
  }, { allow: ['actors'] });
  sh(39, 'gate', stat([0, 1.45, -.2], [0, 1.42, -2.8], 36), (lt, T, a) => {
    scan.rotation.x = 0; a.at(tB, 0, 1.42, -2.8, 0); a.at(stNo, 0, 2.0, -2.7); a.sc(stNo, pop(lt, .25, .3) * .6);
  });
  cue(W(39) + .25, 'buzz');

  // ===== Omnivaleur is de portier =====
  title(t(41, -.1), t(48, -.1), "Omnivaleur is the <em>doorman</em> for your listings.");
  sh(41, 'lab', dolly([0, 1.7, 4.2], [0, 1.7, 2.8], [0, 1.7, -1.4], [0, 1.7, -1.4], 44), (lt, T, a) => {
    a.at(mark, 0, 1.75 + Math.sin(T * 2) * .04, -1.4, 0); a.sc(mark, pop(lt, .1, .5) * 1.25);
  }, { nocap: true });
  cue(W(41) - .05, 'whoosh');
  sh(44, 'lab', orbit([0, 0, -.9], 4.6, 1.5, .8, -.2, 48, 1.55), (lt, T, a) => {
    a.put(door, [0, 0, -.9], 0, 'carry', lt); a.at(scan, 0, 1.42, -.1, 0);
    chan.forEach((c, i) => { a.at(c, [-.8, -.6, .8, .75][i], [1.75, 1.0, 1.75, 1.0][i], -.3); a.sc(c, .45 * pop(T, t(45 + (i < 2 ? i : i - 1), -.05), .3)); });
  }, { nocap: true });

  // ===== De demo: echt dashboard, een verkoop haalt de rest weg =====
  sh(48, 'lab', dolly([0, 1.9, 3.1], [0, 1.5, 2.2], [0, 1.1, -.9], [0, 1.15, -.9], 36), (lt, T, a) => {
    a.at(lap, 0, .87, -.9, 0); lap.userData.lid.rotation.x = -.25; scr(lap, wide.tex); wide.draw(dt(T));
  });
  sh(51, 'lab', dolly([0, 2.2, 5.0], [0, 2.2, 4.5], [0, 2.2, -.9], [0, 2.2, -.9], 42), (lt, T, a) => {
    a.at(card, 0, 2.2, -.9, 0); close.draw(dt(T));
  });
  cue(D0 + 1.0, 'ding');
  sh(54, 'lab', dolly([.7, 2.8, 2.3], [.7, 2.3, 2.3], [.7, 2.8, -.9], [.7, 2.3, -.9], 28), (lt, T, a) => {
    a.at(card, 0, 2.2, -.9, 0); close.draw(dt(T));
  });
  [0, 1, 2, 3].forEach(k => cue(D0 + 1.0 + .5 + k * .45 + .55, 'tick'));
  sh(59, 'lab', dolly([-1.0, 1.6, 4.4], [-.2, 1.5, 3.6], [-.2, 1.2, -.9], [-.1, 1.2, -.9], 54, -3, 0), (lt, T, a) => {
    a.at(lap, 0, .87, -.9, 0); lap.userData.lid.rotation.x = -.25; scr(lap, wide.tex); wide.draw(dt(T)); a.put(door, [-1.1, 0, -.1], .3, 'cheer', lt);
  }, { allow: ['laptop'] });

  // ===== Warm: de beloning =====
  sh(61, 'dawn', dolly([-2.2, 1.2, 2.6], [-.8, 1.4, 1.8], [0, 1.1, -1.8], [0, 1.2, -1.8], 44), (lt, T, a) => {
    a.put(hero, [0, 0, -1.9], .1, 'laugh', lt, { mouth: .8, open: 0 });
  });
  sh(63, 'dawn', dolly([0, .9, 3.4], [0, 1.2, 2.2], [0, 1.9, -1.5], [0, 2.1, -1.5], 46), (lt, T, a) => {
    a.put(b1, [0, 0, -1.5], 0, 'cheer', lt); a.at(hood, 0, 3.0, -1.5, T * 2); a.sc(hood, .8);
  });
  cue(W(63), 'pop');
  sh(66, 'dawn', dolly([2.2, 1.8, 5.2], [1.4, 1.7, 4.4], [-.2, 1.7, -1.5], [-.2, 1.7, -1.5], 46), (lt, T, a) => {
    a.put(hero, [-1.5, 0, -1.8], .6, 'laugh', lt); a.put(b1, [1.0, 0, -1.6], -.4, 'cheer', lt); a.at(hood, 1.0, 3.0, -1.6, T * 2); a.sc(hood, .8);
    a.at(stRef, -.75, 3.0, -1.0); a.sc(stRef, pop(lt, .15, .35));
  });
  cue(W(66), 'hit');
  sh(68, 'warm', dolly([0, 1.6, 5.4], [0, 1.55, 4.4], [0, 1.6, 0], [0, 1.6, 0], 38), (lt, T, a) => {
    a.at(tA, -.45, 1.45 + Math.sin(T * 3) * .02, 0, .2); a.sc(tA, 1.4); a.at(hood, .55, 1.45, -.2, T * 1.2); a.sc(hood, .55); a.at(stOnce, 0, 2.35, .2); a.sc(stOnce, pop(lt, .35, .35) * .75);
  }, { nocap: true });
  cue(W(70), 'ding');
  sh(73, 'warm', stat([0, 1.5, 4.8], [0, 1.6, 0], 40), (lt, T, a) => { a.at(tA, -.45, 1.45, 0, .2); a.sc(tA, 1.4); a.at(hood, .55, 1.45, -.2, T * 1.2); a.sc(hood, .55); }, { nocap: true }, -.1);
  endCard(t(73, -.12), { flat: true, tag: 'Make every listing <b>scan once.</b>', sub: 'Sold once. Gone everywhere else.', note: 'Dashboard shown: Omnivaleur demo account' });
  cue(t(73, -.12), 'pop');
}
