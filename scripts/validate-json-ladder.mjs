#!/usr/bin/env node
// public/json-ladder/<model>/output.json を読んで meta.json を生成する。
// レベル別 JSON をパース可否 → answer-key 突合の 2 段階で採点する。

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

const args = process.argv.slice(2);
function argValue(name, fallback) {
  const i = args.indexOf(name);
  if (i >= 0 && args[i + 1]) return args[i + 1];
  const eq = args.find(a => a.startsWith(`${name}=`));
  return eq ? eq.slice(name.length + 1) : fallback;
}

const THEME_DIR = path.resolve(argValue('--theme-dir', path.join(ROOT, 'public', 'json-ladder')));
const ANSWER_KEY_PATH = path.resolve(argValue('--answer-key', path.join(THEME_DIR, 'answer-key.json')));
const MODEL_FILTER = argValue('--model', null);
const EXPECTED_LEVELS = [1, 2, 3, 4, 5];
// 設問・本文の置き場であってモデル出力ではないため、走査対象から外す
const NON_MODEL_DIRS = new Set(['levels']);

// scripts/validate-pr-triage.mjs から逐語コピー（フェンス優先・壊れたフェンスは raw 再フォールバックしないポリシーを共有する）
function tryParseJson(raw) {
  const trimmed = raw.trim();
  // Prefer fenced JSON so braces in preamble examples do not become parse anchors.
  const fence = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
  let s = fence ? fence[1].trim() : trimmed;
  if (!fence) {
    const first = s.indexOf('{');
    const last = s.lastIndexOf('}');
    if (first >= 0 && last > first) s = s.slice(first, last + 1);
  }
  try { return JSON.parse(s); } catch {
    // 壊れたフェンスで raw に再フォールバックするとモデルの不正ペイロードを隠すため、
    // フェンスがある場合はパース失敗で確定させる
    if (fence) return null;
    try { return JSON.parse(raw); } catch { return null; }
  }
}

const ZERO_WIDTH_RE = /[​‌‍﻿]/g;

function normalizeString(value, mode) {
  if (mode === 'exact') return value.trim();
  return value
    .normalize('NFKC')
    .trim()
    .replace(ZERO_WIDTH_RE, '')
    .replace(/\s+/g, ' ')
    .replace(/，/g, '、')
    .replace(/．/g, '。');
}

// dot + [i] の JSON-path-lite。キーに日本語を含むため、区切り文字だけを見て素直に分割する。
function parsePath(pathStr) {
  const tokens = [];
  let buf = '';
  for (let i = 0; i < pathStr.length; i++) {
    const ch = pathStr[i];
    if (ch === '.') {
      if (buf) tokens.push({ type: 'key', value: buf });
      buf = '';
    } else if (ch === '[') {
      if (buf) tokens.push({ type: 'key', value: buf });
      buf = '';
      const close = pathStr.indexOf(']', i);
      if (close < 0) throw new Error(`unterminated [ in path: ${pathStr}`);
      tokens.push({ type: 'index', value: Number(pathStr.slice(i + 1, close)) });
      i = close;
    } else {
      buf += ch;
    }
  }
  if (buf) tokens.push({ type: 'key', value: buf });
  return tokens;
}

// answer-key の path 集合から「許可キーツリー」を作る。
// node = { keys: Map<string, node>, item: node|null }
//   keys: オブジェクトとして許可されるキー
//   item: 配列要素の許可ツリー（全インデックスの和集合。要素ごとの差は array_length 採点の領分）
function newAllowNode() {
  return { keys: new Map(), item: null };
}

function buildAllowTree(fields) {
  const root = newAllowNode();
  for (const field of fields) {
    let cur = root;
    for (const token of parsePath(field.path)) {
      if (token.type === 'index') {
        if (!cur.item) cur.item = newAllowNode();
        cur = cur.item;
      } else {
        if (!cur.keys.has(token.value)) cur.keys.set(token.value, newAllowNode());
        cur = cur.keys.get(token.value);
      }
    }
  }
  return root;
}

function joinPath(prefix, key) {
  return prefix ? `${prefix}.${key}` : key;
}

// 許可ツリーに無いオブジェクトキーを extra-key として列挙する。
// 配列の余剰要素は array_length 採点でカバー済みなので、ここでは扱わない。
function collectExtraKeys(value, node, prefix, issues) {
  if (value === null || typeof value !== 'object') return;

  if (Array.isArray(value)) {
    if (!node.item) return;
    value.forEach((item, i) => collectExtraKeys(item, node.item, `${prefix}[${i}]`, issues));
    return;
  }

  // 子が未定義のノード（採点対象がスカラーの葉）は構造を規定しないので踏み込まない。
  // 型違いは evaluateField の type-error 側で報告される。
  if (node.keys.size === 0) return;

  for (const key of Object.keys(value)) {
    const child = node.keys.get(key);
    if (!child) {
      issues.push(`extra-key: ${joinPath(prefix, key)}`);
      continue;
    }
    collectExtraKeys(value[key], child, joinPath(prefix, key), issues);
  }
}

