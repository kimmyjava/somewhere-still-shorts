// Procedural B1 asset builder: hand-drawn style stickman cast + props as PNGs,
// composed at the 9:16 design plane (720 x 1280 units). Deterministic wobble.
import fs from 'node:fs';
import path from 'node:path';
import {createCanvas} from '@napi-rs/canvas';

const OUT = path.resolve(import.meta.dirname, 'assets');
fs.mkdirSync(OUT, {recursive: true});

// Deterministic PRNG so rebuilds are reproducible.
let seed = 42;
const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
const wobble = amp => (rnd() - 0.5) * amp;

const INK = '#191916';
const RED = '#EC4338';
const YELLOW = '#F5B82E';
const GREEN = '#3F9142';
const NAVY = '#2B3A67';
const PAPER = '#FDFDFC';

// Hand-drawn slightly wavy line between points.
function wline(ctx, x1, y1, x2, y2, width = 4, color = INK, amp = 1.6) {
  const steps = Math.max(2, Math.round(Math.hypot(x2 - x1, y2 - y1) / 26));
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.beginPath(); ctx.moveTo(x1 + wobble(amp), y1 + wobble(amp));
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    ctx.lineTo(x1 + (x2 - x1) * t + wobble(amp), y1 + (y2 - y1) * t + wobble(amp));
  }
  ctx.stroke();
}

function circle(ctx, cx, cy, r, fill = null, stroke = INK, width = 4) {
  ctx.beginPath();
  for (let i = 0; i <= 26; i++) {
    const a = (i / 26) * Math.PI * 2;
    const rr = r + wobble(1.2);
    const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  }
  ctx.closePath();
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = width; ctx.stroke(); }
}

function ellipsePath(ctx, cx, cy, rx, ry, rot = 0, fill = null, stroke = INK, width = 3.5) {
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(rot); ctx.beginPath();
  for (let i = 0; i <= 30; i++) {
    const a = (i / 30) * Math.PI * 2;
    const x = Math.cos(a) * (rx + wobble(0.8)), y = Math.sin(a) * (ry + wobble(0.8));
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  }
  ctx.closePath();
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = width; ctx.stroke(); }
  ctx.restore();
}

