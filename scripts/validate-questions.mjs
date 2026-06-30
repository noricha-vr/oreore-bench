#!/usr/bin/env node
// public/extract-questions/<model>/output.json を読んで meta.json を生成する。
// 本番運用スキーマ準拠を検証する。

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const THEME_DIR = path.join(ROOT, 'public', 'extract-questions');

const EXPECTED_QUESTIONS_MIN = 15;  // 20 問入力に対して 15 件は出して欲しい
const EXPECTED_QUESTIONS_TARGET = 20;
const MAX_OPTIONS = 12;
const FREE_LABEL = '自由に記述する';

function tryParseJson(raw) {
  let s = raw.trim();
  s = s.replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/i, '').trim();
  const idx = s.indexOf('{');
  if (idx > 0) s = s.slice(idx);
  try { return JSON.parse(s); } catch {
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
                   raw_length: raw.length, issues: ['JSON parse failed'] };
    await fs.writeFile(metaPath, JSON.stringify(meta, null, 2));
    return { model: path.basename(modelDir), ok: false, reason: 'invalid JSON' };
  }
  const v = validate(parsed);
  // 件数は 15〜25 を許容（20 ± 5）。スキーマ準拠は他の基準で
  const countOk = v.question_count >= v.expected_min && v.question_count <= 25;
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
  const entries = await fs.readdir(THEME_DIR, { withFileTypes: true });
  const modelDirs = entries.filter(e => e.isDirectory()).map(e => path.join(THEME_DIR, e.name));
  const results = [];
  for (const d of modelDirs) results.push(await processModel(d));

  console.log('=== extract-questions validation ===');
  for (const r of results) {
    const status = r.ok ? '✅ PASS' : '❌ FAIL';
    const detail = r.ok
      ? `${r.question_count} questions`
      : (r.issues?.slice(0, 2).join(' / ') ?? r.reason);
    console.log(`${status}  ${r.model}  ${detail}`);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
