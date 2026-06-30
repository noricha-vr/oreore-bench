# json-quiz-easy — プロンプト（最小スキーマ）

このテーマの **凍結プロンプト**。新しいモデルで再現する時はこのまま渡してください。

---

以下の Wikipedia 記事を読んで、内容理解を測る**三択クイズを 5 問**作成し、
**JSON 単体**で出力してください。説明文・コードフェンス・前置きは一切付けないこと。

## 出力スキーマ

```ts
{
  quiz: [
    {
      id: number,                // 1 から始まる通し番号
      question: string,
      choices: [
        { label: "A", text: string },
        { label: "B", text: string },
        { label: "C", text: string }
      ],
      answer: "A" | "B" | "C"
    }
  ]
}
```

## ルール

- 必ず **5 問** 生成
- choices は **必ず 3 つ**、label は `A`/`B`/`C`
- `answer` は `A`/`B`/`C` のいずれか
- 解説は不要（含めない）
- 同一の question を重複させない
- 全テキスト日本語
- ルート要素は `quiz` キーのみ
- JSON 以外の出力は禁止

## 入力（Wikipedia 記事「大規模言語モデル」より）

[input.md の本文をここに展開してプロンプトに含める]