// Character spec: head center (hx,hy), head radius r, facing (+1 right/-1 left),
// expressions and whole-body pose via named params.
function stickman(ctx, {
  hx, hy, r = 46, facing = 1,
  // expression
  brows = 'worried', mouth = 'small', eyes = 'open', marks = null,
  // pose (angles in radians from vertical-down or horizontal-out)
  torsoLean = 0, armL = 0.5, armR = -0.5, armLbend = 0.15, armRbend = -0.15,
  legSpread = 0.16, sitting = false, lying = false, holdL = null, holdR = null,
}, heldPhone = null) {
  const hipY = lying ? hy + 12 : sitting ? hy + r + 118 : hy + r + 128;
  const shoulderY = hy + r + 34;
  const neckX = hx + torsoLean * 18;
  const shoulderX = neckX + torsoLean * 10;
  // legs
  if (lying) {
    // Whole body horizontal: neck/shoulder at hy+8, hips at hy+12, legs to the left.
    const sy = hy + 8;
    wline(ctx, hx - r - 30, sy + 6, hx - r - 150, sy + 2);
    wline(ctx, hx - r - 30, sy + 8, hx - r - 158, sy + 20);
    ellipsePath(ctx, hx - r - 166, sy + 6, 13, 9, 0, null, INK, 3.5);
    ellipsePath(ctx, hx - r - 172, sy + 22, 13, 9, 0, null, INK, 3.5);
    // torso along the bed
    wline(ctx, hx - r, sy, hx - r - 34, sy + 6);
  } else if (sitting) {
    // Side sit on an edge: thigh forward, shin down, foot on floor.
    const kneeX = neckX + 86, kneeY = hipY - 8;
    wline(ctx, neckX, hipY, kneeX, kneeY);
    wline(ctx, kneeX, kneeY, kneeX + 4, kneeY + 92);
    ellipsePath(ctx, kneeX + 18, kneeY + 96, 14, 9, 0, null, INK, 3.5);
  } else {
    const footY = hy + r + 250;
    wline(ctx, neckX, hipY, neckX - legSpread * 130, footY);
    wline(ctx, neckX, hipY, neckX + legSpread * 130, footY);
    ellipsePath(ctx, neckX - legSpread * 130 - 8, footY + 4, 14, 9, 0, null, INK, 3.5);
    ellipsePath(ctx, neckX + legSpread * 130 + 8, footY + 4, 14, 9, 0, null, INK, 3.5);
  }
  // torso
  if (lying) {
    wline(ctx, hx - r, hy + 8, hx - r + 2, hy + 10); // stub: neck joins head
  } else {
    wline(ctx, shoulderX, shoulderY, hipX(neckX, torsoLean, hipY, sitting), hipY - 6);
  }
  function hipX(nx, lean, y, sit) { return sit ? nx + lean * 40 - 0 : nx + lean * 12; }
  // neck
  if (!lying) wline(ctx, hx + torsoLean * 4, hy + r, neckX, shoulderY, 3.5);
  // arms
  function arm(sx, sy, ang, bend, side) {
    const ux = sx + Math.cos(ang) * 46 * side, uy = sy + Math.sin(ang) * 46;
    const fAng = ang + bend * side;
    const fx = ux + Math.cos(fAng) * 44 * side, fy = uy + Math.sin(fAng) * 44;
    wline(ctx, sx, sy, ux, uy);
    wline(ctx, ux, uy, fx, fy);
    circle(ctx, fx, fy, 7.5, null, INK, 3.5);
    return [fx, fy];
  }
  let handL, handR;
  if (lying) {
    // arms folded on chest: short lines from shoulder toward body center
    const sx = hx - r + 2, sy = hy + 10;
    wline(ctx, sx, sy, sx - 26, sy + 20); wline(ctx, sx - 26, sy + 20, sx - 10, sy + 30);
    circle(ctx, sx - 10, sy + 30, 7.5, null, INK, 3.5);
    handL = [sx - 10, sy + 30]; handR = handL;
  } else {
    handL = arm(shoulderX - 4, shoulderY + 4, armL, armLbend, -1);
    handR = arm(shoulderX + 4, shoulderY + 4, armR, armRbend, 1);
  }
  if (holdL) holdL(...handL);
  if (holdR) holdR(...handR);
  if (heldPhone) phone(ctx, handR[0] + 12, handR[1] - 8, 26, 44, heldPhone === 'glow');
  // head
  circle(ctx, hx, hy, r, PAPER, INK, 4.5);
  // face
  const ex = hx + facing * 10;
  function eye(ox) {
    if (eyes === 'closed') { wline(ctx, ex + ox - 8, hy - 4, ex + ox + 8, hy - 2, 3); }
    else if (eyes === 'wide') { ellipsePath(ctx, ex + ox, hy - 4, 5.5, 7, 0, INK, null); }
    else if (eyes === 'shut-tight') { wline(ctx, ex + ox - 8, hy - 4, ex + ox + 8, hy - 6, 3.5); }
    else { ellipsePath(ctx, ex + ox, hy - 4, 4, 5.5, 0, INK, null); }
  }
  eye(-13); eye(13);
  // brows
  const bl = ex - 14, br = ex + 14, by = hy - 20;
  if (brows === 'worried') { wline(ctx, bl - 7, by + 4, bl + 7, by - 2, 3.5); wline(ctx, br - 7, by - 2, br + 7, by + 4, 3.5); }
  else if (brows === 'raised') { wline(ctx, bl - 7, by - 8, bl + 7, by - 10, 3.5); wline(ctx, br - 7, by - 10, br + 7, by - 8, 3.5); }
  else if (brows === 'angry') { wline(ctx, bl - 7, by - 2, bl + 7, by + 5, 3.5); wline(ctx, br - 7, by + 5, br + 7, by - 2, 3.5); }
  else if (brows === 'asym') { wline(ctx, bl - 7, by + 3, bl + 7, by + 1, 3.5); wline(ctx, br - 7, by - 9, br + 7, by - 6, 3.5); }
  else if (brows === 'calm') { wline(ctx, bl - 6, by - 3, bl + 6, by - 4, 3.5); wline(ctx, br - 6, by - 4, br + 6, by - 3, 3.5); }
  // mouth
  const my = hy + 18;
  if (mouth === 'small') wline(ctx, ex - 9, my, ex + 9, my + 2, 3.5);
  else if (mouth === 'open-small') ellipsePath(ctx, ex, my + 2, 7, 5, 0, INK, null);
  else if (mouth === 'open-wide') ellipsePath(ctx, ex + facing * 2, my + 2, 12, 10, 0, INK, null);
  else if (mouth === 'grin') { ctx.beginPath(); ctx.moveTo(ex - 13, my - 2); ctx.quadraticCurveTo(ex, my + 12, ex + 13, my - 2); ctx.strokeStyle = INK; ctx.lineWidth = 3.5; ctx.lineCap = 'round'; ctx.stroke(); }
  else if (mouth === 'frown') { ctx.beginPath(); ctx.moveTo(ex - 11, my + 4); ctx.quadraticCurveTo(ex, my - 6, ex + 11, my + 4); ctx.strokeStyle = INK; ctx.lineWidth = 3.5; ctx.stroke(); }
  else if (mouth === 'flat-long') wline(ctx, ex - 13, my, ex + 13, my + 1, 3.5);
  // optional marks: sweat/tear strokes near head
  if (marks === 'sweat') {
    wline(ctx, hx + facing * (r + 4), hy - r * 0.5, hx + facing * (r + 16), hy - r * 0.5 - 12, 3, NAVY, 1);
    wline(ctx, hx + facing * (r + 2), hy - r * 0.1, hx + facing * (r + 14), hy - r * 0.1 - 12, 3, NAVY, 1);
  }
  return {handL, handR, shoulderX, shoulderY, hipY};
}

