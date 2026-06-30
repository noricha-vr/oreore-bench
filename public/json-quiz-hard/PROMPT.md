# json-quiz-hard — プロンプト（複雑スキーマ）

このテーマの **凍結プロンプト**。新しいモデルで再現する時はこのまま渡してください。

---

以下の Wikipedia 記事を読んで、内容理解を測る**四択クイズを 10 問**作成し、
**JSON 単体**で出力してください。説明文・コードフェンス・前置きは一切付けないこと。

このスキーマは json-quiz-medium よりも追加フィールドが多く、配列・enum・ネストオブジェクトを含みます。**すべてのフィールドを正確に出力すること**。

## 出力スキーマ

```ts
{
  quiz: [
    {
      id: number,                            // 1 から始まる通し番号
      question: string,
      difficulty: "easy" | "medium" | "hard", // enum (3値のいずれか)
      choices: [
        { label: "A", text: string },
        { label: "B", text: string },
        { label: "C", text: string },
        { label: "D", text: string }
      ],
      answer: "A" | "B" | "C" | "D",
      explanation: string,
      related_topics: string[],              // 関連トピック 1〜4 個の配列
      source_excerpt: {                      // ネストオブジェクト
        section: string,                     // 記事内のセクション名（"概要" "特性" など）
        quote: string                        // 関連する原文の短い引用（30-80 文字）
      }
    }
  ]
}
```

## ルール

- 必ず **10 問**
- 各 question に choices は **4 つ**、label は `A`/`B`/`C`/`D` 順
- `answer` は `A`/`B`/`C`/`D`
- `difficulty` は必ず `easy` `medium` `hard` のいずれかを文字列で
- `related_topics` は **1 つ以上 4 つ以下** の文字列配列
- `source_excerpt.section` と `quote` は必ず文字列、空文字禁止
- `quote` は本文に含まれる短い引用（要約禁止）
- question 重複なし、選択肢に未記載事実を混ぜない
- 全テキスト日本語
- ルート要素は `quiz` キーのみ
- JSON 以外の出力は禁止

## 入力（Wikipedia 記事「大規模言語モデル」より）

[input.md の本文をここに展開してプロンプトに含める]
