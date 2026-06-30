#!/usr/bin/env node
// public/json-quiz/<model>/output.json を読んで meta.json を生成する。
// Node.js 標準ライブラリのみで動作。
//
// 使い方:
//   node scripts/validate-quiz.mjs

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const PUBLIC_DIR = path.join(ROOT, 'public');

// テーマごとのスキーマ期待値
const THEMES = {
  'json-quiz-easy': {
    quiz_count: 5,
    choices: 3,
    valid_answers: new Set(['A', 'B', 'C']),
    required_fields: ['id', 'question', 'choices', 'answer'],
    forbidden_fields: [],
    has_explanation: false,
    has_difficulty: false,
    has_related_topics: false,
    has_source_excerpt: false,
  },
  'json-quiz-medium': {
    quiz_count: 10,
    choices: 4,
    valid_answers: new Set(['A', 'B', 'C', 'D']),
    required_fields: ['id', 'question', 'choices', 'answer', 'explanation'],
    forbidden_fields: [],
    has_explanation: true,
    has_difficulty: false,
    has_related_topics: false,
    has_source_excerpt: false,
  },
  'json-quiz-hard': {
    quiz_count: 10,
    choices: 4,
    valid_answers: new Set(['A', 'B', 'C', 'D']),
    required_fields: ['id', 'question', 'difficulty', 'choices', 'answer', 'explanation', 'related_topics', 'source_excerpt'],
    forbidden_fields: [],
    has_explanation: true,
    has_difficulty: true,
    has_related_topics: true,
    has_source_excerpt: true,
  },
};
const DIFFICULTY_ENUM = new Set(['easy', 'medium', 'hard']);

/**
 * 文字列から JSON 部分を抽出して parse する。
 * - 先頭/末尾の説明文、コードフェンスを取り除く
 * - 失敗したら null を返す
 */
function tryParseJson(raw) {
  // コードフェンス除去（```json ... ``` / ``` ... ```）
  let s = raw.trim();
  s = s.replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/i, '');
  s = s.trim();

  // 先頭から { または [ を探して末尾の対応する閉じまでで切る
  const firstBrace = s.indexOf('{');
  if (firstBrace > 0) s = s.slice(firstBrace);

  try {
    return JSON.parse(s);
  } catch {
    // ゆるい抽出も失敗 → ナマ JSON.parse で再試行（エラー詳細用）
    try { return JSON.parse(raw); } catch { return null; }
  }
}

function validate(data, schema) {
  const issues = [];
  const expectedLabels = Array.from(schema.valid_answers); // ['A','B',...]

  if (!data || typeof data !== 'object') {
    return { issues: ['root is not an object'] };
  }
  if (!Array.isArray(data.quiz)) {
    return { issues: ['root.quiz is not an array'] };
  }

  const quiz = data.quiz;
  const counts = {
    quiz_count: quiz.length,
    expected_quiz_count: schema.quiz_count,
  };
  if (quiz.length !== schema.quiz_count) {
    issues.push(`expected ${schema.quiz_count} quiz, got ${quiz.length}`);
  }

  let allChoicesOk = true;
  let allAnswersValid = true;
  const questionTexts = new Set();
  let duplicates = 0;
  let missingExplanation = 0;
  let invalidDifficulty = 0;
  let missingRelatedTopics = 0;
  let invalidSourceExcerpt = 0;

  quiz.forEach((q, i) => {
    if (!q || typeof q !== 'object') {
      issues.push(`quiz[${i}] is not an object`);
      allChoicesOk = false; allAnswersValid = false;
      return;
    }
    if (typeof q.question !== 'string') {
      issues.push(`quiz[${i}].question missing`);
    } else {
      const norm = q.question.replace(/\s+/g, '');
      if (questionTexts.has(norm)) duplicates++;
      questionTexts.add(norm);
    }
    if (!Array.isArray(q.choices) || q.choices.length !== schema.choices) {
      issues.push(`quiz[${i}].choices length=${q.choices?.length}`);
      allChoicesOk = false;
    } else {
      const labels = q.choices.map(c => c?.label);
      if (!expectedLabels.every((l, j) => labels[j] === l)) {
        issues.push(`quiz[${i}].choices labels=${labels.join(',')}`);
      }
    }
    if (!schema.valid_answers.has(q.answer)) {
      issues.push(`quiz[${i}].answer=${JSON.stringify(q.answer)}`);
      allAnswersValid = false;
    }
    if (schema.has_explanation) {
      if (typeof q.explanation !== 'string' || !q.explanation.trim()) {
        missingExplanation++;
      }
    }
    if (schema.has_difficulty) {
      if (!DIFFICULTY_ENUM.has(q.difficulty)) {
        invalidDifficulty++;
        issues.push(`quiz[${i}].difficulty=${JSON.stringify(q.difficulty)}`);
      }
    }
    if (schema.has_related_topics) {
      if (!Array.isArray(q.related_topics) || q.related_topics.length < 1 || q.related_topics.length > 4) {
        missingRelatedTopics++;
        issues.push(`quiz[${i}].related_topics len=${q.related_topics?.length}`);
      } else if (!q.related_topics.every(t => typeof t === 'string' && t.trim())) {
        missingRelatedTopics++;
        issues.push(`quiz[${i}].related_topics has non-string or empty`);
      }
    }
    if (schema.has_source_excerpt) {
      const se = q.source_excerpt;
      const ok = se && typeof se === 'object' &&
                 typeof se.section === 'string' && se.section.trim() &&
                 typeof se.quote === 'string' && se.quote.trim();
      if (!ok) {
        invalidSourceExcerpt++;
        issues.push(`quiz[${i}].source_excerpt invalid`);
      }
    }
  });

  return {
    ...counts,
    each_choices_ok: allChoicesOk,
    all_answers_valid: allAnswersValid,
    duplicates_in_questions: duplicates,
    missing_explanation: missingExplanation,
    invalid_difficulty: invalidDifficulty,
    missing_related_topics: missingRelatedTopics,
    invalid_source_excerpt: invalidSourceExcerpt,
    issues,
  };
}

