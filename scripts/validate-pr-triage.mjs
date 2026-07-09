#!/usr/bin/env node
// public/pr-triage/<model>/output.json を読んで meta.json を生成する。
// PR トリアージ JSON のスキーマと answer-key との一致率を検証する。

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

const THEME_DIR = path.resolve(argValue('--theme-dir', path.join(ROOT, 'public', 'pr-triage')));
const ANSWER_KEY_PATH = path.resolve(argValue('--answer-key', path.join(THEME_DIR, 'answer-key.json')));
const EXPECTED_PRS = Array.from({ length: 10 }, (_, i) => 101 + i);
const EXPECTED_SET = new Set(EXPECTED_PRS);
const VERDICTS = new Set(['merge', 'fix', 'close', 'hold']);
const LEVELS = new Set(['high', 'medium', 'low']);

function tryParseJson(raw) {
  let s = raw.trim();
  s = s.replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/i, '').trim();
  const first = s.indexOf('{');
  const last = s.lastIndexOf('}');
  if (first >= 0 && last > first) s = s.slice(first, last + 1);
  try { return JSON.parse(s); } catch {
    try { return JSON.parse(raw); } catch { return null; }
  }
}

async function loadAnswerKey() {
  const key = JSON.parse(await fs.readFile(ANSWER_KEY_PATH, 'utf-8'));
  const answers = Array.isArray(key.answers) ? key.answers : [];
  const byPr = new Map();
  for (const item of answers) {
    if (!item || typeof item !== 'object') continue;
    byPr.set(item.pr, {
      primary: item.primary,
      also: new Set(Array.isArray(item.also_acceptable) ? item.also_acceptable : []),
    });
  }
  return byPr;
}

function nonEmptyStringArray(value) {
  return Array.isArray(value) &&
    value.length > 0 &&
    value.every(item => typeof item === 'string' && item.trim());
}

function stringArray(value) {
  return Array.isArray(value) &&
    value.every(item => typeof item === 'string');
}

function checkPermutation(name, values, issues) {
  if (!Array.isArray(values)) {
    issues.push(`${name} not an array`);
    return false;
  }
  if (values.length !== EXPECTED_PRS.length) {
    issues.push(`${name} length must be 10`);
  }
  const seen = new Set();
  for (const pr of values) {
    if (!Number.isInteger(pr)) issues.push(`${name} contains non-integer PR: ${pr}`);
    else if (!EXPECTED_SET.has(pr)) issues.push(`${name} contains out-of-range PR: ${pr}`);
    else if (seen.has(pr)) issues.push(`${name} contains duplicate PR: ${pr}`);
    seen.add(pr);
  }
  for (const pr of EXPECTED_PRS) {
    if (!seen.has(pr)) issues.push(`${name} missing PR: ${pr}`);
  }
  return values.length === EXPECTED_PRS.length &&
    EXPECTED_PRS.every(pr => seen.has(pr)) &&
    seen.size === EXPECTED_PRS.length;
}

