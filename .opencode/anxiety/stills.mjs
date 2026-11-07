import {createCanvas, loadImage} from '@napi-rs/canvas';
import fs from 'node:fs';
import path from 'node:path';
const {painter} = await import('/workspace/video-generation/.opencode/skills/directing-stickman-videos/scripts/autopilot-render.mjs');
const {loadProject} = await import('/workspace/video-generation/.opencode/skills/directing-stickman-videos/scripts/autopilot-core.mjs');
const p = loadProject(path.resolve('project.json'), undefined);
const draw = await painter(p);
const times = [1.0, 3.5, 7.0, 10.5, 16.0, 27.5, 34.0, 44.0, 52.0, 62.0, 72.0, 82.0];
const cols = 4, cw = 270, ch = 480;
const canvas = createCanvas(cols * cw, Math.ceil(times.length / cols) * ch);
const ctx = canvas.getContext('2d');
ctx.fillStyle = '#ddd'; ctx.fillRect(0, 0, canvas.width, canvas.height);
for (let i = 0; i < times.length; i++) {
  const frame = draw(Math.min(times[i], p.shots.at(-1).end - 0.01));
  const x = (i % cols) * cw, y = Math.floor(i / cols) * ch;
  ctx.drawImage(frame, x, y, cw, ch);
}
fs.writeFileSync('stills.png', canvas.toBuffer('image/png'));
console.log('stills written');
