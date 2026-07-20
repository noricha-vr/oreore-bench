#!/usr/bin/env node
// phoenix-lp（不死鳥スクロール没入型 LP「HIBANA」）の各モデル出力を Playwright でスモーク検証する。
// チェック: ページロード成功 / canvas 要素の存在 / スクロールで描画が変化する（プログレスバー or シーン切替） /
// コンソールエラー 0（Google Fonts 読込失敗など外部リソース起因のエラーは JS エラーではないため許容）
//
// テーマは WebGL 不使用（Canvas 2D 縛り）なので --use-gl=swiftshader 系フラグは不要。
//
// 使い方:
//   PLAYWRIGHT_PATH=<playwright の index.mjs> node scripts/verify-phoenix-lp.mjs [model-dir ...]

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const { chromium } = await import(
  process.env.PLAYWRIGHT_PATH ? pathToFileURL(process.env.PLAYWRIGHT_PATH).href : 'playwright'
);

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const THEME = path.join(ROOT, 'public', 'phoenix-lp');
const SHOTS = path.join(ROOT, 'docs', 'tmp', 'screenshots');
fs.mkdirSync(SHOTS, { recursive: true });

if (!fs.existsSync(THEME)) {
  console.log('NO_THEME  public/phoenix-lp ディレクトリが存在しない');
  process.exit(0);
}

// 指定なしなら public/phoenix-lp/<model>/index.html を持つディレクトリ全部
// （PROMPT.md 等の非モデル成果物は index.html を持たないので自動的にスキップされる）
const explicitModels = process.argv.slice(2);
const allDirs = fs.readdirSync(THEME).filter(d => {
  const p = path.join(THEME, d);
  return fs.statSync(p).isDirectory();
});
const modelsWithOutput = allDirs.filter(d => fs.existsSync(path.join(THEME, d, 'index.html')));
const skipped = allDirs.filter(d => !fs.existsSync(path.join(THEME, d, 'index.html')));

for (const s of skipped) {
  console.log(`SKIP  ${s}  (index.html 未生成)`);
}

const models = explicitModels.length ? explicitModels : modelsWithOutput;

if (models.length === 0) {
  console.log('NO_MODELS  public/phoenix-lp/<model>/index.html がまだない');
  process.exit(0);
}

const browser = await chromium.launch();
const results = [];

function bufEqual(a, b) {
  if (!a || !b) return false;
  if (a.length !== b.length) return false;
  return Buffer.compare(a, b) === 0;
}

async function snapshot(page) {
  return page.screenshot({ fullPage: false });
}

for (const model of models) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

  const r = {
    model,
    loaded: false,
    hasCanvas: false,
    scrollChanged: false,
    errors,
  };

  try {
    const url = pathToFileURL(path.join(THEME, model, 'index.html')).href;
    await page.goto(url, { waitUntil: 'load' });
    // シーン入場アニメーションが動き出すまで少し待つ
    await page.waitForTimeout(800);
    r.loaded = true;

    r.hasCanvas = await page.evaluate(() => {
      const c = document.querySelector('canvas');
      return !!(c && c.width > 0 && c.height > 0);
    });

    await page.screenshot({ path: path.join(SHOTS, `phoenix-lp-${model}-01-initial.png`) });
    const initialShot = await snapshot(page);

    // スクロール駆動で 6 シーンが切り替わる仕様なので、
    // 総スクロール高の中程まで飛ばして描画が変わるかを見る。
    // lerp 平滑化があるので waitForTimeout を長めに取る。
    await page.evaluate(() => {
      const total = Math.max(
        document.body.scrollHeight,
        document.documentElement.scrollHeight
      );
      window.scrollTo(0, Math.floor(total * 0.5));
    });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: path.join(SHOTS, `phoenix-lp-${model}-02-mid.png`) });
    const midShot = await snapshot(page);

    // 終盤（Finale シーン）付近
    await page.evaluate(() => {
      const total = Math.max(
        document.body.scrollHeight,
        document.documentElement.scrollHeight
      );
      window.scrollTo(0, Math.floor(total * 0.9));
    });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: path.join(SHOTS, `phoenix-lp-${model}-03-late.png`) });
    const lateShot = await snapshot(page);

    // 初期 vs 中盤 vs 終盤のいずれかで差分があればシーン遷移が機能している判定
    r.scrollChanged = !bufEqual(initialShot, midShot) || !bufEqual(midShot, lateShot);
  } catch (e) {
    errors.push('script: ' + e.message);
  }

  results.push(r);
  await page.close();
}

await browser.close();

let fail = 0;
for (const r of results) {
  const ok = r.loaded && r.hasCanvas && r.scrollChanged && r.errors.length === 0;
  if (!ok) fail++;
  console.log(
    `${ok ? 'PASS' : 'FAIL'}  ${r.model}  loaded=${r.loaded} canvas=${r.hasCanvas} scrollChanged=${r.scrollChanged} jsErrors=${r.errors.length}`
  );
  for (const e of r.errors.slice(0, 3)) console.log(`      ${e}`);
}
process.exit(fail ? 1 : 0);
