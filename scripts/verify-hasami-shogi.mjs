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

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const THEME = path.join(ROOT, 'public', 'hasami-shogi');
const SHOTS = path.join(ROOT, 'docs', 'tmp', 'screenshots');

// 葉要素のテキストで駒を数える（モデルごとの DOM 差異に依存しないため）
const PIECE_SNAPSHOT = `(() => {
  const leaves = [...document.querySelectorAll('body *')].filter(el =>
    el.children.length === 0 && (el.textContent.trim() === '歩' || el.textContent.trim() === 'と'));
  return leaves.map(el => {
    const r = el.getBoundingClientRect();
    return {
      t: el.textContent.trim(),
      x: Math.round(r.x + r.width / 2),
      y: Math.round(r.y + r.height / 2),
      w: Math.round(r.width),
    };
  }).filter(p => p.x > 0 && p.y > 0);
})()`;

export const median = xs => (xs.length ? [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)] : 0);

// 盤面グリッドの推定。盤外にも「歩」「と」の 1 文字表示（スコアボードのプレイヤーバッジ等）を
// 置くモデルがあり、テキストだけで数えると初期配置が過大になるため、座標で盤面内に絞る。
// class 名やタグに依存しないよう、等間隔に並ぶ最長の列群を盤面とみなし、
// 盤面の行に乗る駒がある列は間隔が乱れていても盤面に含める（除外による判定の甘さを防ぐ）。
// 推定した列数は cols として返し、9 列でなければ呼び出し側が FAIL 扱いにする。
export function boardArea(pieces) {
  if (pieces.length < 4) return null;
  const tol = Math.max(4, median(pieces.map(p => p.w)) * 0.5);

  // 近接する x をまとめて列にする（同じ列の駒は x がほぼ一致する）
  const cols = [];
  for (const x of pieces.map(p => p.x).sort((a, b) => a - b)) {
    if (!cols.length || x - cols[cols.length - 1] > tol) cols.push(x);
  }
  if (cols.length < 3) return null;

  const gaps = cols.slice(1).map((x, i) => x - cols[i]);
  const cell = median(gaps);
  if (cell <= 0) return null;

  // gap がセル幅と一致し続ける最長区間 = 盤面の列。外れた列（バッジ）はここで落ちる
  let best = [0, 0];
  let run = [0, 0];
  for (let i = 0; i < gaps.length; i++) {
    if (Math.abs(gaps[i] - cell) <= cell * 0.25) run[1] = i + 1;
    else run = [i + 1, i + 1];
    if (run[1] - run[0] > best[1] - best[0]) best = [...run];
  }
  let gridCols = cols.slice(best[0], best[1] + 1);
  if (gridCols.length < 3) return null;

  // 盤面の列に乗る駒のうち、複数駒が並ぶ行だけを盤面の行とみなす
  // （盤面の真上・真下に置かれた単独バッジで y 範囲が伸びるのを防ぐ）
  const onGrid = pieces.filter(p => gridCols.some(c => Math.abs(p.x - c) <= tol));
  const rows = [];
  for (const y of onGrid.map(p => p.y).sort((a, b) => a - b)) {
    if (!rows.length || y - rows[rows.length - 1].y > tol) rows.push({ y, n: 1 });
    else rows[rows.length - 1].n++;
  }
  const ys = rows.filter(r => r.n >= 2).map(r => r.y);
  if (!ys.length) return null;

  // 盤面の行に乗る駒は、列間隔が等間隔から外れていても盤上の駒として扱う。
  // 配置を誤るモデルほど列間隔も一緒にずれるため、ここで拾わないと過剰な駒が盤外へ
  // 再分類されて枚数チェックが素通りする（列数が 9 から外れることで FAIL に落ちる）。
  // 盤の行と y が合わないバッジ（スコアボード等）はこの条件を満たさず従来どおり除外される。
  const onBoardRow = c =>
    pieces.some(p => Math.abs(p.x - c) <= tol && ys.some(y => Math.abs(p.y - y) <= tol));
  const strayCols = cols.filter(c => !gridCols.includes(c) && onBoardRow(c));
  if (strayCols.length) gridCols = [...gridCols, ...strayCols].sort((a, b) => a - b);

  const margin = cell * 0.6;
  return {
    xMin: gridCols[0] - margin,
    xMax: gridCols[gridCols.length - 1] + margin,
    yMin: Math.min(...ys) - margin,
    yMax: Math.max(...ys) + margin,
    cols: gridCols.length,
  };
}