function bubble(ctx, x, y, w, h, tailTo = null) {
  ellipsePath(ctx, x, y, w / 2, h / 2, 0, '#FFFFFF', INK, 3.5);
  if (tailTo) {
    const [tx, ty] = tailTo;
    wline(ctx, x - w * 0.18, y + h * 0.38, tx, ty, 3);
    wline(ctx, x + w * 0.1, y + h * 0.44, tx, ty, 3);
  }
}

function phone(ctx, x, y, w = 26, h = 44, glow = false) {
  ctx.save(); ctx.translate(x, y);
  ctx.fillStyle = glow ? '#FFF7D6' : '#FFFFFF';
  ctx.strokeStyle = INK; ctx.lineWidth = 3.5;
  ctx.beginPath(); ctx.roundRect(-w / 2, -h / 2, w, h, 5); ctx.fill(); ctx.stroke();
  if (glow) {
    ctx.strokeStyle = YELLOW; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.roundRect(-w / 2 - 5, -h / 2 - 5, w + 10, h + 10, 8); ctx.stroke();
  }
  ctx.restore();
}

function save(name, w, h, draw) {
  const canvas = createCanvas(w, h);
  const ctx = canvas.getContext('2d');
  draw(ctx);
  // Trim to ink bounding box (drawings sit on transparency) so placement in
  // project.json is by content, not by canvas.
  const {width, height} = canvas;
  const data = ctx.getImageData(0, 0, width, height).data;
  let x0 = width, y0 = height, x1 = -1, y1 = -1;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (data[(y * width + x) * 4 + 3] > 8) {
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
    }
  }
  if (x1 < 0) throw new Error(`empty asset: ${name}`);
  const pad = 6;
  x0 = Math.max(0, x0 - pad); y0 = Math.max(0, y0 - pad);
  x1 = Math.min(width - 1, x1 + pad); y1 = Math.min(height - 1, y1 + pad);
  const cw = x1 - x0 + 1, chh = y1 - y0 + 1;
  const out = createCanvas(cw, chh);
  out.getContext('2d').drawImage(canvas, x0, y0, cw, chh, 0, 0, cw, chh);
  fs.writeFileSync(path.join(OUT, name), out.toBuffer('image/png'));
  manifest[name] = {x: x0, y: y0, w: cw, h: chh};
  console.log(name, `${cw}x${chh}`);
}

const manifest = {};

const W = 720, H = 1280;

