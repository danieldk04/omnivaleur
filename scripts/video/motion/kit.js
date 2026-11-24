// Reusable visual components. All return the element; position with place().
import { node } from './engine.js';

export const LOGO = { vinted: 'assets/vinted.png', marktplaats: 'assets/marktplaats.png', ebay: 'assets/ebay.webp', shop: 'assets/shopify.webp', mark: 'assets/mark.png' };

export function hoodie(parent, color = '#3c4b73', w = 300) {
  const dk = color;
  return node(parent, `width:${w}px;height:${w}px`, `<svg viewBox="0 0 200 200" width="${w}" height="${w}">
    <ellipse cx="100" cy="190" rx="70" ry="7" fill="rgba(0,0,0,.28)"/>
    <path d="M62 58 L38 70 L14 152 L44 162 L56 120 L56 176 Q100 188 144 176 L144 120 L156 162 L186 152 L162 70 L138 58 Q100 84 62 58Z" fill="${color}"/>
    <path d="M62 58 L38 70 L14 152 L44 162 L56 120" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="3"/>
    <ellipse cx="100" cy="56" rx="38" ry="28" fill="${color}" stroke="rgba(0,0,0,.25)" stroke-width="2"/>
    <ellipse cx="100" cy="64" rx="23" ry="18" fill="#0f1a33"/>
    <path d="M91 82 L88 112 M109 82 L112 112" stroke="#fff" stroke-width="3.5" stroke-linecap="round"/>
    <circle cx="88" cy="114" r="4" fill="#fff"/><circle cx="112" cy="114" r="4" fill="#fff"/>
    <path d="M70 134 h60 l8 28 h-76 z" fill="rgba(0,0,0,.18)"/>
    <path d="M56 176 Q100 188 144 176" fill="none" stroke="rgba(0,0,0,.25)" stroke-width="5"/>
  </svg>`);
}

export function chip(parent, key, size = 150) {
  const wide = key === 'marktplaats' || key === 'ebay';
  return node(parent, `width:${size}px;height:${size}px;border-radius:${size * .22}px;background:#fff;box-shadow:0 10px 30px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;overflow:hidden`,
    `<img src="${LOGO[key]}" style="width:${wide ? '82%' : '66%'};height:${wide ? 'auto' : '66%'};object-fit:contain">`);
}

export function stamp(parent, text, color = '#ff4d4d', size = 44) {
  return node(parent, `padding:6px 20px;border:7px solid ${color};border-radius:14px;color:${color};font:900 ${size}px/1 Montserrat;letter-spacing:3px;background:rgba(255,255,255,.92);white-space:nowrap`, text);
}

export function bubble(parent, text, { me = false, w = 420, bg = '#fff', fg = '#0a1936', size = 30 } = {}) {
  return node(parent, `width:${w}px;padding:20px 26px;border-radius:30px ${me ? '30px 8px 30px' : '30px 30px 8px'};background:${me ? '#0649c7' : bg};color:${me ? '#fff' : fg};font:700 ${size}px/1.25 Montserrat;box-shadow:0 8px 24px rgba(0,0,0,.3)`, text);
}

export function avatar(parent, letter, color, size = 110) {
  return node(parent, `width:${size}px;height:${size}px;border-radius:50%;background:${color};color:#fff;font:900 ${size * .46}px/${size}px Montserrat;text-align:center;box-shadow:0 8px 24px rgba(0,0,0,.35);border:6px solid #fff`, letter);
}

export function badge(parent, text, { bg = '#85edbc', fg = '#0a1936', size = 28, pad = '10px 22px' } = {}) {
  return node(parent, `padding:${pad};border-radius:999px;background:${bg};color:${fg};font:800 ${size}px/1 Montserrat;white-space:nowrap;box-shadow:0 6px 18px rgba(0,0,0,.28)`, text);
}

export function check(parent, size = 160, color = '#85edbc') {
  const e = node(parent, `width:${size}px;height:${size}px`, `<svg viewBox="0 0 100 100" width="${size}" height="${size}"><circle cx="50" cy="50" r="46" fill="${color}"/><path class="ck" d="M28 52 L44 68 L74 34" fill="none" stroke="#0a1936" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="80" stroke-dashoffset="0"/></svg>`);
  e.setCk = k => { e.querySelector('.ck').style.strokeDashoffset = String(80 * (1 - k)); };
  return e;
}

export function cross(parent, size = 120, color = '#ff4d4d') {
  const e = node(parent, `width:${size}px;height:${size}px`, `<svg viewBox="0 0 100 100" width="${size}" height="${size}"><circle cx="50" cy="50" r="46" fill="${color}"/><path class="ck" d="M32 32 L68 68 M68 32 L32 68" fill="none" stroke="#fff" stroke-width="10" stroke-linecap="round" stroke-dasharray="52" stroke-dashoffset="0"/></svg>`);
  e.setCk = k => { e.querySelector('.ck').style.strokeDashoffset = String(52 * (1 - k)); };
  return e;
}

