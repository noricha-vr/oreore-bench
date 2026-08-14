// 盤面グリッド判定（boardArea / inArea / countBoard / passed）のテスト。
// 実行: node --test tests/verify-hasami-shogi-grid.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';

import { boardArea, countBoard, inArea, passed } from '../scripts/verify-hasami-shogi.mjs';

const CELL = 71;
const X0 = 185;
const TOP = 238;
const BOTTOM = TOP + CELL * 8;

// 9x9 盤の初期配置（上端に と 9 枚・下端に 歩 9 枚）
function board(cols = 9) {
  const pieces = [];
  for (let i = 0; i < cols; i++) {
    pieces.push({ t: 'と', x: X0 + CELL * i, y: TOP, w: 54 });
    pieces.push({ t: '歩', x: X0 + CELL * i, y: BOTTOM, w: 54 });
  }
  return pieces;
}

const count = (pieces, t) => pieces.filter(p => p.t === t).length;

// 盤面以外の PASS 条件（操作系・JS エラー）は満たしている前提の結果を作る
const result = snapshot => ({
  ...countBoard(snapshot),
  highlight: true,
  playerMoved: true,
  cpuMoved: true,
  errors: [],
});

test('盤外の 1 文字バッジを駒として数えない', () => {
  // qwen3-8-27b 相当: 盤の右側にプレイヤー表示の 歩 / と バッジがある
  const pieces = [
    ...board(),
    { t: '歩', x: 868, y: 182, w: 30 },
    { t: 'と', x: 868, y: 314, w: 30 },
  ];
  const kept = inArea(pieces, boardArea(pieces));
  assert.equal(count(kept, '歩'), 9);
  assert.equal(count(kept, 'と'), 9);

  const r = result(pieces);
  assert.equal(r.gridCols, 9);
  assert.equal(r.excluded, 2); // 盤外扱いで落とした枚数が結果に出る
  assert.equal(r.grid, 'ok');
  assert.ok(passed(r), '正しい 9x9 盤 + 盤外バッジは PASS のまま');
});

test('盤面の列の真上に置かれたバッジも除外する', () => {
  const pieces = [
    ...board(),
    { t: 'と', x: X0 + CELL * 2, y: TOP - CELL * 3, w: 30 },
  ];
  const kept = inArea(pieces, boardArea(pieces));
  assert.equal(count(kept, 'と'), 9);
  assert.equal(count(kept, '歩'), 9); // 歩 は巻き込まれない
  assert.equal(boardArea(pieces).cols, 9);
});

test('盤面グリッド上に本当に 10 枚あれば 10 枚と数える', () => {
  // 判定を甘くしていないことの確認: 等間隔で 10 列並んでいれば盤面として扱う
  const pieces = board(10);
  const kept = inArea(pieces, boardArea(pieces));
  assert.equal(count(kept, '歩'), 10);
  assert.equal(count(kept, 'と'), 10);
  assert.equal(boardArea(pieces).cols, 10);
  assert.ok(!passed(result(pieces)), '10 列盤は PASS にならない');
});

test('列間隔が乱れていても盤上の 10 枚目を落とさない', () => {
  // 末尾の列だけ 1.5 セル離れた 10 列盤。等間隔の最長区間だけを盤面にすると
  // この列が盤外扱いになり 歩=9 で false PASS になっていた
  const stray = X0 + CELL * 9.5;
  const pieces = [
    ...board(),
    { t: 'と', x: stray, y: TOP, w: 54 },
    { t: '歩', x: stray, y: BOTTOM, w: 54 },
  ];
  const r = result(pieces);
  assert.equal(r.fu, 10);
  assert.equal(r.to, 10);
  assert.equal(r.gridCols, 10);
  assert.equal(r.excluded, 0);
  assert.ok(!passed(r), '盤上に 10 枚あるので PASS にならない');
});

test('9 列 + 離れた位置の 10 枚目も盤上として数える', () => {
  // 下段の右端からさらに 1.5 セル離れた 10 枚目。盤の行に乗っているので盤上扱いにする
  const pieces = [...board(), { t: '歩', x: X0 + CELL * 9.5, y: BOTTOM, w: 54 }];
  const r = result(pieces);
  assert.equal(r.fu, 10);
  assert.equal(r.gridCols, 10);
  assert.ok(!passed(r), '歩 10 枚は PASS にならない');
});

test('列内に駒が重複していれば過剰分も数える', () => {
  const pieces = [...board(), { t: '歩', x: X0 + CELL * 3, y: BOTTOM - CELL, w: 54 }];
  const kept = inArea(pieces, boardArea(pieces));
  assert.equal(count(kept, '歩'), 10);
  assert.ok(!passed(result(pieces)));
});

test('駒が足りなければ足りない枚数を返す', () => {
  const pieces = board().filter(p => !(p.t === '歩' && p.x === X0 + CELL * 4));
  const r = result(pieces);
  assert.equal(r.fu, 8);
  assert.equal(r.to, 9);
  assert.equal(r.gridCols, 9);
  assert.ok(!passed(r), '歩 8 枚は PASS にならない');
});

test('盤内へ移動した駒は単独行でも盤上として拾う', () => {
  const initial = [
    ...board(),
    { t: '歩', x: 868, y: 182, w: 30 },
    { t: 'と', x: 868, y: 314, w: 30 },
  ];
  const area = boardArea(initial);
  // 歩 1 枚が 3 マス前進し、その行にはその駒しかいない状態
  const moved = [
    ...inArea(initial, area).filter(p => !(p.t === '歩' && p.x === X0 + CELL * 4)),
    { t: '歩', x: X0 + CELL * 4, y: BOTTOM - CELL * 3, w: 54 },
    { t: '歩', x: 868, y: 182, w: 30 },
    { t: 'と', x: 868, y: 314, w: 30 },
  ];
  const kept = inArea(moved, area);
  assert.equal(count(kept, '歩'), 9);
  assert.ok(kept.some(p => p.t === '歩' && p.y === BOTTOM - CELL * 3));
});

test('駒が取れないページでは矩形を作らず全件をそのまま返す', () => {
  assert.equal(boardArea([]), null);
  // フォールバック時は入力をそのまま返す（空配列だと「常に空を返す」実装でも通るため非空で固定）
  const pieces = [{ t: '歩', x: 10, y: 20, w: 30 }, { t: 'と', x: 40, y: 50, w: 30 }];
  assert.deepEqual(inArea(pieces, null), pieces);

  const r = countBoard(pieces);
  assert.equal(r.grid, 'none');
  assert.equal(r.gridCols, 0);
  assert.equal(r.excluded, 0);
  assert.ok(!passed({ ...r, highlight: true, playerMoved: true, cpuMoved: true, errors: [] }),
    'グリッド推定が成立しないページは PASS にならない');
});
