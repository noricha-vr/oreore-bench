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
  'grok-cli', 'openai-api', 'openrouter-api', 'antigravity-cli', 'codex-exec', 'unknown',
]);
const SYSTEM_PROMPT_ENUM = new Set(['none', 'harness-default', 'custom', 'unknown']);
const EFFORT_ENUM = new Set(['none', 'low', 'medium', 'high', 'unknown']);
const GEN_AT_SOURCE_ENUM = new Set(['measured', 'git-first-commit', 'unknown']);

// キー allowlist（未知キーは全部エラー。system_prompt_text のような迂回キーを構造的に防ぐ）
const RUN_ALLOWED = new Set([
  'schema_version', 'theme', 'model', 'model_id', 'harness', 'reasoning_effort',
  'attempts', 'generated_at', 'generated_at_source', 'sampling', 'system_prompt',
  'post_processing', 'runtime', 'usage', 'cost',
]);
const SAMPLING_ALLOWED = new Set(['temperature', 'max_tokens', 'top_p']);
const RUNTIME_ALLOWED = new Set(['engine', 'quantization', 'api']);
const USAGE_ALLOWED = new Set(['estimated', 'method', 'prompt_tokens', 'completion_tokens', 'note']);
const COST_ALLOWED = new Set([
  'estimated', 'usd', 'actual_usd',
  'prompt_usd_per_mtok', 'completion_usd_per_mtok',
  'pricing_source', 'pricing_model', 'pricing_fetched_at',
]);
// pricing_source enum:
//   openrouter           = 実請求相当 (type=api、単価そのまま cost)
//   openrouter-reference = 参考仮想コスト (type=local + 参考単価あり。actual_usd=0)
//   local-no-reference   = 参考単価なし (type=local、gemma-4-12b-qat のみ)
const PRICING_SOURCE_ENUM = new Set(['openrouter', 'openrouter-reference', 'local-no-reference']);

// runtime の値（engine/quantization/api）は index.html に innerHTML で入るため、
// 短く安全な文字列のみ許可（英数 / ハイフン / アンダースコア / ドット / 空白 / 括弧）。
const RUNTIME_VALUE_RE = /^[A-Za-z0-9._ ()\-]{1,40}$/;

// sampling の値は number | "default" | "unknown" のみ許可
const SAMPLING_VALUE_ALLOWED_STR = new Set(['default', 'unknown']);

function checkAllowedKeys(where, obj, allowed, label) {
  for (const k of Object.keys(obj)) {
    if (!allowed.has(k)) err(where, `${label}: unknown key "${k}" (allowlist: ${[...allowed].join(',')})`);
  }
}

const errors = [];
function err(where, msg) { errors.push(`${where}: ${msg}`); }

function validateRun(run, where) {
  if (typeof run !== 'object' || run === null) return err(where, 'not an object');
  checkAllowedKeys(where, run, RUN_ALLOWED, 'run');
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
  if (!run.sampling || typeof run.sampling !== 'object') {
    err(where, 'sampling missing');
  } else {
    checkAllowedKeys(where, run.sampling, SAMPLING_ALLOWED, 'sampling');
    for (const [k, v] of Object.entries(run.sampling)) {
      const ok = typeof v === 'number' || (typeof v === 'string' && SAMPLING_VALUE_ALLOWED_STR.has(v));
      if (!ok) err(where, `sampling.${k} must be number | "default" | "unknown" (got ${typeof v}: ${JSON.stringify(v)})`);
    }
  }

  // runtime（null か object。object の時はキー allowlist と値パターン検査）
  if (run.runtime !== null && run.runtime !== undefined) {
    if (typeof run.runtime !== 'object') {
      err(where, 'runtime must be object or null');
    } else {
      checkAllowedKeys(where, run.runtime, RUNTIME_ALLOWED, 'runtime');
      for (const [k, v] of Object.entries(run.runtime)) {
        if (typeof v !== 'string' || !RUNTIME_VALUE_RE.test(v)) {
          err(where, `runtime.${k} must match ${RUNTIME_VALUE_RE} (got ${JSON.stringify(v)})`);
        }
      }
    }
  }

  // usage
  const usage = run.usage;
  if (!usage || typeof usage !== 'object') { err(where, 'usage missing'); return; }
  checkAllowedKeys(where, usage, USAGE_ALLOWED, 'usage');
  if (typeof usage.prompt_tokens !== 'number') err(where, 'usage.prompt_tokens must be number');
  if (typeof usage.completion_tokens !== 'number') err(where, 'usage.completion_tokens must be number');
  if (usage.estimated === true && (typeof usage.note !== 'string' || !usage.note)) {
    err(where, 'usage.note required when estimated=true');
  }
  if (typeof usage.method !== 'string') err(where, 'usage.method must be string');

  // cost + tokens 整合 (誤差 1%)
  const cost = run.cost;
  if (!cost || typeof cost !== 'object') { err(where, 'cost missing'); return; }
  checkAllowedKeys(where, cost, COST_ALLOWED, 'cost');
  // cost.usd は null または number のみ許可（undefined = キー欠落もエラー。#8）
  if (!('usd' in cost)) {
    err(where, 'cost.usd key missing (must be null or number)');
  } else if (cost.usd !== null && typeof cost.usd !== 'number') {
    err(where, `cost.usd must be null or number (got ${typeof cost.usd})`);
  }
  if (typeof cost.usd === 'number' &&
      typeof cost.prompt_usd_per_mtok === 'number' && typeof cost.completion_usd_per_mtok === 'number') {
    const expected = usage.prompt_tokens * cost.prompt_usd_per_mtok / 1_000_000
                   + usage.completion_tokens * cost.completion_usd_per_mtok / 1_000_000;
    const denom = Math.max(Math.abs(expected), 1e-9);
    const diff = Math.abs(cost.usd - expected) / denom;
    if (diff > 0.01) {
      err(where, `cost.usd ${cost.usd} inconsistent with tokens*rate ${expected.toFixed(6)} (>1% off)`);
    }
  }
  // pricing_source enum
  if (!PRICING_SOURCE_ENUM.has(cost.pricing_source)) {
    err(where, `cost.pricing_source "${cost.pricing_source}" not in enum ${[...PRICING_SOURCE_ENUM].join('|')}`);
  }
  // actual_usd の型と usd との整合:
  //   pricing_source=openrouter           → actual_usd=null (実請求相当なので null 意味: 実測未取得)
  //   pricing_source=openrouter-reference → actual_usd=0    (ローカル実行なので実請求はゼロ、usd は参考仮想コスト)
  //   pricing_source=local-no-reference   → actual_usd=0    (usd=null と併せて「参考すら無し」を表す)
  if (cost.pricing_source === 'openrouter-reference') {
    if (typeof cost.usd !== 'number') err(where, 'openrouter-reference requires cost.usd = number (reference virtual cost)');
    if (cost.actual_usd !== 0) err(where, 'openrouter-reference requires cost.actual_usd = 0 (local: no real charge)');
  } else if (cost.pricing_source === 'local-no-reference') {
    if (cost.usd !== null) err(where, 'local-no-reference requires cost.usd = null');
    if (cost.actual_usd !== 0) err(where, 'local-no-reference requires cost.actual_usd = 0');
  } else if (cost.pricing_source === 'openrouter') {
    if (typeof cost.usd !== 'number') err(where, 'openrouter requires cost.usd = number');
    if (cost.actual_usd !== null) err(where, 'openrouter requires cost.actual_usd = null (real charge not yet measured)');
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