export function textBlock(parent, html, { size = 56, color = '#fff', w = 640, weight = 900, align = 'center', ls = '-0.5px' } = {}) {
  return node(parent, `width:${w}px;text-align:${align};color:${color};font:${weight} ${size}px/1.08 Montserrat;letter-spacing:${ls};text-shadow:0 4px 16px rgba(0,0,0,.35)`, html);
}

// a line that draws itself from (x1,y1) to (x2,y2); set(k) 0..1
export function line(parent, x1, y1, x2, y2, { color = '#85edbc', width = 8, dash = true } = {}) {
  const len = Math.hypot(x2 - x1, y2 - y1);
  const e = node(parent, 'left:0;top:0;width:720px;height:1280px;transform:none;pointer-events:none',
    `<svg width="720" height="1280" viewBox="0 0 720 1280" style="position:absolute;left:0;top:0"><line class="l" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${width}" stroke-linecap="round" ${dash ? 'stroke-dasharray="2 18"' : ''}/><circle class="d" r="${width * 1.6}" fill="${color}"/></svg>`);
  e.style.transform = 'none';
  e.set = (k, o = 1) => {
    e.style.opacity = o;
    const l = e.querySelector('.l'), d = e.querySelector('.d');
    l.setAttribute('x2', x1 + (x2 - x1) * k); l.setAttribute('y2', y1 + (y2 - y1) * k);
    d.setAttribute('cx', x1 + (x2 - x1) * k); d.setAttribute('cy', y1 + (y2 - y1) * k);
    d.style.opacity = k > 0 && k < 1 ? 1 : 0;
  };
  return e;
}

export function window_(parent, w, h, title = '') {
  return node(parent, `width:${w}px;height:${h}px;border-radius:26px;background:#fff;box-shadow:0 20px 60px rgba(0,0,0,.45);overflow:hidden`,
    `<div style="height:56px;background:#eaf1f6;display:flex;align-items:center;gap:10px;padding:0 20px"><i style="width:14px;height:14px;border-radius:50%;background:#ff6b6b"></i><i style="width:14px;height:14px;border-radius:50%;background:#ffc83d"></i><i style="width:14px;height:14px;border-radius:50%;background:#4cd37b"></i><span style="margin-left:14px;font:700 20px Montserrat;color:#485363">${title}</span></div>`);
}

export function phone(parent, w = 300, h = 560, screenBg = '#fff') {
  const e = node(parent, `width:${w}px;height:${h}px;border-radius:44px;background:#0b1224;padding:12px;box-shadow:0 24px 60px rgba(0,0,0,.5)`,
    `<div class="scr" style="position:relative;width:100%;height:100%;border-radius:34px;background:${screenBg};overflow:hidden"></div>`);
  e.scr = e.querySelector('.scr');
  return e;
}

// ring that fills: set(k) 0..1, number or text in the middle
export function ring(parent, size = 150, color = '#85edbc', track = 'rgba(255,255,255,.18)', label = '') {
  const e = node(parent, `width:${size}px;height:${size}px`, `<svg viewBox="0 0 100 100" width="${size}" height="${size}" style="transform:rotate(-90deg)"><circle cx="50" cy="50" r="42" fill="none" stroke="${track}" stroke-width="9"/><circle class="rg" cx="50" cy="50" r="42" fill="none" stroke="${color}" stroke-width="9" stroke-linecap="round" stroke-dasharray="264" stroke-dashoffset="264"/></svg><div class="lb" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font:900 ${size * .26}px Montserrat;color:#fff">${label}</div>`);
  e.set = (k, txt) => { e.querySelector('.rg').style.strokeDashoffset = String(264 * (1 - k)); if (txt !== undefined) e.querySelector('.lb').textContent = txt; };
  return e;
}

export function laptop(parent, w = 560) {
  const h = w * .62;
  const e = node(parent, `width:${w}px;height:${h + 30}px`,
    `<div class="lid" style="position:absolute;left:${w * .06}px;top:0;width:${w * .88}px;height:${h}px;border-radius:22px 22px 6px 6px;background:#1a2442;padding:14px;transform-origin:50% 100%;box-shadow:0 18px 50px rgba(0,0,0,.45)"><div class="scr" style="position:relative;width:100%;height:100%;border-radius:12px;background:#eaf1f6;overflow:hidden"></div></div>
     <div style="position:absolute;left:0;top:${h - 2}px;width:${w}px;height:30px;border-radius:6px 6px 26px 26px;background:linear-gradient(#cfd6e4,#9aa5bd)"></div>`);
  e.scr = e.querySelector('.scr'); e.lid = e.querySelector('.lid');
  e.open = k => { e.lid.style.transform = `scaleY(${.05 + .95 * k})`; e.lid.style.opacity = '1'; };
  return e;
}

export function clockText(parent, size = 130, color = '#fff') {
  const e = node(parent, `font:900 ${size}px/1 Montserrat;color:${color};letter-spacing:-2px;text-shadow:0 0 40px ${color}55;font-variant-numeric:tabular-nums;white-space:nowrap`, '00:00');
  e.setTime = (min) => { const m = ((Math.round(min) % 1440) + 1440) % 1440; e.textContent = String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'); };
  return e;
}
