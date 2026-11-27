// node cap_dash.mjs <mode wide|close> <fps> <seconds>  -> assets/dash/<mode>/NNNN.jpg
import { chromium } from 'playwright'; import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
const ROOT = path.dirname(new URL(import.meta.url).pathname), [mode='wide', fps='20', secs='6.2'] = process.argv.slice(2);
const types = { '.html': 'text/html', '.png': 'image/png', '.webp': 'image/webp', '.js': 'text/javascript' };
const srv = http.createServer((q, r) => { const p = path.join(ROOT, decodeURIComponent(q.url.split('?')[0])); fs.readFile(p, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'content-type': types[path.extname(p)] || 'application/octet-stream' }); r.end(d); }); }).listen(0);
const b = await chromium.launch(); const pg = await b.newPage({ viewport: mode === 'wide' ? { width: 1440, height: 878 } : { width: 470, height: 500 }, deviceScaleFactor: mode === 'wide' ? 0.72 : 1.6 });
await pg.goto(`http://localhost:${srv.address().port}/dash-sale.html?mode=${mode}`); await pg.waitForTimeout(600);
const out = path.join(ROOT, 'assets/dash', mode); fs.rmSync(out, { recursive: true, force: true }); fs.mkdirSync(out, { recursive: true });
const n = Math.round(Number(secs) * Number(fps));
for (let i = 0; i < n; i++) { await pg.evaluate(t => window.setT(t), i / Number(fps)); await pg.screenshot({ path: path.join(out, String(i).padStart(4, '0') + '.jpg'), type: 'jpeg', quality: 86 }); }
console.log(mode, n, 'frames'); await b.close(); srv.close();
