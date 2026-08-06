# Scripts

主要なベンチマーク補助スクリプトの目次です。

- `mlx-lm-run.py`: loopback の `mlx_lm.server` OpenAI 互換 API でテーマ成果物と実測 `run.json` を生成する。
- `openrouter-run.py`: OpenRouter API でテーマ成果物と実測 `run.json` を生成する。
- `validate-runs.mjs`: 個別 `run.json` と集約 `public/runs.json` のスキーマ・同期を検証する。
- `backfill-runs.py`: 既存 ENTRIES から不足した `run.json` のスケルトンを生成する。