const MISSING = Symbol('missing');

function resolvePath(root, pathStr) {
  let cur = root;
  for (const token of parsePath(pathStr)) {
    if (cur === null || cur === undefined) return MISSING;
    if (token.type === 'index') {
      if (!Array.isArray(cur) || token.value >= cur.length) return MISSING;
      cur = cur[token.value];
    } else {
      if (typeof cur !== 'object' || Array.isArray(cur) || !(token.value in cur)) return MISSING;
      cur = cur[token.value];
    }
  }
  return cur;
}

// got は verdicts にそのまま載せるので、JSON に出せる形に落とす（未定義は null 化）
function forRecord(value) {
  if (value === MISSING || value === undefined) return null;
  return value;
}

function evaluateField(field, root) {
  const value = resolvePath(root, field.path);
  const type = field.type;
  const record = { path: field.path, got: forRecord(value), expected: field.expected ?? null };

  if (value === MISSING) {
    return { ...record, match: 'miss', issue: `missing: ${field.path}` };
  }

  if (type === 'array_length') {
    if (!Array.isArray(value)) {
      return { ...record, got: forRecord(value), match: 'miss', issue: `type-error: ${field.path}` };
    }
    const len = value.length;
    return { ...record, got: len, match: len === field.expected ? 'primary' : 'miss' };
  }

  if (type === 'integer') {
    if (!Number.isInteger(value)) {
      return { ...record, match: 'miss', issue: `type-error: ${field.path}` };
    }
    if (value === field.expected) return { ...record, match: 'primary' };
    const also = Array.isArray(field.also_acceptable) ? field.also_acceptable : [];
    if (also.some(a => a === value)) return { ...record, match: 'acceptable' };
    return { ...record, match: 'miss' };
  }

  if (type === 'boolean') {
    if (typeof value !== 'boolean') {
      return { ...record, match: 'miss', issue: `type-error: ${field.path}` };
    }
    return { ...record, match: value === field.expected ? 'primary' : 'miss' };
  }

  if (type === 'null') {
    if (value !== null) {
      return { ...record, match: 'miss', issue: `type-error: ${field.path}` };
    }
    return { ...record, match: 'primary' };
  }

  if (type === 'string') {
    if (typeof value !== 'string') {
      return { ...record, match: 'miss', issue: `type-error: ${field.path}` };
    }
    const mode = field.normalize ?? 'default';
    const got = normalizeString(value, mode);
    if (typeof field.expected === 'string' && got === normalizeString(field.expected, mode)) {
      return { ...record, match: 'primary' };
    }
    const also = Array.isArray(field.also_acceptable) ? field.also_acceptable : [];
    if (also.some(a => typeof a === 'string' && got === normalizeString(a, mode))) {
      return { ...record, match: 'acceptable' };
    }
    return { ...record, match: 'miss' };
  }

  return { ...record, match: 'miss', issue: `unknown field type: ${type} (${field.path})` };
}

function scoreLevel(fields, root) {
  const verdicts = [];
  const issues = [];
  let primary = 0;
  let acceptable = 0;

  for (const field of fields) {
    const { issue, ...verdict } = evaluateField(field, root);
    if (issue) issues.push(issue);
    if (verdict.match === 'primary') primary++;
    else if (verdict.match === 'acceptable') acceptable++;
    verdicts.push(verdict);
  }

  // PROMPT.md が「キーの追加・省略・改名は不可」を課しているので、未定義キーもスキーマ違反として扱う。
  // ただし accuracy_pct（一致率）には影響させない: 採点対象フィールドの一致度という意味を変えないため。
  collectExtraKeys(root, buildAllowTree(fields), '', issues);

  const total = fields.length;
  return {
    fields_total: total,
    primary_match: primary,
    acceptable_match: acceptable,
    accuracy_pct: total === 0 ? 0 : Math.round(((primary + 0.5 * acceptable) / total) * 100),
    // 値の不一致は許容し、構造の破綻（欠損・型違い・未定義キー）だけを schema_pass の判定に使う
    schema_pass: issues.length === 0,
    issues,
    verdicts,
  };
}

async function loadAnswerKey() {
  const key = JSON.parse(await fs.readFile(ANSWER_KEY_PATH, 'utf-8'));
  const byLevel = new Map();
  for (const item of Array.isArray(key.levels) ? key.levels : []) {
    if (!item || typeof item !== 'object') continue;
    byLevel.set(item.level, Array.isArray(item.fields) ? item.fields : []);
  }
  // answer-key のレベル欠損は「満点でも 0 点」として黙って平均に混ざるため、明示エラーで落とす
  const missing = EXPECTED_LEVELS.filter(l => !byLevel.has(l) || byLevel.get(l).length === 0);
  if (missing.length > 0) {
    throw new Error(`answer-key is missing fields for level(s): ${missing.join(', ')}`);
  }
  return byLevel;
}

