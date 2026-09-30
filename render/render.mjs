// Offline renderer: drives index.html frame by frame in headless Chromium and pipes
// JPEG frames into ffmpeg. Usage: node render.mjs [out.mp4] [fps]
// Optional env: START / END (seconds of song time), AUDIO (file to mux, trimmed to the same window).
import { createRequire } from 'module';
import { spawn, execSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
const require = createRequire(import.meta.url);
// playwright from `npm install` here, or a global install
let chromium;
try { ({ chromium } = require('playwright')); } catch { ({ chromium } = require(execSync('npm root -g').toString().trim() + '/playwright')); }

const here = path.dirname(fileURLToPath(import.meta.url));
const out = process.argv[2] || path.join(here, 'style-test.mp4');
const fps = +(process.argv[3] || 30);
const ffmpeg = process.env.FFMPEG || 'ffmpeg';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto('file://' + path.join(here, 'index.html') + '?render');
await page.evaluate(() => window.READY);   // fonts + sprite images decoded before the first frame
const full = await page.evaluate(() => window.DURATION);
const t0 = +(process.env.START || 0), t1 = +(process.env.END || full), dur = t1 - t0;
const n = Math.ceil(dur * fps);
const audio = process.env.AUDIO ? ['-ss', String(t0), '-t', String(dur), '-i', process.env.AUDIO] : [];
const ff = spawn(ffmpeg, ['-y', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-', ...audio,
  ...(audio.length ? ['-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '256k', '-shortest'] : []),
  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', process.env.PRESET || 'medium', out], { stdio: ['pipe', 'ignore', 'inherit'] });
for (let i = 0; i < n; i++) {
  await page.evaluate(t => window.renderAt(t), t0 + i / fps);
  const buf = await page.screenshot({ type: 'jpeg', quality: 92 });
  if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  if (i % 60 === 0) process.stderr.write(`frame ${i}/${n}\n`);
}
ff.stdin.end();
await new Promise(r => ff.on('close', r));
await browser.close();
console.log('wrote', out, `${n} frames @ ${fps}fps (${dur.toFixed(1)}s)`);
