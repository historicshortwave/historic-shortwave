(() => {
'use strict';
// Historic Shortwave new face (Phase 5c, approved 2026-11-16).
// Drawing, knob feel and scene come from design/phase5-integration-mockup/face.js (Nov 15 values). The mockup's
// synthesized stations and sound are removed: this face draws the real receiver state from app.js (state, tune,
// bounds, BANDS, ACTIVE_BANDS) and hands every change back to app.js, which still owns tuning, the catalog,
// archive playback, seasonal static, status words and the screen-reader values. It reads nothing typed.
// Loaded before app.js; app.js checks window.HSFace and then leaves MAIN TUNING's pointer handling and drawing to it.
const $ = id => document.getElementById(id);
const TAU = Math.PI * 2, LIGHT = -Math.PI * 0.75;       // light comes from upper left
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const root = document.documentElement;
let FONT = '"Barlow Semi Condensed", Arial, sans-serif';
let ready = false;
// A4 (Bill, 2026-11-19): between 760 and 1000 px wide (iPad portrait) the scene is drawn small, so the lettering painted on
// the dial, meter and knobs is enlarged by TXT; face.css enlarges the engraved labels and nameplate the same way.
let TXT = 1, txtMQ = null;
const fs = (px, weight) => `${weight} ${(px * TXT).toFixed(2)}px ${FONT}`;
window.HSFace = { update(){ if (ready) { dirty.tune = dirty.gain = true; sense(); wake(); } } };

const BAND_ANGLES = { '90m': -40, '60m': 0, '49m': 40 };
const BAND_NAMES = { '90m': '90 M', '60m': '60 M', '49m': '49 M' };
const S = { lamp: 0, lampOut: 0, needle: -.03, nv: 0, pointerHz: 4900000, tuneAng: 0, coast: 0, bandAng: 0, t: 0,
            lastHz: null, lastBand: null, lastKnobBand: null, lastGain: -1, acc: null, stopArmed: true };
const dirty = { tune: true, gain: true };

/* ---------- canvases ---------- */
function fit(c, w, h){ const d = Math.min(3, (window.devicePixelRatio || 1) * 1.7); c.width = Math.round(w * d); c.height = Math.round(h * d);
  const x = c.getContext('2d'); x.setTransform(d, 0, 0, d, 0, 0); return x; }
let dial, meter, dx, mx, dW = 0, dH = 0, mW = 0, mH = 0, tx, gx, bx;
function measure(){ dW = dial.clientWidth; dH = dial.clientHeight; dx = fit(dial, dW, dH); mW = meter.clientWidth; mH = meter.clientHeight; mx = fit(meter, mW, mH); }

function engraved(x, text, px, py){ x.fillStyle = 'rgba(255,255,255,.5)'; x.fillText(text, px, py + 1); x.fillStyle = '#1b1e1c'; x.fillText(text, px, py); }
function castShadow(x, c, R, S_){ const ox = S_ * .035, oy = S_ * .05, g = x.createRadialGradient(c + ox, c + oy, R * .72, c + ox, c + oy, R * 1.24);
  g.addColorStop(0, 'rgba(0,0,0,.6)'); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.beginPath(); x.arc(c + ox, c + oy, R * 1.24, 0, TAU); x.fill(); }
function teeth(x, c, R, inner, N, ang, lo, hi, back){ const w = TAU * R / N; x.lineCap = 'butt'; x.lineWidth = w * .55;
  for (let i = 0; i < N; i++) { const a = ang + i * TAU / N, b = Math.max(0, Math.cos(a - LIGHT)), b2 = Math.max(0, Math.cos(a - LIGHT - Math.PI));
    const v = Math.round(lo + (hi - lo) * b * b + back * b2); x.strokeStyle = `rgb(${v},${v + 2},${v})`;
    x.beginPath(); x.moveTo(c + Math.cos(a) * R * inner, c + Math.sin(a) * R * inner); x.lineTo(c + Math.cos(a) * R * .995, c + Math.sin(a) * R * .995); x.stroke(); } }

function drawTune(){ const x = tx, Z = 180, c = Z / 2, R = Z * .42, ang = S.tuneAng;
  x.clearRect(0, 0, Z, Z); castShadow(x, c, R, Z);
  x.fillStyle = '#0a0b0b'; x.beginPath(); x.arc(c, c, R, 0, TAU); x.fill();
  teeth(x, c, R, .86, 88, ang, 24, 178, 40);
  let g = x.createLinearGradient(c + Math.cos(LIGHT) * R, c + Math.sin(LIGHT) * R, c - Math.cos(LIGHT) * R, c - Math.sin(LIGHT) * R);
  g.addColorStop(0, '#e3e5df'); g.addColorStop(.5, '#8a8e89'); g.addColorStop(1, '#2c2e2d');
  x.fillStyle = g; x.beginPath(); x.arc(c, c, R * .87, 0, TAU); x.fill();
  if (x.createConicGradient) { g = x.createConicGradient(LIGHT, c, c);                 // spun-aluminium cap: highlights stay put as it turns
    [[0, '#f5f6f1'], [.11, '#b0b4ae'], [.25, '#7b7f7a'], [.39, '#b3b7b1'], [.5, '#e7e9e3'], [.61, '#a6aaa4'], [.75, '#757974'], [.89, '#acb0aa'], [1, '#f5f6f1']]
      .forEach(([o, col]) => g.addColorStop(o, col)); } else g = '#b9bdb8';
  x.fillStyle = g; x.beginPath(); x.arc(c, c, R * .8, 0, TAU); x.fill();
  x.lineWidth = .6; x.strokeStyle = 'rgba(0,0,0,.055)';
  for (let r = R * .06; r < R * .8; r += 2.3) { x.beginPath(); x.arc(c, c, r, 0, TAU); x.stroke(); }
  x.lineWidth = 1; x.strokeStyle = 'rgba(0,0,0,.4)'; x.beginPath(); x.arc(c, c, R * .8, 0, TAU); x.stroke();
  const px = c + Math.sin(ang) * R * .47, py = c - Math.cos(ang) * R * .47, dr = R * .2;   // finger dimple
  g = x.createRadialGradient(px + Math.cos(LIGHT) * dr * .55, py + Math.sin(LIGHT) * dr * .55, dr * .05, px, py, dr);
  g.addColorStop(0, '#2f3130'); g.addColorStop(.62, '#868a85'); g.addColorStop(1, '#eef0ea');
  x.fillStyle = g; x.beginPath(); x.arc(px, py, dr, 0, TAU); x.fill();
  x.strokeStyle = 'rgba(0,0,0,.28)'; x.beginPath(); x.arc(px, py, dr, 0, TAU); x.stroke(); }

function drawGain(){ const x = gx, Z = 140, c = Z / 2, R = Z * .29, ang = (state.gain * 270 - 135) * Math.PI / 180;
  x.clearRect(0, 0, Z, Z); x.textAlign = 'center'; x.textBaseline = 'middle'; x.font = fs(10 * Math.min(TXT, 1.15) / TXT, 600);
  for (let i = 0; i <= 10; i++) { const a = (-135 + i * 27) * Math.PI / 180, sx = Math.sin(a), sy = -Math.cos(a);
    x.strokeStyle = '#1b1e1c'; x.lineWidth = i % 5 ? 1 : 1.6; x.beginPath(); x.moveTo(c + sx * R * 1.2, c + sy * R * 1.2); x.lineTo(c + sx * R * 1.36, c + sy * R * 1.36); x.stroke();
    if (i % 2 === 0) engraved(x, String(i), c + sx * R * 1.6, c + sy * R * 1.6); }
  castShadow(x, c, R, Z);
  x.fillStyle = '#060707'; x.beginPath(); x.arc(c, c, R, 0, TAU); x.fill();
  teeth(x, c, R, .8, 30, ang, 9, 92, 16);
  let g = x.createRadialGradient(c + Math.cos(LIGHT) * R * .36, c + Math.sin(LIGHT) * R * .36, R * .04, c, c, R * .82);
  g.addColorStop(0, '#555856'); g.addColorStop(.5, '#1c1e1d'); g.addColorStop(1, '#070808');
  x.fillStyle = g; x.beginPath(); x.arc(c, c, R * .8, 0, TAU); x.fill();
  x.strokeStyle = 'rgba(255,255,255,.17)'; x.lineWidth = R * .05; x.lineCap = 'round'; x.beginPath(); x.arc(c, c, R * .66, LIGHT - .55, LIGHT + .55); x.stroke();
  x.strokeStyle = '#f1efe6'; x.lineWidth = R * .075; x.beginPath();
  x.moveTo(c + Math.sin(ang) * R * .3, c - Math.cos(ang) * R * .3); x.lineTo(c + Math.sin(ang) * R * .76, c - Math.cos(ang) * R * .76); x.stroke(); }

function drawBand(){ const x = bx, Z = 150, c = Z / 2, R = Z * .23, ang = S.bandAng;
  x.clearRect(0, 0, Z, Z); x.textAlign = 'center'; x.textBaseline = 'middle'; x.font = fs(12 * Math.min(TXT, 1.15) / TXT, 700);
  ACTIVE_BANDS.forEach(id => { const a = BAND_ANGLES[id] * Math.PI / 180, sx = Math.sin(a), sy = -Math.cos(a);
    x.strokeStyle = '#1b1e1c'; x.lineWidth = 1.6; x.beginPath(); x.moveTo(c + sx * R * 1.42, c + sy * R * 1.42); x.lineTo(c + sx * R * 1.6, c + sy * R * 1.6); x.stroke();
    engraved(x, id.replace('m', ''), c + sx * R * 1.86, c + sy * R * 1.86 + 3); });
  castShadow(x, c, R, Z);
  let g = x.createRadialGradient(c + Math.cos(LIGHT) * R * .4, c + Math.sin(LIGHT) * R * .4, R * .05, c, c, R);
  g.addColorStop(0, '#4c4f4d'); g.addColorStop(.55, '#181a19'); g.addColorStop(1, '#050606');
  x.fillStyle = g; x.beginPath(); x.arc(c, c, R, 0, TAU); x.fill();
  x.save(); x.translate(c, c);
  x.rotate(ang); x.shadowColor = 'rgba(0,0,0,.6)'; x.shadowBlur = 6; x.shadowOffsetX = 3; x.shadowOffsetY = 4;
  g = x.createLinearGradient(-R * .34, 0, R * .34, 0); g.addColorStop(0, '#565957'); g.addColorStop(.42, '#232524'); g.addColorStop(1, '#070808');
  x.fillStyle = g; x.beginPath();                                                    // pointer ("chicken head") bar
  x.moveTo(-R * .3, R * .72); x.quadraticCurveTo(0, R * .95, R * .3, R * .72); x.lineTo(R * .14, -R * 1.16);
  x.quadraticCurveTo(0, -R * 1.3, -R * .14, -R * 1.16); x.closePath(); x.fill();
  x.shadowColor = 'transparent'; x.strokeStyle = 'rgba(255,255,255,.2)'; x.lineWidth = 1; x.beginPath(); x.moveTo(-R * .27, R * .66); x.lineTo(-R * .13, -R * 1.12); x.stroke();
  x.strokeStyle = '#f1efe6'; x.lineWidth = R * .09; x.lineCap = 'round'; x.beginPath(); x.moveTo(0, -R * .5); x.lineTo(0, -R * 1.08); x.stroke();
  x.restore(); }

// Glass dial: all three band scales, the selected band in red; the pointer never marks station positions.
function drawDial(){ const x = dx, w = dW, h = dH, L = S.lampOut; if (!w) return;
  x.fillStyle = '#4b4940'; x.fillRect(0, 0, w, h);
  if (L > .004) { x.globalAlpha = Math.min(1, L);
    let g = x.createLinearGradient(0, 0, 0, h); g.addColorStop(0, '#efcb80'); g.addColorStop(.5, '#f8e4b3'); g.addColorStop(1, '#e0b25f');
    x.fillStyle = g; x.fillRect(0, 0, w, h);
    for (const lx of [w * .2, w * .8]) { g = x.createRadialGradient(lx, h * 1.08, 0, lx, h * 1.08, w * .36);
      g.addColorStop(0, 'rgba(255,248,220,.9)'); g.addColorStop(1, 'rgba(255,248,220,0)'); x.fillStyle = g; x.fillRect(0, 0, w, h); }
    x.globalAlpha = 1; }
  const padL = 58, padR = 20, span = w - padL - padR, rows = [.27, .54, .81];
  x.textBaseline = 'alphabetic';
  ACTIVE_BANDS.forEach((id, i) => { const b = BANDS[id], y = h * rows[i] + 8, on = id === state.band, X = hz => padL + (hz - b.minHz) / (b.maxHz - b.minHz) * span;
    const every = [50000, 100000, 200000].find(st => span * st / (b.maxHz - b.minHz) >= 27 * TXT) || 200000;   // number spacing that leaves room for a four-character label
    x.globalAlpha = on ? 1 : .36; x.strokeStyle = '#1a1610'; x.fillStyle = '#1a1610';
    x.lineWidth = 1; x.beginPath(); x.moveTo(padL, y); x.lineTo(w - padR, y); x.stroke();
    x.textAlign = 'center'; x.font = fs(11, 600);
    for (let hz = Math.ceil(b.minHz / 10000) * 10000; hz <= b.maxHz; hz += 10000) { const major = hz % 50000 === 0, px = X(hz);
      x.lineWidth = major ? 1.5 : 1; x.beginPath(); x.moveTo(px, y); x.lineTo(px, y - (major ? 11 : 6)); x.stroke();
      if (hz % every === 0) x.fillText((hz / 1e6).toFixed(2), px, y - 11 - 4 * TXT); }
    x.textAlign = 'left'; x.font = fs(12, 700); x.fillStyle = on ? '#b3261a' : '#1a1610'; x.fillText(BAND_NAMES[id], 10, y - 2);
    if (on) { x.fillStyle = '#b3261a'; x.beginPath(); x.moveTo(46, y - 10); x.lineTo(52, y - 6); x.lineTo(46, y - 2); x.fill(); } });
  x.globalAlpha = 1; x.textAlign = 'right'; x.font = fs(9, 600); x.fillStyle = 'rgba(26,22,16,.7)'; x.fillText('MEGACYCLES', w - padR, 4 + 8 * TXT);
  const b = BANDS[state.band], px = padL + (S.pointerHz - b.minHz) / (b.maxHz - b.minHz) * (w - padL - padR);
  x.fillStyle = 'rgba(0,0,0,.22)'; x.fillRect(px + 3, 0, 2.4, h);                      // pointer rides above the glass scale
  x.fillStyle = '#c8321f'; x.fillRect(px - 1.1, 0, 2.2, h); x.fillStyle = 'rgba(255,255,255,.4)'; x.fillRect(px - 1.1, 0, .6, h);
  let g = x.createLinearGradient(0, 0, w, 0); g.addColorStop(0, 'rgba(0,0,0,.3)'); g.addColorStop(.07, 'rgba(0,0,0,0)'); g.addColorStop(.93, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.3)');
  x.fillStyle = g; x.fillRect(0, 0, w, h);
  x.fillStyle = `rgba(8,8,6,${.36 * (1 - Math.min(1, L))})`; x.fillRect(0, 0, w, h); }

// S-meter (decision 4: needle alone) with the receiver's status words lit on the cover plate (decision 2).
function drawMeter(word){ const x = mx, w = mW, h = mH, L = S.lampOut; if (!w) return;
  x.fillStyle = '#76725f'; x.fillRect(0, 0, w, h);
  if (L > .004) { x.globalAlpha = Math.min(1, L); let g = x.createRadialGradient(w / 2, h * 1.1, 0, w / 2, h * 1.1, h * 1.25);
    g.addColorStop(0, '#fff6d8'); g.addColorStop(.6, '#f3e7c2'); g.addColorStop(1, '#dcc48c'); x.fillStyle = g; x.fillRect(0, 0, w, h); x.globalAlpha = 1; }
  const cx = w / 2, cy = h * .98, r = Math.min(h * .8, w * .5), A = v => -Math.PI / 2 + (v - .5) * 1.6;
  x.lineCap = 'butt'; x.strokeStyle = '#191815'; x.lineWidth = 1.5; x.beginPath(); x.arc(cx, cy, r, A(0), A(.64)); x.stroke();
  x.strokeStyle = '#b3261a'; x.lineWidth = 2.6; x.beginPath(); x.arc(cx, cy, r, A(.64), A(1)); x.stroke();
  x.textAlign = 'center'; x.textBaseline = 'middle'; x.font = fs(10, 600);
  const mark = (v, label, red) => { const a = A(v), ca = Math.cos(a), sa = Math.sin(a); x.strokeStyle = x.fillStyle = red ? '#b3261a' : '#191815'; x.lineWidth = 1.3;
    x.beginPath(); x.moveTo(cx + ca * r, cy + sa * r); x.lineTo(cx + ca * (r + (label ? 8 : 5)), cy + sa * (r + (label ? 8 : 5))); x.stroke();
    if (label) x.fillText(label, cx + ca * (r + 15), cy + sa * (r + 15)); };
  for (let i = 1; i <= 9; i++) mark(.04 + (i - 1) / 8 * .6, i % 2 ? String(i) : '', false);
  mark(.82, '+20', true); mark(1, '+40', true);
  x.fillStyle = '#191815'; x.font = fs(9, 600); x.fillText('S  UNITS', cx, cy - r * .62);
  const a = A(S.needle), ca = Math.cos(a), sa = Math.sin(a);
  x.lineCap = 'round'; x.strokeStyle = 'rgba(0,0,0,.22)'; x.lineWidth = 2; x.beginPath(); x.moveTo(cx + ca * r * .2 + 3, cy + sa * r * .2 + 4); x.lineTo(cx + ca * r * 1.04 + 3, cy + sa * r * 1.04 + 4); x.stroke();
  x.strokeStyle = '#141412'; x.lineWidth = 1.5; x.beginPath(); x.moveTo(cx + ca * r * .2, cy + sa * r * .2); x.lineTo(cx + ca * r * 1.04, cy + sa * r * 1.04); x.stroke();
  x.fillStyle = '#191a19'; const pw = w * .5, pl = (w - pw) / 2, pt = h * .8; x.beginPath();
  x.moveTo(pl + 9, pt); x.lineTo(pl + pw - 9, pt); x.quadraticCurveTo(pl + pw, pt, pl + pw, pt + 9); x.lineTo(pl + pw, h); x.lineTo(pl, h); x.lineTo(pl, pt + 9); x.quadraticCurveTo(pl, pt, pl + 9, pt); x.fill();
  if (word) { x.save(); let size = Math.max(7, Math.min(10 * TXT, (h - pt) * .5));
    x.textAlign = 'center'; x.textBaseline = 'middle'; const text = word.split('').join(String.fromCharCode(8202));
    x.font = `700 ${size}px ${FONT}`; while (size > 6 && x.measureText(text).width > pw - 10) { size -= .5; x.font = `700 ${size}px ${FONT}`; }
    if (!state.power) {                      // A3 (Bill, 2026-11-19): STANDBY shows dimly, unlit, while the power is off
      x.globalAlpha = .8; x.fillStyle = '#9c8a64'; x.fillText(text, cx, pt + (h - pt) * .55);
    } else { x.globalAlpha = Math.min(1, L * 1.1); x.fillStyle = word === 'AUDIO ERROR' ? '#ff7a5c' : '#ffcf7a';
      x.shadowColor = 'rgba(255,190,90,.75)'; x.shadowBlur = 5; x.fillText(text, cx, pt + (h - pt) * .55); }
    x.restore(); }
  x.fillStyle = `rgba(8,8,6,${.34 * (1 - Math.min(1, L))})`; x.fillRect(0, 0, w, h); }

/* ---------- mechanical counter (kilocycles, one decimal) ---------- */
let strips = [], counterShown = -1;
function drawCounter(hz){ if (hz === counterShown) return; counterShown = hz; const T = hz / 100;
  for (let k = 0; k < 5; k++) { const unit = Math.pow(10, k); let v;
    if (k === 0) v = T % 10; else { const rem = T % unit; v = Math.floor(T / unit) % 10 + Math.max(0, rem - (unit - 1)); }
    strips[4 - k].style.transform = `translateY(${(-v * 38).toFixed(2)}px)`; } }

/* ---------- mechanical sounds (switch, band detent, tuning end stop) ----------
   Short clicks made in the page on the receiver's own audio context, after the first power-on. Never recorded audio. */
let clickBuf = null;
// A2 (Bill, 2026-11-19): no mechanical clicks while the power is off, including the switch moving to OFF.
function mech(kind){ const AC = state.ctx; if (!state.power || !AC || AC.state !== 'running') return;
  if (!clickBuf || clickBuf.sampleRate !== AC.sampleRate) { clickBuf = AC.createBuffer(1, AC.sampleRate * 2, AC.sampleRate); const d = clickBuf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; }
  const t = AC.currentTime, P = { toggle: ['highpass', 1900, .3, .028, 150, .22, .05], detent: ['bandpass', 900, .5, .05, 96, .4, .08], stop: ['lowpass', 500, .3, .05, 70, .35, .09] }[kind];
  const s = AC.createBufferSource(); s.buffer = clickBuf; const f = AC.createBiquadFilter(); f.type = P[0]; f.frequency.value = P[1]; const g = AC.createGain();
  g.gain.setValueAtTime(P[2], t); g.gain.exponentialRampToValueAtTime(.001, t + P[3]); s.connect(f).connect(g).connect(AC.destination); s.start(t, Math.random() * 1.5, P[3] + .02);
  const o = AC.createOscillator(), og = AC.createGain(); o.frequency.setValueAtTime(P[4], t); o.frequency.exponentialRampToValueAtTime(P[4] * .5, t + P[6]);
  og.gain.setValueAtTime(P[5], t); og.gain.exponentialRampToValueAtTime(.001, t + P[6]); o.connect(og).connect(AC.destination); o.start(t); o.stop(t + P[6] + .02); }

/* ---------- MAIN TUNING: speed-sensitive (decision 3) ---------- */
// Hz per revolution: 5 kHz when turned slowly, rising smoothly from 4 rad/s to 100 kHz per revolution at 12 rad/s (Nov 15 values).
const rateFor = v => { const k = Math.max(0, Math.min(1, (Math.abs(v) - 4) / 8)); return 5000 * (1 + 19 * k * k * (3 - 2 * k)); };
// app.js tunes in 0.1 kHz steps, so small knob movements are summed here until they reach a step.
// follow(): tuning done anywhere else (keys, wheel, slider, band guide, Alternative controls, band change, reset)
// turns the knob picture to match, restarts the sum from the new frequency and ends any coast.
function follow(){
  if (S.lastBand !== state.band) { S.lastBand = state.band; S.lastHz = state.hz; S.pointerHz = state.hz; S.acc = null; S.coast = 0; dirty.tune = true; return; }
  if (S.lastHz === state.hz) return;
  if (S.lastHz !== null) S.tuneAng += (state.hz - S.lastHz) / 10000 * TAU;
  S.lastHz = state.hz; S.acc = null; S.coast = 0; dirty.tune = true; }
function tuneBy(hzDelta, angDelta){ const [min, max] = bounds(); follow();
  if (state.hz !== min && state.hz !== max) S.stopArmed = true;      // already clear of the stop, however it got there (keys, guide, band)
  if (S.acc === null) S.acc = state.hz;
  const was = S.acc, next = Math.max(min, Math.min(max, was + hzDelta));
  S.acc = next;
  if (Math.round(next / 100) * 100 !== state.hz) tune(next);
  if (state.hz !== min && state.hz !== max) S.stopArmed = true;      // one full step clear of the stop re-arms its click
  if (next === min || next === max) { if (was !== next && S.stopArmed) { mech('stop'); S.stopArmed = false; } S.coast = 0; }
  S.tuneAng += angDelta; S.lastHz = state.hz; dirty.tune = true; wake(); }

function knobDrag(el, onDelta, onEnd){ let drag = null;
  const ang = e => { const x = e.clientX - drag.cx, y = e.clientY - drag.cy; return Math.hypot(x, y) < 10 ? null : Math.atan2(y, x); };
  el.style.touchAction = 'none';
  el.addEventListener('pointerdown', e => { if (!e.isPrimary || e.button !== 0) return; const r = el.getBoundingClientRect();
    drag = { id: e.pointerId, cx: r.left + r.width / 2, cy: r.top + r.height / 2, a: null, t: performance.now(), v: 0, p: 0 }; drag.a = ang(e);
    el.setPointerCapture(e.pointerId); el.focus({ preventScroll: true }); el.classList.add('grabbing'); e.preventDefault(); S.coast = 0; });
  el.addEventListener('pointermove', e => { if (!drag || e.pointerId !== drag.id) return; const a = ang(e); if (a === null) { drag.a = null; return; }
    // Speed is measured over at least 8 ms. A move that lands 1-3 ms after the last one (WebKit often sends the first
    // move right after pointer-down) would otherwise read as a very fast turn and jump into fast tuning (Nov 18 WebKit
    // check). Such moves still tune at the current speed; their angle is carried into the next speed reading.
    if (drag.a !== null) { const d = Math.atan2(Math.sin(a - drag.a), Math.cos(a - drag.a)), now = performance.now(), dt = (now - drag.t) / 1000;
      drag.p += d; if (dt >= .008) { drag.v = drag.v * .7 + (drag.p / dt) * .3; drag.t = now; drag.p = 0; } onDelta(d, drag.v); }
    drag.a = a; });
  const end = () => { if (!drag) return; const v = performance.now() - drag.t < 90 ? drag.v : 0; drag = null; el.classList.remove('grabbing'); if (onEnd) onEnd(v); };
  el.addEventListener('pointerup', end); el.addEventListener('pointercancel', end); el.addEventListener('lostpointercapture', end); }

/* ---------- scene sizing and a very small pointer parallax ---------- */
let stage, world, rxEl, sceneMQ;
const view = { x: 0, y: 0, tx: 0, ty: 0 };
// Listening view only (Nov 15: no fly-in): 4° downward tilt, flat layout below 760 px.
const cam = { t: 1, shown: -1, Z: 1.64, PITCH0: -22, PITCH1: -4, YAW0: 8 };
const easeIO = u => u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
function camApply(){ const e = easeIO(cam.t), H = rxEl.offsetHeight, Z = 1 + (cam.Z - 1) * e, par = 1 - .65 * e;
  const tx_ = 130 * cam.Z * e, ty = (520 - (600 + (200 + H / 2 - 600) * cam.Z)) * e;
  const pitch = cam.PITCH0 + (cam.PITCH1 - cam.PITCH0) * e - view.y * .8 * par, yaw = cam.YAW0 * (1 - e) + view.x * 1.3 * par;
  world.style.transform = `translate3d(${tx_.toFixed(2)}px,${ty.toFixed(2)}px,0) scale(${Z.toFixed(4)}) rotateX(${pitch.toFixed(3)}deg) rotateY(${yaw.toFixed(3)}deg)`; }
function sizeScene(){ const t = txtMQ && txtMQ.matches ? 1.3 : 1; if (t !== TXT) { TXT = t; dirty.tune = dirty.gain = dirty.band = true; }
  if (sceneMQ.matches) { root.style.setProperty('--k', (stage.clientWidth / 1760).toFixed(4)); world.style.setProperty('--H', rxEl.offsetHeight + 'px'); } measure(); cam.shown = -1; painted = ''; wake(); }

/* ---------- frame loop ----------
   The loop runs only while there is something to show: the receiver is lit (lamp flicker and needle jitter are part of
   the design), or the lamp, needle, dial pointer, band knob or scene is still settling, or a coast is running. Otherwise it
   stops and wake() restarts it: on any input, on HSFace.update() from app.js, on resize, and when the scene scrolls back
   into view. It also stops while the scene is off screen or the tab is hidden. While lit and calm the dial and meter are
   repainted about 30 times a second; while anything is moving they are repainted every frame, as before. */
let last = performance.now(), rafId = 0, onScreen = true, lastPaint = 0, painted = '', lampShown = '';
function wake(){ if (ready && !rafId && onScreen && !document.hidden) { last = performance.now(); rafId = requestAnimationFrame(frame); } }
// Band detent click: heard when the band switch moves, whether or not the scene is being drawn.
function sense(){ const knobBand = state.pendingBand ?? state.band;
  if (S.lastKnobBand !== knobBand) { if (S.lastKnobBand !== null) mech('detent'); S.lastKnobBand = knobBand; } return knobBand; }
function frame(now){ rafId = 0; const dt = Math.max(0, Math.min(.05, (now - last) / 1000)); last = now; S.t += dt;
  const on = !!state.power;
  S.lamp += ((on ? 1 : 0) - S.lamp) * (1 - Math.exp(-dt / (on ? .3 : .13)));           // filament warm-up and die-down
  if (!on && S.lamp < .002) S.lamp = 0;
  S.lampOut = S.lamp * (on && !reduce ? 1 + .012 * Math.sin(S.t * 37) + .008 * Math.sin(S.t * 61.3) : 1);
  const lampText = S.lamp.toFixed(3); if (lampText !== lampShown) { lampShown = lampText; root.style.setProperty('--lamp', lampText); }
  follow();   // changes made elsewhere turn the knob too, and end a coast, before the coast takes its next step
  if (S.coast) { const d = S.coast * dt; tuneBy(d / TAU * rateFor(S.coast), d); S.coast *= Math.exp(-dt / .85); if (Math.abs(S.coast) < .2) S.coast = 0; }
  if (S.lastGain !== state.gain) { S.lastGain = state.gain; dirty.gain = true; }
  const knobBand = sense();
  S.pointerHz = reduce ? state.hz : S.pointerHz + (state.hz - S.pointerHz) * (1 - Math.exp(-dt / .075));  // dial-cord lag
  if (Math.abs(state.hz - S.pointerHz) < .5) S.pointerHz = state.hz;
  // S-meter: lifts under the same condition as the grey face (receiver on and a recording captured), strongest at its frequency.
  const sel = state.selected, captured = on && !!sel;
  const s = captured ? Math.max(0, 1 - Math.abs(state.hz - sel.frequencyHz) / 1600) : 0;
  const target = on ? Math.min(1.02, .07 + (captured ? .25 + .62 * s : 0) + (reduce ? 0 : .012 * Math.sin(S.t * 9.1) + .01 * (Math.random() - .5))) : -.03;
  if (reduce) { S.needle += (target - S.needle) * (1 - Math.exp(-dt / .05)); }
  else { S.nv += (150 * (target - S.needle) - 12.5 * S.nv) * dt; S.needle += S.nv * dt;                // underdamped needle
    if (S.needle < -.04) { S.needle = -.04; S.nv *= -.3; } if (S.needle > 1.05) { S.needle = 1.05; S.nv *= -.3; } }
  const needleMoving = Math.abs(target - S.needle) > .002 || Math.abs(S.nv) > .01;
  if (!on && !needleMoving) { S.needle = target; S.nv = 0; }
  const bandTarget = BAND_ANGLES[knobBand] * Math.PI / 180;
  const prevBandAng = S.bandAng; S.bandAng = reduce ? bandTarget : S.bandAng + (bandTarget - S.bandAng) * (1 - Math.exp(-dt / .03));
  if (Math.abs(bandTarget - S.bandAng) < .0005) S.bandAng = bandTarget;
  let sceneMoving = false;
  if (sceneMQ.matches) { let moved = cam.shown < 0;
    if (Math.abs(view.tx - view.x) > .002 || Math.abs(view.ty - view.y) > .002) { view.x += (view.tx - view.x) * (1 - Math.exp(-dt / .25)); view.y += (view.ty - view.y) * (1 - Math.exp(-dt / .25)); moved = sceneMoving = true; }
    if (moved) { camApply(); cam.shown = cam.t; } }
  else if (cam.shown >= 0) { world.style.transform = ''; cam.shown = -1; }
  const word = ($('receiver-status').textContent || '').trim();   // off: STANDBY, drawn dimly by drawMeter (A3)
  const lit = on || S.lamp > 0;
  const settling = S.coast !== 0 || S.pointerHz !== state.hz || S.bandAng !== bandTarget || (!on && needleMoving) || (!on && S.lamp > 0) || sceneMoving;
  const alive = lit || settling;
  // Repaint the dial and meter only when what they show has changed; while lit and calm, at most about 30 times a second.
  const showing = `${S.lampOut.toFixed(4)}|${S.needle.toFixed(4)}|${S.pointerHz.toFixed(1)}|${state.band}|${word}|${on}|${dW}x${dH}|${mW}x${mH}|${FONT}|${TXT}`;
  const busy = settling || Math.abs(target - S.needle) > .03 || Math.abs(S.nv) > .15 || Math.abs((on ? 1 : 0) - S.lamp) > .01;
  if (showing !== painted && (busy || !alive || now - lastPaint >= 30)) { drawDial(); drawMeter(word); painted = showing; lastPaint = now; }
  drawCounter(state.hz);
  if (dirty.tune) { drawTune(); dirty.tune = false; }
  if (dirty.gain) { drawGain(); dirty.gain = false; }
  if (Math.abs(S.bandAng - prevBandAng) > .0005 || dirty.band) { drawBand(); dirty.band = false; }
  if (alive) wake(); }

function init(){
  FONT = getComputedStyle(root).getPropertyValue('--font-panel') || FONT;
  dial = $('dial'); meter = $('meter'); stage = $('stage'); world = $('world'); rxEl = document.querySelector('.rx'); sceneMQ = matchMedia('(min-width:760px)'); txtMQ = matchMedia('(min-width:760px) and (max-width:1000px)');
  tx = fit($('tuning-knob'), 180, 180); gx = fit($('gain-knob'), 140, 140); bx = fit($('band-knob'), 150, 150);
  strips = [...document.querySelectorAll('#counter .strip')];
  strips.forEach(s => { for (const d of '01234567890') { const e = document.createElement('span'); e.textContent = d; s.append(e); } });
  S.pointerHz = state.hz; S.bandAng = BAND_ANGLES[state.band] * Math.PI / 180; dirty.band = true;
  knobDrag($('tuning-knob'), (d, v) => tuneBy(d / TAU * rateFor(v), d), v => { if (!reduce && Math.abs(v) > 2.5) S.coast = Math.max(-40, Math.min(40, v)); });
  // Any new press, key or wheel movement anywhere on the page ends a coast (follow() covers changes that arrive without one).
  for (const type of ['pointerdown', 'keydown', 'wheel']) addEventListener(type, () => { S.coast = 0; }, { capture: true, passive: true });
  // Any input restarts the frame loop if it had stopped; a frame with nothing new to show paints nothing.
  for (const type of ['pointerdown', 'pointermove', 'pointerup', 'keydown', 'keyup', 'wheel', 'input', 'change', 'click']) addEventListener(type, wake, { capture: true, passive: true });
  $('power-button').addEventListener('click', () => { setTimeout(() => mech('toggle'), 0); });
  stage.addEventListener('pointermove', e => { if (e.buttons || reduce || !sceneMQ.matches) return; const r = stage.getBoundingClientRect();
    view.tx = (e.clientX - r.left) / r.width * 2 - 1; view.ty = (e.clientY - r.top) / r.height * 2 - 1; });
  stage.addEventListener('pointerleave', () => { view.tx = 0; view.ty = 0; wake(); });
  sizeScene();
  if (document.fonts) document.fonts.ready.then(() => { FONT = getComputedStyle(root).getPropertyValue('--font-panel') || FONT; dirty.tune = dirty.gain = dirty.band = true; painted = ''; wake(); });
  addEventListener('resize', sizeScene);
  if (window.ResizeObserver) new ResizeObserver(sizeScene).observe(rxEl);
  // Stop drawing while the scene is scrolled off screen or the tab is hidden; start again when it returns.
  if (window.IntersectionObserver) new IntersectionObserver(entries => { onScreen = entries[entries.length - 1].isIntersecting; if (onScreen) { painted = ''; wake(); } else S.coast = 0; }).observe(stage);
  document.addEventListener('visibilitychange', wake);
  ready = true; wake();
}
// Deferred scripts run before DOMContentLoaded, and face.js runs before app.js, so wait for DOMContentLoaded:
// by then app.js has created the receiver state.
if (document.readyState === 'complete') init(); else document.addEventListener('DOMContentLoaded', init);
})();