function levelsFromOutput(data) {
  const byLevel = new Map();
  const list = data && typeof data === 'object' && Array.isArray(data.levels) ? data.levels : [];
  for (const item of list) {
    if (!item || typeof item !== 'object') continue;
    byLevel.set(item.level, item);
  }
  return byLevel;
}

function evaluateOutput(data, answerKey) {
  const outputLevels = levelsFromOutput(data);
  const levels = EXPECTED_LEVELS.map(level => {
    const fields = answerKey.get(level) ?? [];
    const entry = outputLevels.get(level);
    const raw = entry && typeof entry.raw === 'string' ? entry.raw : null;

    if (raw === null) {
      return {
        level,
        valid_json: false,
        schema_pass: false,
        fields_total: fields.length,
        primary_match: 0,
        acceptable_match: 0,
        accuracy_pct: 0,
        raw_length: 0,
        issues: [entry ? 'raw missing' : `level ${level} missing in output.json`],
        verdicts: [],
      };
    }

    const parsed = tryParseJson(raw);
    if (parsed === null) {
      return {
        level,
        valid_json: false,
        schema_pass: false,
        fields_total: fields.length,
        primary_match: 0,
        acceptable_match: 0,
        accuracy_pct: 0,
        raw_length: raw.length,
        issues: ['parse-failed'],
        verdicts: [],
      };
    }

    const scored = scoreLevel(fields, parsed);
    return {
      level,
      valid_json: true,
      schema_pass: scored.schema_pass,
      fields_total: scored.fields_total,
      primary_match: scored.primary_match,
      acceptable_match: scored.acceptable_match,
      accuracy_pct: scored.accuracy_pct,
      raw_length: raw.length,
      issues: scored.issues,
      verdicts: scored.verdicts,
    };
  });

  const parsePassCount = levels.filter(l => l.valid_json).length;
  const scoreSum = levels.reduce((acc, l) => acc + (l.valid_json ? l.accuracy_pct : 0), 0);

  return {
    levels_total: EXPECTED_LEVELS.length,
    parse_pass_count: parsePassCount,
    score_pct: Math.round(scoreSum / EXPECTED_LEVELS.length),
    levels,
  };
}

async function processModel(modelDir, answerKey) {
  const model = path.basename(modelDir);
  const outputPath = path.join(modelDir, 'output.json');
  const metaPath = path.join(modelDir, 'meta.json');

  let raw;
  try { raw = await fs.readFile(outputPath, 'utf-8'); }
  catch (e) {
    return { model, ok: false, reason: `no output.json: ${e.message}`, skipped: true };
  }

  let data;
  try { data = JSON.parse(raw); }
  catch (e) {
    const meta = {
      generated_at: new Date().toISOString(),
      levels_total: EXPECTED_LEVELS.length,
      parse_pass_count: 0,
      score_pct: 0,
      issues: [`output.json is not valid JSON: ${e.message}`],
      levels: [],
    };
    await fs.writeFile(metaPath, `${JSON.stringify(meta, null, 2)}\n`);
    return { model, ok: false, reason: 'output.json is not valid JSON' };
  }

  const result = evaluateOutput(data, answerKey);
  const meta = { generated_at: new Date().toISOString(), ...result };
  await fs.writeFile(metaPath, `${JSON.stringify(meta, null, 2)}\n`);
  return {
    model,
    ok: result.parse_pass_count === EXPECTED_LEVELS.length,
    ...result,
  };
}

async function main() {
  const answerKey = await loadAnswerKey();
  const entries = await fs.readdir(THEME_DIR, { withFileTypes: true });
  const modelDirs = entries
    .filter(e => e.isDirectory() && !NON_MODEL_DIRS.has(e.name) && (!MODEL_FILTER || e.name === MODEL_FILTER))
    .map(e => path.join(THEME_DIR, e.name));

  const results = [];
  for (const d of modelDirs) {
    const r = await processModel(d, answerKey);
    if (!r.skipped) results.push(r);
  }

  console.log('=== json-ladder validation ===');
  if (results.length === 0) {
    console.error(MODEL_FILTER ? `model not found: ${MODEL_FILTER}` : 'no model directories found');
    if (MODEL_FILTER) process.exitCode = 1;
    return;
  }
  for (const r of results) {
    const status = r.ok ? 'PASS' : 'FAIL';
    const detail = r.levels
      ? `parse ${r.parse_pass_count}/${r.levels_total}, score ${r.score_pct}%`
      : r.reason;
    console.log(`${status}  ${r.model}  ${detail}`);
  }
  if (MODEL_FILTER && results.some(r => !r.ok)) process.exitCode = 1;
}

main().catch(e => { console.error(e); process.exit(1); });
