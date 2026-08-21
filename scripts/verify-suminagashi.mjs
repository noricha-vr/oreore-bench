#!/usr/bin/env node
// suminagashi（WebGL 流体マーブリング）の各モデル出力を Playwright でスモーク検証する。
// チェック: ページロード成功 / canvas 要素の存在 / WebGL2 コンテキスト取得 /
// 描画ピクセルが初期状態から変化する / コンソール JS エラー 0
//
// headless chromium は既定で WebGL を無効化するため --enable-unsafe-swiftshader が必須。
// フラグなしだと「WebGL2 が必要です」のフォールバックが出て、モデル出力の失敗と誤判定する。
//
// 使い方:
//   PLAYWRIGHT_PATH=<playwright の index.mjs> node scripts/verify-suminagashi.mjs [model-dir ...]

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const { chromium } = await import(
  process.env.PLAYWRIGHT_PATH ? pathToFileURL(process.env.PLAYWRIGHT_PATH).href : 'playwright'
);

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const THEME = path.join(ROOT, 'public', 'suminagashi');
const SHOTS = path.join(ROOT, 'docs', 'tmp', 'screenshots');
fs.mkdirSync(SHOTS, { recursive: true });

if (!fs.existsSync(THEME)) {
  console.log('NO_THEME  public/suminagashi ディレクトリが存在しない');
  process.exit(0);
}

const explicitModels = process.argv.slice(2);
const models = (explicitModels.length ? explicitModels : fs.readdirSync(THEME)).filter((name) =>
  fs.existsSync(path.join(THEME, name, 'index.html')),
);

const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader'] });
let failed = 0;

for (const model of models) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const jsErrors = [];
  page.on('pageerror', (e) => jsErrors.push(String(e)));

  let loaded = false;
  let canvas = false;
  let webgl2 = false;
  let painted = false;
  try {
    await page.goto(pathToFileURL(path.join(THEME, model, 'index.html')).href, {
      waitUntil: 'load',
      timeout: 30000,
    });
    loaded = true;
    canvas = (await page.locator('canvas').count()) > 0;

    if (canvas) {
      webgl2 = await page.evaluate(() => {
        const el = document.querySelector('canvas');
        return Boolean(el && (el.getContext('webgl2') || el.__ctx));
      });
      // 初回描画を待つ。流体シミュレーションは自走するので待つだけで絵が出る。
      await page.waitForTimeout(2500);
      // WebGL canvas は preserveDrawingBuffer:false だと drawImage で読めず、
      // 正常な出力まで空判定になる（実測: 全モデルが painted=false）。
      // 代わりに canvas 領域のスクリーンショットを撮り、PNG が単色でないことで判定する。
      const shot = await page.locator('canvas').first().screenshot();
      painted = shot.length > 12000;
    }
    await page.screenshot({ path: path.join(SHOTS, `suminagashi-${model}.png`) });
  } catch (e) {
    jsErrors.push(String(e));
  }

  const ok = loaded && canvas && webgl2 && painted && jsErrors.length === 0;
  if (!ok) failed += 1;
  console.log(
    `${ok ? 'PASS' : 'FAIL'}  ${model}  loaded=${loaded} canvas=${canvas} webgl2=${webgl2} ` +
      `painted=${painted} jsErrors=${jsErrors.length}`,
  );
  if (jsErrors.length) console.log(`      ${jsErrors[0].slice(0, 160)}`);
  await page.close();
}

await browser.close();
process.exit(failed ? 1 : 0);