// ---- character variants (cast: "Mika" - same design every time) -------------
// Standing variants share geometry: head at (360, 470) r46, feet ~766.
const variants = {
  // S1: lying in bed, eyes closed -> wide awake shock handled in-canvas via two assets
  'hero-lying': {hx: 380, hy: 300, lying: true, facing: 1, eyes: 'closed', brows: 'calm', mouth: 'small', armL: 1.2, armR: 0.9, armLbend: 0.1, armRbend: 0.1},
  'hero-lying-shock': {hx: 380, hy: 300, lying: true, facing: 1, eyes: 'wide', brows: 'raised', mouth: 'open-wide', marks: 'sweat', armL: 1.5, armR: -0.9, armLbend: 0.4, armRbend: -0.5},
  // S1/S5: sitting up, phone in right hand
  'hero-sit-phone': {hx: 360, hy: 470, sitting: true, facing: 1, eyes: 'wide', brows: 'worried', mouth: 'open-small', marks: 'sweat', armR: -1.15, armRbend: -0.45, _phone: 'glow'},
  'hero-sit-calm': {hx: 360, hy: 470, sitting: true, facing: 1, eyes: 'open', brows: 'calm', mouth: 'small', armR: -0.9, armRbend: -0.2, _phone: 'plain'},
  // S2: alarm guard (small figure at control panel)
  'guard-panic': {hx: 360, hy: 300, r: 38, facing: 1, eyes: 'wide', brows: 'raised', mouth: 'open-wide', marks: 'sweat', armL: 1.1, armR: -1.1, armLbend: 0.5, armRbend: -0.5, legSpread: 0.22},
  // S2 comparison: nervous presenter
  'hero-present-nervous': {hx: 360, hy: 430, facing: 1, eyes: 'open', brows: 'worried', mouth: 'flat-long', marks: 'sweat', armL: 0.7, armR: -0.7, armLbend: 0.35, armRbend: -0.35},
  // S2 comparison: catastrophic imagining (same figure, terrified)
  'hero-panic-arms-up': {hx: 360, hy: 430, facing: 1, eyes: 'wide', brows: 'raised', mouth: 'open-wide', marks: 'sweat', armL: 1.9, armR: -1.9, armLbend: 0.3, armRbend: -0.3},
  // S3: overthinking, hand to forehead
  'hero-overthink': {hx: 360, hy: 470, facing: 1, eyes: 'shut-tight', brows: 'asym', mouth: 'frown', armR: -2.4, armRbend: -1.25, armL: 0.35},
  // S3: chest clutch (racing heart)
  'hero-chest': {hx: 360, hy: 470, facing: 1, eyes: 'wide', brows: 'worried', mouth: 'open-small', marks: 'sweat', armL: 0.95, armLbend: -0.85, armR: -0.95, armRbend: 0.85},
  // S3: walking away (avoidance), profile
  'hero-avoid': {hx: 360, hy: 470, facing: 1, eyes: 'closed', brows: 'calm', mouth: 'flat-long', armL: 0.9, armR: -0.75, torsoLean: 0.12},
  // S4: calm explaining, open palm gesture
  'hero-explain': {hx: 360, hy: 450, facing: 1, eyes: 'open', brows: 'calm', mouth: 'small', armR: -1.3, armRbend: -0.35, armL: 0.3, armLbend: 0.1},
  // S4: breathing, hand on chest, eyes closed, soft
  'hero-breathe': {hx: 360, hy: 450, facing: 1, eyes: 'closed', brows: 'calm', mouth: 'small', armR: -0.7, armRbend: -0.95, torsoLean: -0.04},
  // S4: grounding, looking around (gaze up-left handled by facing/eyes open)
  'hero-ground': {hx: 360, hy: 450, facing: 1, eyes: 'open', brows: 'raised', mouth: 'small', armL: 0.55, armR: -0.4, armLbend: 0.5},
  // S5: resolved, putting phone down face-down, gentle
  'hero-resolve': {hx: 360, hy: 450, facing: 1, eyes: 'open', brows: 'calm', mouth: 'grin', armR: -0.5, armRbend: -0.15},
  // S6: facing viewer, pointing at camera
  'hero-point': {hx: 360, hy: 460, facing: 1, eyes: 'open', brows: 'raised', mouth: 'grin', armR: -1.5, armRbend: -0.1, armL: 0.25},
};

for (const [name, v] of Object.entries(variants)) {
  save(`${name}.png`, W, H, ctx => {
    stickman(ctx, v, v._phone);
    ctx.strokeStyle = 'transparent';
  });
}

// ---- phone with notification banner (prop for S1 hook) ----------------------
save('phone-notification.png', W, H, ctx => {
  phone(ctx, 360, 210, 170, 300, false);
  // banner
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = INK; ctx.lineWidth = 4;
  ctx.beginPath(); ctx.roundRect(150, 330, 420, 96, 16); ctx.fill(); ctx.stroke();
  ctx.fillStyle = RED; ctx.beginPath(); ctx.arc(178, 356, 10, 0, Math.PI * 2); ctx.fill();
});

