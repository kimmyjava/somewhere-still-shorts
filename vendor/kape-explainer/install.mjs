// Install KAPE Explainer as plain Claude Code skills (no plugin): copies skills/kape-explainer and skills/spatial-film
// side by side into ~/.claude/skills, then runs the setup check. Run it again to update - your profile lives in
// ~/.kape-explainer and is never touched.
// Usage: node install.mjs [--dest <skills dir>] [--force]
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flag = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };
const dest = path.resolve(flag('--dest') || path.join(os.homedir(), '.claude', 'skills'));
const force = args.includes('--force');
const SKILLS = ['kape-explainer', 'spatial-film'];
const MARK = '.kape-explainer-install';  // marks folders this installer wrote, so an update never clobbers someone else's skill

fs.mkdirSync(dest, { recursive: true });
for (const s of SKILLS) {
  const to = path.join(dest, s);
  if (fs.existsSync(to) && !fs.existsSync(path.join(to, MARK)) && !force) {
    console.error(`${to} already exists and was not installed by this script.\n` +
      `Move it aside, or re-run with --force to replace it.`);
    process.exit(1);
  }
}
for (const s of SKILLS) {
  const from = path.join(HERE, 'skills', s);
  const to = path.join(dest, s);
  if (!fs.existsSync(from)) { console.error(`missing ${from} - run this from the unzipped/cloned folder`); process.exit(1); }
  fs.rmSync(to, { recursive: true, force: true });
  fs.cpSync(from, to, { recursive: true, filter: (p) => !p.includes('__pycache__') });
  fs.writeFileSync(path.join(to, MARK), new Date().toISOString() + '\n');
  console.log(`installed ${to}`);
}
console.log('\nchecking your machine...\n');
try {
  execFileSync(process.execPath, [path.join(dest, 'kape-explainer', 'scripts', 'setup-check.mjs')], { stdio: 'inherit' });
  console.log('\nDone. Restart Claude Code, then say: make a kape explainer about <your topic>');
} catch {
  console.log('\nSkills installed. Install what the check lists as MISSING, then restart Claude Code.');
}
