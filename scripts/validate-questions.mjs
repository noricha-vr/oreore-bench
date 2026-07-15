#!/usr/bin/env node
// public/extract-questions/<model>/output.json を読んで meta.json を生成する。
// 本番運用スキーマ準拠を検証する。

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

const themeArg = argValue('--theme', 'extract-questions');
const THEME_DIR = path.resolve(argValue('--theme-dir', path.join(ROOT, 'public', themeArg)));

async function resolveThemeDir(themeDir) {
  const [rootDir, resolvedThemeDir] = await Promise.all([
    fs.realpath(ROOT),
    fs.realpath(themeDir),
  ]);
  const relative = path.relative(rootDir, resolvedThemeDir);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error(`theme dir must resolve within repository root: ${resolvedThemeDir}`);
  }
  return resolvedThemeDir;
}

// テーマごとの期待件数レンジ
const THEME_EXPECTS = {
  'extract-questions':    { min: 15, target: 20, max: 25 },
  'extract-questions-v2': { min: 30, target: 40, max: 45 },
};
const EXPECT = THEME_EXPECTS[themeArg] || { min: 15, target: 20, max: 25 };
const EXPECTED_QUESTIONS_MIN = EXPECT.min;
const EXPECTED_QUESTIONS_TARGET = EXPECT.target;
const EXPECTED_QUESTIONS_MAX = EXPECT.max;
const MAX_OPTIONS = 12;
const FREE_LABEL = '自由に記述する';

export function tryParseJson(raw) {
  const trimmed = raw.trim();
  // Prefer fenced JSON so braces in preamble examples do not become parse anchors.
  const fence = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
  let text = fence ? fence[1].trim() : trimmed;
  if (!fence) {
    const first = text.indexOf('{');
    const last = text.lastIndexOf('}');
    if (first >= 0 && last > first) text = text.slice(first, last + 1);
  }
  try { return JSON.parse(text); } catch {
    if (fence) return null;
    try { return JSON.parse(raw); } catch { return null; }
  }
}

function validate(data) {
  const issues = [];
  if (!data || typeof data !== 'object') return { issues: ['root not an object'] };
  if (!Array.isArray(data.questions)) return { issues: ['root.questions not an array'] };

  const questions = data.questions;
  let goodIdCount = 0;
  let goodOriginalText = 0;
  let goodQuestion = 0;
  let goodOptions = 0;
  let goodConfidence = 0;
  let freeOptionPresent = 0;
  let exceedOptionsCap = 0;
  const seenIds = new Set();
  const seenQuestions = new Set();
  let duplicateIds = 0;
  let duplicateQuestions = 0;

  questions.forEach((q, i) => {
    if (!q || typeof q !== 'object') { issues.push(`questions[${i}] not an object`); return; }
    if (typeof q.id === 'string' && q.id.trim()) {
      goodIdCount++;
      if (seenIds.has(q.id)) duplicateIds++;
      seenIds.add(q.id);
    } else {
      issues.push(`questions[${i}].id missing`);
    }
    if (typeof q.originalText === 'string' && q.originalText.trim()) goodOriginalText++;
    else issues.push(`questions[${i}].originalText missing`);
    if (typeof q.question === 'string' && q.question.trim()) {
      goodQuestion++;
      const norm = q.question.replace(/\s+/g, '');
      if (seenQuestions.has(norm)) duplicateQuestions++;
      seenQuestions.add(norm);
    } else {
      issues.push(`questions[${i}].question missing`);
    }
    if (Array.isArray(q.options)) {
      const optionsValid = q.options.every(o => o && typeof o === 'object' && typeof o.label === 'string');
      if (optionsValid) goodOptions++;
      else issues.push(`questions[${i}].options has invalid item`);
      if (q.options.length > MAX_OPTIONS) {
        exceedOptionsCap++;
        issues.push(`questions[${i}].options exceeds cap (${q.options.length})`);
      }
      if (q.options.some(o => o?.label === FREE_LABEL)) freeOptionPresent++;
    } else {
      issues.push(`questions[${i}].options not an array`);
    }
    if (typeof q.confidence === 'number' && q.confidence >= 0 && q.confidence <= 1) goodConfidence++;
    else issues.push(`questions[${i}].confidence invalid`);
  });

  const total = questions.length;
  return {
    question_count: total,
    expected_min: EXPECTED_QUESTIONS_MIN,
    expected_target: EXPECTED_QUESTIONS_TARGET,
    has_id_pct: total ? Math.round(goodIdCount / total * 100) : 0,
    has_originalText_pct: total ? Math.round(goodOriginalText / total * 100) : 0,
    has_question_pct: total ? Math.round(goodQuestion / total * 100) : 0,
    has_options_pct: total ? Math.round(goodOptions / total * 100) : 0,
    has_confidence_pct: total ? Math.round(goodConfidence / total * 100) : 0,
    free_option_present_pct: total ? Math.round(freeOptionPresent / total * 100) : 0,
    exceed_options_cap: exceedOptionsCap,
    duplicate_ids: duplicateIds,
    duplicate_questions: duplicateQuestions,
    issues: issues.slice(0, 30), // 多すぎても切る
  };
}