function validate(data, answerKey) {
  const issues = [];
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return {
      issues: ['root not an object'],
      primary_match: 0,
      acceptable_match: 0,
      agreement_pct: 0,
      verdicts: [],
    };
  }

  if (!Array.isArray(data.triage)) issues.push('root.triage not an array');
  const triage = Array.isArray(data.triage) ? data.triage : [];
  const triagePrs = [];
  const verdictByPr = new Map();

  if (triage.length !== EXPECTED_PRS.length) issues.push('triage length must be 10');

  triage.forEach((item, i) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      issues.push(`triage[${i}] not an object`);
      return;
    }
    if (!Number.isInteger(item.pr)) issues.push(`triage[${i}].pr invalid`);
    else {
      triagePrs.push(item.pr);
      if (!EXPECTED_SET.has(item.pr)) issues.push(`triage[${i}].pr out of range`);
      if (verdictByPr.has(item.pr)) issues.push(`triage duplicate PR: ${item.pr}`);
      verdictByPr.set(item.pr, item.verdict);
    }
    if (!VERDICTS.has(item.verdict)) issues.push(`triage[${i}].verdict invalid`);
    if (!LEVELS.has(item.confidence)) issues.push(`triage[${i}].confidence invalid`);
    if (!nonEmptyStringArray(item.reasons)) issues.push(`triage[${i}].reasons invalid`);
    if (!stringArray(item.actions)) issues.push(`triage[${i}].actions invalid`);
    if (!LEVELS.has(item.risk_if_merged)) issues.push(`triage[${i}].risk_if_merged invalid`);
  });

  checkPermutation('triage.pr', triagePrs, issues);
  checkPermutation('priority_order', data.priority_order, issues);
  if (typeof data.summary !== 'string' || !data.summary.trim()) {
    issues.push('summary missing');
  }

  let primaryMatch = 0;
  let acceptableMatch = 0;
  const verdicts = EXPECTED_PRS.map(pr => {
    const verdict = verdictByPr.get(pr) ?? null;
    const expected = answerKey.get(pr) ?? { primary: null, also: new Set() };
    let match = 'miss';
    if (verdict === expected.primary) {
      match = 'primary';
      primaryMatch++;
    } else if (expected.also.has(verdict)) {
      match = 'acceptable';
      acceptableMatch++;
    }
    return { pr, verdict, expected: expected.primary, match };
  });

  return {
    triage_count: triage.length,
    primary_match: primaryMatch,
    acceptable_match: acceptableMatch,
    agreement_pct: Math.round(((primaryMatch + 0.5 * acceptableMatch) / EXPECTED_PRS.length) * 100),
    verdicts,
    issues: issues.slice(0, 40),
  };
}

async function processModel(modelDir, answerKey) {
  const outputPath = path.join(modelDir, 'output.json');
  const metaPath = path.join(modelDir, 'meta.json');
  let raw;
  try { raw = await fs.readFile(outputPath, 'utf-8'); }
  catch (e) {
    const meta = {
      valid_json: false,
      generated_at: new Date().toISOString(),
      issues: [`output.json not found: ${e.message}`],
      schema_pass: false,
      primary_match: 0,
      acceptable_match: 0,
      agreement_pct: 0,
      verdicts: [],
    };
    await fs.writeFile(metaPath, `${JSON.stringify(meta, null, 2)}\n`);
    return { model: path.basename(modelDir), ok: false, reason: 'no output.json' };
  }

  const parsed = tryParseJson(raw);
  if (parsed === null) {
    const meta = {
      valid_json: false,
      generated_at: new Date().toISOString(),
      raw_length: raw.length,
      issues: ['JSON parse failed'],
      schema_pass: false,
      primary_match: 0,
      acceptable_match: 0,
      agreement_pct: 0,
      verdicts: [],
    };
    await fs.writeFile(metaPath, `${JSON.stringify(meta, null, 2)}\n`);
    return { model: path.basename(modelDir), ok: false, reason: 'invalid JSON' };
  }

  const v = validate(parsed, answerKey);
  const meta = {
    valid_json: true,
    generated_at: new Date().toISOString(),
    raw_length: raw.length,
    schema_pass: v.issues.length === 0,
    ...v,
  };
  await fs.writeFile(metaPath, `${JSON.stringify(meta, null, 2)}\n`);
  return { model: path.basename(modelDir), ok: meta.schema_pass, ...v };
}

async function main() {
  const answerKey = await loadAnswerKey();
  const entries = await fs.readdir(THEME_DIR, { withFileTypes: true });
  const modelDirs = entries.filter(e => e.isDirectory()).map(e => path.join(THEME_DIR, e.name));
  const results = [];
  for (const d of modelDirs) results.push(await processModel(d, answerKey));

  console.log('=== pr-triage validation ===');
  if (results.length === 0) {
    console.log('no model directories found');
    return;
  }
  for (const r of results) {
    const status = r.ok ? 'PASS' : 'FAIL';
    const detail = r.ok
      ? `agreement ${r.agreement_pct}% (${r.primary_match} primary, ${r.acceptable_match} acceptable)`
      : (r.issues?.slice(0, 2).join(' / ') ?? r.reason);
    console.log(`${status}  ${r.model}  ${detail}`);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
