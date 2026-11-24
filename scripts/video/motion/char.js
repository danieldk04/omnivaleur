// 2D animated character (waist up). pose() is a pure function of its params, so any frame can be rendered.
import { node } from './engine.js';

export const SKIN = { a: '#f1c3a0', b: '#d9a07a', c: '#a8734f', d: '#7a4e32', e: '#f6d7c0' };
const shade = (hex, k) => { const n = parseInt(hex.slice(1), 16); const r = Math.max(0, Math.min(255, ((n >> 16) & 255) * k)), g = Math.max(0, Math.min(255, ((n >> 8) & 255) * k)), b = Math.max(0, Math.min(255, (n & 255) * k)); return `rgb(${r | 0},${g | 0},${b | 0})`; };

const MOUTH = {
  flat: '<path d="M-17 0 L17 0" stroke="#5a2a2a" stroke-width="7" stroke-linecap="round" fill="none"/>',
  smile: '<path d="M-26 -4 Q0 26 26 -4" stroke="#5a2a2a" stroke-width="7" stroke-linecap="round" fill="none"/>',
  grin: '<path d="M-30 -6 Q0 44 30 -6 Z" fill="#7a2330" stroke="#5a2a2a" stroke-width="5" stroke-linejoin="round"/><path d="M-18 8 Q0 22 18 8 Q0 14 -18 8Z" fill="#ff8d8d"/>',
  frown: '<path d="M-22 10 Q0 -12 22 10" stroke="#5a2a2a" stroke-width="7" stroke-linecap="round" fill="none"/>',
  o: '<ellipse cx="0" cy="6" rx="13" ry="17" fill="#7a2330" stroke="#5a2a2a" stroke-width="5"/>',
  wavy: '<path d="M-24 4 Q-12 -6 0 4 T24 4" stroke="#5a2a2a" stroke-width="7" stroke-linecap="round" fill="none"/>',
};

