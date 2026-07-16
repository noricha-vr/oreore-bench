#!/usr/bin/env node
// public/<theme>/<model>/run.json のスキーマ検証。
// - 必須キー / enum / 型 / estimated 時 note 必須 / cost と tokens*単価 の整合 (誤差1%)
// - 出力 (index.html or output.json) を持つ全モデル dir に run.json 存在
// - public/runs.json が per-dir と一致 (stale 検出)
// プライバシー: system_prompt は enum のみ (自由記述を弾く)

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const PUBLIC = path.join(ROOT, 'public');
const RUNS_JSON = path.join(PUBLIC, 'runs.json');

const HARNESS_ENUM = new Set([
  'lmstudio-api', 'gptme-lmstudio', 'claude-agent-sdk', 'claude-cli-headless',
  'grok-cli', 'openai-api', 'openrouter-api', 'antigravity-cli', 'unknown',
]);
const SYSTEM_PROMPT_ENUM = new Set(['none', 'harness-default', 'custom', 'unknown']);
const EFFORT_ENUM = new Set(['none', 'low', 'medium', 'high', 'unknown']);
const GEN_AT_SOURCE_ENUM = new Set(['measured', 'git-first-commit', 'unknown']);

const errors = [];
function err(where, msg) { errors.push(`${where}: ${msg}`); }

function validateRun(run, where) {
  if (typeof run !== 'object' || run === null) return err(where, 'not an object');
  if (run.schema_version !== 1) err(where, `schema_version must be 1, got ${run.schema_version}`);
  for (const k of ['theme', 'model', 'model_id', 'harness', 'reasoning_effort', 'system_prompt', 'post_processing']) {
    if (typeof run[k] !== 'string') err(where, `${k} must be string`);
  }
  if (typeof run.attempts !== 'number') err(where, 'attempts must be number');
  if (run.generated_at !== null && typeof run.generated_at !== 'string') {
    err(where, 'generated_at must be string or null');
  }
  if (!HARNESS_ENUM.has(run.harness)) err(where, `harness "${run.harness}" not in enum`);
  if (!EFFORT_ENUM.has(run.reasoning_effort)) err(where, `reasoning_effort "${run.reasoning_effort}" not in enum`);
  if (!SYSTEM_PROMPT_ENUM.has(run.system_prompt)) {
    // 自由記述 = プロンプト漏洩リスク。ここで必ず失敗させる
    err(where, `system_prompt "${run.system_prompt}" must be one of ${[...SYSTEM_PROMPT_ENUM].join('|')} (label only, never the actual prompt body)`);
  }
  if (!GEN_AT_SOURCE_ENUM.has(run.generated_at_source)) {
    err(where, `generated_at_source "${run.generated_at_source}" not in enum`);
  }

  // sampling
  if (!run.sampling || typeof run.sampling !== 'object') err(where, 'sampling missing');

  // usage
  const usage = run.usage;
  if (!usage || typeof usage !== 'object') { err(where, 'usage missing'); return; }
  if (typeof usage.prompt_tokens !== 'number') err(where, 'usage.prompt_tokens must be number');
  if (typeof usage.completion_tokens !== 'number') err(where, 'usage.completion_tokens must be number');
  if (usage.estimated === true && (typeof usage.note !== 'string' || !usage.note)) {
    err(where, 'usage.note required when estimated=true');
  }
  if (typeof usage.method !== 'string') err(where, 'usage.method must be string');

  // cost + tokens 整合 (誤差 1%)
  const cost = run.cost;
  if (!cost || typeof cost !== 'object') { err(where, 'cost missing'); return; }
  if (cost.usd !== null && typeof cost.usd === 'number' &&
      typeof cost.prompt_usd_per_mtok === 'number' && typeof cost.completion_usd_per_mtok === 'number') {
    const expected = usage.prompt_tokens * cost.prompt_usd_per_mtok / 1_000_000
                   + usage.completion_tokens * cost.completion_usd_per_mtok / 1_000_000;
    const denom = Math.max(Math.abs(expected), 1e-9);
    const diff = Math.abs(cost.usd - expected) / denom;
    if (diff > 0.01) {
      err(where, `cost.usd ${cost.usd} inconsistent with tokens*rate ${expected.toFixed(6)} (>1% off)`);
    }
  }
  // ローカル (usd=null): actual_usd=0 期待
  if (cost.usd === null && cost.actual_usd !== 0) {
    err(where, 'cost.usd=null requires cost.actual_usd=0 (local-only convention)');
  }
}

async function main() {
  // per-dir 走査
  const themes = await fs.readdir(PUBLIC, { withFileTypes: true });
  const perDir = {};
  for (const t of themes) {
    if (!t.isDirectory()) continue;
    const themeDir = path.join(PUBLIC, t.name);
    const models = await fs.readdir(themeDir, { withFileTypes: true });
    for (const m of models) {
      if (!m.isDirectory()) continue;
      const modelDir = path.join(themeDir, m.name);
      const files = await fs.readdir(modelDir);
      const hasOutput = files.includes('index.html') || files.includes('output.json');
      if (!hasOutput) continue;
      const runPath = path.join(modelDir, 'run.json');
      try {
        const raw = await fs.readFile(runPath, 'utf-8');
        const run = JSON.parse(raw);
        const key = `${t.name}/${m.name}`;
        perDir[key] = run;
        validateRun(run, key);
      } catch (e) {
        err(`${t.name}/${m.name}`, `run.json missing or invalid: ${e.message}`);
      }
    }
  }

  // runs.json stale 検出
  try {
    const runsAgg = JSON.parse(await fs.readFile(RUNS_JSON, 'utf-8'));
    const perKeys = new Set(Object.keys(perDir));
    const aggKeys = new Set(Object.keys(runsAgg));
    for (const k of perKeys) {
      if (!aggKeys.has(k)) err('runs.json', `missing key ${k} (run build-runs-json.py)`);
    }
    for (const k of aggKeys) {
      if (!perKeys.has(k)) err('runs.json', `stale key ${k} (no matching per-dir run.json)`);
    }
    for (const k of perKeys) {
      if (!aggKeys.has(k)) continue;
      if (JSON.stringify(perDir[k]) !== JSON.stringify(runsAgg[k])) {
        err('runs.json', `stale content for ${k} (rebuild runs.json)`);
      }
    }
  } catch (e) {
    err('runs.json', `not readable: ${e.message}`);
  }

  if (errors.length) {
    console.error(`FAIL (${errors.length} issues):`);
    for (const e of errors) console.error(`  ${e}`);
    process.exit(1);
  }
  console.log(`OK: ${Object.keys(perDir).length} run.json validated, runs.json in sync`);
}

main().catch(e => { console.error(e); process.exit(1); });
