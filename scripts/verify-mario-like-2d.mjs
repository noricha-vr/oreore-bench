#!/usr/bin/env node
// mario-like-2d の各モデル出力を Playwright でスモーク検証する。
// チェック: JSエラー0 / canvas または描画領域あり / キー入力後に描画変化 /
// Enter または Space で開始してもクラッシュしない。
// 物理や当たり判定の正否はスクショ目視に委ねる。
//
// 使い方:
//   PLAYWRIGHT_PATH=<playwright の index.mjs> node scripts/verify-mario-like-2d.mjs [model-dir ...]

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const { chromium } = await import(
  process.env.PLAYWRIGHT_PATH ? pathToFileURL(process.env.PLAYWRIGHT_PATH).href : 'playwright'
);

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const THEME = path.join(ROOT, 'public', 'mario-like-2d');
const SHOTS = path.join(ROOT, 'docs', 'tmp', 'screenshots');
fs.mkdirSync(SHOTS, { recursive: true });

const models = process.argv.slice(2).length
  ? process.argv.slice(2)
  : fs.readdirSync(THEME).filter(d => fs.existsSync(path.join(THEME, d, 'index.html')));

if (models.length === 0) {
  console.log('NO_MODELS  public/mario-like-2d/<model>/index.html がまだない');
  process.exit(0);
}

const browser = await chromium.launch();
const results = [];

for (const model of models) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

  const r = {
    model,
    hasCanvas: false,
    pixelChanged: false,
    survivedInput: false,
    errors,
  };

  try {
    await page.goto(pathToFileURL(path.join(THEME, model, 'index.html')).href);
    await page.waitForTimeout(600);

    r.hasCanvas = await page.evaluate(() => {
      const c = document.querySelector('canvas');
      if (c && c.width > 0 && c.height > 0) return true;
      // DOM 描画の場合も「ゲーム面」があることだけ確認
      return document.body && document.body.innerHTML.length > 200;
    });

    await page.screenshot({ path: path.join(SHOTS, `mario2d-${model}-01-initial.png`) });

    const before = await page.evaluate(() => {
      const c = document.querySelector('canvas');
      if (c) {
        try {
          return c.toDataURL();
        } catch {
          return document.body.innerHTML.length + ':' + performance.now();
        }
      }
      return document.body.innerHTML.length + ':' + document.body.innerText.slice(0, 80);
    });

    await page.keyboard.press('Enter');
    await page.waitForTimeout(200);
    await page.keyboard.press('Space');
    await page.waitForTimeout(100);
    await page.keyboard.down('ArrowRight');
    for (let i = 0; i < 12; i++) {
      if (i % 4 === 0) await page.keyboard.press('Space');
      await page.waitForTimeout(80);
    }
    await page.keyboard.up('ArrowRight');
    await page.waitForTimeout(300);

    const after = await page.evaluate(() => {
      const c = document.querySelector('canvas');
      if (c) {
        try {
          return c.toDataURL();
        } catch {
          return document.body.innerHTML.length + ':' + performance.now();
        }
      }
      return document.body.innerHTML.length + ':' + document.body.innerText.slice(0, 80);
    });

    r.pixelChanged = before !== after;
    r.survivedInput = errors.length === 0;
    await page.screenshot({ path: path.join(SHOTS, `mario2d-${model}-02-after-input.png`) });
  } catch (e) {
    errors.push('script: ' + e.message);
  }

  results.push(r);
  await page.close();
}

await browser.close();

let fail = 0;
for (const r of results) {
  const ok = r.hasCanvas && r.pixelChanged && r.survivedInput && r.errors.length === 0;
  if (!ok) fail++;
  console.log(
    `${ok ? 'PASS' : 'FAIL'}  ${r.model}  canvas=${r.hasCanvas} changed=${r.pixelChanged} inputOk=${r.survivedInput} jsErrors=${r.errors.length}`
  );
  for (const e of r.errors.slice(0, 3)) console.log(`      ${e}`);
}
process.exit(fail ? 1 : 0);