async function processModel(modelDir) {
  const outputPath = path.join(modelDir, 'output.json');
  const metaPath = path.join(modelDir, 'meta.json');
  let raw;
  try { raw = await fs.readFile(outputPath, 'utf-8'); }
  catch (e) {
    const meta = { valid_json: false, generated_at: new Date().toISOString(),
                   issues: [`output.json not found: ${e.message}`] };
    await fs.writeFile(metaPath, JSON.stringify(meta, null, 2));
    return { model: path.basename(modelDir), ok: false, reason: 'no output.json' };
  }
  const parsed = tryParseJson(raw);
  if (parsed === null) {
    const meta = { valid_json: false, generated_at: new Date().toISOString(),
                   raw_length: raw.length, schema_pass: false,
                   issues: ['JSON parse failed'] };
    await fs.writeFile(metaPath, JSON.stringify(meta, null, 2));
    return { model: path.basename(modelDir), ok: false, reason: 'invalid JSON' };
  }
  const v = validate(parsed);
  const countOk = v.question_count >= v.expected_min && v.question_count <= EXPECTED_QUESTIONS_MAX;
  const meta = {
    valid_json: true,
    generated_at: new Date().toISOString(),
    raw_length: raw.length,
    count_ok: countOk,
    schema_pass:
      v.issues.length === 0 &&
      countOk &&
      v.has_question_pct === 100 &&
      v.has_options_pct === 100 &&
      v.has_id_pct === 100 &&
      v.has_confidence_pct === 100 &&
      v.free_option_present_pct === 100 &&
      v.duplicate_ids === 0 &&
      v.duplicate_questions === 0 &&
      v.exceed_options_cap === 0,
    ...v,
  };
  await fs.writeFile(metaPath, JSON.stringify(meta, null, 2));
  return { model: path.basename(modelDir), ok: meta.schema_pass, ...v };
}

async function main() {
  const themeDir = await resolveThemeDir(THEME_DIR);
  const entries = await fs.readdir(themeDir, { withFileTypes: true });
  const modelDirs = entries.filter(e => e.isDirectory()).map(e => path.join(themeDir, e.name));
  const results = [];
  for (const d of modelDirs) results.push(await processModel(d));

  console.log(`=== ${themeArg} validation ===`);
  for (const r of results) {
    const status = r.ok ? '✅ PASS' : '❌ FAIL';
    const detail = r.ok
      ? `${r.question_count} questions`
      : (r.issues?.slice(0, 2).join(' / ') ?? r.reason);
    console.log(`${status}  ${r.model}  ${detail}`);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(e => { console.error(e); process.exit(1); });
}
