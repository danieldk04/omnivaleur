// Clipping test: samples every shot densely and reports where a body part sits inside a solid prop.
import { chromium } from 'playwright'; import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
const ROOT = path.dirname(new URL(import.meta.url).pathname);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.woff2': 'font/woff2', '.png': 'image/png', '.webp': 'image/webp' };
const server = http.createServer((q, r) => { const p = path.join(ROOT, decodeURIComponent(q.url.split('?')[0])); fs.readFile(p, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'content-type': types[path.extname(p)] || 'application/octet-stream' }); r.end(d); }); }).listen(0);
const browser = await chromium.launch({ args: ['--enable-gpu', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 720, height: 1280 } });
page.on('pageerror', e => console.log('[pageerror]', e.message));
await page.goto(`http://localhost:${server.address().port}/index.html?render=1`);
await page.waitForFunction(() => window.renderAt && window.ready);
const step = Number(process.argv[2] || 0.05), FACT = Number(process.argv[3] || 0.55);
const res = await page.evaluate(async ([step, FACT]) => {
  const THREE = await import('three'); const out = [];
  const dur = window.DURATION;
  for (let t = 0; t < dur; t += step) {
    const idx = window.renderAt(t); const shot = window.getShotObj(idx), sc = shot.scene; sc.updateMatrixWorld(true);
    const chars = [], solids = [];
    sc.traverse(o => { if (o.userData && o.userData.points) chars.push(o); if (o.userData && o.userData.solid) solids.push(o); });
    for (const ch of chars) for (const [n, p, r] of ch.userData.points()) for (const s of solids) {
      if (!s.geometry.boundingBox) s.geometry.computeBoundingBox(); const bb = s.geometry.boundingBox;
      const inv = s.matrixWorld.clone().invert(), lp = p.clone().applyMatrix4(inv), sc2 = new THREE.Vector3().setFromMatrixScale(s.matrixWorld);
      const cl = lp.clone().clamp(bb.min, bb.max), dist = cl.distanceTo(lp) * sc2.x; // sphere-vs-box: how far the part sinks into the prop
      const inside = (dist === 0 ? r : r - dist) > r * FACT;
      if (inside) { const sz = bb.getSize(new THREE.Vector3()); out.push({ t: +t.toFixed(2), shot: idx, part: n, solid: `${sz.x.toFixed(2)}x${sz.y.toFixed(2)}x${sz.z.toFixed(2)}`, at: s.getWorldPosition(new THREE.Vector3()).toArray().map(v => +v.toFixed(2)) }); }
    }
  }
  return out;
}, [step, FACT]);
const by = {}; for (const r of res) { const k = `shot ${r.shot} ${r.part} in ${r.solid}`; (by[k] ||= []).push(r.t); }
for (const [k, v] of Object.entries(by)) console.log(k, `t=${v[0]}..${v[v.length - 1]} (${v.length} frames)`);
console.log('TOTAL clipping frames:', res.length);
await browser.close(); server.close();