async function processModel(themeName, modelDir, schema) {
  const outputPath = path.join(modelDir, 'output.json');
  const metaPath = path.join(modelDir, 'meta.json');

  let raw;
  try {
    raw = await fs.readFile(outputPath, 'utf-8');
  } catch (e) {
    const meta = {
      theme: themeName,
      valid_json: false,
      generated_at: new Date().toISOString(),
      issues: [`output.json not found: ${e.message}`],
    };
    await fs.writeFile(metaPath, JSON.stringify(meta, null, 2));
    return { theme: themeName, model: path.basename(modelDir), ok: false, reason: 'no output.json' };
  }

  const parsed = tryParseJson(raw);
  if (parsed === null) {
    const meta = {
      theme: themeName,
      valid_json: false,
      generated_at: new Date().toISOString(),
      raw_length: raw.length,
      issues: ['JSON parse failed'],
    };
    await fs.writeFile(metaPath, JSON.stringify(meta, null, 2));
    return { theme: themeName, model: path.basename(modelDir), ok: false, reason: 'invalid JSON' };
  }

  const v = validate(parsed, schema);
  const meta = {
    theme: themeName,
    valid_json: true,
    generated_at: new Date().toISOString(),
    raw_length: raw.length,
    schema_pass:
      v.issues.length === 0 &&
      v.quiz_count === schema.quiz_count &&
      v.each_choices_ok &&
      v.all_answers_valid &&
      v.duplicates_in_questions === 0 &&
      v.invalid_difficulty === 0 &&
      v.missing_related_topics === 0 &&
      v.invalid_source_excerpt === 0,
    ...v,
  };
  await fs.writeFile(metaPath, JSON.stringify(meta, null, 2));
  return { theme: themeName, model: path.basename(modelDir), ok: meta.schema_pass, ...v };
}

async function main() {
  const results = [];
  for (const [themeName, schema] of Object.entries(THEMES)) {
    const themeDir = path.join(PUBLIC_DIR, themeName);
    let entries;
    try {
      entries = await fs.readdir(themeDir, { withFileTypes: true });
    } catch {
      console.log(`  (skip ${themeName}: directory not found)`);
      continue;
    }
    const modelDirs = entries
      .filter(e => e.isDirectory())
      .map(e => path.join(themeDir, e.name));
    for (const dir of modelDirs) {
      const r = await processModel(themeName, dir, schema);
      results.push(r);
    }
  }

  console.log('=== json-quiz validation summary ===');
  for (const r of results) {
    const status = r.ok ? '✅ PASS' : '❌ FAIL';
    console.log(`${status}  ${r.theme}/${r.model}`);
    if (!r.ok) console.log(`         issues: ${(r.issues || [r.reason]).slice(0, 3).join(' / ')}`);
  }
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
