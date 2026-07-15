#!/usr/bin/env node
/** Verify equivalent fenced-JSON parsing across question benchmark consumers. */

import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const validator = path.join(ROOT, 'scripts', 'validate-questions.mjs');
const builder = path.join(ROOT, 'scripts', 'build-questions-html.py');
const fixture = 'Preamble with an unrelated { brace.\n```json\n{"questions": []}\n```\n';
const malformedFence = 'Preamble {"questions": []}\n```json\nnot JSON\n```';

function run(command, args) {
  return execFileSync(command, args, { cwd: ROOT, encoding: 'utf8' });
}

function headMeta(relativePath) {
  return JSON.parse(run('git', ['show', `HEAD:${relativePath}`]));
}

function assertThemeDirRejected(command, args) {
  const result = spawnSync(command, args, { cwd: ROOT, encoding: 'utf8' });
  assert.notEqual(result.status, 0, 'theme dir outside the repository must fail');
  assert.match(result.stderr, /theme dir must resolve within repository root/);
}

function fileSnapshot(filePath) {
  return fs.stat(filePath)
    .then(stat => ({ exists: true, size: stat.size, mtimeMs: stat.mtimeMs }))
    .catch(error => {
      if (error.code === 'ENOENT') return { exists: false };
      throw error;
    });
}

async function main() {
  const temporaryRoot = await fs.mkdtemp(path.join(ROOT, '.questions-parser-test-'));
  try {
    const themeDir = path.join(temporaryRoot, 'theme');
    const modelDir = path.join(themeDir, 'claude-opus-4-8');
    await fs.mkdir(modelDir, { recursive: true });
    await fs.writeFile(path.join(modelDir, 'output.json'), fixture);

    assertThemeDirRejected('node', [validator, '--theme-dir=/']);
    assertThemeDirRejected('uv', ['run', '--no-project', 'python', builder, '--theme-dir=/']);

    const unsafeThemeDir = path.join(temporaryRoot, 'unsafe-theme');
    const externalOutput = '/tmp/output.html';
    const outputBefore = await fileSnapshot(externalOutput);
    await fs.mkdir(unsafeThemeDir);
    await fs.symlink('/tmp', path.join(unsafeThemeDir, 'claude-opus-4-8'));
    assertThemeDirRejected('uv', [
      'run', '--no-project', 'python', builder,
      '--theme=extract-questions', `--theme-dir=${unsafeThemeDir}`,
    ]);
    assert.deepEqual(
      await fileSnapshot(externalOutput),
      outputBefore,
      'builder must not write output.html through an external model symlink',
    );

    // Exercise the executable validator, rather than duplicating its parser in this test.
    run('node', [validator, '--theme=extract-questions', `--theme-dir=${themeDir}`]);
    const meta = JSON.parse(await fs.readFile(path.join(modelDir, 'meta.json'), 'utf8'));
    assert.equal(meta.valid_json, true, 'validator must prefer the fenced object');
    await fs.writeFile(path.join(modelDir, 'output.json'), malformedFence);
    run('node', [validator, '--theme=extract-questions', `--theme-dir=${themeDir}`]);
    const malformedMeta = JSON.parse(await fs.readFile(path.join(modelDir, 'meta.json'), 'utf8'));
    assert.equal(malformedMeta.valid_json, false, 'validator must not fall back after a malformed fence');
    await fs.writeFile(path.join(modelDir, 'output.json'), fixture);

    const pythonProbe = [
      'import importlib.util, sys',
      'spec = importlib.util.spec_from_file_location("builder", sys.argv[1])',
      'module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)',
      'assert module.parse_json(sys.argv[2]) == {"questions": []}',
      'assert module.parse_json(sys.argv[3]) is None',
    ].join('; ');
    run('uv', ['run', '--no-project', 'python', '-c', pythonProbe, builder, fixture, malformedFence]);

    // Generate the real template, then evaluate only its self-contained parser without a DOM.
    run('uv', ['run', '--no-project', 'python', builder, '--theme=extract-questions', `--theme-dir=${themeDir}`]);
    const outputHtml = await fs.readFile(path.join(modelDir, 'output.html'), 'utf8');
    const match = outputHtml.match(/function parseOutputJson\(raw\) \{[\s\S]*?\n  \}/);
    assert.ok(match, 'generated HTML must include parseOutputJson');
    const context = { JSON };
    vm.createContext(context);
    vm.runInContext(`${match[0]}; globalThis.parsed = parseOutputJson(${JSON.stringify(fixture)});`, context);
    assert.deepEqual(context.parsed, { questions: [] }, 'inline parser must prefer the fenced object');
    assert.throws(
      () => vm.runInContext(`parseOutputJson(${JSON.stringify(malformedFence)});`, context),
      'inline parser must not fall back after a malformed fence',
    );

    for (const themeName of ['extract-questions', 'extract-questions-v2']) {
      const sourceTheme = path.join(ROOT, 'public', themeName);
      const copiedTheme = path.join(temporaryRoot, `${themeName}-existing`);
      await fs.cp(sourceTheme, copiedTheme, { recursive: true });
      run('node', [validator, `--theme=${themeName}`, `--theme-dir=${copiedTheme}`]);
      for (const entry of await fs.readdir(sourceTheme, { withFileTypes: true })) {
        if (!entry.isDirectory()) continue;
        const model = entry.name;
        const actual = JSON.parse(await fs.readFile(path.join(copiedTheme, model, 'meta.json'), 'utf8'));
        const relativeMetaPath = `public/${themeName}/${model}/meta.json`;
        const baselineMeta = headMeta(relativeMetaPath);
        const expectedStatus = themeName === 'extract-questions' && model === 'gemma-4-26b-a4b-qat'
          ? [false, false]
          : [baselineMeta.valid_json, baselineMeta.schema_pass];
        assert.deepEqual(
          [actual.valid_json, actual.schema_pass],
          expectedStatus,
          `${themeName}/${model} validation status must match the approved baseline`,
        );
      }
    }
  } finally {
    await fs.rm(temporaryRoot, { recursive: true, force: true });
  }
}

await main();
console.log('questions parser regression: PASS (3 paths)');
