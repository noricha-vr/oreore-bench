#!/usr/bin/env node
// hasami-shogi の各モデル出力を Playwright でスモーク検証する。
// 初期配置(歩9/と9)・駒選択→ハイライト→移動→CPU応答・JSエラーを機械チェックし、
// 挟み取り等のルール細部は撮影したスクリーンショットの目視確認に委ねる。
//
// 使い方:
//   PLAYWRIGHT_PATH=<playwright の index.mjs> node scripts/verify-hasami-shogi.mjs [model-dir ...]
// PLAYWRIGHT_PATH 未指定時は通常の 'playwright' 解決を試みる。

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const { chromium } = await import(
  process.env.PLAYWRIGHT_PATH ? pathToFileURL(process.env.PLAYWRIGHT_PATH).href : 'playwright'
);

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const THEME = path.join(ROOT, 'public', 'hasami-shogi');
const SHOTS = path.join(ROOT, 'docs', 'tmp', 'screenshots');
fs.mkdirSync(SHOTS, { recursive: true });

const models = process.argv.slice(2).length
  ? process.argv.slice(2)
  : fs.readdirSync(THEME).filter(d => fs.existsSync(path.join(THEME, d, 'index.html')));

// 葉要素のテキストで駒を数える（モデルごとの DOM 差異に依存しないため）
const PIECE_SNAPSHOT = `(() => {
  const leaves = [...document.querySelectorAll('body *')].filter(el =>
    el.children.length === 0 && (el.textContent.trim() === '歩' || el.textContent.trim() === 'と'));
  return leaves.map(el => {
    const r = el.getBoundingClientRect();
    return { t: el.textContent.trim(), x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
  }).filter(p => p.x > 0 && p.y > 0);
})()`;

const browser = await chromium.launch();
const results = [];

for (const model of models) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 960 } });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

  const r = { model, fu: 0, to: 0, highlight: false, playerMoved: false, cpuMoved: false, errors };
  try {
    await page.goto(pathToFileURL(path.join(THEME, model, 'index.html')).href);
    await page.waitForTimeout(800);

    const before = await page.evaluate(PIECE_SNAPSHOT);
    r.fu = before.filter(p => p.t === '歩').length;
    r.to = before.filter(p => p.t === 'と').length;
    await page.screenshot({ path: path.join(SHOTS, `hasami-${model}-01-initial.png`) });

    // 中央付近の歩を選択 → ハイライト検出 → 3マス上へ移動
    const pawns = before.filter(p => p.t === '歩').sort((a, b) => a.x - b.x);
    const pawn = pawns[Math.floor(pawns.length / 2)];
    const cell = pawns.length > 1 ? pawns[1].x - pawns[0].x : 48; // 隣接歩の間隔 = マスサイズ
    if (pawn) {
      const domBefore = await page.evaluate(() => document.body.innerHTML.length);
      await page.mouse.click(pawn.x, pawn.y);
      await page.waitForTimeout(400);
      // 選択で DOM/クラスが変化したか（ハイライトのヒューリスティック）
      const domAfter = await page.evaluate(() => document.body.innerHTML.length);
      r.highlight = domAfter !== domBefore;
      await page.screenshot({ path: path.join(SHOTS, `hasami-${model}-02-selected.png`) });

      await page.mouse.click(pawn.x, pawn.y - cell * 3);
      await page.waitForTimeout(2500); // CPU 応答待ち

      const after = await page.evaluate(PIECE_SNAPSHOT);
      const key = p => `${p.t}:${p.x},${p.y}`;
      const beforeSet = new Set(before.map(key));
      r.playerMoved = after.some(p => p.t === '歩' && !beforeSet.has(key(p)));
      r.cpuMoved = after.some(p => p.t === 'と' && !beforeSet.has(key(p)));
      await page.screenshot({ path: path.join(SHOTS, `hasami-${model}-03-after-move.png`) });
    }
  } catch (e) {
    errors.push('script: ' + e.message);
  }
  results.push(r);
  await page.close();
}

await browser.close();

let fail = 0;
for (const r of results) {
  const ok = r.fu === 9 && r.to === 9 && r.highlight && r.playerMoved && r.cpuMoved && r.errors.length === 0;
  if (!ok) fail++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${r.model}  歩=${r.fu} と=${r.to} highlight=${r.highlight} player=${r.playerMoved} cpu=${r.cpuMoved} jsErrors=${r.errors.length}`);
  for (const e of r.errors.slice(0, 3)) console.log(`      ${e}`);
}
process.exit(fail ? 1 : 0);