// 盤面矩形は初期配置から一度だけ求め、移動後のスナップショットにも同じ矩形を使う
// （移動で駒が単独の行に来ても盤上の駒として拾えるようにするため）
export const inArea = (pieces, area) =>
  area
    ? pieces.filter(p => p.x >= area.xMin && p.x <= area.xMax && p.y >= area.yMin && p.y <= area.yMax)
    : pieces;

// 駒スナップショットから盤面の枚数・推定列数・盤外扱いで落とした枚数を求める
export function countBoard(snapshot) {
  const area = boardArea(snapshot);
  const on = inArea(snapshot, area);
  return {
    grid: area ? 'ok' : 'none', // none = 盤面推定が成立せず全件素通し
    gridCols: area ? area.cols : 0,
    excluded: snapshot.length - on.length,
    fu: on.filter(p => p.t === '歩').length,
    to: on.filter(p => p.t === 'と').length,
  };
}

// 機械判定の PASS 条件。9x9 が仕様なので、推定列数が 9 でなければ盤面推定が信用できず、
// 過剰な駒が盤外扱いで消えている可能性があるため FAIL にして目視送りにする。
export const passed = r =>
  r.fu === 9 && r.to === 9 && r.gridCols === 9
  && r.highlight && r.playerMoved && r.cpuMoved && r.errors.length === 0;

async function verifyModel(browser, model) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 960 } });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

  const r = {
    model, fu: 0, to: 0, grid: 'none', gridCols: 0, excluded: 0,
    highlight: false, playerMoved: false, cpuMoved: false, errors,
  };
  try {
    await page.goto(pathToFileURL(path.join(THEME, model, 'index.html')).href);
    await page.waitForTimeout(800);

    const snapshot = await page.evaluate(PIECE_SNAPSHOT);
    const area = boardArea(snapshot);
    const before = inArea(snapshot, area);
    Object.assign(r, countBoard(snapshot));
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

      const after = inArea(await page.evaluate(PIECE_SNAPSHOT), area);
      const key = p => `${p.t}:${p.x},${p.y}`;
      const beforeSet = new Set(before.map(key));
      r.playerMoved = after.some(p => p.t === '歩' && !beforeSet.has(key(p)));
      r.cpuMoved = after.some(p => p.t === 'と' && !beforeSet.has(key(p)));
      await page.screenshot({ path: path.join(SHOTS, `hasami-${model}-03-after-move.png`) });
    }
  } catch (e) {
    errors.push('script: ' + e.message);
  }
  await page.close();
  return r;
}

async function main() {
  const { chromium } = await import(
    process.env.PLAYWRIGHT_PATH ? pathToFileURL(process.env.PLAYWRIGHT_PATH).href : 'playwright'
  );
  fs.mkdirSync(SHOTS, { recursive: true });

  const models = process.argv.slice(2).length
    ? process.argv.slice(2)
    : fs.readdirSync(THEME).filter(d => fs.existsSync(path.join(THEME, d, 'index.html')));

  const browser = await chromium.launch();
  const results = [];
  for (const model of models) results.push(await verifyModel(browser, model));
  await browser.close();

  let fail = 0;
  for (const r of results) {
    const ok = passed(r);
    if (!ok) fail++;
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${r.model}  歩=${r.fu} と=${r.to} grid=${r.grid} cols=${r.gridCols} excluded=${r.excluded} highlight=${r.highlight} player=${r.playerMoved} cpu=${r.cpuMoved} jsErrors=${r.errors.length}`);
    for (const e of r.errors.slice(0, 3)) console.log(`      ${e}`);
  }
  process.exit(fail ? 1 : 0);
}

// テストから盤面グリッド判定だけを import できるよう、直接実行時のみブラウザを起動する。
// symlink 経由の起動でも実行されるよう、両辺を realpath に正規化してから比較する
// （文字列一致だけだと symlink 起動時に何もせず exit 0 する「何もしていない成功」になる）。
const realHref = p => {
  try { return pathToFileURL(fs.realpathSync(p)).href; } catch { return null; }
};
if (process.argv[1] && realHref(process.argv[1]) === realHref(fileURLToPath(import.meta.url))) await main();
