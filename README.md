# oreore-bench

> 俺基準のベンチマーク。**同じプロンプトを違うモデルに投げて、何が出てくるか**を残す。

公開サイト: https://oreore-bench.pages.dev  (デプロイ後に更新)

## 何をしているか

LLM を「業務タスクの一発再現性」で評価する場として、現実の制作タスクをそのままぶつけて、生成物をそのまま晒す。指標は `tokens/sec` でも `MMLU` でもなく、**「これは仕事で使えるか」** の一点。

各エントリには:

- 元のプロンプト (`PROMPT.md`)
- 各モデルの 1 ショット出力（手直しなし）
- 生成方法のメモ

がセットで置いてある。**同じプロンプトを別のモデルに投げ直せば、誰でも比較を追加できる**。

## 構造

```
oreore-bench/
  public/                      <- Cloudflare Pages の build root
    index.html                 <- 一覧 + フィルター
    lp-nishibi/
      PROMPT.md                <- このテーマの共通プロンプト
      gemma-4-31b/index.html
      claude-opus-4-8/index.html
    othello/
      PROMPT.md
      gemma-4-26b-a4b-qat/index.html
      gemma-4-31b/index.html
  scripts/
    add-model.sh               <- 新モデルで再現するときのワンライナー
```

## 新しいモデルを追加する

例: `claude-haiku-4-5` で `lp-nishibi` を試す場合

```bash
bash scripts/add-model.sh lp-nishibi claude-haiku-4-5
```

このスクリプトは:

1. `public/lp-nishibi/PROMPT.md` を読む
2. 指定モデルにそのまま投げる（gptme + LM Studio / Claude Agent SDK / OpenRouter のいずれか自動判定）
3. `public/lp-nishibi/<モデル名>/index.html` に保存
4. `public/index.html` のエントリ JSON を更新
5. （任意）`wrangler pages deploy public/` で再デプロイ

## ルール

- **手直しなし**: モデルが書いたものをそのまま置く。バグも残す
- **プロンプトは凍結**: 一度出したプロンプトは編集しない。改訂したい時は別テーマを切る
- **`local/...` モデルも `claude-...` モデルも分け隔てなく**: 同じ俎上に乗せる

## 関連

- 元の実験: https://github.com/noricha-vr/note （private）の `experiments/` 配下
- lifelog note: `gptme-lmstudio-model-override`, `gemma4-26b-vs-31b-coding-comparison`
