#!/usr/bin/env node
// roguelike の各モデル出力を Playwright でスモーク検証する。
// チェック: JSエラー0 / canvas または描画領域あり / Enter/Space 開始でクラッシュしない /
// 矢印キーで描画が変化する / 矢印キー 40 回連打でクラッシュしない / リロードでマップが変わる。
// 戦闘・FOV・階段挙動の正否はスクショ目視に委ねる。
//
// 使い方:
//   PLAYWRIGHT_PATH=<playwright の index.mjs> node scripts/verify-roguelike.mjs [model-dir ...]

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const { chromium } = await import(
  process.env.PLAYWRIGHT_PATH ? pathToFileURL(process.env.PLAYWRIGHT_PATH).href : 'playwright'
);

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const THEME = path.join(ROOT, 'public', 'roguelike');
const SHOTS = path.join(ROOT, 'docs', 'tmp', 'screenshots');
fs.mkdirSync(SHOTS, { recursive: true });

const models = process.argv.slice(2).length
  ? process.argv.slice(2)
  : fs.readdirSync(THEME).filter(d => fs.existsSync(path.join(THEME, d, 'index.html')));

if (models.length === 0) {
  console.log('NO_MODELS  public/roguelike/<model>/index.html がまだない');
  process.exit(0);
}

const browser = await chromium.launch();
const results = [];

const ARROW_KEYS = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];

async function snapshot(page) {
  // ビューポートのスクショ PNG バイト列。canvas / DOM 描画のどちらでも同じ土俵で差分比較できる
  return page.screenshot({ fullPage: false });
}

async function pressStart(page) {
  // タイトル画面の有無がモデル依存なので Enter / Space の両方を送る（両タイミングとも同一シーケンスで撮る前提）
  await page.keyboard.press('Enter');
  await page.waitForTimeout(150);
  await page.keyboard.press('Space');
  await page.waitForTimeout(200);
}

function bufEqual(a, b) {
  if (!a || !b) return false;
  if (a.length !== b.length) return false;
  return Buffer.compare(a, b) === 0;
}

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
    mapChanged: false,
    errors,
  };

  try {
    const url = pathToFileURL(path.join(THEME, model, 'index.html')).href;
    await page.goto(url);
    await page.waitForTimeout(600);

    r.hasCanvas = await page.evaluate(() => {
      const c = document.querySelector('canvas');
      if (c && c.width > 0 && c.height > 0) return true;
      return document.body && document.body.innerHTML.length > 200;
    });

    await page.screenshot({ path: path.join(SHOTS, `roguelike-${model}-01-initial.png`) });

    // 開始
    await pressStart(page);
    await page.screenshot({ path: path.join(SHOTS, `roguelike-${model}-02-after-start.png`) });
    const afterStartShot = await snapshot(page);

    // 矢印キー入力で描画が変化するか、1 手ごとに差分を見る
    // （固定シーケンス一括比較だと右→下→左→上の閉ループで元の位置・同一フレームに戻り偽 FAIL になる）
    let prevShot = afterStartShot;
    for (const key of ARROW_KEYS) {
      await page.keyboard.press(key);
      await page.waitForTimeout(150);
      const shot = await snapshot(page);
      if (!bufEqual(prevShot, shot)) { r.pixelChanged = true; break; }
      prevShot = shot;
    }

    // 40 回ランダム連打（ターン制の連続動作でクラッシュしないか）
    // survivedInput は連打フェーズ中の新規エラーだけで判定する（ロード時エラーは jsErrors 側で見える）
    const errorsBeforeMash = errors.length;
    for (let i = 0; i < 40; i++) {
      const key = ARROW_KEYS[Math.floor(Math.random() * ARROW_KEYS.length)];
      await page.keyboard.press(key);
      await page.waitForTimeout(60);
    }
    await page.screenshot({ path: path.join(SHOTS, `roguelike-${model}-03-after-moves.png`) });

    r.survivedInput = errors.length === errorsBeforeMash;

    // マップのランダム性: リロード + 開始キー後のスクショが1回目の同時点と変わるか
    // （タイトル画面が静的なゲームでも偽陰性にならないよう、開始後の画面同士で比較する）
    await page.goto(url);
    await page.waitForTimeout(600);
    await pressStart(page);
    await page.screenshot({ path: path.join(SHOTS, `roguelike-${model}-04-after-reload.png`) });
    const reloadShot = await snapshot(page);
    r.mapChanged = !bufEqual(afterStartShot, reloadShot);
  } catch (e) {
    errors.push('script: ' + e.message);
  }

  results.push(r);
  await page.close();
}

await browser.close();

let fail = 0;
for (const r of results) {
  const ok = r.hasCanvas && r.pixelChanged && r.survivedInput && r.mapChanged && r.errors.length === 0;
  if (!ok) fail++;
  console.log(
    `${ok ? 'PASS' : 'FAIL'}  ${r.model}  canvas=${r.hasCanvas} moved=${r.pixelChanged} inputOk=${r.survivedInput} mapChanged=${r.mapChanged} jsErrors=${r.errors.length}`
  );
  for (const e of r.errors.slice(0, 3)) console.log(`      ${e}`);
}
process.exit(fail ? 1 : 0);