// ---- thought bubbles (empty, text drawn as separate text layers) ------------
save('bubble-empty.png', W, H, ctx => bubble(ctx, 360, 380, 460, 220));
save('bubble-small.png', W, H, ctx => bubble(ctx, 360, 300, 240, 140));

// ---- alarm control room (S2): panel + flashing light as separate PNGs --------
save('alarm-panel.png', W, H, ctx => {
  // console desk
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = INK; ctx.lineWidth = 4.5;
  ctx.beginPath(); ctx.roundRect(140, 560, 440, 150, 14); ctx.fill(); ctx.stroke();
  // buttons
  for (const [bx, by, c] of [[200, 610, RED], [260, 610, YELLOW], [320, 610, GREEN], [380, 610, NAVY], [440, 610, RED], [500, 610, YELLOW]]) {
    ctx.fillStyle = c; ctx.beginPath(); ctx.arc(bx, by, 17, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.stroke();
  }
  // levers
  wline(ctx, 230, 700, 260, 640); wline(ctx, 350, 700, 380, 645); wline(ctx, 470, 700, 445, 642);
  circle(ctx, 260, 640, 8, INK, null); circle(ctx, 380, 645, 8, INK, null); circle(ctx, 445, 642, 8, INK, null);
});
save('alarm-light-off.png', W, H, ctx => {
  wline(ctx, 560, 240, 560, 300, 4);
  ellipsePath(ctx, 560, 220, 34, 30, 0, '#EDEDEA', INK, 4);
});
save('alarm-light-on.png', W, H, ctx => {
  // rays
  ctx.strokeStyle = RED; ctx.lineWidth = 4;
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    wline(ctx, 560 + Math.cos(a) * 48, 220 + Math.sin(a) * 44, 560 + Math.cos(a) * 86, 220 + Math.sin(a) * 80, 4, RED, 1);
  }
  wline(ctx, 560, 240, 560, 300, 4);
  ellipsePath(ctx, 560, 220, 34, 30, 0, RED, INK, 4);
});

// ---- giant monster made of question marks (S3/S2 imagination) ---------------
function qmark(ctx, x, y, s, color = INK, lw = 8) {
  ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(x - s * 0.45, y - s * 0.55);
  ctx.bezierCurveTo(x - s * 0.45, y - s * 1.05, x + s * 0.45, y - s * 1.05, x + s * 0.45, y - s * 0.5);
  ctx.bezierCurveTo(x + s * 0.45, y - s * 0.1, x, y - s * 0.15, x, y + s * 0.25);
  ctx.stroke();
  circle(ctx, x, y + s * 0.62, lw * 0.85, color, null);
}
save('monster-question.png', W, H, ctx => {
  qmark(ctx, 360, 430, 150, RED, 11);
  qmark(ctx, 205, 560, 90, INK, 8);
  qmark(ctx, 515, 570, 85, INK, 8);
  qmark(ctx, 290, 640, 60, NAVY, 7);
  qmark(ctx, 435, 650, 62, NAVY, 7);
});

// ---- audience (S2 comparison): rows of simple heads --------------------------
save('audience-laughing.png', W, H, ctx => {
  for (const [cx, cy, r] of [[190, 560, 40], [330, 570, 44], [470, 558, 40], [600, 572, 38], [120, 680, 34], [260, 690, 36], [410, 684, 36], [550, 688, 34]]) {
    circle(ctx, cx, cy, r, PAPER, INK, 4);
    // laughing mouths (open arcs)
    ctx.beginPath(); ctx.moveTo(cx - r * 0.45, cy + r * 0.25);
    ctx.quadraticCurveTo(cx, cy + r * 0.85, cx + r * 0.45, cy + r * 0.25);
    ctx.strokeStyle = INK; ctx.lineWidth = 3.5; ctx.stroke();
    ellipsePath(ctx, cx - r * 0.35, cy - r * 0.2, 4, 5, 0, INK, null);
    ellipsePath(ctx, cx + r * 0.35, cy - r * 0.2, 4, 5, 0, INK, null);
  }
});

// ---- bed (S1): blanket over lying hero --------------------------------------
save('bed-blanket.png', W, H, ctx => {
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = INK; ctx.lineWidth = 4.5;
  ctx.beginPath(); ctx.roundRect(60, 420, 600, 190, 18); ctx.fill(); ctx.stroke();
  // blanket fold lines
  wline(ctx, 120, 470, 600, 462, 3, INK, 1);
  wline(ctx, 110, 520, 590, 514, 3, INK, 1);
  wline(ctx, 100, 566, 580, 560, 3, INK, 1);
  // pillow
  ellipsePath(ctx, 520, 440, 90, 34, 0.08, '#FFFFFF', INK, 4);
});

