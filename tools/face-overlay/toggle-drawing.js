(() => {
'use strict';
// Historic Shortwave — bat-handle power toggle drawing, rev 3a (Bill, 2026-11-28). Copyright (c) 2026 William J. Martin. MIT License.
// Drawing only. #power-button stays the control; this follows its aria-checked, which app.js sets on every power change
// (the switch itself, Play and Reset). The SVG is built element by element: first-party scripts write no HTML from strings.
const L = 72, TH = 32, K = 0.72, G = 1.2,   // G: lever width, tip and shadow scale (rev 3a: lever 20% larger, mounting unchanged)
      NS = 'http://www.w3.org/2000/svg';
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const f = v => v.toFixed(2);

// el('circle', { r: 5 }, [children]) -> SVG element
function el(tag, attrs = {}, kids = []){ const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  for (const k of kids) e.append(k); return e; }
const stops = list => list.map(([o, c, op]) => el('stop', op === undefined ? { offset: o, 'stop-color': c } : { offset: o, 'stop-color': c, 'stop-opacity': op }));

function defs(){ return el('defs', {}, [
  el('linearGradient', { id: 'hs-nickel', x1: 0, x2: 1 }, stops([[0, '#4b4944'], ['.12', '#9d9a93'], ['.3', '#f6f4ef'], ['.42', '#d3d0c9'], ['.62', '#6f6c66'], ['.82', '#bdb9b1'], [1, '#3f3d39']])),
  el('radialGradient', { id: 'hs-dome', cx: '.36', cy: '.3', r: '.78' }, stops([[0, '#ffffff'], ['.18', '#eeece7'], ['.5', '#a3a099'], ['.82', '#4a4843'], [1, '#7a776f']])),
  el('linearGradient', { id: 'hs-nut', x1: 0, y1: 0, x2: 1, y2: 1 }, stops([[0, '#f2f1ed'], ['.5', '#b5b2ab'], [1, '#67645e']])),
  el('radialGradient', { id: 'hs-washer', cx: '.4', cy: '.35', r: '.7' }, stops([[0, '#c2bfb8'], [1, '#85827b']])),
  el('radialGradient', { id: 'hs-pivot', cx: '.36', cy: '.32', r: '.75' }, stops([[0, '#e8e6e0'], ['.5', '#7d7a73'], [1, '#2e2d2a']])),
  el('linearGradient', { id: 'hs-oc-up', x1: 0, y1: 1, x2: 0, y2: 0 }, stops([[0, '#000', '.5'], ['.55', '#000', 0]])),
  el('linearGradient', { id: 'hs-oc-dn', x1: 0, y1: 0, x2: 0, y2: 1 }, stops([[0, '#000', '.5'], ['.55', '#000', 0]])),
  el('filter', { id: 'hs-blur', x: '-60%', y: '-60%', width: '220%', height: '220%' }, [el('feGaussianBlur', { stdDeviation: '2.2' })])]); }

const hex = r => [0, 1, 2, 3, 4, 5].map(i => { const a = Math.PI / 3 * i + Math.PI / 6; return `${f(r * Math.cos(a))},${f(r * Math.sin(a))}`; }).join(' ');
// Washer (no tab), hex nut, threaded bushing, bore, pivot ball. Pivot at (0,0). Unchanged from Rev 2.
function base(){ return [
  el('circle', { r: 31, fill: 'url(#hs-washer)', stroke: '#6c6a64' }),
  el('circle', { r: '29.5', fill: 'none', stroke: '#d8d6d0', 'stroke-width': '.6', opacity: '.6' }),
  el('polygon', { points: hex(25), fill: 'url(#hs-nut)', stroke: '#55534e' }),
  el('circle', { r: 20, fill: 'none', stroke: '#f6f5f2', opacity: '.55' }),
  el('circle', { r: 14, fill: '#8d8a84' }),
  el('circle', { r: '12.5', fill: 'none', stroke: '#dcdad4', 'stroke-width': '.8' }),
  el('circle', { r: 11, fill: 'none', stroke: '#5c5a55', 'stroke-width': '.8' }),
  el('circle', { r: '9.6', fill: 'none', stroke: '#cbc8c1', 'stroke-width': '.6' }),
  el('circle', { r: '8.5', fill: '#141413' }),
  el('circle', { r: '5.5', fill: 'url(#hs-pivot)' })]; }

// Lever parts, made once; draw(phi) recomputes their geometry from the lean. Never mirrored.
function leverParts(){ const p = {
  shPath: el('path'), shTip: el('circle', { r: f(8.6 * G) }),
  body: el('path', { fill: 'url(#hs-nickel)' }), occl: el('path'),
  strip: el('path', { fill: '#fff', opacity: '.55' }),
  dome: el('ellipse', { rx: f(7.9 * G), ry: f(7.5 * G), fill: 'url(#hs-dome)', stroke: '#5c5a55', 'stroke-width': '.5' }),
  spec: el('ellipse', { cx: f(-2.7 * G), rx: f(2.3 * G), ry: f(1.6 * G), fill: '#fff', opacity: '.85' }) };
  p.group = el('g', { class: 'hs-lever' }, [el('g', { opacity: '.36', filter: 'url(#hs-blur)' }, [p.shPath, p.shTip]), p.body, p.occl, p.strip, p.dome, p.spec]);
  return p; }
// phi in degrees: positive = up (ON), negative = down (OFF), 0 = toward the viewer.
function drawLever(p, phi){ const r = phi * Math.PI / 180, ty = -L * Math.sin(r), H = L * Math.cos(r), sx = .2 * H, sy = .26 * H;
  const b = 3.6 * G, t = 6.2 * G, body = `M${f(-b)},0 L${f(b)},0 L${f(t)},${f(ty)} L${f(-t)},${f(ty)} Z`;
  p.shPath.setAttribute('d', `M${f(2 - b)},3 L${f(2 + b)},3 L${f(t + sx)},${f(ty + sy)} L${f(-t + sx)},${f(ty + sy)} Z`);
  p.shTip.setAttribute('cx', f(sx)); p.shTip.setAttribute('cy', f(ty + sy));
  p.body.setAttribute('d', body); p.occl.setAttribute('d', body); p.occl.setAttribute('fill', `url(#${ty < 0 ? 'hs-oc-up' : 'hs-oc-dn'})`);
  p.strip.setAttribute('d', `M${f(-1.9 * G)},0 L${f(-1.1 * G)},0 L${f(-2.1 * G)},${f(ty)} L${f(-3.3 * G)},${f(ty)} Z`);
  p.dome.setAttribute('cy', f(ty)); p.spec.setAttribute('cy', f(ty - 2.7 * G)); }

function init(){ const btn = document.getElementById('power-button'); if (!btn) return;
  const W = 60 / K, Hh = 92 / K;   // the button is 60 x 92 px; viewBox in switch units at scale 0.72, pivot at the centre
  const parts = leverParts();
  const svg = el('svg', { class: 'hs-toggle', 'aria-hidden': 'true', focusable: 'false',
    viewBox: `${f(-W / 2)} ${f(-Hh / 2)} ${f(W)} ${f(Hh)}` }, [defs(), ...base(), parts.group]);
  btn.append(svg);   // after the ON/OFF legends, so its shadow falls over the paint
  const isOn = () => btn.getAttribute('aria-checked') === 'true';
  let phi = isOn() ? TH : -TH, raf = 0;
  const draw = () => drawLever(parts, phi);
  function swing(to){ cancelAnimationFrame(raf); raf = 0;   // a new throw replaces one still in progress
    if (reduce || phi === to) { phi = to; draw(); return; }
    const from = phi, t0 = performance.now();
    const step = t => { const p = Math.min(1, (t - t0) / 110); phi = from + (to - from) * p * p; draw(); raf = p < 1 ? requestAnimationFrame(step) : 0; };
    raf = requestAnimationFrame(step); }
  draw();
  new MutationObserver(() => swing(isOn() ? TH : -TH)).observe(btn, { attributes: true, attributeFilter: ['aria-checked'] });
  window.HSToggle = { get phi(){ return phi; } };   // read-only lever angle, for checks
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
