import {createCanvas} from '@napi-rs/canvas';
import fs from 'node:fs';
import path from 'node:path';
const {painter} = await import('/workspace/video-generation/.opencode/skills/directing-stickman-videos/scripts/autopilot-render.mjs');
const {loadProject} = await import('/workspace/video-generation/.opencode/skills/directing-stickman-videos/scripts/autopilot-core.mjs');
const p = loadProject(path.resolve('project.json'), undefined);
const draw = await painter(p);
const times = [27.5, 30.5, 33.0, 38.0, 47.0, 55.0, 58.5, 62.0, 66.5, 78.0, 84.0, 87.5];
const cols = 4, cw = 270, ch = 480;
const canvas = createCanvas(cols * cw, Math.ceil(times.length / cols) * ch);
const ctx = canvas.getContext('2d');
ctx.fillStyle = '#ddd'; ctx.fillRect(0, 0, canvas.width, canvas.height);
for (let i = 0; i < times.length; i++) {
  const frame = draw(times[i]);
  ctx.drawImage(frame, (i % cols) * cw, Math.floor(i / cols) * ch, cw, ch);
}
fs.writeFileSync('stills2.png', canvas.toBuffer('image/png'));
console.log('ok');