// ---- laptop (S3 avoidance) ---------------------------------------------------
save('laptop.png', W, H, ctx => {
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = INK; ctx.lineWidth = 4.5;
  ctx.beginPath(); ctx.roundRect(200, 480, 320, 200, 10); ctx.fill(); ctx.stroke();
  wline(ctx, 240, 540, 480, 536, 3, INK, 1);
  wline(ctx, 240, 580, 470, 576, 3, INK, 1);
  wline(ctx, 240, 620, 455, 616, 3, INK, 1);
  // lid
  ctx.beginPath(); ctx.roundRect(160, 700, 400, 26, 8); ctx.fill(); ctx.stroke();
});

// ---- small problem -> monster seed (S3): scribble cloud ----------------------
save('tiny-problem.png', W, H, ctx => {
  ellipsePath(ctx, 360, 500, 60, 40, 0, '#FFFFFF', INK, 4);
  wline(ctx, 330, 495, 385, 505, 3, INK, 1);
});

// ---- 5-4-3 grounding: eye / hand / ear icons --------------------------------
save('icon-eye.png', W, H, ctx => {
  ellipsePath(ctx, 360, 480, 90, 56, 0, '#FFFFFF', INK, 5);
  circle(ctx, 360, 480, 26, INK, null);
});
save('icon-hand.png', W, H, ctx => {
  const palm = {x: 360, y: 520};
  circle(ctx, palm.x, palm.y, 52, '#FFFFFF', INK, 5);
  for (let i = 0; i < 4; i++) {
    const a = -1.9 + i * 0.42;
    wline(ctx, palm.x + Math.cos(a) * 44, palm.y + Math.sin(a) * 44,
      palm.x + Math.cos(a) * 92, palm.y + Math.sin(a) * 92, 6);
  }
  wline(ctx, palm.x - 48, palm.y + 30, palm.x - 84, palm.y + 66, 6);
});
save('icon-ear.png', W, H, ctx => {
  ctx.strokeStyle = INK; ctx.lineWidth = 5; ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(340, 420);
  ctx.bezierCurveTo(330, 380, 400, 370, 402, 430);
  ctx.bezierCurveTo(404, 470, 380, 480, 372, 510);
  ctx.stroke();
  ctx.beginPath(); ctx.arc(368, 445, 16, 0, Math.PI * 2); ctx.stroke();
});
save('icon-lungs.png', W, H, ctx => {
  ellipsePath(ctx, 320, 500, 42, 60, 0.15, '#FFFFFF', INK, 5);
  ellipsePath(ctx, 400, 500, 42, 60, -0.15, '#FFFFFF', INK, 5);
  wline(ctx, 360, 420, 360, 520, 5);
  wline(ctx, 360, 520, 330, 560, 5); wline(ctx, 360, 520, 390, 560, 5);
});

// ---- breathing ring (S4 slow down): concentric guide -------------------------
save('breath-ring.png', W, H, ctx => {
  circle(ctx, 360, 480, 150, null, GREEN, 5);
  circle(ctx, 360, 480, 100, null, GREEN, 4);
});

// ---- presenter screen (S2 normal comparison) ---------------------------------
save('podium.png', W, H, ctx => {
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = INK; ctx.lineWidth = 4.5;
  ctx.beginPath(); ctx.roundRect(240, 560, 240, 160, 10); ctx.fill(); ctx.stroke();
  wline(ctx, 270, 610, 450, 606, 3, INK, 1);
  wline(ctx, 270, 650, 450, 646, 3, INK, 1);
});

// ---- phone face-down on table (S5 resolve) -----------------------------------
save('phone-down.png', W, H, ctx => {
  ctx.fillStyle = '#FFFFFF'; ctx.strokeStyle = INK; ctx.lineWidth = 4.5;
  ctx.beginPath(); ctx.roundRect(250, 520, 220, 120, 10); ctx.fill(); ctx.stroke();
  circle(ctx, 360, 580, 8, INK, null);
  // small table line
  wline(ctx, 170, 660, 550, 656, 4);
});

console.log('assets done:', fs.readdirSync(OUT).filter(f => f.endsWith('.png')).length, 'files');
fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2));
