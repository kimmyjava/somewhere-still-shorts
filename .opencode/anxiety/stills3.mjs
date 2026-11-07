import {createCanvas} from '@napi-rs/canvas';
import fs from 'node:fs';
import path from 'node:path';
const {painter} = await import('/workspace/video-generation/.opencode/skills/directing-stickman-videos/scripts/autopilot-render.mjs');
const {loadProject} = await import('/workspace/video-generation/.opencode/skills/directing-stickman-videos/scripts/autopilot-core.mjs');
const p = loadProject(path.resolve('project.json'), undefined);
const draw = await painter(p);
const times = [1.5, 6.5, 8.5, 13.0, 20.0, 44.0, 48.0, 51.5, 73.5, 78.5, 84.5, 88.3];
const cols = 4, cw = 270, ch = 480;
const canvas = createCanvas(cols * cw, Math.ceil(times.length / cols) * ch);
const ctx = canvas.getContext('2d');
ctx.fillStyle = '#ddd'; ctx.fillRect(0, 0, canvas.width, canvas.height);
for (let i = 0; i < times.length; i++) {
  const frame = draw(times[i]);
  ctx.drawImage(frame, (i % cols) * cw, Math.floor(i / cols) * ch, cw, ch);
}
fs.writeFileSync('stills3.png', canvas.toBuffer('image/png'));
console.log('ok');