export function character(parent, { skin = SKIN.a, hair = '#2a1d16', hoodie = '#3c4b73', style = 'short', glasses = false, w = 400 } = {}) {
  const id = 'c' + Math.random().toString(36).slice(2, 7);
  const hd = shade(hoodie, .78), hl = shade(hoodie, 1.18), sk2 = shade(skin, .86);
  const hairSVG = {
    short: `<path d="M-82 -10 Q-92 -92 0 -96 Q92 -92 82 -10 Q70 -52 20 -62 Q-30 -48 -52 -22 Q-70 -4 -82 -10Z" fill="${hair}"/>`,
    bun: `<circle cx="0" cy="-104" r="30" fill="${hair}"/><path d="M-84 0 Q-96 -98 0 -98 Q96 -98 84 0 Q74 -46 0 -52 Q-74 -46 -84 0Z" fill="${hair}"/>`,
    cap: `<path d="M-84 -14 Q-90 -96 0 -98 Q90 -96 84 -14 Z" fill="#e8872a"/><path d="M-84 -14 Q0 -40 130 -8 Q60 -30 84 -14Z" fill="${shade('#e8872a', .8)}"/>`,
    beanie: `<path d="M-86 -16 Q-90 -100 0 -104 Q90 -100 86 -16 Q0 -34 -86 -16Z" fill="#c43c4a"/><rect x="-88" y="-30" width="176" height="22" rx="10" fill="${shade('#c43c4a', .8)}"/><circle cx="0" cy="-108" r="14" fill="#f4d9dc"/>`,
    curly: `<g fill="${hair}"><circle cx="-60" cy="-50" r="32"/><circle cx="-24" cy="-72" r="34"/><circle cx="20" cy="-74" r="34"/><circle cx="60" cy="-50" r="32"/><circle cx="0" cy="-60" r="40"/></g>`,
  }[style];
  const e = node(parent, `width:${w}px;height:${w * 1.1}px`, `
<svg viewBox="0 0 400 440" width="${w}" height="${w * 1.1}" style="overflow:visible">
 <defs><linearGradient id="${id}b" x1="0" x2="1"><stop offset="0" stop-color="${hoodie}"/><stop offset="1" stop-color="${hd}"/></linearGradient>
 <linearGradient id="${id}s" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="${skin}"/><stop offset="1" stop-color="${sk2}"/></linearGradient></defs>
 <g class="body">
  <ellipse cx="200" cy="228" rx="104" ry="44" fill="${hd}"/>
  <path d="M112 226 Q112 206 150 204 L250 204 Q288 206 288 226 L300 440 L100 440Z" fill="url(#${id}b)"/>
  <path d="M170 226 Q200 262 230 226 Z" fill="#0f1a33" opacity=".5"/>
  <path d="M188 246 L186 296 M212 246 L214 296" stroke="#fff" stroke-width="5" stroke-linecap="round"/><circle cx="186" cy="300" r="6" fill="#fff"/><circle cx="214" cy="300" r="6" fill="#fff"/>
  <path d="M138 380 h124 l16 60 h-156 z" fill="${hd}" opacity=".7"/>
  <g class="armL" transform="translate(126 232)"><rect x="-20" y="-6" width="40" height="104" rx="20" fill="${hoodie}"/><g class="foreL" transform="translate(0 92)"><rect x="-18" y="-4" width="36" height="92" rx="18" fill="${hl}"/><circle cx="0" cy="92" r="21" fill="${skin}"/></g></g>
  <g class="armR" transform="translate(274 232)"><rect x="-20" y="-6" width="40" height="104" rx="20" fill="${hoodie}"/><g class="foreR" transform="translate(0 92)"><rect x="-18" y="-4" width="36" height="92" rx="18" fill="${hl}"/><circle cx="0" cy="92" r="21" fill="${skin}"/></g></g>
 </g>
 <g class="head" transform="translate(200 150)">
  <circle cx="-80" cy="8" r="18" fill="${sk2}"/><circle cx="80" cy="8" r="18" fill="${sk2}"/>
  <rect x="-78" y="-82" width="156" height="164" rx="64" fill="url(#${id}s)"/>
  ${hairSVG}
  <ellipse class="bagL" cx="-36" cy="26" rx="22" ry="8" fill="#6a4a8a" opacity="0"/><ellipse class="bagR" cx="36" cy="26" rx="22" ry="8" fill="#6a4a8a" opacity="0"/>
  <ellipse cx="-52" cy="30" rx="16" ry="9" fill="#ff7d7d" class="blushL" opacity=".0"/><ellipse cx="52" cy="30" rx="16" ry="9" fill="#ff7d7d" class="blushR" opacity=".0"/>
  <g class="eyeL" transform="translate(-34 -2)"><ellipse class="wh" rx="17" ry="20" fill="#fff"/><ellipse class="pu" rx="9" ry="11" fill="#1b1b2a"/><circle class="gl" cx="3" cy="-4" r="3.2" fill="#fff"/><path class="hp" d="M-17 6 Q0 -22 17 6" stroke="#1b1b2a" stroke-width="7" stroke-linecap="round" fill="none" opacity="0"/><rect class="lid" x="-19" y="-24" width="38" height="0" fill="${skin}"/></g>
  <g class="eyeR" transform="translate(34 -2)"><ellipse class="wh" rx="17" ry="20" fill="#fff"/><ellipse class="pu" rx="9" ry="11" fill="#1b1b2a"/><circle class="gl" cx="3" cy="-4" r="3.2" fill="#fff"/><path class="hp" d="M-17 6 Q0 -22 17 6" stroke="#1b1b2a" stroke-width="7" stroke-linecap="round" fill="none" opacity="0"/><rect class="lid" x="-19" y="-24" width="38" height="0" fill="${skin}"/></g>
  ${glasses ? '<g fill="none" stroke="#1b1b2a" stroke-width="6"><rect x="-58" y="-24" width="48" height="42" rx="14"/><rect x="10" y="-24" width="48" height="42" rx="14"/><path d="M-10 -8 h20"/></g>' : ''}
  <rect class="browL" x="-58" y="-40" width="44" height="9" rx="4.5" fill="${hair === '#2a1d16' ? '#2a1d16' : hair}"/><rect class="browR" x="14" y="-40" width="44" height="9" rx="4.5" fill="${hair === '#2a1d16' ? '#2a1d16' : hair}"/>
  <g class="mouth" transform="translate(0 44)"></g>
  <path class="sweat" d="M66 -40 Q80 -10 66 -2 Q52 -10 66 -40Z" fill="#8fd3ff" opacity="0"/>
 </g>
</svg>`);
  const q = s => e.querySelector(s), qa = s => [...e.querySelectorAll(s)];
  const body = q('.body'), head = q('.head'), aL = q('.armL'), aR = q('.armR'), fL = q('.foreL'), fR = q('.foreR');
  const eyes = [q('.eyeL'), q('.eyeR')], mouth = q('.mouth');
  let lastMouth = '';
  e.pose = (p = {}, t = 0) => {
    const o = { bob: 0, lean: 0, headRot: 0, headY: 0, gx: 0, gy: 0, lSh: 6, lEl: 4, rSh: -6, rEl: -4, eye: 1, happy: 0, brow: 0, browY: 0, mouth: 'smile', talk: 0, sweat: 0, bags: 0, blush: 0, ...p };
    const idle = Math.sin(t * 2.1) * 3, blinkPh = (t % 3.4); const blink = blinkPh > 3.25 ? 0.12 : 1;
    body.setAttribute('transform', `translate(0 ${o.bob + idle}) rotate(${o.lean} 200 440)`);
    head.setAttribute('transform', `translate(${200 + o.lean * -1.2} ${150 + o.headY + o.bob + idle * 1.2}) rotate(${o.headRot})`);
    aL.setAttribute('transform', `translate(126 232) rotate(${o.lSh})`); fL.setAttribute('transform', `translate(0 92) rotate(${o.lEl})`);
    aR.setAttribute('transform', `translate(274 232) rotate(${o.rSh})`); fR.setAttribute('transform', `translate(0 92) rotate(${o.rEl})`);
    const open = Math.max(.08, o.eye * blink);
    eyes.forEach(g => {
      g.querySelector('.wh').setAttribute('ry', 20 * open); g.querySelector('.pu').setAttribute('ry', Math.min(11, 20 * open * .9));
      g.querySelector('.pu').setAttribute('cx', o.gx * 6); g.querySelector('.pu').setAttribute('cy', o.gy * 6);
      g.querySelector('.gl').setAttribute('cy', -4 + o.gy * 6 - (1 - open) * 4); g.querySelector('.gl').setAttribute('cx', 3 + o.gx * 6);
      const hp = g.querySelector('.hp'); hp.setAttribute('opacity', o.happy); g.querySelector('.wh').setAttribute('opacity', 1 - o.happy); g.querySelector('.pu').setAttribute('opacity', 1 - o.happy); g.querySelector('.gl').setAttribute('opacity', 1 - o.happy);
      const lid = g.querySelector('.lid'); const cover = Math.max(0, (1 - o.eye) * 0) ; lid.setAttribute('height', cover);
    });
    const bl = q('.browL'), br = q('.browR');
    bl.setAttribute('transform', `translate(-36 ${-35 + o.browY}) rotate(${o.brow}) translate(36 35)`); br.setAttribute('transform', `translate(36 ${-35 + o.browY}) rotate(${-o.brow}) translate(-36 35)`);
    q('.sweat').setAttribute('opacity', o.sweat); q('.sweat').setAttribute('transform', `translate(0 ${o.sweat * 14})`);
    q('.bagL').setAttribute('opacity', o.bags); q('.bagR').setAttribute('opacity', o.bags);
    q('.blushL').setAttribute('opacity', o.blush); q('.blushR').setAttribute('opacity', o.blush);
    let m = o.mouth; let html = MOUTH[m] || MOUTH.flat;
    if (o.talk) { const a = (Math.sin(t * 15) * .5 + .5) * o.talk; html = `<ellipse cx="0" cy="${4 + a * 4}" rx="${14 + a * 8}" ry="${3 + a * 15}" fill="#7a2330" stroke="#5a2a2a" stroke-width="5"/>`; }
    if (html !== lastMouth) { mouth.innerHTML = html; lastMouth = html; }
  };
  return e;
}
