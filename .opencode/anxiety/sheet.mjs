import fs from 'node:fs';
import path from 'node:path';
import {createCanvas, loadImage} from '@napi-rs/canvas';
const names = ['hero-lying','hero-lying-shock','hero-sit-phone','guard-panic','hero-overthink','hero-chest','hero-explain','hero-breathe','hero-point','monster-question','audience-laughing','alarm-panel'];
const cols = 4, rows = 3, cw = 300, ch = 533;
const canvas = createCanvas(cols*cw, rows*ch);
const ctx = canvas.getContext('2d');
ctx.fillStyle = '#FDFDFC'; ctx.fillRect(0,0,canvas.width,canvas.height);
for (let i = 0; i < names.length; i++) {
  const img = await loadImage(path.resolve('assets', names[i] + '.png'));
  const x = (i % cols) * cw, y = Math.floor(i / cols) * ch;
  ctx.drawImage(img, x, y, cw, ch);
  ctx.strokeStyle = '#ccc'; ctx.strokeRect(x+.5, y+.5, cw-1, ch-1);
}
fs.writeFileSync('contact-sheet.png', canvas.toBuffer('image/png'));
console.log('written');
